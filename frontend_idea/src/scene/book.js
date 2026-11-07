// The Modda book: covers, two page stacks, a pool of bendable turning sheets and the two open pages.
// The spine lies along z at x = 0; pages turn from +x (right) to −x (left). Adapted from web/src/scene/book.js.
import * as THREE from 'three';
import { gsap } from 'gsap';
import { blankPage, coverTexture, clothTexture, paperEdge, mirrored, sweepPages, PX } from './pages.js';

export const W = 1.45, H = 1.95;
const SEG = 28, C = 0.045, OVER = 0.05, TOTAL = 260, PT = 0.0011, POOL = 8, LIFT = 0.0015;

function sheetGeometry() {
  const cols = SEG + 1;
  const pos = new Float32Array(cols * 2 * 3), uv = new Float32Array(cols * 2 * 2), idx = [];
  for (let i = 0; i < cols; i++) {
    const u = i / SEG;
    pos.set([u * W, 0, -H / 2], i * 6); pos.set([u * W, 0, H / 2], i * 6 + 3);
    uv.set([u, 1], i * 4); uv.set([u, 0], i * 4 + 2);
    if (i < SEG) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
}
/** p: 0 flat on the right … 1 flat on the left; curl makes the outer edge trail. */
function bend(geom, p, curl, y0, y1) {
  const pos = geom.attributes.position.array;
  const ds = W / SEG, lift = Math.sin(p * Math.PI), base = y0 + (y1 - y0) * p + LIFT;
  let x = 0, y = 0;
  for (let i = 0; i <= SEG; i++) {
    pos[i * 6] = x; pos[i * 6 + 1] = base + y; pos[i * 6 + 3] = x; pos[i * 6 + 4] = base + y;
    const a = p * Math.PI - curl * lift * Math.pow((i + 0.5) / SEG, 1.3) * 1.25;
    x += ds * Math.cos(a); y += ds * Math.sin(a);
  }
  geom.attributes.position.needsUpdate = true;
  geom.computeVertexNormals();
}

export class Book {
  constructor(scene, { reducedMotion = false, envMap = null } = {}) {
    this.reduced = reducedMotion;
    this.group = new THREE.Group();
    scene.add(this.group);
    this.nRight = TOTAL; this.nLeft = 0;
    this.isOpen = false; this.riffling = false; this.flipsInAir = 0; this.time = 0;
    this.hits = { left: [], right: [] };

    const coverMat = new THREE.MeshStandardMaterial({ map: clothTexture(), roughness: 0.7 });
    const coverTop = new THREE.MeshStandardMaterial({ map: coverTexture((c) => { this.coverCanvas = c; }), roughness: 0.5, metalness: 0.18, envMap, envMapIntensity: 0.6 });
    const inside = new THREE.MeshStandardMaterial({ color: '#e7e1d0', roughness: 0.9 });
    const edge = paperEdge(); edge.repeat.set(1, 24);
    const edgeMat = new THREE.MeshStandardMaterial({ map: edge, roughness: 0.95, color: '#f2ecdc' });
    const paperTop = new THREE.MeshStandardMaterial({ color: '#f3efe4', roughness: 0.92 });

    const cw = W + OVER, ch = H + OVER * 2;
    this.back = new THREE.Mesh(new THREE.BoxGeometry(cw, C, ch), [coverMat, coverMat, inside, coverMat, coverMat, coverMat]);
    this.back.position.set(cw / 2, C / 2, 0);
    this.hinge = new THREE.Group();
    this.front = new THREE.Mesh(new THREE.BoxGeometry(cw, C, ch), [coverMat, coverMat, coverTop, inside, coverMat, coverMat]);
    this.front.position.set(cw / 2, C / 2, 0);
    this.hinge.add(this.front);
    this.spine = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1, ch),
      [coverMat, new THREE.MeshStandardMaterial({ map: clothTexture({ spine: true }), roughness: 0.6 }), coverMat, coverMat, coverMat, coverMat]);
    const stackMats = [edgeMat, edgeMat, paperTop, paperTop, edgeMat, edgeMat];
    this.rightStack = new THREE.Mesh(new THREE.BoxGeometry(W - 0.01, 1, H), stackMats);
    this.leftStack = new THREE.Mesh(new THREE.BoxGeometry(W - 0.01, 1, H), stackMats.map((m) => m.clone()));

    this.blankR = [1, 2, 3, 4].map((s) => blankPage(s, 'right'));
    this.blankL = [5, 6, 7, 8].map((s) => blankPage(s, 'left'));
    const plane = () => new THREE.PlaneGeometry(W - 0.01, H).rotateX(-Math.PI / 2);
    this.rightPage = new THREE.Mesh(plane(), new THREE.MeshStandardMaterial({ map: this.blankR[0], roughness: 0.9 }));
    this.leftPage = new THREE.Mesh(plane(), new THREE.MeshStandardMaterial({ map: this.blankL[0], roughness: 0.9 }));
    this.rightPage.name = 'page-right'; this.leftPage.name = 'page-left';
    for (const m of [this.back, this.front, this.spine, this.rightStack, this.leftStack]) { m.castShadow = true; m.receiveShadow = true; }
    this.rightPage.receiveShadow = this.leftPage.receiveShadow = true;
    this.group.add(this.back, this.hinge, this.spine, this.rightStack, this.leftStack, this.rightPage, this.leftPage);

    this.pool = [];
    for (let i = 0; i < POOL; i++) {
      const geo = sheetGeometry();
      const f = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: this.blankR[i % 4], roughness: 0.9, side: THREE.FrontSide }));
      const b = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: mirrored(this.blankL[i % 4]), roughness: 0.9, side: THREE.BackSide }));
      f.castShadow = b.castShadow = true; f.visible = b.visible = false;
      this.group.add(f, b);
      this.pool.push({ geo, f, b, busy: false });
    }
    this.blankBacks = this.blankL.map((t) => mirrored(t));
    this.state = { cover: 0, open: 0 };
    this.layout();
  }

  rightTop() { return C + this.nRight * PT; }
  leftTop() { return C + this.nLeft * PT; }

  layout() {
    const hr = Math.max(this.nRight * PT, 0.0005), hl = Math.max(this.nLeft * PT, 0.0005);
    this.rightStack.scale.y = hr; this.rightStack.position.set(W / 2, C + hr / 2, 0);
    this.leftStack.scale.y = hl; this.leftStack.position.set(-W / 2, C + hl / 2, 0);
    this.leftStack.visible = this.state.cover > 0.98;
    this.rightPage.position.set(W / 2, this.rightTop() + 0.0006, 0);
    this.leftPage.position.set(-W / 2, this.leftTop() + 0.0006, 0);
    this.leftPage.visible = this.state.cover > 0.98 && this.nLeft > 2;
    const a = this.state.cover * Math.PI, closedY = this.rightTop();
    this.hinge.rotation.z = a;
    this.hinge.position.set(0, closedY + (C - closedY) * this.state.cover, 0);
    const spineH = (this.rightTop() + C) * (1 - this.state.cover) + C * this.state.cover;
    this.spine.scale.y = spineH; this.spine.position.set(-0.03, spineH / 2, 0);
    this.group.position.x = -(W / 2) * (1 - this.state.open);
  }

  update(dt) {
    this.time += dt;
    if (!this.isOpen && !this.reduced) {
      this.group.rotation.y = Math.sin(this.time * 0.35) * 0.05;
      this.group.position.y = Math.sin(this.time * 0.8) * 0.015;
    } else {
      this.group.rotation.y += (0 - this.group.rotation.y) * Math.min(1, dt * 4);
      this.group.position.y += (0 - this.group.position.y) * Math.min(1, dt * 4);
    }
  }

  dur(sec) { return this.reduced ? 0.01 : sec; }

  open() {
    if (this.isOpen) return this.opening ?? Promise.resolve();
    this.isOpen = true;
    this.opening = new Promise((resolve) => gsap.to(this.state, {
      cover: 1, open: 1, duration: this.dur(1.0), ease: 'power2.inOut',
      onUpdate: () => this.layout(), onComplete: () => { this.opening = null; resolve(); },
    }));
    return this.opening;
  }

  /** Open and riffle while the backend works; an early answer simply stops the riffle (no waiting). */
  beginSearch() {
    this.wantRiffle = true;
    this.setPages(this.blankL[0], this.blankR[0]);
    this.hits = { left: [], right: [] };
    this.open().then(() => { if (this.wantRiffle) this.startRiffle(); });
  }

  close() {
    this.wantRiffle = false; this.stopRiffle();
    this.hits = { left: [], right: [] };
    return new Promise((resolve) => {
      const finish = () => gsap.to(this, {
        nLeft: 0, nRight: TOTAL, duration: this.dur(0.35), onUpdate: () => this.layout(),
        onComplete: () => gsap.to(this.state, {
          cover: 0, open: 0, duration: this.dur(0.9), ease: 'power2.inOut',
          onUpdate: () => this.layout(), onComplete: () => { this.isOpen = false; resolve(); },
        }),
      });
      if (this.flipsInAir) gsap.delayedCall(this.dur(0.5), finish); else finish();
    });
  }

  setPages(left, right) {
    if (left) { this.leftPage.material.map = left; this.leftPage.material.needsUpdate = true; }
    if (right) { this.rightPage.material.map = right; this.rightPage.material.needsUpdate = true; }
  }

  /** One sheet turn. dir +1 right → left. faces: {front, back} textures (back already mirrored). */
  flip(dir = 1, duration = 0.5, faces = null, { count = true } = {}) {
    const slot = this.pool.find((p) => !p.busy);
    if (!slot) return Promise.resolve();
    const n = count ? 1 + Math.floor(Math.random() * 3) : 0;
    if (dir > 0 && this.nRight - n < 6) return Promise.resolve();
    if (dir < 0 && (count ? this.nLeft - n < 0 : this.nLeft < 4)) return Promise.resolve();
    slot.busy = true; this.flipsInAir++;
    slot.f.material.map = faces?.front ?? this.blankR[Math.floor(Math.random() * 4)];
    slot.b.material.map = faces?.back ?? this.blankBacks[Math.floor(Math.random() * 4)];
    slot.f.material.needsUpdate = slot.b.material.needsUpdate = true;
    if (dir > 0) this.nRight -= n; else this.nLeft -= n;
    this.layout();
    const st = { p: dir > 0 ? 0 : 1 };
    slot.f.visible = slot.b.visible = true;
    bend(slot.geo, st.p, dir * 0.9, this.rightTop(), this.leftTop());
    return new Promise((resolve) => gsap.to(st, {
      p: dir > 0 ? 1 : 0, duration: this.dur(duration), ease: 'power1.inOut',
      onUpdate: () => bend(slot.geo, st.p, dir * 0.9, this.rightTop(), this.leftTop()),
      onComplete: () => {
        if (dir > 0) this.nLeft += n; else this.nRight += n;
        slot.f.visible = slot.b.visible = false; slot.busy = false; this.flipsInAir--;
        this.layout(); resolve();
      },
    }));
  }

  startRiffle() {
    if (this.reduced) return;
    this.riffling = true;
    let d = this.nRight > this.nLeft + 30 ? 1 : -1;
    const tick = () => {
      if (!this.riffling) return;
      if (d > 0 && this.nRight < 40) d = -1;
      if (d < 0 && this.nLeft < 40) d = 1;
      this.flip(d, 0.55);
      this.riffleCall = gsap.delayedCall(this.dur(0.09), tick);
    };
    tick();
  }
  stopRiffle() { this.riffling = false; this.riffleCall?.kill(); }

  async settle() {
    const wait = (s) => new Promise((r) => gsap.delayedCall(this.dur(s), r));
    while (this.flipsInAir) await wait(0.05);
  }

  /** Stop searching, glide to a place in the book (0…1) and turn the last sheet onto the given spread. */
  async landOn(position, spread) {
    this.wantRiffle = false; this.stopRiffle();
    await this.open();
    await this.settle();
    const want = Math.round(20 + Math.min(1, Math.max(0, position)) * (TOTAL - 60));
    const dir = want >= this.nLeft ? 1 : -1;
    const glide = new Promise((resolve) => gsap.to(this, {
      nLeft: want, nRight: TOTAL - want, duration: this.dur(0.7), ease: 'power1.inOut',
      onUpdate: () => this.layout(), onComplete: resolve,
    }));
    for (let k = 0; k < 5 && !this.reduced; k++) { this.flip(dir, 0.3, null, { count: false }); await new Promise((r) => setTimeout(r, 90)); }
    await glide; await this.settle();
    await this.turnTo(spread, 1, 1.0);
  }

  /** Turn one sheet so the open pages become `spread` ({left, right, hits}). */
  async turnTo(spread, dir = 1, duration = 0.85) {
    await this.settle();
    const curL = this.leftPage.material.map, curR = this.rightPage.material.map;
    this.hits = { left: [], right: [] };
    if (dir > 0) {
      this.setPages(null, spread.right);
      await this.flip(1, duration, { front: curR, back: mirrored(spread.left) });
      this.setPages(spread.left, null);
    } else {
      this.setPages(spread.left, null);
      await this.flip(-1, duration, { front: spread.right, back: mirrored(curL) });
      this.setPages(null, spread.right);
    }
    this.hits = { left: spread.leftHits || [], right: spread.rightHits || [] };
    this.layout();
    this.sweep();
  }

  /** Replace a page in place (no turn) — used while the answer is being written. */
  replace(side, texture, hits = []) {
    if (side === 'left') this.setPages(texture, null); else this.setPages(null, texture);
    this.hits[side] = hits;
    this.sweep();
  }

  /** Free the GPU memory of result pages the book no longer shows (they are 2048 × 2752 each). */
  sweep() {
    const inUse = new Set([this.leftPage.material.map, this.rightPage.material.map]);
    for (const p of this.pool) if (p.busy) { inUse.add(p.f.material.map); inUse.add(p.b.material.map); }
    sweepPages(inUse);
  }

  /** Raycast the open pages: {side, x, y, hit} in page-canvas pixels. */
  pick(raycaster) {
    if (!this.isOpen) return null;
    const res = raycaster.intersectObjects([this.leftPage, this.rightPage], false)[0];
    if (!res || !res.uv) return null;
    const side = res.object === this.leftPage ? 'left' : 'right';
    const x = res.uv.x * PX.w, y = (1 - res.uv.y) * PX.h;
    const hit = (this.hits[side] || []).find((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) || null;
    return { side, x, y, hit };
  }

  /** The book's footprint corners (world), for placing the HTML controls. */
  anchor() { return new THREE.Vector3(0, 0, H / 2 + 0.15); }
}
