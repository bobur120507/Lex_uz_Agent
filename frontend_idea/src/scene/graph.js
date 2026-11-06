// The process graph above the book: the Mind (LLM) in the centre, eight processing stages around it,
// spokes Mind ↔ stage, arcs stage → next stage (the pipeline order), particles only on running edges,
// and a beam down to the book. Labels and clicks are HTML buttons placed over the anchors (accessible).
import * as THREE from 'three';
import { gsap } from 'gsap';
import { STAGES } from '../config.js';

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
    this.brain = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(brainPoints(this.reduced ? 500 : 1300, 0.42), 3)),
      new THREE.PointsMaterial({ color: '#7fe3f2', size: 0.016, transparent: true, opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: '#9fe9d8', transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.coreGlow.scale.set(1.7, 1.7, 1);
    this.coreRing = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.006, 8, 96),
      new THREE.MeshBasicMaterial({ color: '#d6b66d', transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.core.add(this.coreGlow, this.brain, this.coreRing);
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
      const spokeLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(spoke.getPoints(32)),
        new THREE.LineBasicMaterial({ color: '#65d8ee', transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
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
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: '#d6b66d', transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false }));
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
      n.spokeLine.material.color.copy(st === 'waiting' || st === 'skipped' ? new THREE.Color('#65d8ee') : col);
      n.spokeLine.material.opacity = st === 'running' ? 0.75 : st === 'done' ? 0.4 : st === 'warning' || st === 'failed' ? 0.5 : 0.16;
    }
    for (const a of this.arcs) {
      const a0 = statuses[a.from], a1 = statuses[a.to];
      const lit = (a0 === 'done' || a0 === 'warning') && a1 && a1 !== 'waiting' && a1 !== 'skipped';
      a.line.material.color.set(lit ? COLORS.done : '#d6b66d');
      a.line.material.opacity = lit ? 0.55 : 0.14;
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
      this.brain.scale.setScalar(breathe);
      this.brain.rotation.y = Math.sin(t * 0.25) * 0.35;              // a gentle sway, never a full spin
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
      n.spokeLine.geometry.setFromPoints(n.spoke.getPoints(32));
    });
    this.arcs.forEach((arc, i) => {
      const pts = [];
      for (let k = 0; k <= 24; k++) {
        const a = ANGLES[i] + (ANGLES[i + 1] - ANGLES[i]) * (k / 24);
        pts.push(new THREE.Vector3(this.center.x + rx * Math.cos(a), this.center.y + ry * Math.sin(a), this.center.z + 0.02));
      }
      arc.curve = new THREE.CatmullRomCurve3(pts);
      arc.line.geometry.setFromPoints(pts);
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
