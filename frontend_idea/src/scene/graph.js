// The process graph above the book: the Mind (LLM) in the centre, eight processing stages around it,
// spokes Mind ↔ stage, arcs stage → next stage (the pipeline order), particles only on running edges,
// and a beam down to the book. Labels and clicks are HTML buttons placed over the anchors (accessible).
import * as THREE from 'three';
import { gsap } from 'gsap';
import { STAGES } from '../config.js';
import { flowLine } from '../viz/fx.js';

const COLORS = {
  waiting: '#5d6b64', running: '#d6b66d', runningCyan: '#65d8ee', runningBlue: '#73afe0', done: '#39d6a0',
  warning: '#e5ad5c', failed: '#e36f72', skipped: '#46524c', unobserved: '#46524c',
};
const ANGLES = [150, 110, 70, 30, -30, -70, -110, -150].map((d) => (d * Math.PI) / 180);

function glowTexture(inner = 'rgba(255,255,255,1)', mid = 'rgba(255,255,255,0.25)') {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, inner); r.addColorStop(0.25, mid); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

/** Points on two brain-like lobes with a central fissure and folds (a stylised "mind", not a model of anything). */
function brainPoints(n, r) {
  const pos = new Float32Array(n * 3);
  let i = 0, tries = 0;
  while (i < n && tries < n * 20) {
    tries++;
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    let x = s * Math.cos(th), y = u * 0.78, z = s * Math.sin(th) * 0.82;
    if (Math.abs(x) < 0.07) continue;                                   // fissure between the lobes
    const fold = 1 + 0.06 * Math.sin(9 * y + 4 * z) * Math.cos(7 * x);
    x *= fold; y *= fold; z *= fold;
    x += Math.sign(x) * 0.06;
    pos.set([x * r, y * r, z * r], i * 3); i++;
  }
  return pos;
}

/** Soft round points with per-point size and colour (the Mind's neurons), additive, size-attenuated. */
function neuronMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uScale: { value: 900 }, uLevel: { value: 0 } },
    vertexShader: /* glsl */`
      attribute float size; attribute vec3 color; attribute float phase;
      uniform float uTime, uScale, uLevel; varying vec3 vColor; varying float vA;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        float beat = 0.75 + 0.25 * sin(uTime * (1.2 + uLevel * 2.5) + phase * 6.2831);
        vColor = color * (0.8 + 0.6 * uLevel) * beat; vA = beat;
        gl_PointSize = size * uScale / -mv.z;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */`
      varying vec3 vColor; varying float vA;
      void main() {
        float r = length(gl_PointCoord - 0.5) * 2.0; if (r > 1.0) discard;
        float a = smoothstep(1.0, 0.0, r); a *= a;
        gl_FragColor = vec4(vColor * (0.6 + 1.4 * smoothstep(0.35, 0.0, r)), a * vA);
      }`,
  });
}

/** Each neuron linked to its two nearest neighbours: the Mind's "synapses" (decorative structure). */
function synapses(pos, maxLen) {
  const n = pos.length / 3, seg = [];
  for (let i = 0; i < n; i++) {
    let b1 = -1, b2 = -1, d1 = Infinity, d2 = Infinity;
    for (let j = 0; j < n; j++) {
      if (j === i) continue;
      const dx = pos[i * 3] - pos[j * 3], dy = pos[i * 3 + 1] - pos[j * 3 + 1], dz = pos[i * 3 + 2] - pos[j * 3 + 2];
      const d = dx * dx + dy * dy + dz * dz;
      if (d < d1) { d2 = d1; b2 = b1; d1 = d; b1 = j; } else if (d < d2) { d2 = d; b2 = j; }
    }
    for (const [b, d] of [[b1, d1], [b2, d2]]) if (b > i && d < maxLen * maxLen) seg.push(i, b);
  }
  return seg;
}

export class Graph {
  constructor(scene, { reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.group = new THREE.Group();
    scene.add(this.group);
    this.center = new THREE.Vector3(0, 1.75, -0.75);
    this.rx = 1.85; this.ry = 0.56;
    this.time = 0;
    this.status = Object.fromEntries(STAGES.map((s) => [s.id, 'waiting']));
    this.active = null;
    this.level = 0;                                          // 0 idle … 1 researching

    const glow = glowTexture();
    // --- the Mind
    this.core = new THREE.Group();
    this.core.position.copy(this.center);
    const N = this.reduced ? 500 : 1400;
    const bp = brainPoints(N, 0.42);
    const bc = new Float32Array(N * 3), bs = new Float32Array(N), ph = new Float32Array(N);
    const teal = new THREE.Color('#62e6f2'), gold = new THREE.Color('#f0c66e'), deep = new THREE.Color('#2f7fd6'), cc = new THREE.Color();
    for (let i = 0; i < N; i++) {
      const x = bp[i * 3], y = bp[i * 3 + 1], z = bp[i * 3 + 2], r = Math.hypot(x, y, z) / 0.42;
      cc.copy(deep).lerp(teal, Math.min(1, r * 1.1)).lerp(gold, Math.max(0, (y / 0.42) * 0.35 + (Math.random() < 0.06 ? 0.6 : 0)));
      bc.set([cc.r, cc.g, cc.b], i * 3);
      bs[i] = 0.012 + Math.random() * 0.016 + (Math.random() < 0.04 ? 0.02 : 0);
      ph[i] = Math.random();
    }
    const bg = new THREE.BufferGeometry();
    bg.setAttribute('position', new THREE.BufferAttribute(bp, 3));
    bg.setAttribute('color', new THREE.BufferAttribute(bc, 3));
    bg.setAttribute('size', new THREE.BufferAttribute(bs, 1));
    bg.setAttribute('phase', new THREE.BufferAttribute(ph, 1));
    this.brain = new THREE.Points(bg, neuronMaterial());
    this.brain.frustumCulled = false;
    // synapses: nearest-neighbour links, and sparks that run along them (faster while a request runs)
    const links = synapses(bp, 0.11);
    this.synSeg = links;
    const lp = new Float32Array(links.length * 3);
    links.forEach((idx, k) => lp.set([bp[idx * 3], bp[idx * 3 + 1], bp[idx * 3 + 2]], k * 3));
    this.synapse = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(lp, 3)),
      new THREE.LineBasicMaterial({ color: '#4fc9e0', transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.brainPos = bp;
    const SP = this.reduced ? 0 : 90;
    this.sparks = Array.from({ length: SP }, () => ({ seg: Math.floor(Math.random() * (links.length / 2)), t: Math.random(), v: 0.6 + Math.random() * 1.4 }));
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.max(1, SP) * 3), 3));
    sg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(Math.max(1, SP) * 3).fill(1.4), 3));
    sg.setAttribute('size', new THREE.BufferAttribute(new Float32Array(Math.max(1, SP)).fill(0.03), 1));
    sg.setAttribute('phase', new THREE.BufferAttribute(new Float32Array(Math.max(1, SP)), 1));
    this.sparkPts = new THREE.Points(sg, neuronMaterial());
    this.sparkPts.frustumCulled = false;
    this.coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: '#9fe9d8', transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.coreGlow.scale.set(1.7, 1.7, 1);
    this.coreRing = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.006, 8, 96),
      new THREE.MeshBasicMaterial({ color: '#d6b66d', transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.brainGroup = new THREE.Group();
    this.brainGroup.add(this.synapse, this.brain, this.sparkPts);
    this.core.add(this.coreGlow, this.brainGroup, this.coreRing);
    this.group.add(this.core);

    // --- orbit rings (decorative frame of the graph, no data)
    const ellipse = (rx, ry, color, opacity, tilt = 0) => {
      const pts = new THREE.EllipseCurve(0, 0, rx, ry, 0, Math.PI * 2).getPoints(160).map((p) => new THREE.Vector3(p.x, p.y, 0));
      const l = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false }));
      l.position.copy(this.center); l.rotation.z = tilt; this.group.add(l); return l;
    };
    this.orbits = [ellipse(this.rx, this.ry, '#65d8ee', 0.22), ellipse(this.rx * 1.18, this.ry * 1.22, '#d6b66d', 0.12, 0.05), ellipse(this.rx * 0.62, this.ry * 0.7, '#65d8ee', 0.1, -0.08)];

    // --- stage anchors, spokes, arcs
    this.nodes = STAGES.map((s, i) => {
      const a = ANGLES[i];
      const p = new THREE.Vector3(this.center.x + this.rx * Math.cos(a), this.center.y + this.ry * Math.sin(a), this.center.z + 0.02);
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 12), new THREE.MeshBasicMaterial({ color: COLORS.waiting }));
      dot.position.copy(p);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: COLORS.waiting, transparent: true, opacity: 0.35, depthWrite: false, blending: THREE.AdditiveBlending }));
      halo.position.copy(p); halo.scale.set(0.55, 0.55, 1);
      this.group.add(dot, halo);
      const mid = p.clone().lerp(this.center, 0.5).add(new THREE.Vector3(0, 0, 0.25));
      const spoke = new THREE.QuadraticBezierCurve3(this.center.clone(), mid, p.clone());
      const spokeLine = flowLine(spoke.getPoints(24), { color: '#65d8ee', width: 0.0045, speed: 0.35, dashes: 2, glow: 1.2, opacity: 0.25 });
      this.group.add(spokeLine);
      return { id: s.id, kind: s.kind, pos: p, dot, halo, spoke, spokeLine };
    });
    this.arcs = this.nodes.slice(0, -1).map((n, i) => {
      const a0 = ANGLES[i], a1 = ANGLES[i + 1];
      const pts = [];
      for (let k = 0; k <= 24; k++) {
        const a = a0 + (a1 - a0) * (k / 24);
        pts.push(new THREE.Vector3(this.center.x + this.rx * Math.cos(a), this.center.y + this.ry * Math.sin(a), this.center.z + 0.02));
      }
      const curve = new THREE.CatmullRomCurve3(pts);
      const line = flowLine(pts, { color: '#d6b66d', width: 0.0035, speed: 0.25, dashes: 1, glow: 1.0, opacity: 0.2 });
      this.group.add(line);
      return { from: n.id, to: this.nodes[i + 1].id, curve, line };
    });

    // --- particles travelling along running edges
    const pm = new THREE.SpriteMaterial({ map: glow, color: '#ffe3a1', transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.particles = Array.from({ length: this.reduced ? 0 : 36 }, () => {
      const s = new THREE.Sprite(pm.clone()); s.scale.set(0.07, 0.07, 1); s.visible = false; this.group.add(s);
      return { s, curve: null, t: Math.random(), speed: 0.35 + Math.random() * 0.4 };
    });

    // --- beam from the graph down to the book
    const beamTex = (() => {
      const c = document.createElement('canvas'); c.width = 4; c.height = 256;
      const g = c.getContext('2d'); const r = g.createLinearGradient(0, 0, 0, 256);
      r.addColorStop(0, 'rgba(101,216,238,0.0)'); r.addColorStop(0.35, 'rgba(101,216,238,0.35)'); r.addColorStop(1, 'rgba(57,214,160,0.05)');
      g.fillStyle = r; g.fillRect(0, 0, 4, 256);
      return new THREE.CanvasTexture(c);
    })();
    this.beam = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.85, this.center.y - 0.45, 40, 1, true),
      new THREE.MeshBasicMaterial({ map: beamTex, transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.beam.position.set(0, (this.center.y - 0.45) / 2 + 0.3, this.center.z * 0.55);
    this.group.add(this.beam);
  }

  colorFor(id, status) {
    if (status === 'running') {
      const kind = this.nodes.find((n) => n.id === id)?.kind;
      return kind === 'cyan' ? COLORS.runningCyan : kind === 'blue' ? COLORS.runningBlue : COLORS.running;
    }
    return COLORS[status] || COLORS.waiting;
  }

  setStatuses(statuses, active) {
    this.status = { ...statuses };
    this.active = active;
    for (const n of this.nodes) {
      const st = statuses[n.id] || 'waiting';
      const col = new THREE.Color(this.colorFor(n.id, st));
      n.dot.material.color.copy(col);
      n.halo.material.color.copy(col);
      n.halo.material.opacity = st === 'waiting' ? 0.25 : st === 'skipped' ? 0.15 : 0.6;
      const su = n.spokeLine.material.uniforms;
      su.uColor.value.copy(st === 'waiting' || st === 'skipped' ? new THREE.Color('#65d8ee') : col);
      su.uOpacity.value = st === 'running' ? 0.95 : st === 'done' ? 0.5 : st === 'warning' || st === 'failed' ? 0.6 : 0.22;
      su.uSpeed.value = st === 'running' ? 1.4 : st === 'done' ? 0.35 : 0.15;
      su.uGlow.value = st === 'running' ? 2.4 : 1.2;
    }
    for (const a of this.arcs) {
      const a0 = statuses[a.from], a1 = statuses[a.to];
      const lit = (a0 === 'done' || a0 === 'warning') && a1 && a1 !== 'waiting' && a1 !== 'skipped';
      a.line.material.uniforms.uColor.value.set(lit ? COLORS.done : '#d6b66d');
      a.line.material.uniforms.uOpacity.value = lit ? 0.7 : 0.18;
      a.line.material.uniforms.uSpeed.value = lit ? 0.6 : 0.2;
    }
    // particles only on edges of running stages (spoke + incoming arc)
    const curves = [];
    for (const n of this.nodes) if (statuses[n.id] === 'running') {
      curves.push({ c: n.spoke, col: this.colorFor(n.id, 'running') });
      const arc = this.arcs.find((x) => x.to === n.id);
      if (arc) curves.push({ c: arc.curve, col: this.colorFor(n.id, 'running') });
    }
    this.particles.forEach((p, i) => {
      const pick = curves.length ? curves[i % curves.length] : null;
      p.curve = pick?.c ?? null;
      p.s.visible = !!pick;
      if (pick) p.s.material.color.set(pick.col);
    });
    const busy = Object.values(statuses).some((s) => s === 'running');
    gsap.to(this, { level: busy ? 1 : 0, duration: 0.6 });
  }

  update(dt) {
    this.time += dt;
    const t = this.time;
    if (!this.reduced) {
      const breathe = 1 + Math.sin(t * 1.3) * 0.02 + this.level * 0.03;
      this.brainGroup.scale.setScalar(breathe);
      this.brainGroup.rotation.y = Math.sin(t * 0.25) * 0.35;         // a gentle sway, never a full spin
      const sp = this.sparkPts.geometry.attributes.position.array, bp = this.brainPos, seg = this.synSeg;
      for (let i = 0; i < this.sparks.length; i++) {
        const k = this.sparks[i];
        k.t += dt * k.v * (0.6 + this.level * 2.2);
        if (k.t >= 1) { k.t = 0; k.seg = Math.floor(Math.random() * (seg.length / 2)); }
        const a = seg[k.seg * 2], b = seg[k.seg * 2 + 1];
        sp[i * 3] = bp[a * 3] + (bp[b * 3] - bp[a * 3]) * k.t;
        sp[i * 3 + 1] = bp[a * 3 + 1] + (bp[b * 3 + 1] - bp[a * 3 + 1]) * k.t;
        sp[i * 3 + 2] = bp[a * 3 + 2] + (bp[b * 3 + 2] - bp[a * 3 + 2]) * k.t;
      }
      this.sparkPts.geometry.attributes.position.needsUpdate = true;
      this.coreRing.rotation.x = Math.PI / 2 - 0.35 + Math.sin(t * 0.4) * 0.08;   // a slow tilt, no spinning
      this.coreRing.rotation.y = Math.sin(t * 0.21) * 0.25;
      for (const n of this.nodes) {
        if (this.status[n.id] === 'running') n.halo.scale.setScalar(0.55 + Math.sin(t * 5) * 0.12);
        else n.halo.scale.setScalar(0.55);
      }
      for (const p of this.particles) {
        if (!p.curve) continue;
        p.t = (p.t + dt * p.speed) % 1;
        p.s.position.copy(p.curve.getPointAt(p.t));
        p.s.material.opacity = Math.sin(p.t * Math.PI);
      }
    }
    this.coreGlow.material.opacity = 0.38 + this.level * 0.3 + (this.reduced ? 0 : Math.sin(t * 1.7) * 0.05);
    const scale = ((window.innerHeight || 900) * Math.min(window.devicePixelRatio || 1, 2) * 0.5) / Math.tan((18 * Math.PI) / 180);
    for (const m of [this.brain.material, this.sparkPts.material]) { m.uniforms.uTime.value = t; m.uniforms.uScale.value = scale; m.uniforms.uLevel.value = this.level; }
    this.synapse.material.opacity = 0.12 + this.level * 0.18;
    for (const n of this.nodes) n.spokeLine.material.uniforms.uTime.value = t;
    for (const a of this.arcs) a.line.material.uniforms.uTime.value = t;
    this.beam.material.opacity = 0.1 + this.level * 0.25;
  }

  /** Ellipse radii of the stage ring (taller on phones so the eight nodes do not overlap). */
  setShape(rx, ry) {
    if (Math.abs(rx - this.rx) < 1e-6 && Math.abs(ry - this.ry) < 1e-6) return;
    const kx = rx / this.rx, ky = ry / this.ry;
    this.rx = rx; this.ry = ry;
    for (const o of this.orbits) { o.scale.x *= kx; o.scale.y *= ky; }
    this.nodes.forEach((n, i) => {
      const a = ANGLES[i];
      n.pos.set(this.center.x + rx * Math.cos(a), this.center.y + ry * Math.sin(a), this.center.z + 0.02);
      n.dot.position.copy(n.pos); n.halo.position.copy(n.pos);
      const mid = n.pos.clone().lerp(this.center, 0.5).add(new THREE.Vector3(0, 0, 0.25));
      n.spoke = new THREE.QuadraticBezierCurve3(this.center.clone(), mid, n.pos.clone());
      const fresh = flowLine(n.spoke.getPoints(24), { color: '#65d8ee', width: 0.0045, speed: 0.35, dashes: 2, glow: 1.2, opacity: 0.25 });
      n.spokeLine.geometry.dispose(); n.spokeLine.geometry = fresh.geometry;
    });
    this.arcs.forEach((arc, i) => {
      const pts = [];
      for (let k = 0; k <= 24; k++) {
        const a = ANGLES[i] + (ANGLES[i + 1] - ANGLES[i]) * (k / 24);
        pts.push(new THREE.Vector3(this.center.x + rx * Math.cos(a), this.center.y + ry * Math.sin(a), this.center.z + 0.02));
      }
      arc.curve = new THREE.CatmullRomCurve3(pts);
      const fresh = flowLine(pts, { color: '#d6b66d', width: 0.0035, speed: 0.25, dashes: 1, glow: 1.0, opacity: 0.2 });
      arc.line.geometry.dispose(); arc.line.geometry = fresh.geometry;
    });
    this.setStatuses(this.status, this.active);
  }

  /** Scale the whole graph about the origin and put its centre at height cy (answer mode: smaller, higher). */
  setLayout({ scale = 1, cy = this.center.y, duration = 0 } = {}) {
    const y = cy - this.center.y * scale;
    if (!duration || this.reduced) { this.group.scale.setScalar(scale); this.group.position.y = y; return; }
    gsap.to(this.group.scale, { x: scale, y: scale, z: scale, duration, ease: 'power2.inOut' });
    gsap.to(this.group.position, { y, duration, ease: 'power2.inOut' });
  }

  anchor(id) {
    this.group.updateMatrixWorld();
    const v = id === 'mind' ? this.center.clone() : this.nodes.find((n) => n.id === id).pos.clone();
    return this.group.localToWorld(v);
  }
}
