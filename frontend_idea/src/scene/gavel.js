// The judge's gavel on the right of the book — the pair to Lady Justice on the left.
// Model: src/assets/models/judges-gavel.glb (Bobur's 3D_Models/judges_gavel.glb, textures shrunk by
// scripts/shrink_textures.py). It strikes its block twice when the answer's verdict arrives (with the scales),
// and again when it is clicked. Without the file: a simple wooden stand-in.
import * as THREE from 'three';
import { gsap } from 'gsap';

const MODELS = import.meta.glob('../assets/models/judges-gavel.glb', { query: '?url', import: 'default', eager: true });
const MODEL_URL = Object.values(MODELS)[0] || null;
const TOP = 0.66;                                    // height of the plinth the gavel lies on
const TURN = Math.PI / 2;
const LENGTH = 1.45;                                 // the gavel’s longest side, in scene units

export class Gavel {
  constructor(scene, { envMap = null, reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.envMap = envMap;
    this.group = new THREE.Group();
    this.group.position.set(3.1, 0, -1.0);           // mirrors the statue (−3.15, 0, −1.05)
    this.group.rotation.y = -0.5;
    this.home = this.group.position.clone();
    scene.add(this.group);
    this.gold = new THREE.MeshStandardMaterial({ color: '#c9a24d', metalness: 1, roughness: 0.3, envMap, envMapIntensity: 1.25 });
    this.dark = new THREE.MeshStandardMaterial({ color: '#1a211e', metalness: 0.3, roughness: 0.55, envMap, envMapIntensity: 0.4 });
    this.angle = 0;                                  // hammer lift (radians)
    this.plinth();
    this.ring = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.24, 64), new THREE.MeshBasicMaterial({
      color: '#ffd27a', transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
    this.ring.rotation.x = -Math.PI / 2;
    this.ring.position.y = TOP + 0.005;
    this.group.add(this.ring);
    this.light = new THREE.PointLight('#ffd9a0', 2.4, 2.8, 1.7);     // a warm key light: dark wood on a dark stage
    this.light.position.set(0.25, TOP + 0.95, 0.55);
    this.group.add(this.light);
    this.ready = (MODEL_URL ? this.loadModel(MODEL_URL).catch((e) => { console.warn('gavel model:', e.message); this.standIn(); })
      : Promise.resolve(this.standIn())).then(() => this.makePivot());
  }

  plinth() {
    const p = new THREE.Group();
    const part = (rt, rb, h, y, mat) => {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, 48), mat);
      m.position.y = y; m.castShadow = m.receiveShadow = true; p.add(m);
    };
    part(0.62, 0.66, 0.16, 0.08, this.dark);          // a low, wide plinth in the statue pedestal's style
    part(0.56, 0.6, 0.05, 0.185, this.gold);
    part(0.5, 0.54, TOP - 0.3, 0.21 + (TOP - 0.3) / 2, this.dark);
    part(0.6, 0.53, 0.06, TOP - 0.06, this.gold);     // gold rim
    part(0.6, 0.6, 0.03, TOP - 0.015, this.dark);     // the top the gavel lies on
    this.group.add(p);
  }

  async loadModel(url) {
    const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
    const gltf = await new GLTFLoader().loadAsync(url);
    const model = gltf.scene;
    model.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = o.receiveShadow = true;
      for (const m of [o.material].flat()) { m.envMap = this.envMap; m.envMapIntensity = 1.1; m.needsUpdate = true; }
    });
    model.rotation.y = TURN;                         // the handle across the view, not pointing at the camera
    model.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(model, true);         // precise: the vertices, not rotated boxes
    const size = box.getSize(new THREE.Vector3());
    model.scale.setScalar(LENGTH / Math.max(size.x, size.y, size.z, 1e-6));
    model.updateMatrixWorld(true);
    box.setFromObject(model, true);
    const c = box.getCenter(new THREE.Vector3());
    model.position.set(-c.x, TOP - box.min.y, -c.z);
    this.group.add(model);
    this.model = model;
    model.traverse((o) => { if (/hammer/i.test(o.name) && !this.hammer && !o.isMesh) this.hammer = o; });
    model.traverse((o) => { if (/wood/i.test(o.name) && !this.block && !o.isMesh) this.block = o; });
    if (!this.hammer) model.traverse((o) => { if (o.isMesh && !this.hammer && /hammer/i.test(o.name)) this.hammer = o; });
  }

  standIn() {
    const wood = new THREE.MeshStandardMaterial({ color: '#5b3a1e', roughness: 0.45, metalness: 0.05, envMap: this.envMap, envMapIntensity: 0.6 });
    const block = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.28, 0.12, 48), wood);
    block.position.y = TOP + 0.06;
    const hammer = new THREE.Group();
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.34, 32), wood);
    head.rotation.z = Math.PI / 2; head.position.set(0, 0.2, 0.1);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.083, 0.083, 0.04, 32), this.gold);
    band.rotation.z = Math.PI / 2; band.position.copy(head.position);
    const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.03, 0.62, 16), wood);
    handle.rotation.x = Math.PI / 2; handle.position.set(0, 0.2, 0.44);
    hammer.add(head, band, handle);
    hammer.position.y = TOP;
    for (const m of [block, head, band, handle]) m.castShadow = m.receiveShadow = true;
    this.group.add(block, hammer);
    this.model = new THREE.Group();
    this.hammer = hammer; this.block = block;
  }

  /** The hammer turns around its handle's end (the hand), so the head lifts and comes down on the block. */
  makePivot() {
    if (!this.hammer) return;
    this.group.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(this.group.matrixWorld).invert();
    const hb = new THREE.Box3().setFromObject(this.hammer).applyMatrix4(inv);
    const bb = this.block ? new THREE.Box3().setFromObject(this.block).applyMatrix4(inv) : null;
    const size = hb.getSize(new THREE.Vector3()), mid = hb.getCenter(new THREE.Vector3());
    const along = size.x >= size.z ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1);
    const half = (size.x >= size.z ? size.x : size.z) / 2;
    const a = mid.clone().addScaledVector(along, half), b = mid.clone().addScaledVector(along, -half);
    const blockC = bb ? bb.getCenter(new THREE.Vector3()) : mid;
    const hand = a.distanceTo(blockC) > b.distanceTo(blockC) ? a : b;   // the end away from the block
    hand.y = mid.y;
    this.pivot = new THREE.Object3D();
    this.pivot.position.copy(hand);
    this.group.add(this.pivot);
    this.pivot.updateMatrixWorld(true);
    this.pivot.attach(this.hammer);
    this.axis = new THREE.Vector3().crossVectors(along, new THREE.Vector3(0, 1, 0)).normalize();
    // pick the turning direction that lifts the head
    const head = mid.clone().sub(hand);
    if (head.clone().applyAxisAngle(this.axis, 0.3).y < head.y) this.axis.negate();
    this.impact = new THREE.Vector3(blockC.x, TOP + 0.005, blockC.z);
    this.ring.position.copy(this.impact);
  }

  /** Two strikes, in the rhythm of the gavel sound (impacts 0.49 s apart): lift, hold, down hard; a half lift,
   *  down again; a small rebound. A ring of light at each impact; `onImpact(n)` fires at impact n (sound). */
  strike() {
    if (!this.pivot || this.reduced) { this.onImpact?.(1); return; }
    gsap.killTweensOf(this, 'angle');
    gsap.timeline()
      .to(this, { angle: 0.5, duration: 0.32, ease: 'power2.out' })
      .to(this, { angle: 0, duration: 0.13, ease: 'power4.in', delay: 0.08, onComplete: () => { this.flash(); this.onImpact?.(1); } })
      .to(this, { angle: 0.3, duration: 0.24, ease: 'power2.out' })
      .to(this, { angle: 0, duration: 0.13, ease: 'power4.in', delay: 0.12, onComplete: () => { this.flash(); this.onImpact?.(2); } })
      .to(this, { angle: 0.07, duration: 0.09, ease: 'power1.out' })
      .to(this, { angle: 0, duration: 0.12, ease: 'power1.in' });
  }

  flash() {
    this.ring.scale.setScalar(0.6);
    this.ring.material.opacity = 0.9;
    gsap.to(this.ring.scale, { x: 2.4, y: 2.4, z: 2.4, duration: 0.7, ease: 'power2.out' });
    gsap.to(this.ring.material, { opacity: 0, duration: 0.7, ease: 'power2.out' });
    gsap.fromTo(this.light, { intensity: 7 }, { intensity: 2.4, duration: 0.8, ease: 'power2.out' });
  }

  setMode(answer, duration = 1.1) {
    const x = answer ? 2.45 : this.home.x, z = answer ? -0.75 : this.home.z, s = answer ? 0.82 : 1;
    const d = this.reduced ? 0 : duration;
    gsap.to(this.group.position, { x, z, duration: d, ease: 'power2.inOut' });
    gsap.to(this.group.scale, { x: s, y: s, z: s, duration: d, ease: 'power2.inOut' });
  }

  update() {
    if (this.pivot) this.pivot.quaternion.setFromAxisAngle(this.axis, this.angle);
  }

  pick(ray) {
    return this.group.visible && ray.intersectObject(this.group, true).length > 0;
  }
}
