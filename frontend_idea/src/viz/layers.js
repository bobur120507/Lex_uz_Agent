// The model's layers as a tower of rings (v3 «Mind» tower, 8-noyabr) — since v4 it stands BEHIND the transformer block of
// the layered network (network.js): the block drawn in front is one layer; the tower shows that it repeats card.layers
// times, receding into depth. Everything countable is real (Ollama's model card):
//   • one ring per transformer layer, nearest = layer 1;
//   • each ring split into `heads` sectors (attention heads); heads that share a key/value group (grouped-query
//     attention, `kvHeads`) share a hue; the inner circle of dots stands for the feed-forward block;
//   • the beam through the centre is the residual stream every layer reads from and writes to.
// Not drawn: activations or attention weights — Ollama does not expose them. A ring lights up only while a pulse (an
// output token being replayed) passes it, or when it is selected; the brightness is not a measurement.
import { glowPoints, flowLine, ring, PALETTE } from './fx.js';

export const MAX_LAYERS = 64;                              // glowPoints keeps per-group brightness for 64 groups

/**
 * @param THREE  the three.js namespace of the view
 * @param o      { layers, heads, kvHeads, radius, innerRadius, gap }
 * @returns      { group, materials, depth, update(dt, time, wave: Float32Array, selected), layerZ(i) }
 */
export function layerTower(THREE, { layers, heads = 8, kvHeads = null, radius = 2.4, innerRadius = 1.3, gap = 0.16 } = {}) {
  const L = Math.max(1, Math.min(layers || 1, MAX_LAYERS));
  const H = Math.max(4, Math.min(heads || 8, 32));
  const KV = kvHeads && kvHeads < H ? kvHeads : H;
  const group = new THREE.Group();
  const z = (i) => -i * gap;

  // ---- attention-head arcs (outer) and feed-forward dots (inner), one brightness group per layer
  const per = Math.max(3, Math.min(6, Math.round(48 / H)));
  const ffn = 24;
  const n = L * (H * per + ffn);
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n), grp = new Float32Array(n);
  const hues = [new THREE.Color('#5fe1f5'), new THREE.Color('#9b8cff'), new THREE.Color('#2fd4b0'), new THREE.Color('#f0a35c')];
  const c = new THREE.Color();
  let k = 0;
  for (let i = 0; i < L; i++) {
    for (let hd = 0; hd < H; hd++) {
      const g = Math.floor(hd / (H / KV));                 // shared key/value group → one hue
      const span = ((Math.PI * 2) / H) * 0.6, a0 = (hd / H) * Math.PI * 2 + Math.PI / 2 + i * 0.04;
      c.copy(KV < H ? hues[g % hues.length] : PALETTE.cyan);
      for (let j = 0; j < per; j++) {
        const a = a0 + (per > 1 ? j / (per - 1) : 0.5) * span;
        pos.set([Math.cos(a) * radius, Math.sin(a) * radius, z(i)], k * 3);
        col.set([c.r * 0.75, c.g * 0.75, c.b * 0.75], k * 3); size[k] = 0.06; grp[k] = i; k++;
      }
    }
    for (let j = 0; j < ffn; j++) {
      const a = (j / ffn) * Math.PI * 2 - i * 0.05;
      c.copy(PALETTE.violet).lerp(PALETTE.blue, i / Math.max(1, L - 1));
      pos.set([Math.cos(a) * innerRadius, Math.sin(a) * innerRadius, z(i)], k * 3);
      col.set([c.r * 0.5, c.g * 0.5, c.b * 0.5], k * 3); size[k] = 0.036; grp[k] = i; k++;
    }
  }
  const neurons = glowPoints({ count: n, positions: pos, colors: col, sizes: size, groups: grp });
  group.add(neurons);

  // ---- one thin ring per layer (in the XY plane, facing the camera)
  const rings = [];
  for (let i = 0; i < L; i++) {
    const r = ring(radius, { color: '#5fe1f5', tube: 0.004, opacity: 0.1, intensity: 1 });
    r.rotation.x = 0;
    r.position.z = z(i);
    group.add(r);
    rings.push(r);
  }

  // ---- residual stream: a beam through the centre, light flowing from the block (front) to the last layer
  const depth = (L - 1) * gap;
  const spine = flowLine([new THREE.Vector3(0, 0, 0.6), new THREE.Vector3(0, 0, -depth / 2), new THREE.Vector3(0, 0, -depth - 0.5)],
    { color: '#7ff0e0', width: 0.016, speed: 0.45, dashes: 6, glow: 1.6, opacity: 0.6 });
  group.add(spine);

  const gold = new THREE.Color('#f0b44c').multiplyScalar(1.6), cyan = new THREE.Color('#5fe1f5');
  const gains = neurons.material.uniforms.uGroup.value;
  for (let i = 0; i < 64; i++) gains[i] = 0.6;

  return {
    group, depth, count: L,
    materials: [neurons.material],
    layerZ: z,
    /** wave[i] 0…1: how much a passing pulse lights layer i; selected: −1 or a layer index */
    update(dt, time, wave, selected) {
      neurons.material.uniforms.uTime.value = time;
      spine.material.uniforms.uTime.value = time;
      for (let i = 0; i < L; i++) {
        const w = wave ? wave[Math.min(wave.length - 1, i)] : 0;
        const target = (selected < 0 ? 0.6 : i === selected ? 2.4 : 0.35) + w * 1.8;
        gains[i] += (target - gains[i]) * Math.min(1, dt * (w > 0.5 ? 16 : 5));
        rings[i].material.opacity = (i === selected ? 0.9 : 0.14) + w * 0.45;
        rings[i].material.color.copy(i === selected ? gold : cyan);
      }
    },
  };
}
