// The exact embedding as a 3-D field of light (v3, 8-noyabr): one bar per dimension on a 32 × 32 grid
// (dimension i at row ⌊i/32⌋, column i mod 32), height ∝ value / max|value| — gold rises for positive values,
// cyan sinks for negative ones under a glass floor. Every bar is a real number from GET /ask/{id}/embedding;
// hover shows it exactly, click selects it (the value list on the right jumps there).
import { mini3d, LOW } from './mini3d.js';
import { textSprite, glowSprite } from './fx.js';
import { h } from '../ui/dom.js';

export function vectorField(vector, { onSelect, height = 420 } = {}) {
  const wrap = h('div', { class: 'viz viz--field' });
  const tip = h('div', { class: 'viz__tip', hidden: true });
  const n = vector.length, cols = Math.ceil(Math.sqrt(n)), rows = Math.ceil(n / cols);
  let view = null, api = { select() {}, dispose() {} };
  // the panel is built before it is in the DOM: start the 3-D view once the wrapper has a size
  const start = () => {
    const v = view = mini3d(wrap, { height, fov: 38, camera: [0.9, 1.45, 3.5], target: [0, 0.05, 0], autoRotate: 0.5,
      bloom: { strength: 0.75, radius: 0.5, threshold: 0.28 } });
    const { THREE, scene } = v;
    const max = Math.max(...vector.map(Math.abs)) || 1;
    const cell = 3.2 / cols, w = cell * 0.62, H = 1.7;
    const geo = new THREE.BoxGeometry(w, 1, w); geo.translate(0, 0.5, 0);           // grows from its base
    const mat = new THREE.MeshBasicMaterial({ vertexColors: false, toneMapped: true });
    const bars = new THREE.InstancedMesh(geo, mat, n);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(), p3 = new THREE.Vector3(), c = new THREE.Color();
    const gold = new THREE.Color('#f2c46b'), cyan = new THREE.Color('#4fdcf2'), dim = new THREE.Color('#1d3a35');
    const at = (i) => [((i % cols) - (cols - 1) / 2) * cell, (Math.floor(i / cols) - (rows - 1) / 2) * cell];
    const colorOf = (i, boost = 1) => {
      const k = Math.min(1, Math.abs(vector[i]) / max);
      return c.copy(dim).lerp(vector[i] >= 0 ? gold : cyan, Math.min(1, k * 2.2)).multiplyScalar((0.55 + 1.8 * Math.pow(k, 1.3)) * boost);
    };
    for (let i = 0; i < n; i++) bars.setColorAt(i, colorOf(i));
    const place = (i, grow) => {
      const [x, z] = at(i), val = vector[i] / max, hgt = Math.max(0.004, Math.abs(val) * H * grow);
      sc.set(1, hgt, 1); q.identity();
      if (val < 0) q.setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI);         // negative: hang below the floor
      p3.set(x, 0, z); m4.compose(p3, q, sc); bars.setMatrixAt(i, m4);
    };
    for (let i = 0; i < n; i++) place(i, LOW ? 1 : 0);
    scene.add(bars);

    // glass floor: grid lines and a faint plate
    const span = cols * cell;
    const grid = new THREE.GridHelper(span, cols, new THREE.Color('#2a5a52'), new THREE.Color('#183630'));
    grid.material.transparent = true; grid.material.opacity = 0.45; grid.material.depthWrite = false; scene.add(grid);
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(span * 1.04, span * 1.04),
      new THREE.MeshBasicMaterial({ color: '#0d2a25', transparent: true, opacity: 0.35, depthWrite: false, side: THREE.DoubleSide }));
    plate.rotation.x = -Math.PI / 2; scene.add(plate);
    const lab = (t, x, z, col) => { const s = textSprite(t, { color: col, height: 0.024, mono: true, weight: 500, screen: true }); s.position.set(x, 0.02, z); scene.add(s); };
    lab(`${n} oʻlcham · 32 × ${rows}`, 0, span / 2 + 0.3, '#9fb3aa');
    lab('+ musbat', -span / 2 - 0.1, -span / 2 - 0.25, '#f2c46b');
    lab('− manfiy', span / 2 + 0.1, -span / 2 - 0.25, '#4fdcf2');
    const marker = glowSprite('#ffffff', 0.18, 2.2); marker.visible = false; scene.add(marker);

    // grow-in wave from the centre
    if (!LOW) {
      const order = [...Array(n).keys()].map((i) => { const [x, z] = at(i); return Math.hypot(x, z); });
      const far = Math.max(...order);
      let t = 0;
      const tick = (dt) => {
        if (t > 1.6) return;
        t += dt;
        for (let i = 0; i < n; i++) { const k = Math.min(1, Math.max(0, (t - (order[i] / far) * 0.8) / 0.8)); place(i, 1 - Math.pow(1 - k, 3)); }
        bars.instanceMatrix.needsUpdate = true;
      };
      v.onTick(tick);
    }
    let selected = -1, hover = -1;
    const paint = (i, boost) => { if (i < 0) return; bars.setColorAt(i, colorOf(i, boost)); bars.instanceColor.needsUpdate = true; };
    const pickAt = (e) => { const hit = v.pick(e, [bars]); return hit ? hit.instanceId : -1; };
    v.el.addEventListener('mousemove', (e) => {
      const i = pickAt(e);
      if (i !== hover) { if (hover !== selected) paint(hover, 1); hover = i; if (i >= 0 && i !== selected) paint(i, 1.9); }
      if (i < 0) { tip.hidden = true; v.el.style.cursor = ''; return; }
      const r = wrap.getBoundingClientRect();
      tip.hidden = false; v.el.style.cursor = 'pointer';
      tip.textContent = `embedding[${i}] = ${vector[i].toFixed(6)}`;
      tip.style.left = `${e.clientX - r.left}px`; tip.style.top = `${e.clientY - r.top}px`;
    });
    v.el.addEventListener('mouseleave', () => { tip.hidden = true; if (hover !== selected) paint(hover, 1); hover = -1; });
    const select = (i) => {
      if (selected >= 0) paint(selected, 1);
      selected = i; paint(i, 2.6);
      const [x, z] = at(i), val = vector[i] / max;
      marker.visible = true; marker.position.set(x, val >= 0 ? Math.abs(val) * H + 0.08 : -Math.abs(val) * H - 0.08, z);
    };
    v.el.addEventListener('click', (e) => { const i = pickAt(e); if (i >= 0) { select(i); onSelect?.(i); } });
    wrap.append(tip);
    api = { select, dispose: () => v.dispose(), view: v };
  };
  const ro = new ResizeObserver(() => { if (!view && wrap.clientWidth) { ro.disconnect(); start(); } });
  ro.observe(wrap);
  return { el: wrap, select: (i) => api.select(i), dispose: () => { ro.disconnect(); api.dispose(); } };
}
