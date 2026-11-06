// Lady Justice on the left of the scene. Loads src/assets/models/lady-justice.glb when it exists (bundled by
// Vite); otherwise builds a simple gold stand-in figure. Clicking her opens the scales inspector (HTML button
// placed over her). The scales in the stand-in tilt by the real answer score.
import * as THREE from 'three';
import { gsap } from 'gsap';

// Vite turns this into {} when the file is absent — no network request, no 404 in the console.
const MODELS = import.meta.glob('../assets/models/lady-justice.glb', { query: '?url', import: 'default', eager: true });
const MODEL_URL = Object.values(MODELS)[0] || null;

const HEIGHT = 2.35;

export class Justice {
  constructor(scene, { envMap = null, reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.group = new THREE.Group();
    this.group.position.set(-3.15, 0, -1.05);
    this.home = this.group.position.clone();
    this.group.rotation.y = 0.5;
    scene.add(this.group);
    this.gold = new THREE.MeshStandardMaterial({ color: '#c9a24d', metalness: 1, roughness: 0.3, envMap, envMapIntensity: 1.25 });
    this.dark = new THREE.MeshStandardMaterial({ color: '#1a211e', metalness: 0.3, roughness: 0.55, envMap, envMapIntensity: 0.4 });
    this.tilt = 0;
    this.source = 'stand-in';
    this.pedestal();
    if (MODEL_URL) this.loadModel(MODEL_URL).catch(() => this.standIn());
    else this.standIn();
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
    const k = (HEIGHT - this.base) / (size.y || 1);
    model.scale.setScalar(k);
    box.setFromObject(model);
    model.position.y += this.base - box.min.y;
    const center = box.getCenter(new THREE.Vector3());
    model.position.x -= center.x; model.position.z -= center.z;
    model.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = o.receiveShadow = true;
        // the sculpt carries grey cavity shading as vertex colours: gold × that shading looks like cast bronze
        const m = this.gold.clone();
        m.vertexColors = !!o.geometry.attributes.color;
        m.color.set(m.vertexColors ? '#e9c26a' : '#c9a24d');
        o.material = m;
      }
      const name = (o.name || '').toLowerCase();
      if (name.includes('beam')) this.beam = o;
    });
    this.group.add(model);
    this.figure = model;
    this.source = 'model';
  }

  /** A simple gold figure: robe, torso, head with blindfold, raised arm with the scales. */
  standIn() {
    const f = new THREE.Group();
    const y0 = this.base;
    const robeProfile = [[0.0, 0], [0.3, 0], [0.31, 0.05], [0.27, 0.3], [0.21, 0.65], [0.16, 0.95], [0.14, 1.12], [0.0, 1.14]]
      .map(([x, y]) => new THREE.Vector2(x, y));
    const robe = new THREE.Mesh(new THREE.LatheGeometry(robeProfile, 48), this.gold);
    robe.position.y = y0;
    // folds: a few thin vertical ridges on the robe
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2;
      const ridge = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.03, 0.95, 6), this.gold);
      ridge.position.set(Math.cos(a) * 0.23, y0 + 0.5, Math.sin(a) * 0.23);
      ridge.rotation.z = Math.cos(a) * 0.12; ridge.rotation.x = -Math.sin(a) * 0.12;
      f.add(ridge);
    }
    const chest = new THREE.Mesh(new THREE.SphereGeometry(0.17, 32, 20), this.gold);
    chest.scale.set(1, 1.25, 0.8); chest.position.y = y0 + 1.22;
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.055, 0.1, 16), this.gold);
    neck.position.y = y0 + 1.43;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 32, 24), this.gold);
    head.scale.set(0.92, 1.08, 0.98); head.position.y = y0 + 1.56;
    const bun = new THREE.Mesh(new THREE.SphereGeometry(0.06, 20, 16), this.gold);
    bun.position.set(0, y0 + 1.6, -0.09);
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.014, 8, 40), this.dark);
    band.position.set(0, y0 + 1.57, 0.005); band.rotation.x = Math.PI / 2 - 0.15;
    f.add(robe, chest, neck, head, bun, band);

    // right arm (viewer's left) resting, left arm raised holding the scales
    const limb = (from, to, r) => {
      const v = new THREE.Vector3().subVectors(to, from);
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.8, r, v.length(), 12), this.gold);
      m.position.copy(from).addScaledVector(v, 0.5);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.clone().normalize());
      f.add(m); return m;
    };
    const sh = new THREE.Vector3(0.16, y0 + 1.33, 0), elbow = new THREE.Vector3(0.36, y0 + 1.55, 0.05), hand = new THREE.Vector3(0.44, y0 + 1.88, 0.06);
    limb(sh, elbow, 0.045); limb(elbow, hand, 0.04);
    const sh2 = new THREE.Vector3(-0.16, y0 + 1.33, 0), el2 = new THREE.Vector3(-0.24, y0 + 1.05, 0.08), h2 = new THREE.Vector3(-0.16, y0 + 0.86, 0.14);
    limb(sh2, el2, 0.045); limb(el2, h2, 0.04);

    // the scales: rod from the hand, a pivoting beam, two pans on cords
    const rodTop = hand.clone().add(new THREE.Vector3(0, 0.22, 0));
    limb(hand, rodTop, 0.012);
    this.beam = new THREE.Group();
    this.beam.position.copy(rodTop);
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.74, 10), this.gold);
    bar.rotation.z = Math.PI / 2;
    const knob = new THREE.Mesh(new THREE.SphereGeometry(0.025, 16, 12), this.gold);
    this.beam.add(bar, knob);
    this.pans = [-1, 1].map((side) => {
      const hang = new THREE.Group();
      hang.position.set(side * 0.36, 0, 0);
      const cords = new THREE.Group();
      for (let k = 0; k < 3; k++) {
        const a = (k / 3) * Math.PI * 2;
        const end = new THREE.Vector3(Math.cos(a) * 0.1, -0.36, Math.sin(a) * 0.1);
        const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), end]);
        cords.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: '#e0c27a' })));
      }
      const pan = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.08, 0.03, 32, 1, true), this.gold);
      pan.material = this.gold.clone(); pan.material.side = THREE.DoubleSide;
      pan.position.y = -0.37;
      hang.add(cords, pan);
      this.beam.add(hang);
      return hang;
    });
    f.add(this.beam);
    f.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    this.group.add(f);
    this.figure = f;
    this.source = 'stand-in';
  }

  /** Answer mode brings her a little closer to the book so she stays in the frame. */
  setMode(answer, duration = 1.2) {
    const x = answer ? -2.72 : this.home.x, z = answer ? -0.75 : this.home.z;
    gsap.to(this.group.position, { x, z, duration: this.reduced ? 0 : duration, ease: 'power2.inOut' });
  }

  /** score 0…100 (or null): balanced at 100, tilted towards the answer pan when evidence is missing. */
  setScore(score) {
    const target = score == null ? 0 : -((100 - Math.max(0, Math.min(100, score))) / 100) * 0.32;
    gsap.to(this, { tilt: target, duration: this.reduced ? 0 : 1.6, ease: 'elastic.out(1, 0.5)' });
  }

  update(dt, t) {
    if (!this.beam) return;
    const sway = this.reduced ? 0 : Math.sin(t * 0.9) * 0.012;
    this.beam.rotation.z = this.tilt + sway;
    if (this.pans) for (const p of this.pans) p.rotation.z = -this.beam.rotation.z;   // pans hang straight down
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
