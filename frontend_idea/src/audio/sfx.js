// Sound effects (8-noyabr). Two recorded sounds from Bobur (public/sounds, Pixabay):
//   gavel.mp3 — two strikes, at 0.036 s and 0.527 s (the gavel animation strikes twice in the same rhythm);
//   flame.mp3 — the flames on the scales flaring up.
// The rest is synthesised with Web Audio, so nothing else has to be downloaded:
//   page()   — a sheet turning: a short band-passed noise «swish»; softer and limited while the book riffles;
//   book()   — the cover opening/closing: a low soft thump;
//   scales() — the pans swinging: a small bell chime with a chain-like clink.
// The audio context starts on the first click/key (browser autoplay rules); before that nothing plays.
// Mute: the speaker button in the top bar (remembered in this browser), or ?mute=1.

const BASE = (import.meta.env?.BASE_URL || '/');
const FILES = { gavel: 'sounds/gavel.mp3', flame: 'sounds/flame.mp3' };
const KEY = 'modda.sound';

let ctx = null, master = null, limiter = null, noise = null;
const buffers = {};
let muted = false;
try { muted = localStorage.getItem(KEY) === 'off'; } catch { /* storage blocked: sound stays on */ }
if (typeof location !== 'undefined' && /[?&]mute=1/.test(location.search)) muted = true;
const listeners = new Set();
let active = 0;                                   // voices playing now (page swishes are capped)
export const played = { gavel: 0, flame: 0, page: 0, book: 0, scales: 0 };   // for tests and the debug console

function ensure() {
  if (ctx || typeof window === 'undefined') return ctx;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  ctx = new AC();
  master = ctx.createGain(); master.gain.value = muted ? 0 : 0.6;
  limiter = ctx.createDynamicsCompressor();       // flame + scales + gavel overlap at the verdict: never clip
  limiter.threshold.value = -12; limiter.knee.value = 6; limiter.ratio.value = 12; limiter.attack.value = 0.002; limiter.release.value = 0.2;
  master.connect(limiter).connect(ctx.destination);
  const len = ctx.sampleRate;                     // 1 s of white noise, reused by every synthesised sound
  noise = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = noise.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  for (const [name, path] of Object.entries(FILES)) {
    fetch(BASE + path).then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(r.status))))
      .then((b) => ctx.decodeAudioData(b)).then((buf) => { buffers[name] = buf; })
      .catch(() => { /* a missing sound is not an error for the page */ });
  }
  return ctx;
}

/** Call once at start: the context is created on the first user gesture. */
export function initSound() {
  const unlock = () => { ensure(); ctx?.resume?.(); };
  for (const ev of ['pointerdown', 'keydown', 'touchstart']) window.addEventListener(ev, unlock, { capture: true, passive: true });
}

export const isMuted = () => muted;
export function setMuted(on) {
  muted = !!on;
  try { localStorage.setItem(KEY, muted ? 'off' : 'on'); } catch { /* not remembered */ }
  if (master) master.gain.setTargetAtTime(muted ? 0 : 0.6, ctx.currentTime, 0.05);
  for (const fn of listeners) fn(muted);
}
export const onMuteChange = (fn) => listeners.add(fn);

const ready = () => ctx && ctx.state === 'running' && !muted;

function sample(name, { when = 0, offset = 0, gain = 1, rate = 1 } = {}) {
  if (!ready() || !buffers[name]) return;
  played[name]++;
  const s = ctx.createBufferSource(); s.buffer = buffers[name]; s.playbackRate.value = rate;
  const g = ctx.createGain(); g.gain.value = gain;
  s.connect(g).connect(master);
  s.start(ctx.currentTime + when, offset);
}

/** The gavel's two strikes; call at the moment of the FIRST impact (the file's first strike is 36 ms in). */
export function gavel() { sample('gavel', { offset: 0.036, gain: 0.9 }); }

/** Flames flaring on the scales. */
export function flame() { sample('flame', { gain: 0.45 }); }

/** One sheet turning. soft: riffling (quiet, varied, at most 3 at a time). */
export function page({ soft = false, duration = 0.5 } = {}) {
  if (!ready() || (soft && active >= 3)) return;
  played.page++;
  const t = ctx.currentTime, len = Math.min(0.42, duration * 0.7);
  const src = ctx.createBufferSource(); src.buffer = noise;
  const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.9;
  const f0 = (soft ? 1600 : 1200) * (0.85 + Math.random() * 0.3);
  bp.frequency.setValueAtTime(f0, t); bp.frequency.exponentialRampToValueAtTime(f0 * 2.6, t + len * 0.6);
  const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 400;
  const g = ctx.createGain(), peak = soft ? 0.05 + Math.random() * 0.03 : 0.22;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(peak, t + len * 0.35);
  g.gain.exponentialRampToValueAtTime(peak * 0.35, t + len * 0.7);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  src.connect(bp).connect(hp).connect(g).connect(master);
  src.start(t, Math.random() * 0.5, len + 0.05);
  active++; src.onended = () => { active--; };
}

/** The cover opening or closing: a low, soft thump. */
export function book({ close = false } = {}) {
  if (!ready()) return;
  played.book++;
  const t = ctx.currentTime + (close ? 0.75 : 0.05);
  const o = ctx.createOscillator(); o.type = 'sine';
  o.frequency.setValueAtTime(close ? 95 : 120, t); o.frequency.exponentialRampToValueAtTime(48, t + 0.25);
  const og = ctx.createGain(); og.gain.setValueAtTime(0.0001, t); og.gain.exponentialRampToValueAtTime(close ? 0.32 : 0.18, t + 0.012); og.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
  o.connect(og).connect(master); o.start(t); o.stop(t + 0.32);
  const n = ctx.createBufferSource(); n.buffer = noise;
  const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900;
  const ng = ctx.createGain(); ng.gain.setValueAtTime(0.0001, t); ng.gain.exponentialRampToValueAtTime(0.12, t + 0.01); ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
  n.connect(lp).connect(ng).connect(master); n.start(t, 0.2, 0.2);
}

/** The scales swinging to the verdict: a small brass bell and a few chain clinks. */
export function scales() {
  if (!ready()) return;
  played.scales++;
  const t = ctx.currentTime + 0.12;
  const base = 740;
  [[1, 0.16, 2.2], [2.76, 0.07, 1.4], [5.4, 0.04, 0.9], [8.93, 0.02, 0.6]].forEach(([ratio, amp, dec]) => {
    const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = base * ratio;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(amp, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + dec);
    o.connect(g).connect(master); o.start(t); o.stop(t + dec + 0.05);
  });
  for (let i = 0; i < 4; i++) {                       // chain: short bright ticks, a little apart
    const tt = t + 0.18 + i * (0.07 + Math.random() * 0.05);
    const n = ctx.createBufferSource(); n.buffer = noise;
    const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 5200 + Math.random() * 2400; bp.Q.value = 6;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, tt); g.gain.exponentialRampToValueAtTime(0.09 - i * 0.015, tt + 0.003); g.gain.exponentialRampToValueAtTime(0.0001, tt + 0.06);
    n.connect(bp).connect(g).connect(master); n.start(tt, Math.random() * 0.8, 0.08);
  }
}

export const state = () => ({ context: ctx?.state ?? 'none', muted, loaded: Object.keys(buffers) });
/** Debug/recording only: the context and the master bus (e.g. to record what the page plays). */
export const tap = () => (ensure(), { ctx, master: limiter });
