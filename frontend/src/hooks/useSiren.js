export function playSiren({ durationMs = 3000, freqStart = 400, freqEnd = 1200 } = {}) {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    const t = ctx.currentTime;
    const half = durationMs / 1000 / 2;
    osc.frequency.setValueAtTime(freqStart, t);
    osc.frequency.exponentialRampToValueAtTime(freqEnd, t + half);
    osc.frequency.exponentialRampToValueAtTime(freqStart, t + half * 2);
    gain.gain.setValueAtTime(0.001, t);
    gain.gain.exponentialRampToValueAtTime(0.3, t + 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, t + durationMs / 1000);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + durationMs / 1000);
  } catch (e) {
    console.warn("Siren failed:", e);
  }
}
