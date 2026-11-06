// Renderer, camera shots, lights, the reading desk with its glowing platform, dust, and a small
// environment map so gold (cover foil, the statue) reflects light. One renderer for the whole page.
import * as THREE from 'three';
import { gsap } from 'gsap';

export function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGL2RenderingContext && c.getContext('webgl2'));
  } catch { return false; }
}

// look: where the camera aims; the book is at the origin, the graph above it, the statue on the left
const SHOTS = {
  idle:     { pos: [0, 2.35, 6.9], look: [0, 1.22, 0] },
  research: { pos: [0, 2.45, 6.5], look: [0, 1.25, 0] },
  answer:   { pos: [0, 3.25, 5.3], look: [0, 0.78, -0.3] },
};
const TABLET = {
  idle:     { pos: [0, 2.6, 8.6], look: [0, 1.5, 0] },
  research: { pos: [0, 2.6, 8.4], look: [0, 1.5, 0] },
  answer:   { pos: [0, 4.2, 6.0], look: [0, 0.9, -0.3] },
};
const MOBILE = {
  idle:     { pos: [0, 2.9, 11.0], look: [0, 1.75, 0] },
  research: { pos: [0, 2.9, 10.8], look: [0, 1.75, 0] },
  answer:   { pos: [0, 5.0, 6.6], look: [0, 1.0, -0.3] },
};

function envMap(renderer) {
  const pm = new THREE.PMREMGenerator(renderer);
  const s = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(10, 6, 10), new THREE.MeshBasicMaterial({ color: '#0c1512', side: THREE.BackSide }));
  s.add(room);
  const panel = (color, w, h, pos, rot = [0, 0, 0]) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
    m.position.set(...pos); m.rotation.set(...rot); s.add(m);
  };
  panel('#ffcf8a', 3, 1.4, [-3, 2.4, 2], [0, Math.PI / 3, 0]);        // warm desk lamp
  panel('#6fe0d0', 2, 3, [4.6, 1.5, -2], [0, -Math.PI / 2, 0]);       // cool window
  panel('#f7f2e6', 4, 0.5, [0, 2.9, 0], [Math.PI / 2, 0, 0]);         // ceiling strip
  const tex = pm.fromScene(s, 0.04).texture;
  pm.dispose();
  return tex;
}

export class Stage {
  constructor(canvas, { reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.scene = new THREE.Scene();
    this.env = envMap(this.renderer);
    this.camera = new THREE.PerspectiveCamera(36, 1, 0.1, 60);
    this.look = new THREE.Vector3();
    this.shotName = 'idle';

    this.scene.add(new THREE.HemisphereLight('#bcd7c9', '#0b0f0d', 0.32));
    const lamp = new THREE.SpotLight('#ffd9a0', 42, 0, 0.55, 0.7, 1.5);
    lamp.position.set(-2.2, 5.2, 2.6);
    lamp.target.position.set(0.1, 0, 0);
    lamp.castShadow = true;
    lamp.shadow.mapSize.set(1024, 1024);
    lamp.shadow.bias = -0.0004; lamp.shadow.normalBias = 0.02;
    this.scene.add(lamp, lamp.target);
    const statueLight = new THREE.SpotLight('#ffd49a', 30, 9, 0.45, 0.8, 1.4);
    statueLight.position.set(-1.2, 4.6, 2.4);
    statueLight.target.position.set(-3.1, 1.2, -0.9);
    this.scene.add(statueLight, statueLight.target);
    const rim = new THREE.DirectionalLight('#6fd3c1', 0.5);
    rim.position.set(3, 1.6, -3);
    this.scene.add(rim);

    // desk: a large dark disc that fades into the background
    const deskTex = (() => {
      const c = document.createElement('canvas'); c.width = c.height = 512;
      const g = c.getContext('2d');
      const r = g.createRadialGradient(256, 256, 30, 256, 256, 256);
      r.addColorStop(0, 'rgba(32,40,36,1)'); r.addColorStop(0.55, 'rgba(20,27,24,0.95)'); r.addColorStop(1, 'rgba(10,14,13,0)');
      g.fillStyle = r; g.fillRect(0, 0, 512, 512);
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
    })();
    const desk = new THREE.Mesh(new THREE.CircleGeometry(9, 64).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ map: deskTex, transparent: true, roughness: 0.75, metalness: 0.1, envMap: this.env, envMapIntensity: 0.25 }));
    desk.receiveShadow = true;
    this.scene.add(desk);
    this.platform = this.makePlatform();
    this.scene.add(this.platform);
    this.dust = this.makeDust();
    this.scene.add(this.dust);

    this.clock = new THREE.Clock();
    this.onFrame = [];
    this.frames = 0; this.fpsT = 0; this.fps = 0;
    this.running = true;
    document.addEventListener('visibilitychange', () => { this.running = !document.hidden; if (this.running) { this.clock.getDelta(); this.loop(); } });
    window.addEventListener('resize', () => this.resize());
    this.resize();
    this.setShot('idle', 0);
    this.loop();
  }

  /** Concentric glowing rings under the book (cyan / emerald), like the reference image. */
  makePlatform() {
    const g = new THREE.Group();
    const ring = (r0, r1, color, opacity) => {
      const m = new THREE.Mesh(new THREE.RingGeometry(r0, r1, 128).rotateX(-Math.PI / 2),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false }));
      m.position.y = 0.004; g.add(m); return m;
    };
    this.rings = [ring(1.95, 1.99, '#65d8ee', 0.55), ring(2.18, 2.2, '#39d6a0', 0.35), ring(2.5, 2.515, '#d6b66d', 0.22), ring(1.65, 1.66, '#65d8ee', 0.25)];
    const glow = (() => {
      const c = document.createElement('canvas'); c.width = c.height = 256;
      const x = c.getContext('2d'); const r = x.createRadialGradient(128, 128, 40, 128, 128, 128);
      r.addColorStop(0, 'rgba(101,216,238,0.0)'); r.addColorStop(0.72, 'rgba(101,216,238,0.22)'); r.addColorStop(0.8, 'rgba(57,214,160,0.08)'); r.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = r; x.fillRect(0, 0, 256, 256);
      return new THREE.CanvasTexture(c);
    })();
    const halo = new THREE.Mesh(new THREE.PlaneGeometry(6, 6).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ map: glow, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.position.y = 0.003; g.add(halo);
    this.halo = halo;
    return g;
  }

  makeDust() {
    const n = this.reduced ? 0 : 220;
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) pos.set([(Math.random() - 0.5) * 9, Math.random() * 4, (Math.random() - 0.5) * 5], i * 3);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color: '#ffe6c2', size: 0.014, transparent: true, opacity: 0.5, depthWrite: false }));
  }

  get layoutKind() {
    if (this.width < 768) return 'mobile';
    if (this.width < 1200 || this.width / this.height < 1.3) return 'tablet';
    return 'desktop';
  }

  setShot(name, duration = 1.1) {
    this.shotName = name;
    const set = { desktop: SHOTS, tablet: TABLET, mobile: MOBILE }[this.layoutKind];
    const s = set[name];
    const d = this.reduced ? 0 : duration;
    gsap.to(this.camera.position, { x: s.pos[0], y: s.pos[1], z: s.pos[2], duration: d, ease: 'power2.inOut', overwrite: true });
    gsap.to(this.look, { x: s.look[0], y: s.look[1], z: s.look[2], duration: d, ease: 'power2.inOut', overwrite: true });
  }

  setActivity(level) {                                   // 0 idle … 1 busy: platform glow
    gsap.to(this.halo.material, { opacity: 0.55 + level * 0.45, duration: 0.6 });
  }

  resize() {
    this.width = window.innerWidth; this.height = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, this.width < 768 ? 1.25 : 1.75);
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(this.width, this.height, false);
    this.camera.aspect = this.width / this.height;
    this.camera.fov = this.layoutKind === 'mobile' ? 44 : 36;
    this.camera.updateProjectionMatrix();
    if (this.shotName) this.setShot(this.shotName, 0.3);
    this.onResize?.();
  }

  /** World → CSS pixel position (and whether it is in front of the camera). */
  project(v, out = { x: 0, y: 0, visible: false }) {
    const p = v.clone().project(this.camera);
    out.x = (p.x * 0.5 + 0.5) * this.width;
    out.y = (-p.y * 0.5 + 0.5) * this.height;
    out.visible = p.z < 1 && p.z > -1;
    return out;
  }

  loop() {
    if (!this.running) return;
    requestAnimationFrame(() => this.loop());
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.elapsedTime;
    if (this.dust.geometry.attributes.position.count) {
      this.dust.rotation.y = t * 0.01;
      this.dust.position.y = Math.sin(t * 0.2) * 0.05;
    }
    if (!this.reduced) this.rings.forEach((r, i) => { r.material.opacity = (i === 0 ? 0.5 : 0.28) + Math.sin(t * 0.8 + i) * 0.06; });
    this.camera.lookAt(this.look);
    this.camera.updateMatrixWorld();
    for (const fn of this.onFrame) fn(dt, t);
    this.renderer.render(this.scene, this.camera);
    this.frames++; this.fpsT += dt;
    if (this.fpsT >= 1) { this.fps = Math.round(this.frames / this.fpsT); this.frames = 0; this.fpsT = 0; window.__moddaFps = this.fps; }
  }
}
