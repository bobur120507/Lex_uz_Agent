// Lady Justice on the left of the scene (src/assets/models/lady-justice.glb, or a simple gold stand-in).
// Her own scales show the answer's score: one pan carries the score medallion, the other the official Lex.uz
// logo in 3-D (extruded from the SVG Bobur provided); the pans weigh by the real `scoring.completed` value
// (balanced at 100). Each pan burns with a flame-like glow exactly as wide as the pan, and embers rise from it.
// Clicking her brings the camera to her upper body (main.js → focusJustice()).
import * as THREE from 'three';
import { gsap } from 'gsap';

// Vite turns these into {} when a file is absent — no network request, no 404 in the console.
const MODELS = import.meta.glob('../assets/models/lady-justice.glb', { query: '?url', import: 'default', eager: true });
const MODEL_URL = Object.values(MODELS)[0] || null;
// the official Lex.uz logo (any of these names; an .svg becomes a real 3-D logo, an image goes on a medallion)
const LOGOS = import.meta.glob('../assets/models/{lex_uz,lexuz,lex-uz,lexuz-logo}.{svg,png,webp,jpg}', { query: '?url', import: 'default', eager: true });
const LOGO_URL = Object.entries(LOGOS).sort(([a], [b]) => Number(!a.endsWith('.svg')) - Number(!b.endsWith('.svg')))[0]?.[1] || null;

const HEIGHT = 2.35;
const SIZE = 1.21;                                   // 2 × 10 % bigger than the first version (1.1²)
const MAX_DROP = 0.026;                              // pan travel (model units) when the score is 0

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return { tex: t, canvas: c };
}
const glowTex = () => canvasTex(64, 64, (g) => {
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,240,200,1)'); r.addColorStop(0.35, 'rgba(255,200,110,0.5)'); r.addColorStop(1, 'rgba(255,170,60,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
}).tex;

// A flame-shaped glow: tongues of light rising from the pan, as wide as the pan, flickering with noise.
const FLAME_VERT = `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FLAME_FRAG = `
uniform float uTime; uniform float uShine; uniform float uSeed;
varying vec2 vUv;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void main() {
  float x = vUv.x * 2.0 - 1.0, y = vUv.y;
  float t = uTime;
  float n = fbm(vec2(x * 2.4 + uSeed, y * 2.2 - t * 1.7));
  float n2 = fbm(vec2(x * 4.1 - uSeed, y * 3.4 - t * 2.6));
  float xs = x + (n - 0.5) * 0.55 * y;                           // tongues lean and sway as they rise
  float width = 1.0 - smoothstep(0.62, 0.92, abs(xs));           // no wider than the pan
  float h = 0.28 + 0.62 * n2 * (1.0 - 0.35 * abs(x));            // ragged tips, taller in the middle
  float body = 1.0 - smoothstep(h - 0.32, h, y);
  float base = smoothstep(0.02, 0.26, y) * (1.0 - smoothstep(0.86, 1.0, y));   // soft foot: no hard edge under the dish
  float f = clamp(width * body * base * (0.55 + 0.75 * n), 0.0, 1.0);
  f = pow(f, 1.35);
  vec3 col = mix(vec3(1.0, 0.42, 0.06), vec3(1.0, 0.78, 0.32), smoothstep(0.15, 0.6, f));
  col = mix(col, vec3(1.0, 0.97, 0.86), smoothstep(0.7, 1.0, f));
  gl_FragColor = vec4(col, f * uShine);
}`;
function flameMesh(seed) {
  const mat = new THREE.ShaderMaterial({
    vertexShader: FLAME_VERT, fragmentShader: FLAME_FRAG, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uTime: { value: 0 }, uShine: { value: 0 }, uSeed: { value: seed } },
  });
  const geo = new THREE.PlaneGeometry(1, 1); geo.translate(0, 0.5, 0);     // origin at the bottom edge
  const m = new THREE.Mesh(geo, mat); m.renderOrder = 5; m.frustumCulled = false;
  return m;
}

/** The Lex.uz SVG logo as a solid: extruded paths, blue gradient from the SVG, centred, 1 unit wide. */
async function logo3D(url, envMap) {
  const { SVGLoader } = await import('three/examples/jsm/loaders/SVGLoader.js');
  // gradients (fill:url(#…)) are not supported by SVGLoader; the gradient is applied below as vertex colours
  const text = (await (await fetch(url)).text()).replace(/url\(#[^)]*\)/g, '#0064A9');
  const data = new SVGLoader().parse(text);
  const shapes = data.paths.flatMap((p) => SVGLoader.createShapes(p));
  if (!shapes.length) throw new Error('logo: no shapes');
  const box0 = new THREE.Box2();
  for (const sh of shapes) for (const v of sh.getPoints(4)) box0.expandByPoint(v);
  const size = box0.getSize(new THREE.Vector2());
  const geo = new THREE.ExtrudeGeometry(shapes, {
    depth: size.y * 0.09, bevelEnabled: true, bevelThickness: size.y * 0.018, bevelSize: size.y * 0.012, bevelSegments: 2, curveSegments: 6,
  });
  // SVG y points down: mirror, then restore the triangle winding so the faces stay outward
  geo.scale(1, -1, 1);
  const pos = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < pos.count; i += 3) {
    for (const a of [pos, uv].filter(Boolean)) {
      for (let k = 0; k < a.itemSize; k++) { const t = a.array[(i + 1) * a.itemSize + k]; a.array[(i + 1) * a.itemSize + k] = a.array[(i + 2) * a.itemSize + k]; a.array[(i + 2) * a.itemSize + k] = t; }
    }
  }
  geo.computeVertexNormals();
  geo.computeBoundingBox();
  const bb = geo.boundingBox, c = bb.getCenter(new THREE.Vector3());
  geo.translate(-c.x, -bb.min.y, -c.z);                                   // bottom-centre at the origin
  const w = bb.max.x - bb.min.x, hgt = bb.max.y - bb.min.y;
  geo.scale(1 / w, 1 / w, 1 / w);
  // the logo's own gradient: #0064A9 at the bottom → #68ACD7 at the top
  const lo = new THREE.Color('#0064A9'), hi = new THREE.Color('#68ACD7'), col = new Float32Array(pos.count * 3), tmp = new THREE.Color();
  for (let i = 0; i < pos.count; i++) { tmp.copy(lo).lerp(hi, Math.min(1, Math.max(0, pos.getY(i) / (hgt / w)))); tmp.toArray(col, i * 3); }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.15, roughness: 0.32, envMap, envMapIntensity: 0.9,
    emissive: new THREE.Color('#1f6fb8'), emissiveIntensity: 0 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.userData.aspect = hgt / w;
  return mesh;
}

export class Justice {
  constructor(scene, { envMap = null, reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.position.set(-3.15, 0, -1.05);
    this.group.rotation.y = 0.5;
    this.group.scale.setScalar(SIZE);
    this.home = this.group.position.clone();
    scene.add(this.group);
    this.gold = new THREE.MeshStandardMaterial({ color: '#c9a24d', metalness: 1, roughness: 0.3, envMap, envMapIntensity: 1.25 });
    this.dark = new THREE.MeshStandardMaterial({ color: '#1a211e', metalness: 0.3, roughness: 0.55, envMap, envMapIntensity: 0.4 });
    this.weigh = 0;                                  // −1 … 1: positive = the answer pan is lower
    this.shine = 0;                                  // 0 … 1: glow of the scales
    this.score = null;
    this.source = 'stand-in';
    this.pans = [];                                  // [{obj, base: Vector3, side}] — side: 'answer' | 'lexuz'
    this.pedestal();
    this.makeItems();
    this.ready = (MODEL_URL ? this.loadModel(MODEL_URL).catch(() => this.standIn()) : Promise.resolve(this.standIn()))
      .then(() => this.assignSides());
  }

  pedestal() {
    const p = new THREE.Group();
    const a = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.5, 0.18, 48), this.dark);
    a.position.y = 0.09;
    const b = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.43, 0.06, 48), this.gold);
    b.position.y = 0.21;
    const c = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.4, 0.14, 48), this.dark);
    c.position.y = 0.31;
    for (const m of [a, b, c]) { m.castShadow = m.receiveShadow = true; p.add(m); }
    this.group.add(p);
    this.base = 0.38;
  }

  async loadModel(url) {
    const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
    const gltf = await new GLTFLoader().loadAsync(url);
    const model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    model.scale.setScalar((HEIGHT - this.base) / (size.y || 1));
    box.setFromObject(model);
    model.position.y += this.base - box.min.y;
    const center = box.getCenter(new THREE.Vector3());
    model.position.x -= center.x; model.position.z -= center.z;
    const pans = [];
    model.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = o.name === 'body'; o.receiveShadow = true;
      // the sculpt carries grey cavity shading as vertex colours: gold × that shading looks like cast bronze
      const m = this.gold.clone();
      m.vertexColors = !!o.geometry.attributes.color;
      m.color.set(m.vertexColors ? '#e9c26a' : '#c9a24d');
      if (/^pan_/.test(o.name)) { m.emissive = new THREE.Color('#6b4a12'); m.emissiveIntensity = 0; pans.push(o); }
      o.material = m;
    });
    this.group.add(model);
    this.figure = model;
    this.source = 'model';
    this.pans = pans.map((obj) => ({ obj, base: obj.position.clone(), kind: 'move' }));
  }

  /** A simple gold figure (used only when the .glb is missing): robe, head, raised arm with scales. */
  standIn() {
    const f = new THREE.Group();
    const y0 = this.base;
    const robe = new THREE.Mesh(new THREE.LatheGeometry([[0, 0], [0.3, 0], [0.31, 0.05], [0.27, 0.3], [0.21, 0.65], [0.16, 0.95], [0.14, 1.12], [0, 1.14]]
      .map(([x, y]) => new THREE.Vector2(x, y)), 48), this.gold);
    robe.position.y = y0;
    const chest = new THREE.Mesh(new THREE.SphereGeometry(0.17, 32, 20), this.gold);
    chest.scale.set(1, 1.25, 0.8); chest.position.y = y0 + 1.22;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 32, 24), this.gold);
    head.position.y = y0 + 1.56;
    f.add(robe, chest, head);
    const limb = (from, to, r) => {
      const v = new THREE.Vector3().subVectors(to, from);
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.8, r, v.length(), 12), this.gold);
      m.position.copy(from).addScaledVector(v, 0.5);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.clone().normalize());
      f.add(m);
    };
    const sh = new THREE.Vector3(0.16, y0 + 1.33, 0), el = new THREE.Vector3(0.36, y0 + 1.55, 0.05), hand = new THREE.Vector3(0.44, y0 + 1.88, 0.06);
    limb(sh, el, 0.045); limb(el, hand, 0.04);
    const top = hand.clone().add(new THREE.Vector3(0, 0.22, 0));
    limb(hand, top, 0.012);
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.74, 10), this.gold);
    bar.rotation.z = Math.PI / 2; bar.position.copy(top);
    f.add(bar);
    for (const side of [-1, 1]) {
      const pan = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.08, 0.03, 32), this.gold.clone());
      pan.material.emissive = new THREE.Color('#6b4a12'); pan.material.emissiveIntensity = 0;
      pan.position.set(top.x + side * 0.36, top.y - 0.37, top.z);
      f.add(pan);
      this.pans.push({ obj: pan, base: pan.position.clone(), kind: 'move' });
    }
    f.traverse((o) => { if (o.isMesh) o.castShadow = o.receiveShadow = true; });
    this.group.add(f);
    this.figure = f;
    this.source = 'stand-in';
  }

  /** Left pan (as seen from the front) carries the answer's score, the right one the Lex.uz logo. */
  assignSides() {
    if (this.pans.length < 2) return;
    this.group.updateMatrixWorld(true);
    const right = new THREE.Vector3(Math.cos(this.group.rotation.y), 0, -Math.sin(this.group.rotation.y));
    const x = (p) => new THREE.Box3().setFromObject(p.obj).getCenter(new THREE.Vector3()).dot(right);
    this.pans.sort((a, b) => x(a) - x(b));
    this.pans[0].side = 'answer'; this.pans[1].side = 'lexuz';
    // pan diameter in group units (the dish is round, so its box is the same at any turn of the group)
    for (const p of this.pans) {
      const sz = new THREE.Box3().setFromObject(p.obj).getSize(new THREE.Vector3());
      p.d = Math.max(sz.x, sz.z) / SIZE || 0.2;
    }
    this.placeLogo();
  }

  /** The two objects lying on the pans, the flames and the embers around them. */
  makeItems() {
    const glow = glowTex();
    // score medallion: a gold disc with the number, facing the viewer
    this.scoreFace = canvasTex(512, 512, () => {});
    this.drawScore(null);
    const disc = (map, rim) => {
      const g = new THREE.Group();
      const edge = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.08, 64), new THREE.MeshStandardMaterial({ color: rim, metalness: 1, roughness: 0.25, envMap: this.gold.envMap, envMapIntensity: 1.4 }));
      edge.rotation.x = Math.PI / 2;
      const face = new THREE.Mesh(new THREE.CircleGeometry(0.46, 64), new THREE.MeshBasicMaterial({ map, transparent: true }));
      face.position.z = 0.041;
      const back = face.clone(); back.rotation.y = Math.PI; back.position.z = -0.041;
      g.add(edge, face, back);
      g.userData.aspect = 1;
      return g;
    };
    this.scoreItem = disc(this.scoreFace.tex, '#d6b66d');
    // Lex.uz: until (or unless) the 3-D logo is ready, a medallion with the wordmark or the logo image
    this.logoFace = canvasTex(512, 512, (g, w, h) => this.drawLexuz(g, w, h, null));
    this.logoItem = disc(this.logoFace.tex, '#e8c878');
    this.logoMode = 'medallion';
    if (LOGO_URL && /\.svg(\?|$)/i.test(LOGO_URL)) {
      logo3D(LOGO_URL, this.gold.envMap).then((mesh) => {
        const g = new THREE.Group(); g.add(mesh); g.userData.aspect = mesh.userData.aspect; g.visible = this.logoItem.visible;
        this.group.remove(this.logoItem); this.logoItem = g; this.logoMode = '3d'; this.logoMesh = mesh; this.group.add(g);
        this.placeLogo();
      }).catch((err) => { console.warn('Lex.uz logo (3-D) failed, using the image:', err.message); this.logoImage(); });
    } else if (LOGO_URL) this.logoImage();
    // one flame per pan + rising embers
    this.flames = [0, 1].map((i) => { const f = flameMesh(i * 7.31 + 1.7); this.group.add(f); return f; });
    this.flamesFront = [0, 1].map((i) => { const f = flameMesh(i * 3.17 + 9.4); f.renderOrder = 6; this.group.add(f); return f; });   // low flames licking the dish in front
    for (const it of [this.scoreItem, this.logoItem]) { it.visible = false; this.group.add(it); }
    const n = this.reduced ? 0 : 36;                   // per pan
    this.embers = Array.from({ length: n * 2 }, (_, i) => ({ pan: i % 2, a: Math.random() * Math.PI * 2, r: Math.sqrt(Math.random()) * 0.42,
      v: 0.35 + Math.random() * 0.5, ph: Math.random(), wob: Math.random() * 6 }));
    const geo = new THREE.BufferGeometry()
      .setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 6), 3))
      .setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 6), 3));
    this.sparks = new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.03, map: glow, vertexColors: true, transparent: true, opacity: 0,
      depthWrite: false, blending: THREE.AdditiveBlending }));
    this.sparks.frustumCulled = false;
    this.group.add(this.sparks);
    this.light = new THREE.PointLight('#ffb35a', 0, 3.2, 1.6);
    this.group.add(this.light);
  }

  logoImage() {
    const img = new Image();
    img.onload = () => { this.drawLexuz(this.logoFace.canvas.getContext('2d'), 512, 512, img); this.logoFace.tex.needsUpdate = true; };
    img.src = LOGO_URL;
  }

  /** Item sizes follow the pans: the medallion is 80 % of the dish, the 3-D logo a little wider than it. */
  placeLogo() {
    if (!this.pans[1]?.d) return;
    for (const [p, it] of [[this.pans[0], this.scoreItem], [this.pans[1], this.logoItem]]) {
      it.userData.k = it === this.logoItem && this.logoMode === '3d' ? p.d * 1.06 : p.d * 0.66;
    }
  }

  drawScore(score) {
    const g = this.scoreFace.canvas.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, 512, 512); g.setTransform(2, 0, 0, 2, 0, 0);   // drawn in 256 units, 2× sharp
    const bg = g.createRadialGradient(128, 110, 10, 128, 128, 128);
    bg.addColorStop(0, '#2a2312'); bg.addColorStop(1, '#120f08');
    g.fillStyle = bg; g.beginPath(); g.arc(128, 128, 126, 0, Math.PI * 2); g.fill();
    g.strokeStyle = '#d6b66d'; g.lineWidth = 6; g.beginPath(); g.arc(128, 128, 112, 0, Math.PI * 2); g.stroke();
    g.textAlign = 'center'; g.fillStyle = '#f3d68c';
    g.shadowColor = 'rgba(255,210,120,0.9)'; g.shadowBlur = 18;
    g.font = '600 104px "Literata", Georgia, serif';
    g.fillText(score == null ? '—' : String(Math.round(score)), 128, 150);
    g.shadowBlur = 0; g.fillStyle = '#c8b27a';
    g.font = '500 26px "Onest", system-ui, sans-serif';
    g.fillText('JAVOB · /100', 128, 196);
    this.scoreFace.tex.needsUpdate = true;
  }

  drawLexuz(g, w, h, img) {
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, w, h); g.setTransform(w / 256, 0, 0, h / 256, 0, 0);
    if (img) {                                                     // the official logo on an ivory face
      const bg = g.createRadialGradient(128, 110, 10, 128, 128, 128);
      bg.addColorStop(0, '#fbf8ef'); bg.addColorStop(1, '#e6dfcc');
      g.fillStyle = bg; g.beginPath(); g.arc(128, 128, 126, 0, Math.PI * 2); g.fill();
      g.strokeStyle = '#e0bd63'; g.lineWidth = 6; g.beginPath(); g.arc(128, 128, 112, 0, Math.PI * 2); g.stroke();
      const iw = img.naturalWidth || img.width || 1, ih = img.naturalHeight || img.height || 1;
      const k = Math.min(184 / iw, 150 / ih);
      g.drawImage(img, 128 - (iw * k) / 2, 128 - (ih * k) / 2, iw * k, ih * k);
      return;
    }
    const bg = g.createRadialGradient(128, 110, 10, 128, 128, 128);
    bg.addColorStop(0, '#1d2d50'); bg.addColorStop(1, '#0c1530');
    g.fillStyle = bg; g.beginPath(); g.arc(128, 128, 126, 0, Math.PI * 2); g.fill();
    g.strokeStyle = '#e0bd63'; g.lineWidth = 6; g.beginPath(); g.arc(128, 128, 112, 0, Math.PI * 2); g.stroke();
    g.textAlign = 'center'; g.fillStyle = '#f0d58e';
    g.font = '700 52px "Onest", system-ui, sans-serif';
    g.fillText('LEX.UZ', 128, 140);
    g.font = '500 24px "Onest", system-ui, sans-serif'; g.fillStyle = '#c9b67e';
    g.fillText('MANBA', 128, 184);
  }

  /** score 0…100 or null. Balanced at 100; the answer pan sinks by how much is not backed by Lex.uz. */
  setScore(score) {
    this.score = score;
    this.drawScore(score);
    const target = score == null ? 0 : (100 - Math.max(0, Math.min(100, score))) / 100;
    gsap.to(this, { weigh: target, duration: this.reduced ? 0 : 2.2, ease: 'elastic.out(1, 0.45)' });
    gsap.to(this, { shine: score == null ? 0 : 0.6, duration: 1 });
    for (const it of [this.scoreItem, this.logoItem]) it.visible = score != null;
  }

  /** Focus mode (statue in the centre): the scales shine brightest. */
  setFocus(on) { gsap.to(this, { shine: on ? 1 : this.score == null ? 0 : 0.6, duration: 0.8 }); }

  /** Answer mode brings her a little closer to the book so she stays in the frame. */
  setMode(answer, duration = 1.2) {
    const x = answer ? -2.72 : this.home.x, z = answer ? -0.75 : this.home.z;
    gsap.to(this.group.position, { x, z, duration: this.reduced ? 0 : duration, ease: 'power2.inOut' });
  }

  update(dt, t) {
    if (this.pans.length < 2 || !this.pans[0].side) return;
    const sway = this.reduced ? 0 : Math.sin(t * 0.9) * 0.08;
    const w = Math.max(-1, Math.min(1, this.weigh + sway * (this.score == null ? 1 : 0.15)));
    for (const p of this.pans) {
      const dir = p.side === 'answer' ? -1 : 1;
      p.obj.position.y = p.base.y + dir * w * (this.source === 'model' ? MAX_DROP : MAX_DROP * 2.2);   // model pans live in model units
      p.obj.material.emissiveIntensity = this.shine * (0.9 + Math.sin(t * 7.3 + dir) * 0.08 + Math.sin(t * 2.2) * 0.12);
    }
    const inv = new THREE.Matrix4().copy(this.group.matrixWorld).invert();
    const camLocal = this.camera ? this.camera.position.clone().applyMatrix4(inv) : new THREE.Vector3(Math.sin(-0.5) * 5, 1.5, Math.cos(-0.5) * 5);
    const dishes = [];
    [[this.pans[0], this.scoreItem, this.flames[0], this.flamesFront[0]], [this.pans[1], this.logoItem, this.flames[1], this.flamesFront[1]]].forEach(([p, item, flame, front]) => {
      // the dish is the lowest part of the pan object (its chains go up): things stand on the dish
      const box = new THREE.Box3().setFromObject(p.obj);
      const wc = box.getCenter(new THREE.Vector3());
      const c = new THREE.Vector3(wc.x, box.min.y, wc.z).applyMatrix4(inv);
      const d = p.d || 0.2;
      c.y += d * 0.1;
      dishes.push({ c, d });
      const k = item.userData.k || d * 0.8;
      const lift = item.userData.aspect === 1 ? k * 0.52 : 0;            // the medallion stands on its rim, the logo on its base
      item.position.set(c.x, c.y + lift, c.z);
      item.scale.setScalar(k);
      const toCam = new THREE.Vector3(camLocal.x - c.x, 0, camLocal.z - c.z).normalize();
      const facing = Math.atan2(toCam.x, toCam.z);
      item.rotation.y = facing + (this.reduced ? 0 : Math.sin(t * 0.7 + (item === this.logoItem ? 1.3 : 0)) * 0.14);   // face the viewer
      if (this.logoMesh) this.logoMesh.material.emissiveIntensity = this.shine * 0.35;
      // the flame: a camera-facing sheet exactly as wide as the dish, standing just behind the item on it
      flame.position.set(c.x - toCam.x * d * 0.22, c.y - d * 0.16, c.z - toCam.z * d * 0.22);
      flame.rotation.set(0, facing, 0);
      flame.scale.set(d * 1.08, d * 1.9, 1);
      front.position.set(c.x + toCam.x * d * 0.3, c.y - d * 0.08, c.z + toCam.z * d * 0.3);
      front.rotation.set(0, facing, 0);
      front.scale.set(d * 1.08, d * 0.62, 1);
      for (const [fl, k] of [[flame, 1], [front, 0.65]]) {
        fl.material.uniforms.uTime.value = this.reduced ? 0 : t;
        fl.material.uniforms.uShine.value = (0.25 + this.shine * 0.85) * k;
        fl.visible = this.shine > 0.01;
      }
    });
    // embers rise from the dishes and fade
    const pa = this.sparks.geometry.attributes.position.array, ca = this.sparks.geometry.attributes.color.array;
    this.embers.forEach((e, i) => {
      const { c, d } = dishes[e.pan];
      const life = (t * e.v * 0.55 + e.ph) % 1;
      const r = e.r * d * (1 - life * 0.45);
      pa[i * 3] = c.x + Math.cos(e.a + life * 2) * r + Math.sin(t * 3 + e.wob) * d * 0.04;
      pa[i * 3 + 1] = c.y + life * d * 2.1;
      pa[i * 3 + 2] = c.z + Math.sin(e.a + life * 2) * r;
      const k = Math.pow(1 - life, 1.6);
      ca[i * 3] = k; ca[i * 3 + 1] = k * (0.62 + 0.3 * (1 - life)); ca[i * 3 + 2] = k * 0.25;
    });
    this.sparks.geometry.attributes.position.needsUpdate = true;
    this.sparks.geometry.attributes.color.needsUpdate = true;
    this.sparks.material.opacity = this.shine;
    const mid = dishes[0].c.clone().add(dishes[1].c).multiplyScalar(0.5);
    this.light.position.set(mid.x, mid.y + 0.25, mid.z + 0.3);
    this.light.intensity = this.shine * (5 + Math.sin(t * 9.1) * 0.6 + Math.sin(t * 4.3) * 0.4);
    this.scalesCenter = mid;
  }

  /** World position of the scales (for the focus camera). */
  focusPoint() {
    const p = this.scalesCenter ? this.scalesCenter.clone() : new THREE.Vector3(0, 1.3, 0);
    return this.group.localToWorld(p);
  }

  /** Camera that frames her upper body — from just under the scale pans to the top of the scales — in the free
   *  part of the screen (between the header and the question field), the caption on the right. */
  focusShot(kind = 'desktop') {
    this.group.updateMatrixWorld(true);
    const f = new THREE.Vector3(Math.sin(this.group.rotation.y), 0, Math.cos(this.group.rotation.y));
    const right = new THREE.Vector3(f.z, 0, -f.x);
    const box = this.figure ? new THREE.Box3().setFromObject(this.figure) : new THREE.Box3().setFromObject(this.group);
    const top = box.max.y;
    let low = box.min.y + (top - box.min.y) * 0.45;                      // waist
    for (const p of this.pans) low = Math.min(low, new THREE.Box3().setFromObject(p.obj).min.y - (p.d || 0.2) * SIZE * 0.35);
    const span = (top - low) * 1.06;
    const mid = (top + low) / 2;
    const fov = THREE.MathUtils.degToRad(kind === 'mobile' ? 44 : 36), tan = Math.tan(fov / 2);
    const H = window.innerHeight, W = window.innerWidth, aspect = W / Math.max(1, H);
    // the free band of the screen: header ≈ 76 px on top, question field ≈ 150 px at the bottom (more on phones)
    const topPx = 76, botPx = kind === 'mobile' ? 250 : 150;
    const band = (H - topPx - botPx) / H;                              // share of the height
    const shift = ((botPx - topPx) / 2) / (H / 2);                      // how far the band's centre is above the screen's
    const halfW = Math.max(box.max.x - box.min.x, box.max.z - box.min.z) * 0.55;
    const byH = span / 2 / (tan * band);
    const byW = halfW / (tan * aspect * (kind === 'desktop' ? 0.62 : 0.9));   // desktop: leave the right third to the caption
    const dist = Math.max(byH, byW);
    const look = box.getCenter(new THREE.Vector3());
    look.y = mid - shift * tan * dist;                                  // so the figure sits in the band, not behind the field
    if (kind === 'desktop') look.addScaledVector(right, tan * aspect * dist * 0.2);   // her left of centre
    const pos = look.clone().addScaledVector(f, dist).add(new THREE.Vector3(0, dist * 0.05, 0));
    return { pos: pos.toArray(), look: look.toArray() };
  }

  /** Screen rectangle of the figure (for the HTML hit area). */
  screenBox(stage) {
    const top = this.group.localToWorld(new THREE.Vector3(0.2, HEIGHT + 0.25, 0));
    const bottom = this.group.localToWorld(new THREE.Vector3(0, 0.1, 0));
    const a = stage.project(top), b = stage.project(bottom);
    const h = Math.max(40, b.y - a.y);
    return { x: (a.x + b.x) / 2, y: a.y, w: h * 0.42, h };
  }
}
