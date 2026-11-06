// A small, self-contained Three.js view for inspectors (its own renderer, disposed when the panel closes).
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { REDUCED } from '../config.js';

export function mini3d(container, { height = 420, camera = [0, 0, 6], target = [0, 0, 0], fov = 45 } = {}) {
  container.style.height = `${height}px`;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  container.append(renderer.domElement);
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(fov, 1, 0.01, 200);
  cam.position.set(...camera);
  const controls = new OrbitControls(cam, renderer.domElement);
  controls.target.set(...target);
  controls.enableDamping = !REDUCED;
  controls.dampingFactor = 0.08;
  controls.minDistance = 0.5; controls.maxDistance = 60;
  const home = { pos: cam.position.clone(), target: controls.target.clone() };
  const ticks = [];
  let alive = true, raf = 0;
  const size = () => {
    const w = container.clientWidth || 600, hgt = container.clientHeight || height;
    renderer.setSize(w, hgt, false);
    renderer.domElement.style.width = '100%'; renderer.domElement.style.height = '100%';
    cam.aspect = w / hgt; cam.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(size); ro.observe(container); size();
  const clock = new THREE.Clock();
  const loop = () => {
    if (!alive) return;
    raf = requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05);
    controls.update();
    for (const fn of ticks) fn(dt, clock.elapsedTime);
    renderer.render(scene, cam);
  };
  loop();
  return {
    THREE, scene, camera: cam, controls, renderer, el: renderer.domElement,
    onTick: (fn) => ticks.push(fn),
    reset() { cam.position.copy(home.pos); controls.target.copy(home.target); controls.update(); },
    fly(pos, look, dur = 0.8) {
      const p0 = cam.position.clone(), t0 = controls.target.clone(), p1 = new THREE.Vector3(...pos), t1 = new THREE.Vector3(...look);
      if (REDUCED) { cam.position.copy(p1); controls.target.copy(t1); return; }
      const start = performance.now();
      const step = () => {
        const k = Math.min(1, (performance.now() - start) / (dur * 1000)), e = 1 - Math.pow(1 - k, 3);
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
      renderer.dispose(); renderer.domElement.remove();
    },
  };
}

export function dotTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.45, 'rgba(255,255,255,0.85)'); r.addColorStop(0.7, 'rgba(255,255,255,0.15)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}
