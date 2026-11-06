// The model's architecture in 3-D: one plate per transformer layer (the real count from Ollama), each with a
// fixed sample of neuron dots, an input-token row and an output vector. Lines between plates show that every
// layer feeds the next — a diagram of the structure, not measured activations (Ollama does not expose them).
import { mini3d, dotTexture } from './mini3d.js';

export function layerStack(container, card, { tokens = null, onLayer } = {}) {
  const L = card.layers;
  const gap = 0.28, depth = (L - 1) * gap;
  const v = mini3d(container, { height: 460, camera: [5.2, 2.6, depth / 2 + 5.6], target: [0, 0, depth / 2] });
  const { THREE, scene } = v;
  const tex = dotTexture();
  const cols = 8, rows = 6;                                          // sample shown per layer (48 dots)
  const plates = [];
  const plateGeo = new THREE.PlaneGeometry(2.2, 1.6);
  const dotPos = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) dotPos.push(new THREE.Vector3((c - (cols - 1) / 2) * 0.26, (r - (rows - 1) / 2) * 0.24, 0));
  for (let i = 0; i < L; i++) {
    const g = new THREE.Group();
    g.position.z = i * gap;
    const plate = new THREE.Mesh(plateGeo, new THREE.MeshBasicMaterial({ color: '#65d8ee', transparent: true, opacity: 0.045, side: THREE.DoubleSide, depthWrite: false }));
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(plateGeo), new THREE.LineBasicMaterial({ color: '#65d8ee', transparent: true, opacity: 0.25 }));
    const pts = new THREE.Points(new THREE.BufferGeometry().setFromPoints(dotPos), new THREE.PointsMaterial({ color: '#9fe9f5', size: 0.07, map: tex, transparent: true, opacity: 0.75, depthWrite: false }));
    g.add(plate, edge, pts); g.userData = { layer: i };
    plate.userData = { layer: i };
    scene.add(g); plates.push({ g, plate, edge, pts });
  }
  // connections: each dot to the same and neighbouring dots of the next layer (structure only)
  const seg = [];
  for (let i = 0; i < L - 1; i++) for (let d = 0; d < dotPos.length; d += 3) {
    const a = dotPos[d], b = dotPos[(d + 7) % dotPos.length];
    seg.push(a.x, a.y, i * gap, b.x, b.y, (i + 1) * gap);
  }
  const links = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(seg, 3)),
    new THREE.LineBasicMaterial({ color: '#65d8ee', transparent: true, opacity: 0.08 }));
  scene.add(links);
  // input tokens (gold) and output (emerald)
  const nTok = Math.max(1, Math.min(tokens || 12, 64));
  const tokPts = [];
  for (let t = 0; t < nTok; t++) tokPts.push(new THREE.Vector3((t - (nTok - 1) / 2) * (2.2 / Math.max(nTok, 8)), -1.15, -0.55));
  scene.add(new THREE.Points(new THREE.BufferGeometry().setFromPoints(tokPts), new THREE.PointsMaterial({ color: '#d6b66d', size: 0.09, map: tex, transparent: true, depthWrite: false })));
  const out = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: '#39d6a0', depthWrite: false }));
  out.position.set(0, 0, depth + 0.6); out.scale.set(0.32, 0.32, 1); scene.add(out);

  let sel = -1;
  const select = (i) => {
    sel = Math.max(0, Math.min(L - 1, i));
    plates.forEach((p, k) => {
      const on = k === sel;
      p.plate.material.opacity = on ? 0.16 : 0.045;
      p.edge.material.opacity = on ? 0.9 : 0.22;
      p.edge.material.color.set(on ? '#d6b66d' : '#65d8ee');
      p.pts.material.opacity = on ? 1 : 0.55;
    });
    v.fly([3.4, 1.4, sel * gap + 2.6], [0, 0, sel * gap]);
    onLayer?.(sel);
  };
  v.el.addEventListener('click', (e) => { const hit = v.pick(e, plates.map((p) => p.plate)); if (hit) select(hit.object.userData.layer); });
  return { view: v, select, get selected() { return sel; }, count: L, toggleLinks(on) { links.visible = on; } };
}
