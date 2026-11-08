// The model as a glowing tower (v3, 8-noyabr). Everything countable is real and comes from Ollama's model card
// and from this request:
//   • one ring per transformer layer (card.layers), stacked bottom → top in computation order;
//   • each ring split into card.attention_heads sectors; heads that share a key/value group (card.kv_heads,
//     grouped-query attention) share a hue; the inner ring stands for the feed-forward block (card.ffn_size);
//   • the central beam is the residual stream that every layer reads from and writes to;
//   • the gold disc at the bottom holds the request's input tokens, the emerald disc on top fills with its
//     output tokens; light pulses rising through the tower are those output tokens, replayed at the measured
//     tokens/s (for the embedding model: one forward pass of the input tokens).
// Not drawn: activations or attention weights — Ollama does not expose them. A ring lights up only while a
// pulse passes it; the brightness is not a measurement.
import { mini3d, LOW } from './mini3d.js';
import { glowPoints, scalePoints, flowLine, textSprite, glowSprite, ring, PALETTE } from './fx.js';

const MAXL = 64;

export function layerStack(container, card, { tokens = null, run = null, kind = 'llm', onLayer, height = 460 } = {}) {
  const L = Math.min(card.layers, MAXL);
  const H = Math.max(4, Math.min(card.attention_heads || 16, 64));
  const KV = card.kv_heads && card.kv_heads < H ? card.kv_heads : H;
  const tall = Math.max(3.2, Math.min(L * 0.17, 6.4));
  const gap = tall / Math.max(1, L - 1), y0 = -tall / 2;
  const R = 1.05, RF = 0.62;
  // wide panels: the tower lies left → right (input on the left); narrow ones: bottom → top
  const wide = (container.clientWidth || 900) / height > 1.25;
  const len = tall + 2.9, fov = 40;
  const aspect = wide ? (container.clientWidth || 900) / height : 1;
  const hHalf = Math.atan(Math.tan((fov * Math.PI) / 360) * aspect);
  const dist = wide ? ((len / 2) * 1.12) / Math.tan(hHalf) : ((len / 2) * 1.1) / Math.tan((fov * Math.PI) / 360);
  const home = wide ? [-dist * 0.18, dist * 0.42, dist * 0.92] : [dist * 0.56, len * 0.18, dist * 0.8];
  const v = mini3d(container, { height, fov, camera: home, target: [0, 0, 0], autoRotate: wide ? 0 : 0.4,
    bloom: { strength: 0.62, radius: 0.55, threshold: 0.32 } });
  const { THREE } = v;
  const tower = new THREE.Group();
  if (wide) tower.rotation.z = -Math.PI / 2;
  v.scene.add(tower);
  const scene = tower;                                   // everything below is built in the tower's own frame
  const world = (x, y, z) => { tower.updateMatrixWorld(); return tower.localToWorld(new THREE.Vector3(x, y, z)); };
  const layerY = (i) => y0 + i * gap;

  // ---- neurons: attention-head arcs (outer) and feed-forward dots (inner), one group per layer
  const per = Math.max(3, Math.min(10, Math.round(220 / H)));
  const ffnDots = 56;
  const n = L * (H * per + ffnDots);
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n), grp = new Float32Array(n);
  const c = new THREE.Color();
  let k = 0;
  for (let i = 0; i < L; i++) {
    const t = L > 1 ? i / (L - 1) : 0, y = layerY(i);
    const base = PALETTE.cyan.clone().lerp(PALETTE.teal, t);
    for (let hd = 0; hd < H; hd++) {
      const g = Math.floor(hd / (H / KV));                                         // shared key/value group
      const span = ((Math.PI * 2) / H) * 0.74, a0 = (hd / H) * Math.PI * 2 + i * 0.045;
      c.copy(base).offsetHSL(((g % 4) - 1.5) * 0.035, 0, ((g % 2) ? 0.04 : -0.02));
      for (let j = 0; j < per; j++) {
        const a = a0 + (per > 1 ? j / (per - 1) : 0.5) * span;
        pos.set([Math.cos(a) * R, y, Math.sin(a) * R], k * 3);
        col.set([c.r * 0.62, c.g * 0.62, c.b * 0.62], k * 3); size[k] = 0.036; grp[k] = i; k++;
      }
    }
    for (let j = 0; j < ffnDots; j++) {
      const a = (j / ffnDots) * Math.PI * 2 - i * 0.06;
      pos.set([Math.cos(a) * RF, y, Math.sin(a) * RF], k * 3);
      c.copy(PALETTE.violet).lerp(PALETTE.blue, t);
      col.set([c.r * 0.5, c.g * 0.5, c.b * 0.5], k * 3); size[k] = 0.024; grp[k] = i; k++;
    }
  }
  const neurons = glowPoints({ count: n, positions: pos, colors: col, sizes: size, groups: grp });
  scene.add(neurons);

  // ---- per-layer rings (thin), invisible pick discs
  const rings = [], discs = [];
  const discGeo = new THREE.CircleGeometry(R * 1.12, 48);
  for (let i = 0; i < L; i++) {
    const r = ring(R, { color: '#5fe1f5', tube: 0.0035, opacity: 0.22, intensity: 1 }); r.position.y = layerY(i); scene.add(r); rings.push(r);
    const d = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
    d.rotation.x = -Math.PI / 2; d.position.y = layerY(i); d.userData.layer = i; scene.add(d); discs.push(d);
  }

  // ---- residual stream: a vertical beam with light flowing up, and spokes to every layer
  const spine = flowLine([new THREE.Vector3(0, y0 - 0.7, 0), new THREE.Vector3(0, -tall / 2 + tall * 0.5, 0), new THREE.Vector3(0, -y0 + 0.75, 0)],
    { color: '#7ff0e0', width: 0.014, speed: 0.55, dashes: 7, glow: 1.8, opacity: 0.8 });
  scene.add(spine);
  const spokeSeg = [];
  for (let i = 0; i < L; i++) for (let s = 0; s < 8; s++) {
    const a = (s / 8) * Math.PI * 2 + i * 0.3;
    spokeSeg.push(0, layerY(i), 0, Math.cos(a) * RF, layerY(i), Math.sin(a) * RF);
    spokeSeg.push(Math.cos(a) * RF, layerY(i), Math.sin(a) * RF, Math.cos(a) * R * 0.97, layerY(i), Math.sin(a) * R * 0.97);
  }
  const spokes = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(spokeSeg, 3)),
    new THREE.LineBasicMaterial({ color: new THREE.Color('#5fe1f5').multiplyScalar(0.6), transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(spokes);

  // ---- token discs (phyllotaxis): input below, output on top (fills while pulses arrive)
  const golden = Math.PI * (3 - Math.sqrt(5));
  const disc = (count, y, color, radius, dot) => {
    const N = Math.max(1, count), p = new Float32Array(N * 3), cc = new Float32Array(N * 3), sz = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const r = radius * Math.sqrt((i + 0.5) / N), a = i * golden;
      p.set([Math.cos(a) * r, y, Math.sin(a) * r], i * 3); cc.set([color.r, color.g, color.b], i * 3); sz[i] = dot;
    }
    const pts = glowPoints({ count: N, positions: p, colors: cc, sizes: sz });
    scene.add(pts); return pts;
  };
  const inTok = Math.max(1, Math.min(tokens || 16, 2400));
  const inDisc = disc(inTok, y0 - 0.7, PALETTE.gold, R * 0.95, inTok > 900 ? 0.018 : 0.03);
  const outN = kind === 'llm' ? Math.max(1, Math.min(run?.output_tokens || 0, 2400)) : 1;
  const outDisc = disc(outN, -y0 + 0.75, kind === 'llm' ? PALETTE.emerald : PALETTE.white, kind === 'llm' ? R * 0.8 : 0.001, kind === 'llm' ? 0.034 : 0.16);
  outDisc.geometry.setDrawRange(0, kind === 'llm' ? 0 : 1);
  const inRing = ring(R * 0.98, { color: '#e8c477', tube: 0.005, opacity: 0.55, intensity: 1.6 }); inRing.position.y = y0 - 0.7; scene.add(inRing);
  const outRing = ring(R * 0.85, { color: '#39e0a6', tube: 0.005, opacity: 0.55, intensity: 1.6 }); outRing.position.y = -y0 + 0.75; scene.add(outRing);
  const lab = (text, y, color) => {
    const s = textSprite(text, { color, height: 0.024, mono: true, weight: 500, screen: true }); s.material.color.setScalar(0.85);
    s.position.copy(world(0, y, 0)).add(new THREE.Vector3(0, -(R + 0.38), 0)); s.center.set(0.5, 0.5); v.scene.add(s); return s;
  };
  lab(`KIRISH · ${fmt(tokens)} token`, y0 - 0.7, '#e8c477');
  lab(kind === 'llm' ? `CHIQISH · ${fmt(run?.output_tokens)} token` : `CHIQISH · ${card.hidden_size ? fmt(card.hidden_size) : ''} oʻlchamli vektor`, -y0 + 0.75, '#39e0a6');

  // ---- pulses: output tokens rising through the tower at the measured rate
  const POOL = LOW ? 0 : 220;
  const pp = new Float32Array(POOL * 3), pc = new Float32Array(POOL * 3), ps = new Float32Array(POOL);
  for (let i = 0; i < POOL; i++) { pp[i * 3 + 1] = -999; pc.set([1.6, 2.6, 2.3], i * 3); ps[i] = 0.075; }
  const pulses = POOL ? glowPoints({ count: POOL, positions: pp, colors: pc, sizes: ps }) : null;
  if (pulses) scene.add(pulses);
  scalePoints(v, neurons.material, inDisc.material, outDisc.material, ...(pulses ? [pulses.material] : []));

  const rate = kind === 'llm' ? (run?.tokens_per_s || 0) : 0;
  const total = kind === 'llm' ? (run?.output_tokens || 0) : inTok;
  const TRANSIT = 1.4;                                   // seconds for one pulse to cross the tower (visual pace)
  const fly = [];                                        // {t0, slot, a}
  let clock = 0, spawned = 0, arrived = 0, restartAt = 0, slot = 0;
  const flash = new Float32Array(L);
  let sel = -1;

  v.onTick((dt, time) => {
    neurons.material.uniforms.uTime.value = time;
    spine.material.uniforms.uTime.value = time;
    clock += dt;
    if (pulses && total > 0) {
      if (restartAt && clock >= restartAt) { clock = 0; spawned = 0; arrived = 0; restartAt = 0; fly.length = 0; outDisc.geometry.setDrawRange(0, kind === 'llm' ? 0 : 1); }
      const due = restartAt ? spawned : kind === 'llm' ? Math.min(total, Math.floor(clock * (rate || 20))) : Math.min(total, Math.floor(clock * Math.max(60, total / 0.6)));
      while (spawned < due && fly.length < POOL) { fly.push({ t0: clock, slot: slot++ % POOL, a: Math.random() * Math.PI * 2, r: 0.04 + Math.random() * 0.1 }); spawned++; }
      if (spawned < due) spawned = due;                  // pool full: count them, they are drawn as a denser stream
      flash.fill(0);
      const arr = pulses.geometry.attributes.position.array;
      for (let i = fly.length - 1; i >= 0; i--) {
        const f = fly[i], u = (clock - f.t0) / TRANSIT;
        if (u >= 1) { arr[f.slot * 3 + 1] = -999; fly.splice(i, 1); arrived++; if (kind === 'llm') outDisc.geometry.setDrawRange(0, Math.min(outN, Math.round((arrived / total) * outN))); continue; }
        const y = y0 - 0.7 + u * (tall + 1.45);
        arr.set([Math.cos(f.a + u * 3) * f.r, y, Math.sin(f.a + u * 3) * f.r], f.slot * 3);
        const li = Math.round((y - y0) / gap);
        if (li >= 0 && li < L) flash[li] = 1;
      }
      pulses.geometry.attributes.position.needsUpdate = true;
      if (!restartAt && spawned >= total && fly.length === 0) restartAt = clock + 2.2;
    }
    const g = neurons.material.uniforms.uGroup.value;
    for (let i = 0; i < L; i++) {
      const target = (sel < 0 ? 0.85 : i === sel ? 2.2 : 0.42) + flash[i] * 1.6;
      g[i] += (target - g[i]) * Math.min(1, dt * (flash[i] ? 18 : 5));
      rings[i].material.opacity = (i === sel ? 0.9 : 0.16) + flash[i] * 0.35;
    }
  });

  let selLabel = null;
  const select = (i, flyTo = true) => {
    sel = Math.max(0, Math.min(L - 1, i));
    rings.forEach((r, k2) => r.material.color.copy(k2 === sel ? new THREE.Color('#f0b44c').multiplyScalar(1.5) : new THREE.Color('#5fe1f5')));
    if (selLabel) { v.scene.remove(selLabel); selLabel.material.map.dispose(); selLabel.material.dispose(); }
    const parts = [`${sel + 1}-qatlam`, `${card.attention_heads ?? H} bosh`, KV < H ? `${KV} KV guruh` : null, card.hidden_size ? `${fmt(card.hidden_size)} kenglik` : null].filter(Boolean);
    selLabel = textSprite(parts.join(' · '), { color: '#f3e3bb', height: 0.026, bg: 'rgba(10,18,16,0.82)', mono: true, weight: 500, screen: true }); selLabel.material.color.setScalar(0.85);
    const at = world(0, layerY(sel), 0);
    selLabel.position.copy(at).add(new THREE.Vector3(0, R + 0.22, 0)); selLabel.center.set(0.5, 0.5); v.scene.add(selLabel);
    if (flyTo) v.fly(wide ? [at.x - 1.6, at.y + 2.2, at.z + 5.2] : [4.2, at.y + 1.9, 4.8], [at.x + (wide ? 0.9 : 0), at.y, at.z]);
    onLayer?.(sel);
  };
  v.el.addEventListener('click', (e) => { const hit = v.pick(e, discs); if (hit) select(hit.object.userData.layer); });
  const top = glowSprite('#39e0a6', 0.5, 1.4); top.position.y = -y0 + 0.75; scene.add(top);
  const bottom = glowSprite('#e8c477', 0.5, 1.2); bottom.position.y = y0 - 0.7; scene.add(bottom);
  return {
    view: v, select, get selected() { return sel; }, count: L,
    toggleLinks(on) { spokes.visible = on; },
    clear() {
      sel = -1;
      rings.forEach((r) => r.material.color.set('#5fe1f5'));
      if (selLabel) { v.scene.remove(selLabel); selLabel.material.map.dispose(); selLabel.material.dispose(); selLabel = null; }
    },
    replay: { rate, total, transit: TRANSIT },
  };
}

function fmt(x) { return x == null ? '—' : Number(x).toLocaleString('uz-UZ').replace(/,/g, ' '); }
