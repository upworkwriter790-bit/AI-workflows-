// Product icon → status orb, on hover.
// Each product's static line-art icon crossfades into an animated "thinking"
// orb (thinking-orbs' engine, pinned from jsDelivr) for as long as the cursor
// is anywhere over that product's row, then crossfades back. Touch devices
// and prefers-reduced-motion keep the static icon only — this is pure
// decoration, never the only way to read a product's name or description.

const ENGINE_URL = "https://cdn.jsdelivr.net/npm/thinking-orbs@0.3.2/dist/engine.es.js";
const SIZE = 64; // the library's own tuned preset — drawn at full size, then
                  // displayed smaller via the .pi-orb CSS box (downscaled
                  // only, never stretched up from a smaller preset)

const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (canHover && !reduceMotion) {
  (async function main() {
    let engine;
    try {
      engine = await Promise.race([
        import(ENGINE_URL),
        new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 3000)),
      ]);
    } catch (err) {
      return; // static icons stay as-is, nothing else to do
    }
    const { MODE_DRAWS, STATE_TO_MODE, resolvePreset } = engine;
    if (!MODE_DRAWS || !resolvePreset) return;

    document.querySelectorAll(".catalog-row").forEach((row) => {
      const pi = row.querySelector(".pi[data-orb]");
      if (!pi) return;
      const state = pi.dataset.orb;
      const mode = STATE_TO_MODE ? STATE_TO_MODE[state] : null;
      const draw = mode ? MODE_DRAWS[mode] : null;
      if (!draw) return;

      const canvas = pi.querySelector(".pi-orb");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = SIZE * dpr;
      canvas.height = SIZE * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const preset = resolvePreset(state, SIZE);
      let raf = 0;

      function frame(t) {
        ctx.clearRect(0, 0, SIZE, SIZE);
        draw(ctx, SIZE, (t / 1000) * preset.speed, true, preset.opts);
        raf = requestAnimationFrame(frame);
      }

      row.addEventListener("pointerenter", (e) => {
        if (e.pointerType === "touch") return;
        row.classList.add("is-orb-active");
        if (!raf) raf = requestAnimationFrame(frame);
      });
      row.addEventListener("pointerleave", () => {
        row.classList.remove("is-orb-active");
        cancelAnimationFrame(raf);
        raf = 0;
      });
    });
  })();
}
