// Particle logo hero.
// Particles sampled from the real logo PNG fly in and form it. At rest, the
// particles themselves stay the visual permanently (the real PNG stays
// hidden via CSS) — nearby ones push away from the cursor and spring back
// into place. Anime.js (pinned, from jsDelivr) drives the entrance; one
// canvas loop does the per-particle physics both while forming and at rest.
// Any failure restores the plain CSS entrance, so the logo is never left
// hidden.

window.__ptl = true;

const ANIME_URL = "https://cdn.jsdelivr.net/npm/animejs@4.5.0/dist/bundles/anime.esm.min.js";

const root = document.documentElement;
const hero = document.querySelector(".hero");
const frame = document.querySelector(".hero-logo-frame");
const img = document.querySelector(".hero-logo");
const canvas = document.getElementById("hero-particles");

function fallback() {
  if (!root.classList.contains("ptl")) return;
  root.classList.remove("ptl");
  if (!frame) return;
  frame.style.opacity = "";
  frame.classList.remove("is-in");
  void frame.offsetWidth;
  requestAnimationFrame(() => frame.classList.add("is-in"));
}

(async function main() {
  if (!root.classList.contains("ptl") || !hero || !frame || !img || !canvas) return fallback();
  try {
    const anime = await Promise.race([
      import(ANIME_URL),
      new Promise((_, reject) => setTimeout(() => reject(new Error("anime timeout")), 3000)),
    ]);
    await img.decode();
    start(anime);
  } catch (err) {
    fallback();
  }
})();

function start({ animate }) {
  const ctx = canvas.getContext("2d");
  if (typeof animate !== "function" || !ctx) throw new Error("unsupported");

  const mobile = window.matchMedia("(max-width: 720px)").matches;
  const MAX = mobile ? 2600 : 7000;
  const DOT = mobile ? 1.9 : 1.7;
  const BLUES = [[111, 168, 255], [61, 127, 255], [150, 190, 255]];
  const WHITE = [232, 237, 245];
  // repulsion-and-spring constants for the resting (post-formed) physics —
  // particles near the cursor push away, then spring back to their sampled
  // target position once it moves on
  const REPEL_R = 60, REPEL_PUSH = 7, SPRING = 0.08, DAMP = 0.85;

  const st = { form: 0 };
  const ptr = { x: -9999, y: -9999, inside: false };
  let phase = "forming"; // forming | live
  let formed = false;
  let visible = true;
  let raf = 0;
  let W = 0, H = 0, dpr = 1, ox = 0, oy = 0, lw = 0, lh = 0;
  let n = 0;
  let X, Y, VX, VY, TX, TY, SX, SY, CX, CY, DL;
  let alphaData = null, alphaW = 0, alphaH = 0;

  function layout() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const hr = hero.getBoundingClientRect();
    const ir = img.getBoundingClientRect();
    W = hr.width;
    H = hr.height;
    ox = ir.left - hr.left;
    oy = ir.top - hr.top;
    lw = ir.width;
    lh = ir.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function renderAlphaMap() {
    const w = Math.max(1, Math.round(lw));
    const h = Math.max(1, Math.round(lh));
    const off = document.createElement("canvas");
    off.width = w;
    off.height = h;
    const octx = off.getContext("2d", { willReadFrequently: true });
    octx.drawImage(img, 0, 0, w, h);
    alphaData = octx.getImageData(0, 0, w, h).data;
    alphaW = w;
    alphaH = h;
  }

  function sample() {
    const px = [];
    for (let y = 0; y < alphaH; y++) {
      for (let x = 0; x < alphaW; x++) {
        if (alphaData[(y * alphaW + x) * 4 + 3] > 140) px.push(x, y);
      }
    }
    const total = px.length / 2;
    if (total <= MAX) return px;
    const idx = Array.from({ length: total }, (_, i) => i);
    for (let i = 0; i < MAX; i++) {
      const j = i + Math.floor(Math.random() * (total - i));
      const tmp = idx[i];
      idx[i] = idx[j];
      idx[j] = tmp;
    }
    const out = new Array(MAX * 2);
    for (let i = 0; i < MAX; i++) {
      out[i * 2] = px[idx[i] * 2];
      out[i * 2 + 1] = px[idx[i] * 2 + 1];
    }
    return out;
  }

  function build() {
    layout();
    renderAlphaMap();
    const pts = sample();
    n = pts.length / 2;
    X = new Float32Array(n); Y = new Float32Array(n);
    VX = new Float32Array(n); VY = new Float32Array(n);
    TX = new Float32Array(n); TY = new Float32Array(n);
    SX = new Float32Array(n); SY = new Float32Array(n);
    CX = new Float32Array(n); CY = new Float32Array(n);
    DL = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const tx = ox + pts[i * 2] + 0.5;
      const ty = oy + pts[i * 2 + 1] + 0.5;
      const sx = Math.random() * W;
      const sy = Math.random() * H * 0.6;
      const dx = tx - sx;
      const dy = ty - sy;
      const len = Math.hypot(dx, dy) || 1;
      const bend = (Math.random() * 2 - 1) * len * 0.32;
      TX[i] = tx; TY[i] = ty; SX[i] = sx; SY[i] = sy;
      CX[i] = (sx + tx) / 2 + (-dy / len) * bend;
      CY[i] = (sy + ty) / 2 + (dx / len) * bend;
      DL[i] = Math.random() * 0.28;
      X[i] = formed ? tx : sx;
      Y[i] = formed ? ty : sy;
    }
  }

  function place() {
    const f = st.form;
    for (let i = 0; i < n; i++) {
      const d = DL[i];
      let t = (f - d) / (1 - d);
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      const u = 1 - t;
      X[i] = u * u * SX[i] + 2 * u * t * CX[i] + t * t * TX[i];
      Y[i] = u * u * SY[i] + 2 * u * t * CY[i] + t * t * TY[i];
    }
  }

  function mixColor(base, amount) {
    const r = Math.round(base[0] + (WHITE[0] - base[0]) * amount);
    const g = Math.round(base[1] + (WHITE[1] - base[1]) * amount);
    const b = Math.round(base[2] + (WHITE[2] - base[2]) * amount);
    return `rgb(${r},${g},${b})`;
  }

  // The one particle renderer, used for both the forming entrance and the
  // resting state afterward — color ramps from blue to white as st.form
  // reaches 1, then stays solid white at rest (phase !== "forming").
  function drawForming() {
    ctx.clearRect(0, 0, W, H);
    const ramp = phase === "forming" ? Math.min(1, st.form * 12) : 1;
    const alpha = 0.95 * ramp;
    if (alpha <= 0.003) return;
    const amount = phase === "forming" ? Math.pow(st.form, 0.8) : 1;
    ctx.globalAlpha = alpha;
    const half = DOT / 2;
    for (let b = 0; b < 3; b++) {
      ctx.fillStyle = mixColor(BLUES[b], amount);
      for (let i = b; i < n; i += 3) ctx.fillRect(X[i] - half, Y[i] - half, DOT, DOT);
    }
    ctx.globalAlpha = 1;
  }

  function schedule() {
    if (raf || !visible || document.hidden) return;
    raf = requestAnimationFrame(tick);
  }

  // Resting-phase physics: particles stay the permanent visual (the real PNG
  // stays hidden via CSS). Anything near the cursor pushes away, then springs
  // back toward its sampled target position once the cursor moves on.
  function settle() {
    let moving = false;
    for (let i = 0; i < n; i++) {
      if (ptr.inside) {
        const dx = X[i] - ptr.x, dy = Y[i] - ptr.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < REPEL_R * REPEL_R && d2 > 0.1) {
          const d = Math.sqrt(d2), k = 1 - d / REPEL_R;
          VX[i] += (dx / d) * k * k * REPEL_PUSH;
          VY[i] += (dy / d) * k * k * REPEL_PUSH;
        }
      }
      VX[i] += (TX[i] - X[i]) * SPRING;
      VY[i] += (TY[i] - Y[i]) * SPRING;
      VX[i] *= DAMP;
      VY[i] *= DAMP;
      X[i] += VX[i];
      Y[i] += VY[i];
      if (Math.abs(VX[i]) > 0.02 || Math.abs(VY[i]) > 0.02) moving = true;
    }
    return moving;
  }

  function tick(now) {
    raf = 0;
    if (!visible || document.hidden) return;
    if (phase === "forming") {
      place();
      drawForming();
      raf = requestAnimationFrame(tick);
      return;
    }
    const moving = settle();
    drawForming();
    if (moving || ptr.inside) raf = requestAnimationFrame(tick);
  }

  function onFormed() {
    if (formed) return;
    formed = true;
    st.form = 1;
    for (let i = 0; i < n; i++) { X[i] = TX[i]; Y[i] = TY[i]; VX[i] = 0; VY[i] = 0; }
    phase = "live";
  }

  // Text follows the logo instead of waiting for the CSS sweep timing.
  const lede = document.querySelector(".hero-lede");
  const actions = document.querySelector(".hero-actions");
  if (lede) lede.style.setProperty("--base", "1300ms");
  if (actions) actions.style.setProperty("--base", "1450ms");

  build();
  schedule();

  animate(st, {
    form: 1,
    duration: 2400,
    delay: 250,
    ease: "outExpo",
    onUpdate: () => { if (!formed && st.form >= 0.985) onFormed(); },
    onComplete: onFormed,
  });

  window.addEventListener("pointermove", (e) => {
    if (e.pointerType === "touch" || !visible) return;
    const r = canvas.getBoundingClientRect();
    ptr.x = e.clientX - r.left;
    ptr.y = e.clientY - r.top;
    const pad = 30;
    ptr.inside = ptr.x > ox - pad && ptr.x < ox + lw + pad && ptr.y > oy - pad && ptr.y < oy + lh + pad;
    if (ptr.inside && formed) schedule();
  }, { passive: true });

  document.documentElement.addEventListener("pointerleave", () => { ptr.inside = false; schedule(); });
  window.addEventListener("blur", () => { ptr.inside = false; });

  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    if (visible) schedule();
  }, { threshold: 0 }).observe(hero);

  document.addEventListener("visibilitychange", () => { if (!document.hidden) schedule(); });

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      build();
      schedule();
    }, 200);
  });
}
