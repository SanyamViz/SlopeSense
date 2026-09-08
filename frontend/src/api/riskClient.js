/**
 * Risk data client.
 *
 * ALL network access for the dashboard goes through this module. The only
 * tunable is RISK_API_BASE -- point it at a different origin/path to swap the
 * mock file for the real API without touching any component or view.
 *
 * The endpoint shape is the FastAPI document at /risk-map:
 *   { metadata, summary, locations: [ { location_id, name, district,
 *       coordinates: {lat, lon}, risk_score, risk_level, factors: [...],
 *       alert: { message_en, message_local, recommended_action } } ] }
 */

/**
 * Base URL of the risk API. Resolution order (first non-empty wins):
 *   1. Runtime override window.RISK_API_BASE (injected via index.html at
 *      build time, or set externally) -- retargets the backend without
 *      rebuilding the SPA.
 *   2. Fallback http://localhost:8000 (local dev with the API on :8000).
 *
 *   Note: the VITE_ public prefix is intentionally NOT used. Public prefixes
 *   cause Vite to inline the value into the JS bundle at build time, which
 *   exposes it to the browser. Instead, the value is injected into the served
 *   index.html at build time (see vite.config.js transformIndexHtml hook).
 */
const RUNTIME_BASE =
  typeof window !== "undefined" && window.RISK_API_BASE
    ? String(window.RISK_API_BASE).replace(/\/$/, "")
    : null;

export const RISK_API_BASE =
  RUNTIME_BASE ||
  "http://localhost:8000";

/** Fetch the full risk document. Throws on non-2xx so callers can show errors. */
export async function fetchRiskMap() {
  const res = await fetch(`${RISK_API_BASE}/risk-map`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Risk API /risk-map returned ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** Fetch infrastructure graph + stranded zones from the dedicated endpoint. */
export async function fetchInfrastructure() {
  const res = await fetch(`${RISK_API_BASE}/infrastructure`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Risk API /infrastructure returned ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** Fetch a single location by id (used by the side panel deep-link). */
export async function fetchRiskById(id) {
  const res = await fetch(`${RISK_API_BASE}/risk/${encodeURIComponent(id)}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Risk API /risk/${id} returned ${res.status}`);
  }
  return res.json();
}

/** Fetch active high/severe alerts, sorted by severity (score desc). */
export async function fetchActiveAlerts(minLevel = "high") {
  const res = await fetch(
    `${RISK_API_BASE}/alerts/active?min_level=${encodeURIComponent(minLevel)}`,
    { headers: { Accept: "application/json" } },
  );
  if (!res.ok) {
    throw new Error(`Risk API /alerts/active returned ${res.status}`);
  }
  return res.json();
}

/** Fetch frontend config (breakpoints, thresholds, weights) for sliders. */
export async function fetchConfig() {
  const res = await fetch(`${RISK_API_BASE}/config`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Risk API /config returned ${res.status}`);
  }
  return res.json();
}

/** Run a what-if simulation for a location with overridden factor values. */
export async function fetchSimulate(locationId, overrides = {}) {
  const res = await fetch(`${RISK_API_BASE}/simulate`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ location_id: locationId, overrides }),
  });
  if (!res.ok) {
    throw new Error(`Risk API /simulate returned ${res.status}`);
  }
  return res.json();
}

/**
 * Reload the output JSON from disk (call after re-running the pipeline).
 * Returns the new total location count.
 */
export async function fetchReload() {
  const res = await fetch(`${RISK_API_BASE}/reload`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Risk API /reload returned ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch impact assessment: nearby hospitals, available capacity, and alternative
 * evacuation routes for every zone.
 */
export async function fetchImpactAssessment(radiusKm = 20) {
  const res = await fetch(
    `${RISK_API_BASE}/impact-assessment?radius_km=${encodeURIComponent(radiusKm)}`,
    { headers: { Accept: "application/json" } },
  );
  if (!res.ok) {
    throw new Error(`Risk API /impact-assessment returned ${res.status}`);
  }
  return res.json();
}