// The 3-D PCA space as a nebula (v3, 8-noyabr). All positions come from GET /ask/{id}/embedding:
//   • the index sample (2 000 chunks) — dust whose brightness falls with its real distance from the question;
//   • the retrieved candidates — glowing orbs, larger = higher cosine, with their rank;
//   • the question — an emerald core with a slow pulse ring;
//   • beams candidate → question, thicker for a higher cosine, light flowing towards the question.
// The view is centred on the question; scaling keeps every ratio (distances are the projection's).
import * as THREE from 'three';
import { mini3d, LOW } from './mini3d.js';
import { glowPoints, scalePoints, flowLine, textSprite, glowSprite, ring } from './fx.js';
import { h } from '../ui/dom.js';

export function pcaCloud(container, data, { onPick, height = 520 } = {}) {
  const q0 = data.projection.coordinates;
  const raw = (p) => new THREE.Vector3(p.x - q0.x, p.y - q0.y, p.z - q0.z);
  const xyz = (a) => ({ x: a[0], y: a[1], z: a[2] });
  const refs = data.reference_cloud.map((r) => raw(xyz(r.xyz)));
  const cands = data.candidates.map((c) => ({ c, p: raw(xyz(c.xyz)) }));
  const d = [...refs, ...cands.map((x) => x.p)].map((p) => p.length()).sort((a, b) => a - b);
  const r92 = d[Math.floor(d.length * 0.92)] || 1;
  const k = 1.7 / r92;
  refs.forEach((p) => p.multiplyScalar(k)); cands.forEach((x) => x.p.multiplyScalar(k));
  // the camera starts close enough to tell the candidates apart (they sit near the question by definition);
  // zooming out shows the whole index sample. No distortion: one uniform scale for everything.
  const rc = Math.max(0.12, ...cands.map((x) => x.p.length()));
  const cd = Math.min(4.2, Math.max(1.1, rc * 3.4));
  const v = mini3d(container, { height, fov: 42, camera: [cd * 0.55, cd * 0.38, cd * 0.85], target: [0, 0, 0], autoRotate: 0.5,
    bloom: { strength: 0.8, radius: 0.55, threshold: 0.26 } });
  const { scene } = v;

  // dust: the index sample
  const N = refs.length, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), sz = new Float32Array(N);
  const near = new THREE.Color('#5fe9d6'), far = new THREE.Color('#2b4a63'), c = new THREE.Color();
  refs.forEach((p, i) => {
    const t = Math.min(1, p.length() / 2.2);
    c.copy(near).lerp(far, Math.pow(t, 0.7)).multiplyScalar(0.55 + 0.6 * (1 - t));
    pos.set([p.x, p.y, p.z], i * 3); col.set([c.r, c.g, c.b], i * 3); sz[i] = 0.022 + 0.018 * (1 - t);
  });
  const dust = glowPoints({ count: N, positions: pos, colors: col, sizes: sz, twinkle: LOW ? 0 : 0.12 });
  scene.add(dust);
  scalePoints(v, dust.material);

  // candidates: orbs, beams, rank labels
  const cos = cands.map((x) => x.c.cosine ?? 0), cmin = Math.min(...cos), cmax = Math.max(...cos);
  const norm = (x) => (cmax > cmin ? (x - cmin) / (cmax - cmin) : 1);
  const beams = new THREE.Group(), orbs = [];
  for (const { c: cand, p } of cands) {
    const s = norm(cand.cosine ?? cmin);
    const orb = glowSprite(s > 0.66 ? '#8fd0ff' : '#5f8fd8', (0.07 + 0.06 * s) * Math.max(0.6, cd / 2.5), 1.1 + 0.9 * s);
    orb.position.copy(p); orb.userData = cand; scene.add(orb); orbs.push(orb);
    const core = glowSprite('#ffffff', (0.022 + 0.014 * s) * Math.max(0.6, cd / 2.5), 1.3); core.position.copy(p); scene.add(core);
    const mid = p.clone().multiplyScalar(0.5).add(new THREE.Vector3(0, 0.12 + 0.1 * p.length(), 0));
    const beam = flowLine([p.clone(), mid, new THREE.Vector3(0, 0, 0)], { color: '#6fb6ff', width: (0.0015 + 0.003 * s) * Math.max(0.6, cd / 2.5), speed: 0.5 + 0.4 * s,
      dashes: 2, glow: 1.6, opacity: 0.35 + 0.5 * s });
    beams.add(beam);
    const lab = textSprite(`#${cand.rank}`, { color: '#cfe6ff', height: 0.022, mono: true, weight: 600, screen: true });
    lab.position.copy(p).add(new THREE.Vector3(0, 0.05 * Math.max(0.6, cd / 2.5), 0)); scene.add(lab);
  }
  scene.add(beams);

  // the question
  const q = new THREE.Group();
  const qs = Math.max(0.55, cd / 2.5);
  const qGlow = glowSprite('#39e0a6', 0.24 * qs, 1.2), qCore = glowSprite('#eafff6', 0.05 * qs, 1.8);
  qGlow.userData = { query: true };
  const pulse = ring(0.08, { color: '#39e0a6', tube: 0.0025, opacity: 0.6, intensity: 1.3 });
  const pulse2 = ring(0.08, { color: '#39e0a6', tube: 0.0025, opacity: 0.6, intensity: 1.3 });
  pulse.scale.setScalar(qs); pulse2.scale.setScalar(qs);
  q.add(qGlow, qCore, pulse, pulse2); scene.add(q);
  const qLab = textSprite('SAVOL', { color: '#8ff5cf', height: 0.022, mono: true, weight: 600, screen: true });
  qLab.position.set(0, -0.09 * qs, 0); scene.add(qLab);

  // floor and axes (the projection's own axes, with their explained variance)
  const floor = new THREE.PolarGridHelper(2.6, 12, 6, 96, new THREE.Color('#1f4a43'), new THREE.Color('#163631'));
  floor.position.y = -1.6; floor.material.transparent = true; floor.material.opacity = 0.5; floor.material.depthWrite = false; scene.add(floor);
  const ev = data.projection.explained_variance || [];
  const axes = new THREE.Group();
  [[1, 0, 0, '#e8c477'], [0, 1, 0, '#5fe1f5'], [0, 0, 1, '#9b8cff']].forEach(([x, y, z, color], i) => {
    const dir = new THREE.Vector3(x, y, z);
    axes.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([dir.clone().multiplyScalar(-0.35), dir.clone().multiplyScalar(0.55)]),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })));
    const l = textSprite(`PC${i + 1}${ev[i] != null ? ` · ${(ev[i] * 100).toFixed(1)}%` : ''}`, { color, height: 0.02, mono: true, weight: 500, screen: true });
    l.position.copy(dir.multiplyScalar(0.68)); axes.add(l);
  });
  scene.add(axes);

  v.onTick((dt, t) => {
    dust.material.uniforms.uTime.value = t;
    beams.children.forEach((b) => { b.material.uniforms.uTime.value = t; });
    if (!LOW) {
      for (const [i, r] of [pulse, pulse2].entries()) {
        const u = ((t * 0.45 + i * 0.5) % 1);
        r.scale.setScalar(qs * (1 + u * 3.2)); r.material.opacity = 0.55 * (1 - u);
        r.quaternion.copy(v.camera.quaternion);
      }
      qGlow.material.rotation = t * 0.2;
    }
  });

  const tip = h('div', { class: 'viz__tip', hidden: true });
  container.append(tip);
  v.el.addEventListener('mousemove', (e) => {
    const hit = v.pick(e, [qGlow, ...orbs]);
    if (!hit) { tip.hidden = true; v.el.style.cursor = ''; return; }
    const dd = hit.object.userData, r = container.getBoundingClientRect();
    tip.hidden = false; v.el.style.cursor = dd.query ? '' : 'pointer';
    tip.textContent = dd.query ? 'Savol vektori (proeksiya)' : `#${dd.rank} ${dd.doc_title ?? ''}${dd.article_no ? `, ${dd.article_no}-modda` : ''} · cos ${dd.cosine}`;
    tip.style.left = `${e.clientX - r.left}px`; tip.style.top = `${e.clientY - r.top}px`;
  });
  v.el.addEventListener('click', (e) => { const hit = v.pick(e, orbs); if (hit) onPick?.(hit.object.userData); });
  return {
    view: v,
    toggleCloud(on) { dust.visible = on; },
    toggleLines(on) { beams.visible = on; },
    toggleQuery(on) { q.visible = on; qLab.visible = on; },
  };
}
