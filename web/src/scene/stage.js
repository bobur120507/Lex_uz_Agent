// Renderer, camera rig, warm "desk lamp" light, the table and floating dust.
import * as THREE from 'three';
import { gsap } from 'gsap';

export function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGL2RenderingContext && c.getContext('webgl2'));
  } catch { return false; }
}

// Camera shots. "side" moves the book left so the answer panel fits on the right.
const SHOTS = {
  idle:   { pos: [0.1, 3.5, 5.2], look: [0, 0.3, 0.05] },
  search: { pos: [0, 4.0, 3.0], look: [0, 0, 0.25] },
  side:   { pos: [1.3, 4.7, 3.7], look: [1.3, 0, 0.3] },
  closed: { pos: [0.1, 3.5, 5.2], look: [0, 0.3, 0.05] },
};
const MOBILE = {
  idle:   { pos: [0, 3.6, 5.6], look: [-0.18, 0, 0.5] },
  search: { pos: [0, 7.4, 4.4], look: [0, 0, 0.55] },
  side:   { pos: [0, 7.6, 3.2], look: [0, 0, 1.55] },
  closed: { pos: [0, 3.7, 5.8], look: [0, 0, 0.5] },
};

export class Stage {
  constructor(canvas, { reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#0b0f0d');
    this.scene.fog = new THREE.Fog('#0b0f0d', 6, 13);

    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);
    this.look = new THREE.Vector3();
    this.shotName = 'idle';

    // lights
    this.scene.add(new THREE.HemisphereLight('#bcd7c9', '#0b0f0d', 0.35));
    const lamp = new THREE.SpotLight('#ffd9a0', 38, 0, 0.5, 0.65, 1.6);
    lamp.position.set(-1.6, 4.6, 1.9);
    lamp.target.position.set(0.1, 0, 0);
    lamp.castShadow = true;
    lamp.shadow.mapSize.set(1024, 1024);
    lamp.shadow.bias = -0.0004;
    lamp.shadow.normalBias = 0.02;
    this.scene.add(lamp, lamp.target);
    const rim = new THREE.DirectionalLight('#6fd3a1', 0.35);
    rim.position.set(3, 1.2, -3);
    this.scene.add(rim);

    // table
    const table = new THREE.Mesh(
      new THREE.CircleGeometry(7, 64).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: '#141b17', roughness: 0.85, metalness: 0.05 }),
    );
    table.receiveShadow = true;
    this.scene.add(table);

    this.dust = this.makeDust();
    this.scene.add(this.dust);

    this.clock = new THREE.Clock();
    this.onFrame = [];
    this.frames = 0; this.fpsT = 0; this.fps = 0;
    this.running = true;
    document.addEventListener('visibilitychange', () => { this.running = !document.hidden; if (this.running) this.loop(); });
    window.addEventListener('resize', () => this.resize());
    this.resize();
    this.setShot('idle', 0);
    this.loop();
  }

  makeDust() {
    const n = this.reduced ? 0 : 260;
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) pos.set([(Math.random() - 0.5) * 6, Math.random() * 3, (Math.random() - 0.5) * 4], i * 3);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const m = new THREE.PointsMaterial({ color: '#ffe6c2', size: 0.012, transparent: true, opacity: 0.55, depthWrite: false });
    return new THREE.Points(g, m);
  }

  get mobile() { return this.width / this.height < 0.85; }

  setShot(name, duration = 1.1) {
    this.shotName = name;
    const s = (this.mobile ? MOBILE : SHOTS)[name];
    const d = this.reduced ? 0 : duration;
    gsap.to(this.camera.position, { x: s.pos[0], y: s.pos[1], z: s.pos[2], duration: d, ease: 'power2.inOut' });
    gsap.to(this.look, { x: s.look[0], y: s.look[1], z: s.look[2], duration: d, ease: 'power2.inOut' });
  }

  resize() {
    this.width = window.innerWidth; this.height = window.innerHeight;
    this.renderer.setSize(this.width, this.height, false);
    this.camera.aspect = this.width / this.height;
    this.camera.fov = this.mobile ? 48 : 38;
    this.camera.updateProjectionMatrix();
    if (this.shotName) this.setShot(this.shotName, 0.4);
  }

  loop() {
    if (!this.running) return;
    requestAnimationFrame(() => this.loop());
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.elapsedTime;
    if (this.dust.geometry.attributes.position.count) {
      this.dust.rotation.y = t * 0.012;
      this.dust.position.y = Math.sin(t * 0.2) * 0.05;
    }
    for (const fn of this.onFrame) fn(dt, t);
    this.camera.lookAt(this.look);
    this.renderer.render(this.scene, this.camera);
    this.frames++; this.fpsT += dt;
    if (this.fpsT >= 1) {
      this.fps = Math.round(this.frames / this.fpsT);
      this.frames = 0; this.fpsT = 0;
      window.__moddaFps = this.fps;
      this.onFps?.(this.fps);
    }
  }
}
