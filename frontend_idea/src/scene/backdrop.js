// The dark legal library behind the scene, drawn once on a 2D canvas (no image file, no 3D cost):
// bookshelves on both sides, a warm lamp glow on the left, a cool window glow on the right, a vignette.

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function shelf(ctx, x0, x1, top, bottom, rand, light) {
  const rows = 5;
  const rowH = (bottom - top) / rows;
  for (let r = 0; r < rows; r++) {
    const y1 = top + (r + 1) * rowH;
    ctx.fillStyle = 'rgba(30, 24, 18, 0.95)';                         // shelf board
    ctx.fillRect(x0, y1 - 8, x1 - x0, 8);
    let x = x0 + 4;
    while (x < x1 - 10) {
      const w = 10 + rand() * 22, h = rowH * (0.62 + rand() * 0.3);
      const hue = [150, 28, 210, 12, 40][Math.floor(rand() * 5)];
      const l = 9 + rand() * 9 + light * (1 - Math.abs((x - (x0 + x1) / 2) / ((x1 - x0) / 2))) * 6;
      ctx.fillStyle = `hsl(${hue}, ${18 + rand() * 22}%, ${l}%)`;
      ctx.fillRect(x, y1 - 8 - h, w, h);
      if (rand() > 0.55) {                                            // gilt bands on spines
        ctx.fillStyle = `rgba(214, 182, 109, ${0.12 + rand() * 0.18})`;
        ctx.fillRect(x + 2, y1 - 8 - h + h * 0.14, w - 4, 2);
        ctx.fillRect(x + 2, y1 - 8 - h * 0.2, w - 4, 2);
      }
      x += w + 1 + (rand() > 0.9 ? 12 : 0);
    }
  }
}

export function drawBackdrop(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const w = window.innerWidth, h = window.innerHeight;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const rand = rng(42);

  const base = ctx.createLinearGradient(0, 0, 0, h);
  base.addColorStop(0, '#08100e'); base.addColorStop(0.6, '#0a1311'); base.addColorStop(1, '#050908');
  ctx.fillStyle = base; ctx.fillRect(0, 0, w, h);

  const sw = Math.min(w * 0.3, 520);
  ctx.globalAlpha = 0.75;
  shelf(ctx, -10, sw, h * 0.08, h * 0.86, rand, 1);
  shelf(ctx, w - sw, w + 10, h * 0.06, h * 0.84, rand, 0.4);
  ctx.globalAlpha = 1;

  // tall window with cold light behind the right shelves
  const win = ctx.createLinearGradient(w * 0.72, 0, w * 0.9, 0);
  win.addColorStop(0, 'rgba(70, 150, 150, 0)'); win.addColorStop(0.5, 'rgba(70, 150, 150, 0.16)'); win.addColorStop(1, 'rgba(70, 150, 150, 0)');
  ctx.fillStyle = win; ctx.fillRect(w * 0.72, h * 0.04, w * 0.18, h * 0.55);

  const lamp = ctx.createRadialGradient(w * 0.16, h * 0.62, 10, w * 0.16, h * 0.62, Math.max(w, h) * 0.5);
  lamp.addColorStop(0, 'rgba(255, 190, 110, 0.20)'); lamp.addColorStop(0.4, 'rgba(255, 170, 90, 0.07)'); lamp.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = lamp; ctx.fillRect(0, 0, w, h);

  const centre = ctx.createRadialGradient(w * 0.5, h * 0.45, 10, w * 0.5, h * 0.45, Math.max(w, h) * 0.55);
  centre.addColorStop(0, 'rgba(10, 30, 26, 0.85)'); centre.addColorStop(0.55, 'rgba(8, 18, 16, 0.55)'); centre.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = centre; ctx.fillRect(0, 0, w, h);

  const vig = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.max(w, h) * 0.75);
  vig.addColorStop(0, 'rgba(0,0,0,0)'); vig.addColorStop(1, 'rgba(0,0,0,0.78)');
  ctx.fillStyle = vig; ctx.fillRect(0, 0, w, h);
}
