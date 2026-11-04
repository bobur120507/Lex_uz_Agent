// The book: covers, two page stacks, a pool of bendable flipping pages, and the two open pages.
// Coordinates: the spine lies along the z axis at x = 0; pages turn from +x (right) to -x (left).
import * as THREE from 'three';
import { gsap } from 'gsap';
import { genericPage, headerPage, articlePage, coverTexture, clothTexture, paperEdge } from './textures.js';

export const W = 1.45;            // page width
export const H = 1.95;            // page height (along z)
const SEG = 28;                   // bend segments across a page
const C = 0.045;                  // cover thickness
const OVER = 0.05;                // cover overhang
const TOTAL = 260;                // virtual pages in the book
const PT = 0.0011;                // thickness of one virtual page
const POOL = 8;                   // flipping pages that can be in the air at once
const LIFT = 0.0015;              // keeps flipping pages above the stacks (no z-fighting)

function pageGeometry() {
  const cols = SEG + 1;
  const pos = new Float32Array(cols * 2 * 3);
  const uv = new Float32Array(cols * 2 * 2);
  const idx = [];
  for (let i = 0; i < cols; i++) {
    const u = i / SEG;
    // row 0: far edge (z = -H/2), row 1: near edge (z = +H/2)
    pos.set([u * W, 0, -H / 2], i * 6);
    pos.set([u * W, 0, H / 2], i * 6 + 3);
    uv.set([u, 1], i * 4);
    uv.set([u, 0], i * 4 + 2);
    if (i < SEG) {
      const a = i * 2, b = a + 1, c = a + 2, d = a + 3;
      idx.push(a, b, c, c, b, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** p: 0 = flat on the right, 1 = flat on the left. curl > 0 makes the outer edge trail behind. */
function bend(geom, p, curl, y0, y1) {
  const pos = geom.attributes.position.array;
  const ds = W / SEG;
  const lift = Math.sin(p * Math.PI);
  const base = y0 + (y1 - y0) * p + LIFT;
  let x = 0, y = 0;
  for (let i = 0; i <= SEG; i++) {
    pos[i * 6] = x; pos[i * 6 + 1] = base + y;
    pos[i * 6 + 3] = x; pos[i * 6 + 4] = base + y;
    const t = (i + 0.5) / SEG;
    const a = p * Math.PI - curl * lift * Math.pow(t, 1.3) * 1.25;
    x += ds * Math.cos(a);
    y += ds * Math.sin(a);
  }
  geom.attributes.position.needsUpdate = true;
  geom.computeVertexNormals();
}

export class Book {
  constructor(scene, { reducedMotion = false } = {}) {
    this.reduced = reducedMotion;
    this.group = new THREE.Group();
    scene.add(this.group);
    this.nRight = TOTAL;
    this.nLeft = 0;
    this.isOpen = false;
    this.riffling = false;
    this.speed = 1;
    this.flipsInAir = 0;
    this.time = 0;

    const leatherFace = coverTexture();
    const leatherPlain = clothTexture();
    const spineTex = clothTexture({ spine: true });
    const edge = paperEdge();
    edge.repeat.set(1, 24);
    const coverMat = new THREE.MeshStandardMaterial({ map: leatherPlain, roughness: 0.7, metalness: 0.0 });
    // gold foil reads as gold only with a little metalness; the cloth stays matte
    const coverTop = new THREE.MeshStandardMaterial({ map: leatherFace, roughness: 0.55, metalness: 0.15 });
    const inside = new THREE.MeshStandardMaterial({ color: '#e7e1d0', roughness: 0.9 });
    const edgeMat = new THREE.MeshStandardMaterial({ map: edge, roughness: 0.95, color: '#f2ecdc' });
    const paperTop = new THREE.MeshStandardMaterial({ color: '#f3efe4', roughness: 0.92 });

    // back cover (under the right stack)
    const cw = W + OVER, ch = H + OVER * 2;
    this.back = new THREE.Mesh(new THREE.BoxGeometry(cw, C, ch), [coverMat, coverMat, inside, coverMat, coverMat, coverMat]);
    this.back.position.set(cw / 2, C / 2, 0);
    // front cover on a hinge at the spine
    this.hinge = new THREE.Group();
    const front = new THREE.Mesh(new THREE.BoxGeometry(cw, C, ch), [coverMat, coverMat, coverTop, inside, coverMat, coverMat]);
    front.position.set(cw / 2, C / 2, 0);
    this.hinge.add(front);
    // spine
    const spineMat = new THREE.MeshStandardMaterial({ map: spineTex, roughness: 0.6 });
    this.spine = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1, ch), [coverMat, spineMat, coverMat, coverMat, coverMat, coverMat]);
    // stacks: BoxGeometry faces [+x, -x, +y, -y, +z, -z]
    const stackMats = [edgeMat, edgeMat, paperTop, paperTop, edgeMat, edgeMat];
    this.rightStack = new THREE.Mesh(new THREE.BoxGeometry(W - 0.01, 1, H), stackMats);
    this.leftStack = new THREE.Mesh(new THREE.BoxGeometry(W - 0.01, 1, H), stackMats.map((m) => m.clone()));

    // the two visible open pages (their textures change when the book lands on an article)
    this.genericR = [1, 2, 3, 4].map((s) => genericPage(s));
    this.genericL = [5, 6, 7, 8].map((s) => genericPage(s, true));
    this.rightPage = new THREE.Mesh(new THREE.PlaneGeometry(W - 0.01, H).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ map: this.genericR[0], roughness: 0.9 }));
    this.leftPage = new THREE.Mesh(new THREE.PlaneGeometry(W - 0.01, H).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ map: this.genericL[0], roughness: 0.9 }));
    // left-page textures are mirrored (made for the back of a turning sheet), so flip this plane's u too
    const luv = this.leftPage.geometry.attributes.uv;
    for (let i = 0; i < luv.count; i++) luv.setX(i, 1 - luv.getX(i));
    luv.needsUpdate = true;

    for (const m of [this.back, front, this.spine, this.rightStack, this.leftStack]) {
      m.castShadow = true; m.receiveShadow = true;
    }
    this.rightPage.receiveShadow = this.leftPage.receiveShadow = true;
    this.group.add(this.back, this.hinge, this.spine, this.rightStack, this.leftStack, this.rightPage, this.leftPage);

    // flipping page pool: front (recto) + back (verso) meshes share one geometry
    this.pool = [];
    for (let i = 0; i < POOL; i++) {
      const geo = pageGeometry();
      const fm = new THREE.MeshStandardMaterial({ map: this.genericR[i % 4], roughness: 0.9, side: THREE.FrontSide });
      const bm = new THREE.MeshStandardMaterial({ map: this.genericL[i % 4], roughness: 0.9, side: THREE.BackSide });
      const f = new THREE.Mesh(geo, fm), b = new THREE.Mesh(geo, bm);
      f.castShadow = b.castShadow = true;
      f.visible = b.visible = false;
      this.group.add(f, b);
      this.pool.push({ geo, f, b, busy: false });
    }

    this.state = { cover: 0, open: 0 };   // cover: 0 closed … 1 lying on the left; open: book centering
    this.layout();
  }

  rightTop() { return C + this.nRight * PT; }
  leftTop() { return C + this.nLeft * PT; }

  /** Place stacks, covers and open pages from the current counters and cover angle. */
  layout() {
    const hr = Math.max(this.nRight * PT, 0.0005), hl = Math.max(this.nLeft * PT, 0.0005);
    this.rightStack.scale.y = hr; this.rightStack.position.set(W / 2, C + hr / 2, 0);
    this.leftStack.scale.y = hl; this.leftStack.position.set(-W / 2, C + hl / 2, 0);
    this.leftStack.visible = this.state.cover > 0.98;
    this.rightPage.position.set(W / 2, this.rightTop() + 0.0006, 0);
    this.leftPage.position.set(-W / 2, this.leftTop() + 0.0006, 0);
    this.leftPage.visible = this.state.cover > 0.98 && this.nLeft > 2;

    // hinge: closed → on top of the right stack; open → flat on the table, left side
    const a = this.state.cover * Math.PI;
    const closedY = this.rightTop();
    this.hinge.rotation.z = a;
    this.hinge.position.set(0, closedY + (C - closedY) * this.state.cover, 0);
    const spineH = (this.rightTop() + C) * (1 - this.state.cover) + C * this.state.cover;
    this.spine.scale.y = spineH;
    this.spine.position.set(-0.03, spineH / 2, 0);
    // center of the book moves from the closed block to the spine
    this.group.position.x = -(W / 2) * (1 - this.state.open);
  }

  update(dt) {
    this.time += dt;
    if (!this.isOpen && !this.reduced) {                     // idle "breathing"
      this.group.rotation.y = Math.sin(this.time * 0.35) * 0.06 - 0.12;
      this.group.position.y = Math.sin(this.time * 0.8) * 0.015;
    } else {
      this.group.rotation.y += (0 - this.group.rotation.y) * Math.min(1, dt * 4);
      this.group.position.y += (0 - this.group.position.y) * Math.min(1, dt * 4);
    }
  }

  dur(sec) { return this.reduced ? 0.01 : sec / this.speed; }

  open() {
    if (this.isOpen) return this.opening ?? Promise.resolve();
    this.isOpen = true;
    this.opening = new Promise((resolve) => {
      gsap.to(this.state, {
        cover: 1, open: 1, duration: this.dur(1.0), ease: 'power2.inOut',
        onUpdate: () => this.layout(), onComplete: () => { this.opening = null; resolve(); },
      });
    });
    return this.opening;
  }

  /** Open (if needed) and riffle — unless an answer has already started the landing meanwhile. */
  beginSearch() {
    this.wantRiffle = true;
    this.resetPages();
    this.open().then(() => { if (this.wantRiffle) this.startRiffle(); });
  }

  close() {
    this.wantRiffle = false;
    this.stopRiffle();
    return new Promise((resolve) => {
      const finish = () => {
        // pages go back to the right side when the book closes
        gsap.to(this, {
          nLeft: 0, nRight: TOTAL, duration: this.dur(0.35), onUpdate: () => this.layout(),
          onComplete: () => gsap.to(this.state, {
            cover: 0, open: 0, duration: this.dur(0.9), ease: 'power2.inOut',
            onUpdate: () => this.layout(), onComplete: () => { this.isOpen = false; resolve(); },
          }),
        });
      };
      if (this.flipsInAir) gsap.delayedCall(this.dur(0.5), finish); else finish();
    });
  }

  /** One page turn. dir +1: right → left, -1: left → right. textures: {front, back}. */
  flip(dir = 1, duration = 0.5, textures = null, { count = true } = {}) {
    const slot = this.pool.find((p) => !p.busy);
    if (!slot) return Promise.resolve();
    // a few sheets go over together; with count=false the sheet is only for show (the stacks glide instead)
    const n = count ? 1 + Math.floor(Math.random() * 3) : 0;
    if (dir > 0 && this.nRight - n < 6) return Promise.resolve();
    if (dir < 0 && (count ? this.nLeft - n < 0 : this.nLeft < 4)) return Promise.resolve();
    slot.busy = true; this.flipsInAir++;
    if (textures) { slot.f.material.map = textures.front; slot.b.material.map = textures.back; }
    else {
      slot.f.material.map = this.genericR[Math.floor(Math.random() * 4)];
      slot.b.material.map = this.genericL[Math.floor(Math.random() * 4)];
    }
    slot.f.material.needsUpdate = slot.b.material.needsUpdate = true;
    if (dir > 0) this.nRight -= n; else this.nLeft -= n;
    this.layout();
    const st = { p: dir > 0 ? 0 : 1 };
    slot.f.visible = slot.b.visible = true;
    bend(slot.geo, st.p, dir * 0.9, this.rightTop(), this.leftTop());
    return new Promise((resolve) => {
      gsap.to(st, {
        p: dir > 0 ? 1 : 0, duration: this.dur(duration), ease: 'power1.inOut',
        onUpdate: () => bend(slot.geo, st.p, dir * 0.9, this.rightTop(), this.leftTop()),
        onComplete: () => {
          if (dir > 0) this.nLeft += n; else this.nRight += n;
          slot.f.visible = slot.b.visible = false;
          slot.busy = false; this.flipsInAir--;
          this.layout();
          resolve();
        },
      });
    });
  }

  /** Fast page-turning while the backend searches. Runs until stopRiffle(). */
  startRiffle() {
    if (this.reduced) return;
    this.riffling = true;
    const dir = () => (this.nRight > this.nLeft + 30 ? 1 : -1);
    let d = dir();
    const tick = () => {
      if (!this.riffling) return;
      if (d > 0 && this.nRight < 40) d = -1;
      if (d < 0 && this.nLeft < 40) d = 1;
      this.flip(d, 0.55);
      this.riffleCall = gsap.delayedCall(this.dur(0.085), tick);
    };
    tick();
  }

  stopRiffle() {
    this.riffling = false;
    this.riffleCall?.kill();
  }

  /** Keep turning towards the target page, then turn the last page slowly and show the article. */
  async landOn(target) {
    this.wantRiffle = false;
    this.stopRiffle();
    await this.open();
    const want = Math.round(20 + target.position * (TOTAL - 60));   // target.position in [0, 1]
    const wait = (s) => new Promise((r) => gsap.delayedCall(this.dur(s), r));
    while (this.flipsInAir) await wait(0.05);                        // riffle pages land first
    // the stacks glide to the target page in under a second while a few sheets fly for show
    const dir = want >= this.nLeft ? 1 : -1;
    const glide = new Promise((resolve) => gsap.to(this, {
      nLeft: want, nRight: TOTAL - want, duration: this.dur(0.8), ease: 'power1.inOut',
      onUpdate: () => this.layout(), onComplete: resolve,
    }));
    for (let k = 0; k < 7; k++) { this.flip(dir, 0.32, null, { count: false }); await wait(0.1); }
    await glide;
    this.nLeft = want; this.nRight = TOTAL - want;
    while (this.flipsInAir) await wait(0.05);

    const right = articlePage(target);
    const left = headerPage(target);
    // the final sheet: its back becomes the left page, and the right stack now shows the article
    const prevRight = this.rightPage.material.map;
    this.rightPage.material.map = right; this.rightPage.material.needsUpdate = true;
    await this.flip(1, 1.1, { front: prevRight, back: left });
    this.leftPage.material.map = left; this.leftPage.material.needsUpdate = true;
    this.layout();
  }

  /** The open pages back to generic ones (before a new search). */
  resetPages() {
    this.rightPage.material.map = this.genericR[0];
    this.leftPage.material.map = this.genericL[0];
    this.rightPage.material.needsUpdate = this.leftPage.material.needsUpdate = true;
  }
}
