// The model as a layered neural network in 3-D (v4, 8-noyabr — Bobur's reference: columns of neurons, every
// neuron joined to every neuron of the next column, labels under each column, a brace under the hidden part).
// Left → right, in computation order:
//   KIRISH (this request's input tokens) → EMBEDDING (hidden_size) → one transformer block: ATTENTION
//   (attention_heads; heads sharing a key/value group have one hue) → FFN (ffn_size) → QOLDIQ OQIM (hidden_size)
//   → CHIQISH (output tokens; for the embedding model: the pooled vector).
// The block repeats card.layers times: behind it stands the v3 tower (layers.js) — one ring per layer receding into
// depth, with its attention heads (KV-group hues), feed-forward dots and the residual-stream beam; also the arc over
// the block and the row of ticks under the brace (one per layer). A pulse crossing the block runs through the rings.
// Every number written is real (Ollama's model card and this request). The number of spheres in a column is a
// sample — proportional to √width so the shape stays truthful (FFN is 4× wider → 2× the spheres); the real
// width is written under it. Not drawn: activations or attention weights (Ollama does not expose them). Light
// pulses are this request's output tokens replayed at the measured tokens/s; a sphere flashes only while a pulse
// passes it — that brightness is not a measurement.
import { mini3d, LOW } from './mini3d.js';
import { glowPoints, scalePoints, flowLine, textSprite, PALETTE } from './fx.js';
import { layerTower } from './layers.js';

const DX = 2.9, SY = 0.235, R = 0.088;

export function layerNetwork(container, card, { tokens = null, run = null, kind = 'llm', onLayer, height = 460 } = {}) {
  const L = Math.max(1, card.layers || 1);
  const H = card.attention_heads || 0;
  const KV = card.kv_heads && H && card.kv_heads < H ? card.kv_heads : H;
  const llm = kind === 'llm';
  const sample = (w) => Math.max(4, Math.min(26, Math.round(Math.sqrt(w || 0) / 4.2)));
  const outTok = run?.output_tokens || 0;

  // ---- the columns (only those the model card has numbers for)
  const cols = [
    { key: 'in', name: 'KIRISH', sub: `${fmt(tokens)} token`, n: Math.max(3, Math.min(tokens || 6, 8)), color: '#e8c477', io: true,
      about: 'shu soʻrovning kirish tokenlari' },
    card.hidden_size && { key: 'emb', name: 'EMBEDDING', sub: `${fmt(card.hidden_size)} oʻlcham`, n: sample(card.hidden_size), color: '#7cc4f2',
      about: 'har token — hidden_size uzunlikdagi vektor' },
    H && { key: 'attn', name: 'ATTENTION', sub: KV < H ? `${H} bosh · ${KV} KV guruh` : `${H} bosh`, n: Math.max(4, Math.min(H, 16)), color: '#5fe1f5', kv: KV < H ? KV : 0,
      about: KV < H ? `${H} ta attention boshi; bir rangdagilar bitta key/value guruhini boʻlishadi` : `${H} ta attention boshi`, block: true },
    card.ffn_size && { key: 'ffn', name: 'FFN', sub: `${fmt(card.ffn_size)} neyron`, n: sample(card.ffn_size), color: '#8fb4ff',
      about: 'feed-forward qatlami — eng keng qism', block: true },
    card.hidden_size && { key: 'res', name: 'QOLDIQ OQIM', sub: `${fmt(card.hidden_size)} oʻlcham`, n: sample(card.hidden_size), color: '#7cc4f2',
      about: 'blok natijasi qoldiq oqimga qoʻshiladi va keyingi blokka oʻtadi', block: true },
    llm
      ? { key: 'out', name: 'CHIQISH', sub: `${fmt(run?.output_tokens)} token`, n: Math.max(2, Math.min(outTok || 2, 6)), color: '#39e0a6', io: true,
        about: 'model yozgan tokenlar (javob)' }
      : { key: 'out', name: 'VEKTOR', sub: `${fmt(card.hidden_size)} oʻlcham`, n: Math.max(3, Math.min(sample(card.hidden_size), 8)), color: '#f2f6f2', io: true,
        about: 'savolning yagona vektori (qidiruv uchun)' },
  ].filter(Boolean);
  const C = cols.length;
  const x0 = -((C - 1) * DX) / 2;
  cols.forEach((c, i) => {
    c.x = x0 + i * DX;
    c.nodes = Array.from({ length: c.n }, (_, j) => {
      const y = (j - (c.n - 1) / 2) * SY;
      return [c.x, y, -y * y * 0.05];                                // a slight curve: the column has depth when the camera turns
    });
  });
  const half = Math.max(...cols.map((c) => ((c.n - 1) / 2) * SY));
  const blockCols = cols.filter((c) => c.block);
  const subLines = Math.max(...cols.map((c) => c.sub.split(' · ').length));
  // Built in «layout» coordinates (columns along x, neurons along y). Narrow panels (a phone): the whole network is
  // turned a quarter so it flows top → bottom; the labels then stand to the left of each row, the brace to the right.
  const fov = 38, w0 = container.clientWidth || 900, aspect = w0 / height;
  const vert = aspect < 1.05;
  const top = half + 0.35, yName = -half - 0.5, ySub = yName - 0.3, yBrace = vert ? half + 0.5 : ySub - 0.27 * (subLines - 1) - 0.5;
  const out = vert ? 1 : -1;                                // the brace's bump points away from the columns

  // ---- camera: fit the whole network (screen x/y bounds), slightly from the left and above
  const vHalf = (fov * Math.PI) / 360, hHalf = Math.atan(Math.tan(vHalf) * aspect);
  const T = 2 * Math.tan(vHalf);                            // world units per «screen height» at distance 1
  let sx0, sx1, sy0, sy1, dist;
  if (vert) {
    // labels are screen-sized: their width in world units grows with the distance, so solve for it
    const kL = Math.max(...cols.flatMap((c) => [0.024 * textAspect(c.name, 600), ...c.sub.split(' · ').map((t) => 0.019 * textAspect(t, 500, true))]));
    const kR = 0.022 * Math.max(textAspect(`${L}/${L}-qatlam`, 600), textAspect(card.ffn_size ? `FFN ${fmt(card.ffn_size)}` : 'BLOK', 600), textAspect(`${KV} KV guruh`, 600));
    const W0 = yBrace + 0.4 - yName;
    dist = Math.max(W0 / (T * Math.max(0.12, 0.84 * aspect - 1.15 * (kL + kR))), ((-2 * x0 + 1.2) / 2) * 1.08 / Math.tan(vHalf));
    sx0 = yName - 1.15 * kL * T * dist; sx1 = yBrace + 0.4 + 1.15 * kR * T * dist; sy0 = x0 - 0.6; sy1 = -x0 + 0.6;
  } else {
    [sx0, sx1, sy0, sy1] = [x0 - 1.0, -x0 + 1.0, yBrace - 0.75, top + 1.3];
    dist = Math.max(((sx1 - sx0) / 2) * 1.16 / Math.tan(hHalf), ((sy1 - sy0) / 2) * 1.1 / Math.tan(vHalf));   // + room for the turned view
  }
  const cx = (sx0 + sx1) / 2, cy = (sy0 + sy1) / 2;
  const gap = vert ? 0.027 * T * dist : 0.27;               // one text line, in world units (labels are screen-sized)
  const AZ = vert ? -0.08 : -0.2, EL = vert ? 0.12 : 0.24, SWAY = vert ? 0.05 : 0.08;   // from above: the tower rises behind the block   // a little from the side: the tower’s depth shows
  const camAt = (az) => [cx + Math.sin(az) * Math.cos(EL) * dist, cy + Math.sin(EL) * dist, Math.cos(az) * Math.cos(EL) * dist];
  const v = mini3d(container, { height, fov, camera: camAt(AZ), target: [cx, cy, 0], autoRotate: 0,
    bloom: { strength: 0.55, radius: 0.5, threshold: 0.42 } });
  const { THREE } = v;
  const net = new THREE.Group();
  if (vert) net.rotation.z = -Math.PI / 2;                  // layout (x, y) → screen (y, −x)
  v.scene.add(net);
  const scene = net;

  v.scene.add(new THREE.HemisphereLight('#dff4ff', '#0b1714', 1.1));
  const key = new THREE.DirectionalLight('#ffffff', 2.2); key.position.set(-4, 6, 8); v.scene.add(key);
  const rim = new THREE.DirectionalLight('#5fe1f5', 1.4); rim.position.set(5, -2, -6); v.scene.add(rim);

  // ---- neurons: shaded spheres (one instanced mesh) + a halo per sphere that flashes when a pulse passes
  const all = cols.flatMap((c, ci) => c.nodes.map((p, j) => ({ p, ci, j, color: nodeColor(THREE, c, j) })));
  const N = all.length;
  const spheres = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 24, 16),
    new THREE.MeshStandardMaterial({ roughness: 0.32, metalness: 0.08, emissive: '#0d2a2a', emissiveIntensity: 0.6 }), N);
  const m4 = new THREE.Matrix4();
  all.forEach((a, i) => {
    const r = cols[a.ci].io ? R * 1.25 : R;
    m4.makeScale(r, r, r).setPosition(...a.p);
    spheres.setMatrixAt(i, m4);
    spheres.setColorAt(i, a.color);
  });
  spheres.instanceMatrix.needsUpdate = true; spheres.instanceColor.needsUpdate = true;
  scene.add(spheres);
  const hp = new Float32Array(N * 3), hc = new Float32Array(N * 3), hs = new Float32Array(N);
  all.forEach((a, i) => { hp.set(a.p, i * 3); hs[i] = cols[a.ci].io ? 0.42 : 0.34; });
  const halos = glowPoints({ count: N, positions: hp, colors: hc, sizes: hs });
  scene.add(halos);
  const flash = new Float32Array(N);
  const first = []; { let k = 0; for (const c of cols) { first.push(k); k += c.n; } }

  // ---- connections: every neuron to every neuron of the next column
  const seg = [], segCol = [];
  const ca = new THREE.Color(), cb = new THREE.Color();
  for (let i = 0; i < C - 1; i++) {
    for (let a = 0; a < cols[i].n; a++) for (let b = 0; b < cols[i + 1].n; b++) {
      seg.push(...cols[i].nodes[a], ...cols[i + 1].nodes[b]);
      ca.copy(all[first[i] + a].color).multiplyScalar(0.3); cb.copy(all[first[i + 1] + b].color).multiplyScalar(0.3);
      segCol.push(ca.r, ca.g, ca.b, cb.r, cb.g, cb.b);
    }
  }
  const links = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(seg, 3)).setAttribute('color', new THREE.Float32BufferAttribute(segCol, 3)),
    new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(links);

  // ---- the tower behind the block: card.layers rings receding into depth (v3 Mind tower, layers.js)
  let tower = null, ringLabel = null;
  if (blockCols.length && card.layers) {
    const xm = (blockCols[0].x + blockCols[blockCols.length - 1].x) / 2;
    tower = layerTower(THREE, { layers: card.layers, heads: H || 8, kvHeads: KV < H ? KV : null, radius: half * 0.86,
      innerRadius: half * 0.46, gap: Math.min(0.26, 9 / Math.max(1, card.layers)) });
    tower.group.position.set(xm, 0, -1.3);
    scene.add(tower.group);
  }

  // ---- labels under the columns (screen-sized, always readable)
  const sprites = [];
  const label = (text, at, o, k = 0.85, anchor = [0.5, 0.5]) => {   // k < 1 keeps the text under the bloom threshold: crisp
    const s = textSprite(text, { screen: true, ...o }); s.material.color.setScalar(k); s.position.set(...at); s.center.set(...anchor);
    scene.add(s); sprites.push(s); return s;
  };
  for (const c of cols) {
    const subs = c.sub.split(' · ');
    if (vert) {                                             // a small stack to the left of the row (layout +x = screen down)
      const h0 = (-gap * subs.length) / 2;
      label(c.name, [c.x + h0, yName, 0], { color: c.io ? c.color : '#cfe8f2', height: 0.024, weight: 600 }, 0.62, [1, 0.5]);
      subs.forEach((t, i) => label(t, [c.x + h0 + gap * (i + 1), yName, 0], { color: '#8fa7a0', height: 0.019, mono: true, weight: 500 }, 0.85, [1, 0.5]));
    } else {
      label(c.name, [c.x, yName, 0], { color: c.io ? c.color : '#cfe8f2', height: 0.026, weight: 600 }, 0.62);
      subs.forEach((t, i) => label(t, [c.x, ySub - i * 0.27, 0], { color: '#8fa7a0', height: 0.021, mono: true, weight: 500 }));
    }
  }

  // ---- the block: a brace under it with one tick per layer, and an arc over it (the block repeats L times)
  let ticks = null, arc = null, arcLabel = null, braceLabel = [], braceAt = null, info = null;
  const drop = (sp) => { if (sp) { scene.remove(sp); sp.material.map.dispose(); sp.material.dispose(); } };
  const say = (text, at, anchor = [0.5, 0]) => {           // a column's note
    drop(info);
    info = textSprite(text, { color: '#f3e3bb', height: 0.024, bg: 'rgba(10,18,16,0.9)', mono: true, weight: 500, screen: true });
    info.material.color.setScalar(0.62); info.position.set(...at); info.center.set(...anchor); scene.add(info);
    if (arc) { arc.visible = false; arcLabel.visible = false; }
  };
  const setBrace = (text) => {                              // the selected layer is written at the brace
    if (!braceAt) return;
    braceLabel.forEach(drop);
    const lines = vert ? text.replace('TRANSFORMER BLOKI × ', 'BLOK · × ').split(' · ') : [text];
    braceLabel = lines.map((t, i) => label(t, [braceAt[0] - (gap * (lines.length - 1)) / 2 + gap * i, braceAt[1], 0],
      { color: '#e8c477', height: vert ? 0.022 : 0.025, weight: 600 }, 0.7, vert ? [0, 0.5] : [0.5, 0.5]));
  };
  if (blockCols.length) {
    const xa = blockCols[0].x - 0.55, xb = blockCols[blockCols.length - 1].x + 0.55, xm = (xa + xb) / 2;
    const brace = [[xa, yBrace - out * 0.14], [xa, yBrace], [xm - 0.16, yBrace], [xm, yBrace + out * 0.16], [xm + 0.16, yBrace], [xb, yBrace], [xb, yBrace - out * 0.14]]
      .map(([x, y]) => new THREE.Vector3(x, y, 0));
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(brace),
      new THREE.LineBasicMaterial({ color: new THREE.Color('#8fa7a0'), transparent: true, opacity: 0.7 })));
    braceAt = vert ? [xm, yBrace + 0.32, 0] : [xm, yBrace - 0.42, 0];
    setBrace(`TRANSFORMER BLOKI × ${L}`);
    const tp = new Float32Array(L * 3), tc = new Float32Array(L * 3), ts = new Float32Array(L);
    for (let i = 0; i < L; i++) { tp.set([xa + 0.12 + ((xb - xa - 0.24) * (i + 0.5)) / L, yBrace - out * 0.1, 0], i * 3); ts[i] = 0.07; }
    ticks = glowPoints({ count: L, positions: tp, colors: tc, sizes: ts });
    scene.add(ticks);
    const xr = blockCols[blockCols.length - 1].x, xl = blockCols[0].x;
    if (!vert) {                                            // on a phone the brace alone says it (no room above)
    arc = flowLine([new THREE.Vector3(xr, top, 0), new THREE.Vector3((xr + xl) / 2 + 0.9, top + 0.95, -0.2), new THREE.Vector3((xr + xl) / 2 - 0.9, top + 0.95, -0.2),
      new THREE.Vector3(xl, top, 0)], { color: '#e8c477', width: 0.011, speed: 0.35, dashes: 4, glow: 1.5, opacity: 0.75 });
    scene.add(arc);
    arcLabel = label(`${L} marta takrorlanadi`, [(xr + xl) / 2, top + 1.22, -0.2], { color: '#e8c477', height: 0.021, mono: true, weight: 500 });
    }
  }

  // ---- pulses: output tokens travelling left → right at the measured rate (embedding model: one forward pass)
  const POOL = LOW ? 0 : 160;
  const pp = new Float32Array(POOL * 3), pc = new Float32Array(POOL * 3), ps = new Float32Array(POOL);
  for (let i = 0; i < POOL; i++) { pp[i * 3 + 1] = -999; pc.set(llm ? [1.6, 2.6, 2.2] : [2.4, 2.2, 1.6], i * 3); ps[i] = 0.16; }
  const pulses = POOL ? glowPoints({ count: POOL, positions: pp, colors: pc, sizes: ps }) : null;
  if (pulses) scene.add(pulses);
  scalePoints(v, halos.material, ...(ticks ? [ticks.material] : []), ...(pulses ? [pulses.material] : []), ...(tower ? tower.materials : []));

  const rate = llm ? (run?.tokens_per_s || 0) : 0;
  const total = llm ? outTok : Math.max(1, Math.min(tokens || 16, 120));
  const HOP = 0.3;                                         // seconds per column hop (visual pace)
  const bStart = cols.findIndex((c) => c.block), bEnd = cols.length - 1 - [...cols].reverse().findIndex((c) => c.block);
  const fly = [];
  let clock = 0, spawned = 0, restartAt = 0, slot = 0, sel = -1, touched = false;
  v.controls.addEventListener('start', () => { touched = true; });
  const tickLevel = new Float32Array(L);

  v.onTick((dt, time) => {
    halos.material.uniforms.uTime.value = time;
    if (arc) arc.material.uniforms.uTime.value = time;
    clock += dt;
    if (!touched && !LOW) {                                  // a slow sway instead of a full orbit: always seen from the front
      const p = camAt(AZ + Math.sin(time * 0.22) * SWAY);
      v.camera.position.set(...p);
    }
    flash.forEach((f, i) => { flash[i] = f * Math.exp(-dt * 4); });
    tickLevel.forEach((f, i) => { tickLevel[i] = f * Math.exp(-dt * 3); });
    if (pulses && total > 0) {
      if (restartAt && clock >= restartAt) { clock = 0; spawned = 0; restartAt = 0; fly.length = 0; }
      const due = restartAt ? spawned : llm ? Math.min(total, Math.floor(clock * (rate || 20))) : Math.min(total, Math.floor(clock * 200));
      while (spawned < due && fly.length < POOL) {
        fly.push({ t0: clock, slot: slot++ % POOL, path: cols.map((c) => Math.floor(Math.random() * c.n)), hit: -1 });
        spawned++;
      }
      if (spawned < due) spawned = due;
      const arr = pulses.geometry.attributes.position.array;
      for (let i = fly.length - 1; i >= 0; i--) {
        const f = fly[i], u = (clock - f.t0) / HOP, s = Math.floor(u);
        if (s >= C - 1) { arr[f.slot * 3 + 1] = -999; fly.splice(i, 1); flash[first[C - 1] + f.path[C - 1]] = 1; continue; }
        const a = cols[s].nodes[f.path[s]], b = cols[s + 1].nodes[f.path[s + 1]], k = u - s;
        arr.set([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k], f.slot * 3);
        if (s !== f.hit) { f.hit = s; flash[first[s] + f.path[s]] = 1; }
        if (ticks && s >= bStart && s < bEnd) {                // inside the block: the pass through its L layers
          const q = (u - bStart) / Math.max(1, bEnd - bStart);
          tickLevel[Math.min(L - 1, Math.floor(q * L))] = 1;
        }
      }
      pulses.geometry.attributes.position.needsUpdate = true;
      if (!restartAt && spawned >= total && fly.length === 0) restartAt = clock + 2.0;
    }
    const col = halos.geometry.attributes.color.array;
    for (let i = 0; i < N; i++) {
      const c = all[i].color, g = 0.16 + flash[i] * 1.9 + (sel >= 0 && cols[all[i].ci].block ? 0.12 : 0);
      col[i * 3] = c.r * g; col[i * 3 + 1] = c.g * g; col[i * 3 + 2] = c.b * g;
    }
    halos.geometry.attributes.color.needsUpdate = true;
    tower?.update(dt, time, tickLevel, sel);
    if (ticks) {
      const tc2 = ticks.geometry.attributes.color.array;
      const tsz = ticks.geometry.attributes.size.array;
      for (let i = 0; i < L; i++) {
        tsz[i] = i === sel ? 0.2 : 0.07;
        const g = i === sel ? 2.6 : 0.32 + tickLevel[i] * 1.8;
        tc2[i * 3] = 0.91 * g; tc2[i * 3 + 1] = 0.77 * g; tc2[i * 3 + 2] = 0.47 * g;
      }
      ticks.geometry.attributes.color.needsUpdate = true; ticks.geometry.attributes.size.needsUpdate = true;
    }
  });

  // ---- selection: a layer (the ‹ › buttons) or a column (click a sphere)
  const select = (i) => {
    sel = Math.max(0, Math.min(L - 1, i));
    if (blockCols.length) {
      const parts = [`${sel + 1} / ${L}-qatlam`, H ? `${H} bosh` : null, KV < H ? `${KV} KV guruh` : null, card.ffn_size ? `FFN ${fmt(card.ffn_size)}` : null].filter(Boolean);
      setBrace(parts.join(' · '));
    }
    if (tower) {                                           // the selected ring in the tower gets its number
      drop(ringLabel);
      ringLabel = textSprite(`${sel + 1}-qatlam`, { color: '#f3e3bb', height: 0.022, bg: 'rgba(10,18,16,0.85)', mono: true, weight: 500, screen: true });
      ringLabel.material.color.setScalar(0.62); ringLabel.center.set(0.5, 0);
      ringLabel.position.set(tower.group.position.x, half * 0.86 + 0.12, tower.group.position.z + tower.layerZ(sel));
      scene.add(ringLabel);
    }
    onLayer?.(sel);
  };
  // the nearest sphere on screen (within 28 px): the spheres are small, a ray would often miss them
  const wp = new THREE.Vector3();
  v.el.addEventListener('click', (e) => {
    const r = v.el.getBoundingClientRect();
    net.updateMatrixWorld();
    let best = -1, bd = 28 * 28;
    all.forEach((a, i) => {
      wp.set(...a.p); net.localToWorld(wp).project(v.camera);
      const dx = ((wp.x + 1) / 2) * r.width - (e.clientX - r.left), dy = ((1 - wp.y) / 2) * r.height - (e.clientY - r.top);
      if (dx * dx + dy * dy < bd) { bd = dx * dx + dy * dy; best = i; }
    });
    if (best < 0) return;
    const c = cols[all[best].ci];
    if (vert) say(`${c.name} · ${c.sub}`, [c.x - 0.3, 0, 0.4], [0.5, 0.5]);
    else say(`${c.name} · ${c.sub} — ${c.about}`, [c.x, c.nodes[c.n - 1][1] + 0.25, 0.4]);
  });

  return {
    view: v, select, get selected() { return sel; }, count: L, columns: cols.map((c) => c.key),
    toggleLinks(on) { links.visible = on; },
    clear() {
      sel = -1;
      drop(info); info = null;
      drop(ringLabel); ringLabel = null;
      if (arc) { arc.visible = true; arcLabel.visible = true; }
      setBrace(`TRANSFORMER BLOKI × ${L}`);
      setTimeout(() => { touched = false; }, 950);           // after the camera flew home, the sway resumes
    },
    replay: { rate, total, hop: HOP },
    /** screen position (px, relative to the canvas) of a column's middle sphere — for tests */
    screenOf(key) {
      const c = cols.find((x) => x.key === key); if (!c) return null;
      net.updateMatrixWorld(); const r = v.el.getBoundingClientRect();
      wp.set(...c.nodes[Math.floor(c.n / 2)]); net.localToWorld(wp).project(v.camera);
      return { x: ((wp.x + 1) / 2) * r.width, y: ((1 - wp.y) / 2) * r.height };
    },
  };
}

function nodeColor(THREE, c, j) {
  if (c.key === 'attn' && c.kv) {
    // heads that share a key/value group share a hue (grouped-query attention)
    const hues = ['#5fe1f5', '#9b8cff', '#2fd4b0', '#f0a35c'];
    return new THREE.Color(hues[Math.floor(j / (c.n / c.kv)) % hues.length]);
  }
  return new THREE.Color(c.color);
}

// the width/height ratio of a textSprite with this text (same font, size 44, padding 16)
let measure = null;
function textAspect(text, weight = 600, mono = false) {
  measure ||= document.createElement('canvas').getContext('2d');
  measure.font = `${weight} 44px ${mono ? 'JetBrains Mono, ui-monospace, monospace' : 'Onest, Inter, system-ui, sans-serif'}`;
  return (Math.ceil(measure.measureText(text).width) + 32) / Math.ceil(44 * 1.5);
}

function fmt(x) { return x == null ? '—' : Number(x).toLocaleString('uz-UZ').replace(/,/g, ' '); }
