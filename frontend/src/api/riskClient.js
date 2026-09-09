/**
 * Risk data client.
 *
 * ALL network access for the dashboard goes through this module. The only
 * tunable is VITE_API_BASE_URL -- point it at a different origin/path to swap the
 * mock file for the real API without touching any component or view.
 *
 * The endpoint shape is the FastAPI document at /risk-map:
 *   { metadata, summary, locations: [ { location_id, name, district,
 *       coordinates: {lat, lon}, risk_score, risk_level, factors: [...],
 *       alert: { message_en, message_local, recommended_action } } ] }
 */

/**
 * Base URL of the risk API. Resolution order (first non-empty wins):
 *   1. VITE_API_BASE_URL (standard Vite public env var, set in Vercel/Render).
 *   2. Fallback http://localhost:8000 (local dev with the API on :8000).
 */
const RUNTIME_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

if (!RUNTIME_BASE) {
  console.warn(
    "[riskClient] VITE_API_BASE_URL is not set. " +
      "Defaulting to http://localhost:8000. " +
      "Set VITE_API_BASE_URL (e.g. in Vercel) to point at your real backend."
  );
}

// Default to the local FastAPI server so dev builds, `vite preview`, and the
// committed dist bundle all work out of the box. Vercel/production overrides
// this by setting VITE_API_BASE_URL to the deployed backend URL.
export const RISK_API_BASE = RUNTIME_BASE || "http://localhost:8000";

const RETRYABLE_COLD = new Set([404, 502, 503]);
const RETRYABLE_WARM = new Set([502, 503]);
const NEVER_RETRY = new Set([400, 401, 403, 422]);

const DELAYS_COLD = [2000, 5000, 10000];
const DELAYS_WARM = [1000];

let isWarm = false;
let warmingCount = 0;
const warmingListeners = new Set();

export function onWarmingChange(fn) {
  warmingListeners.add(fn);
  return () => warmingListeners.delete(fn);
}

function setWarming(active) {
  if (active) {
    warmingCount++;
  } else {
    warmingCount = Math.max(0, warmingCount - 1);
  }
  const isActive = warmingCount > 0;
  warmingListeners.forEach((fn) => fn(isActive));
}

function createApiError(endpoint, res, body) {
  const err = new Error(
    `Risk API ${endpoint} returned ${res.status} ${res.statusText}` +
      (body ? `: ${typeof body === "string" ? body : JSON.stringify(body)}` : "")
  );
  err.status = res.status;
  err.endpoint = endpoint;
  err.body = body;
  return err;
}

async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timeoutMs = options.timeout ?? 30000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${RISK_API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    return res;
  } catch (err) {
    if (err.name === "AbortError") {
      const e = new Error("Request timeout");
      e.name = "AbortError";
      throw e;
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

async function withRetry(fetchFn) {
  const maxRetries = isWarm ? 1 : 3;
  const delays = isWarm ? DELAYS_WARM : DELAYS_COLD;
  let lastError;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const result = await fetchFn();
      isWarm = true;
      setWarming(false);
      return result;
    } catch (err) {
      lastError = err;
      const status = err.status;

      let shouldRetry = false;
      if (attempt < maxRetries) {
        if (err instanceof TypeError) {
          shouldRetry = true;
        } else if (err.name === "AbortError") {
          shouldRetry = true;
        } else if (status && !NEVER_RETRY.has(status)) {
          shouldRetry = isWarm ? RETRYABLE_WARM.has(status) : RETRYABLE_COLD.has(status);
        }
      }

      if (!shouldRetry) {
        setWarming(false);
        throw err;
      }

      setWarming(true);
      const delay = delays[Math.min(attempt, delays.length - 1)];
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  setWarming(false);
  throw lastError;
}

/** Fetch the full risk document. Throws on non-2xx so callers can show errors. */
export async function fetchRiskMap() {
  return withRetry(async () => {
    const res = await apiFetch("/risk-map", {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw createApiError("/risk-map", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/** Fetch infrastructure graph + stranded zones from the dedicated endpoint. */
export async function fetchInfrastructure() {
  return withRetry(async () => {
    const res = await apiFetch("/infrastructure", {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw createApiError("/infrastructure", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/** Fetch a single location by id (used by the side panel deep-link). */
export async function fetchRiskById(id) {
  return withRetry(async () => {
    const res = await apiFetch(`/risk/${encodeURIComponent(id)}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw createApiError(`/risk/${id}`, res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/** Fetch active high/severe alerts, sorted by severity (score desc). */
export async function fetchActiveAlerts(minLevel = "high") {
  return withRetry(async () => {
    const res = await apiFetch(
      `/alerts/active?min_level=${encodeURIComponent(minLevel)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!res.ok) {
      throw createApiError("/alerts/active", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/** Fetch frontend config (breakpoints, thresholds, weights) for sliders. */
export async function fetchConfig() {
  return withRetry(async () => {
    const res = await apiFetch("/config", {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw createApiError("/config", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/** Run a what-if simulation for a location with overridden factor values. */
export async function fetchSimulate(locationId, overrides = {}) {
  return withRetry(async () => {
    const res = await apiFetch("/simulate", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ location_id: locationId, overrides }),
    });
    if (!res.ok) {
      throw createApiError("/simulate", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/**
 * Reload the output JSON from disk (call after re-running the pipeline).
 * Returns the new total location count.
 */
export async function fetchReload() {
  return withRetry(async () => {
    const res = await apiFetch("/reload", {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw createApiError("/reload", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/**
 * Dispatch a real SMS/WhatsApp alert via Twilio to every configured recipient.
 *
 * Body shape matches POST /dispatch on the backend:
 *   { sector, location_id, message_en, message_local, channel }
 *
 * channel defaults to "whatsapp". Returns the dispatch result:
 *   { sent, failed, results: [{ to, sid, status }, ...] }
 * Throws on non-2xx so callers can surface an honest error state.
 */
export async function dispatchAlert({ sector, locationId, messageEn, messageLocal, channel = "whatsapp" }) {
  return withRetry(async () => {
    const res = await apiFetch("/dispatch", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sector,
        location_id: locationId,
        message_en: messageEn,
        message_local: messageLocal,
        channel,
      }),
    });
    if (!res.ok) {
      throw createApiError("/dispatch", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}

/**
 * Fetch impact assessment: nearby hospitals, available capacity, and alternative
 * evacuation routes for every zone.
 */
export async function fetchImpactAssessment(radiusKm = 20) {
  return withRetry(async () => {
    const res = await apiFetch(
      `/impact-assessment?radius_km=${encodeURIComponent(radiusKm)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!res.ok) {
      throw createApiError("/impact-assessment", res, await res.text().catch(() => null));
    }
    return res.json();
  });
}
