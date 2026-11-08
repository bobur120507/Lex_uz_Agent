// A small, self-contained Three.js view for inspectors (its own renderer, disposed when the panel closes).
// v3 (8-noyabr): HDR pipeline — ACES tone mapping, multisampled render target, UnrealBloom (glow comes from
// bright colours, not from textures), a radial background, slow auto-orbit that stops when the user takes over.
// ?quality=low or reduced motion: no bloom, no auto-orbit.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { REDUCED } from '../config.js';

export const LOW = REDUCED || (typeof location !== 'undefined' && /[?&]quality=low/.test(location.search));

export function mini3d(container, {
  height = 420, camera = [0, 0, 6], target = [0, 0, 0], fov = 45,
  bloom = { strength: 0.85, radius: 0.6, threshold: 0.18 }, autoRotate = 0.35, background = ['#10201c', '#04090a'],
} = {}) {
  container.style.height = `${height}px`;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = backgroundTexture(...background);
  const cam = new THREE.PerspectiveCamera(fov, 1, 0.01, 400);
  cam.position.set(...camera);
  const controls = new OrbitControls(cam, renderer.domElement);
  controls.target.set(...target);
  controls.enableDamping = !REDUCED;
  controls.dampingFactor = 0.08;
  controls.minDistance = 0.4; controls.maxDistance = 80;
  controls.autoRotate = !LOW && autoRotate > 0;
  controls.autoRotateSpeed = autoRotate;
  controls.addEventListener('start', () => { controls.autoRotate = false; });
  const home = { pos: cam.position.clone(), target: controls.target.clone() };

  let composer = null, bloomPass = null;
  if (bloom && !LOW) {
    const rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
    composer = new EffectComposer(renderer, rt);
    composer.addPass(new RenderPass(scene, cam));
    bloomPass = new UnrealBloomPass(new THREE.Vector2(256, 256), bloom.strength, bloom.radius, bloom.threshold);
    composer.addPass(bloomPass);
    composer.addPass(new OutputPass());
  }
  const ticks = [];
  let alive = true, raf = 0;
  const size = () => {
    const w = container.clientWidth || 600, hgt = container.clientHeight || height;
    renderer.setSize(w, hgt, false);
    composer?.setPixelRatio(renderer.getPixelRatio());
    composer?.setSize(w, hgt);
    renderer.domElement.style.width = '100%'; renderer.domElement.style.height = '100%';
    cam.aspect = w / hgt; cam.updateProjectionMatrix();
    for (const fn of resizers) fn(w, hgt, renderer.getPixelRatio());
  };
  const resizers = [];
  const ro = new ResizeObserver(size); ro.observe(container);
  const clock = new THREE.Clock();
  let compiled = false;
  const loop = () => {
    if (!alive) return;
    raf = requestAnimationFrame(loop);
    if (document.hidden) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    controls.update();
    for (const fn of ticks) fn(dt, clock.elapsedTime);
    // first frame: compile the scene's shaders in parallel (KHR_parallel_shader_compile) instead of freezing the
    // page for ~1 s while the window opens (GPU run 8-noyabr: one 9 fps second); the view appears when ready
    if (compiled !== true) {
      if (compiled === false && renderer.compileAsync && renderer.extensions.has('KHR_parallel_shader_compile')) {
        compiled = renderer.compileAsync(scene, cam).catch(() => {}).then(() => { compiled = true; });
        return;
      }
      if (compiled !== false) return;
    }
    if (composer) composer.render(); else renderer.render(scene, cam);
  };
  size();
  raf = requestAnimationFrame(loop);              // first frame after the caller has built its scene
  return {
    THREE, scene, camera: cam, controls, renderer, el: renderer.domElement, bloom: bloomPass,
    get pixelRatio() { return renderer.getPixelRatio(); },
    onTick: (fn) => ticks.push(fn),
    onResize: (fn) => { resizers.push(fn); fn(container.clientWidth || 600, container.clientHeight || height, renderer.getPixelRatio()); },
    reset() { controls.autoRotate = !LOW && autoRotate > 0; this.fly(home.pos.toArray(), home.target.toArray()); },
    fly(pos, look, dur = 0.9) {
      const p0 = cam.position.clone(), t0 = controls.target.clone(), p1 = new THREE.Vector3(...pos), t1 = new THREE.Vector3(...look);
      if (REDUCED) { cam.position.copy(p1); controls.target.copy(t1); return; }
      const start = performance.now();
      const step = () => {
        const k = Math.min(1, (performance.now() - start) / (dur * 1000)), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        cam.position.lerpVectors(p0, p1, e); controls.target.lerpVectors(t0, t1, e);
        if (k < 1 && alive) requestAnimationFrame(step);
      };
      step();
    },
    pick(event, objects, threshold = 0.06) {
      const r = renderer.domElement.getBoundingClientRect();
      const m = new THREE.Vector2(((event.clientX - r.left) / r.width) * 2 - 1, -((event.clientY - r.top) / r.height) * 2 + 1);
      const ray = new THREE.Raycaster(); ray.params.Points.threshold = threshold; ray.setFromCamera(m, cam);
      return ray.intersectObjects(objects, false)[0] || null;
    },
    dispose() {
      alive = false; cancelAnimationFrame(raf); ro.disconnect(); controls.dispose();
      scene.traverse((o) => { o.geometry?.dispose?.(); const m = o.material; (Array.isArray(m) ? m : m ? [m] : []).forEach((x) => { x.map?.dispose?.(); x.dispose?.(); }); });
      scene.background?.dispose?.();
      composer?.renderTarget1?.dispose(); composer?.renderTarget2?.dispose(); bloomPass?.dispose?.();
      renderer.dispose(); renderer.domElement.remove();
    },
  };
}

function backgroundTexture(inner, outer) {
  const c = document.createElement('canvas'); c.width = c.height = 512;
  const g = c.getContext('2d'); const r = g.createRadialGradient(256, 220, 10, 256, 256, 380);
  r.addColorStop(0, inner); r.addColorStop(1, outer);
  g.fillStyle = r; g.fillRect(0, 0, 512, 512);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function dotTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.45, 'rgba(255,255,255,0.85)'); r.addColorStop(0.7, 'rgba(255,255,255,0.15)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}
