// The 3-D PCA projection: reference sample (grey), retrieved candidates (blue, larger = better rank),
// the query (emerald) and lines query → candidate. All coordinates come from GET /ask/{id}/embedding.
import { mini3d, dotTexture } from './mini3d.js';
import { h } from '../ui/dom.js';

export function pcaCloud(container, data, { onPick } = {}) {
  const v = mini3d(container, { height: 440, camera: [0, 0, 3.2] });
  const { THREE, scene } = v;
  const all = [data.projection.coordinates, ...data.candidates.map((c) => ({ x: c.xyz[0], y: c.xyz[1], z: c.xyz[2] })),
    ...data.reference_cloud.map((r) => ({ x: r.xyz[0], y: r.xyz[1], z: r.xyz[2] }))];
  const ext = Math.max(...all.flatMap((p) => [Math.abs(p.x), Math.abs(p.y), Math.abs(p.z)])) || 1;
  const k = 1.25 / ext;                                            // fit into the view; ratios are kept
  const P = (p) => new THREE.Vector3(p.x * k, p.y * k, p.z * k);
  const tex = dotTexture();

  const ref = new THREE.BufferGeometry().setFromPoints(data.reference_cloud.map((r) => P({ x: r.xyz[0], y: r.xyz[1], z: r.xyz[2] })));
  const refPts = new THREE.Points(ref, new THREE.PointsMaterial({ color: '#6f8279', size: 0.035, map: tex, transparent: true, opacity: 0.55, depthWrite: false }));
  scene.add(refPts);

  const cands = data.candidates.map((c) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: '#73afe0', depthWrite: false }));
    const size = 0.13 - Math.min(c.rank - 1, 8) * 0.008;
    s.scale.set(size, size, 1); s.position.copy(P({ x: c.xyz[0], y: c.xyz[1], z: c.xyz[2] })); s.userData = c;
    scene.add(s); return s;
  });
  const q = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: '#39d6a0', depthWrite: false }));
  q.scale.set(0.2, 0.2, 1); q.position.copy(P(data.projection.coordinates)); q.userData = { query: true };
  scene.add(q);
  const lines = new THREE.Group();
  for (const s of cands) {
    const g = new THREE.BufferGeometry().setFromPoints([q.position, s.position]);
    lines.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: '#65d8ee', transparent: true, opacity: 0.35 })));
  }
  scene.add(lines);
  const axes = new THREE.AxesHelper(0.35); axes.material.transparent = true; axes.material.opacity = 0.35; scene.add(axes);

  const tip = h('div', { class: 'viz__tip', hidden: true });
  container.append(tip);
  v.el.addEventListener('mousemove', (e) => {
    const hit = v.pick(e, [q, ...cands]);
    if (!hit) { tip.hidden = true; v.el.style.cursor = ''; return; }
    const d = hit.object.userData, r = container.getBoundingClientRect();
    tip.hidden = false; v.el.style.cursor = d.query ? '' : 'pointer';
    tip.textContent = d.query ? 'Savol vektori (proeksiya)' : `#${d.rank} ${d.doc_title ?? ''}${d.article_no ? `, ${d.article_no}-modda` : ''} · cos ${d.cosine}`;
    tip.style.left = `${e.clientX - r.left}px`; tip.style.top = `${e.clientY - r.top}px`;
  });
  v.el.addEventListener('click', (e) => { const hit = v.pick(e, cands); if (hit) onPick?.(hit.object.userData); });
  return {
    view: v,
    toggleCloud(on) { refPts.visible = on; },
    toggleLines(on) { lines.visible = on; },
    toggleQuery(on) { q.visible = on; },
  };
}
