// Shared visual building blocks for the inspector views (v3): soft glowing points with size attenuation,
// lines/tubes with light flowing along them, crisp text labels, and a glow sprite. Colours are given in
// linear HDR-ish values so that the bloom pass in mini3d.js picks up the bright parts.
import * as THREE from 'three';

/**
 * Glowing points. Attributes: position, color (vec3), size (float, world units), and optionally
 * `group` (float, e.g. the layer index) for per-group brightness through uniform `uGroup[64]`.
 */
export function glowPoints({ count, positions, colors, sizes, groups = null, opacity = 1, additive = true, twinkle = 0 }) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  g.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
  g.setAttribute('group', new THREE.BufferAttribute(groups || new Float32Array(count), 1));
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    uniforms: {
      uTime: { value: 0 }, uScale: { value: 400 }, uOpacity: { value: opacity }, uTwinkle: { value: twinkle },
      uGroup: { value: new Array(64).fill(1) }, uHover: { value: -1 },
    },
    vertexShader: /* glsl */`
      attribute float size; attribute float group; attribute vec3 color;
      uniform float uScale, uTime, uTwinkle; uniform float uGroup[64]; uniform float uHover;
      varying vec3 vColor; varying float vGain;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        float gain = uGroup[int(clamp(group, 0.0, 63.0))];
        float tw = 1.0 + uTwinkle * sin(uTime * 2.1 + position.x * 13.0 + position.y * 7.0 + position.z * 5.0);
        vGain = gain * tw;
        vColor = color;
        float hover = (abs(float(gl_VertexID) - uHover) < 0.5) ? 2.2 : 1.0;
        gl_PointSize = max(1.5, size * uScale * (0.65 + 0.35 * gain) * hover / -mv.z);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */`
      uniform float uOpacity; varying vec3 vColor; varying float vGain;
      void main() {
        vec2 d = gl_PointCoord - 0.5; float r = length(d) * 2.0;
        if (r > 1.0) discard;
        float core = smoothstep(0.45, 0.0, r);
        float halo = pow(1.0 - r, 2.4) * 0.4;
        gl_FragColor = vec4(vColor * (core * 1.25 + halo) * vGain, (core + halo) * uOpacity);
      }`,
  });
  const p = new THREE.Points(g, m);
  p.frustumCulled = false;
  return p;
}

/** Keep the points' screen size right when the canvas or pixel ratio changes. */
export function scalePoints(view, ...materials) {
  view.onResize((w, h, pr) => {
    const k = (h * pr * 0.5) / Math.tan(THREE.MathUtils.degToRad(view.camera.fov) / 2);
    for (const m of materials) m.uniforms.uScale.value = k;
  });
}

/** A line strip with light travelling from its start to its end. `dist` runs 0…1 along the line. */
export function flowLine(points, { color = '#65d8ee', speed = 0.6, opacity = 0.8, width = 0.004, dashes = 3, glow = 1.4, closed = false } = {}) {
  const curve = new THREE.CatmullRomCurve3(points, closed);
  const geo = new THREE.TubeGeometry(curve, Math.max(8, points.length * 6), width, 6, closed);
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(color) }, uSpeed: { value: speed }, uOpacity: { value: opacity },
      uDashes: { value: dashes }, uGlow: { value: glow } },
    vertexShader: /* glsl */`varying float vD; void main() { vD = uv.x; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */`
      uniform float uTime, uSpeed, uOpacity, uDashes, uGlow; uniform vec3 uColor; varying float vD;
      void main() {
        float f = fract(vD * uDashes - uTime * uSpeed);
        float pulse = pow(smoothstep(0.0, 0.85, f) * smoothstep(1.0, 0.85, f), 1.5);
        float base = 0.22;
        gl_FragColor = vec4(uColor * (base + pulse * uGlow), (base + pulse) * uOpacity);
      }`,
  });
  const mesh = new THREE.Mesh(geo, m);
  mesh.userData.curve = curve;
  return mesh;
}

/** Crisp text on a sprite (canvas texture). `height` is the sprite's world height. */
export function textSprite(text, { color = '#e9efe9', size = 44, height = 0.12, weight = 600, font = 'Onest, Inter, system-ui, sans-serif',
  bg = null, pad = 16, mono = false, screen = false } = {}) {
  const c = document.createElement('canvas'); const g = c.getContext('2d');
  const f = `${weight} ${size}px ${mono ? 'JetBrains Mono, ui-monospace, monospace' : font}`;
  g.font = f; const w = Math.ceil(g.measureText(text).width) + pad * 2, h = Math.ceil(size * 1.5);
  c.width = w; c.height = h;
  g.font = f; g.textBaseline = 'middle';
  if (bg) { g.fillStyle = bg; roundRect(g, 0, 0, w, h, h / 2); g.fill(); }
  g.fillStyle = color; g.fillText(text, pad, h / 2 + 1);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  // screen: constant on-screen size (height = fraction of the view's height), like an HTML label
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: !screen, toneMapped: false, sizeAttenuation: !screen }));
  s.scale.set((height * w) / h, height, 1);
  s.renderOrder = screen ? 10 : 0;
  return s;
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

let glowTex = null;
export function glowTexture() {
  if (glowTex) return glowTex;
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.18, 'rgba(255,255,255,0.75)'); r.addColorStop(0.45, 'rgba(255,255,255,0.18)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  glowTex = new THREE.CanvasTexture(c);
  return glowTex;
}

/** A soft glowing sprite (HDR colour: values > 1 bloom). */
export function glowSprite(color, scale = 0.2, intensity = 2) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(color).multiplyScalar(intensity),
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  s.scale.set(scale, scale, 1);
  return s;
}

/** A ring drawn in the XZ plane (a thin torus), additive. */
export function ring(radius, { color = '#65d8ee', tube = 0.004, opacity = 0.6, intensity = 1.5, arc = Math.PI * 2 } = {}) {
  const m = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 6, 160, arc),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending }));
  m.rotation.x = Math.PI / 2;
  return m;
}

export const PALETTE = {
  gold: new THREE.Color('#e8c477'), cyan: new THREE.Color('#5fe1f5'), teal: new THREE.Color('#2fd4b0'), emerald: new THREE.Color('#39e0a6'),
  blue: new THREE.Color('#78aef0'), violet: new THREE.Color('#9b8cff'), grey: new THREE.Color('#6f8279'), white: new THREE.Color('#f2f6f2'),
};
