// Reveal on load and on scroll. The hidden states in the CSS only exist while
// <html> carries .js (set in the head); if this file never loads, the head
// script removes .js after a few seconds so nothing stays invisible.
(function () {
  window.__reveal = true;
  if (!document.documentElement.classList.contains("js")) return;

  function splitWords(el) {
    const nodes = Array.from(el.childNodes);
    const label = nodes
      .map((n) => (n.nodeType === Node.TEXT_NODE ? n.textContent : " "))
      .join("")
      .replace(/\s+/g, " ")
      .trim();
    const wrap = document.createElement("span");
    wrap.setAttribute("aria-hidden", "true");
    let k = 0;
    nodes.forEach((node) => {
      if (node.nodeType !== Node.TEXT_NODE) {
        wrap.appendChild(node.cloneNode(true));
        return;
      }
      node.textContent.split(/\s+/).filter(Boolean).forEach((word) => {
        const outer = document.createElement("span");
        outer.className = "w";
        const inner = document.createElement("span");
        inner.className = "wi";
        inner.style.setProperty("--k", k++);
        inner.textContent = word;
        outer.appendChild(inner);
        wrap.appendChild(outer);
        wrap.appendChild(document.createTextNode(" "));
      });
    });
    el.setAttribute("aria-label", label);
    el.replaceChildren(wrap);
  }

  document.querySelectorAll('[data-reveal="words"]').forEach(splitWords);

  const items = document.querySelectorAll("[data-reveal]");
  if (!("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-in"));
    return;
  }
  // A clip-path'd element is fully clipped until revealed, which some browsers
  // report as "not intersecting" forever, so those are observed via their parent.
  const watched = new Map();
  items.forEach((el) => {
    const target = el.dataset.reveal === "clip" ? el.parentElement : el;
    if (!watched.has(target)) watched.set(target, []);
    watched.get(target).push(el);
  });
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        watched.get(entry.target).forEach((el) => el.classList.add("is-in"));
        io.unobserve(entry.target);
      });
    },
    { threshold: 0.12 }
  );
  watched.forEach((_, target) => io.observe(target));

  // Safety net: anything already on screen but still hidden after 3s is shown.
  setTimeout(() => {
    items.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!el.classList.contains("is-in") && r.top < window.innerHeight && r.bottom > 0) {
        el.classList.add("is-in");
      }
    });
  }, 3000);
})();

// Placeholder links (href="#") should do nothing rather than jump to the top.
document.querySelectorAll('a[href="#"]').forEach((a) => {
  a.addEventListener("click", (e) => e.preventDefault());
});

// Footer year
document.getElementById("year").textContent = new Date().getFullYear();

// Mobile nav toggle (hamburger)
(function () {
  const toggle = document.getElementById("nav-toggle");
  const nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;

  function setOpen(open) {
    nav.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    document.body.style.overflow = open ? "hidden" : "";
  }

  toggle.addEventListener("click", () => setOpen(!nav.classList.contains("is-open")));
  nav.addEventListener("click", (e) => {
    if (e.target.tagName === "A") setOpen(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && nav.classList.contains("is-open")) setOpen(false);
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 720) setOpen(false);
  });

  // Products accordion (mobile only) — collapsed until the chevron is tapped
  const chevron = document.querySelector(".nav-toggle-chevron");
  const navItem = chevron ? chevron.closest(".nav-item") : null;
  if (chevron && navItem) {
    chevron.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const expanded = navItem.classList.toggle("is-expanded");
      chevron.setAttribute("aria-expanded", String(expanded));
    });
  }
})();

// Contact form — no backend wired up yet, so just acknowledge the submission
const form = document.getElementById("contact-form");
const note = document.getElementById("form-note");
if (form) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    note.textContent = "Thanks — this form isn't wired to send yet. Reach us directly until it is.";
  });
}

// AI audit form — the audit engine isn't connected yet either
const auditForm = document.getElementById("audit-form");
const auditNote = document.getElementById("audit-note");
if (auditForm) {
  auditForm.addEventListener("submit", (e) => {
    e.preventDefault();
    auditNote.textContent = "Thanks — the audit engine isn't connected yet, so nothing was submitted. Get in touch and we'll run it by hand.";
  });
}

// Site-wide circuit rain — a Matrix-style falling stream in the brand's
// electric blue, mouse-reactive, fixed behind every section on every page.
// Freezes on a single static frame for reduced-motion users.
(function () {
  const canvas = document.getElementById("bg-rain");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const GLYPHS = "01╱╲┼─│+·0101ABCDEF01".split("");
  const FONT_SIZE = 17;
  const ACCENT = "94, 150, 255";
  const ACCENT_BRIGHT = "200, 220, 255";
  const BG = "7, 11, 18";
  const MOUSE_RADIUS = 190;

  let width, height, dpr;
  let columns = [];
  let mouse = { x: -9999, y: -9999 };

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = `${FONT_SIZE}px "Space Mono", monospace`;
    ctx.textBaseline = "top";

    const colCount = Math.ceil(width / FONT_SIZE);
    columns = Array.from({ length: colCount }, (_, i) => ({
      x: i * FONT_SIZE,
      y: Math.random() * -height,
      speed: 0.14 + Math.random() * 0.22,
    }));

    // paint an opaque base so the fade-trail effect has something to fade onto
    ctx.fillStyle = `rgb(${BG})`;
    ctx.fillRect(0, 0, width, height);
  }

  function draw() {
    // translucent overlay creates the trailing fade behind each falling glyph
    ctx.fillStyle = `rgba(${BG}, 0.11)`;
    ctx.fillRect(0, 0, width, height);

    for (const col of columns) {
      const dx = col.x - mouse.x;
      const dy = col.y - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const near = dist < MOUSE_RADIUS;
      const boost = near ? 1 - dist / MOUSE_RADIUS : 0;

      const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      ctx.fillStyle = near
        ? `rgba(${ACCENT_BRIGHT}, ${0.7 + boost * 0.3})`
        : `rgba(${ACCENT}, 0.78)`;
      ctx.fillText(glyph, col.x, col.y);

      col.y += FONT_SIZE * (col.speed + boost * 0.8);
      if (col.y > height + FONT_SIZE && Math.random() > 0.975) {
        col.y = Math.random() * -200;
        col.speed = 0.14 + Math.random() * 0.22;
      }
    }
  }

  function loop() {
    draw();
    requestAnimationFrame(loop);
  }

  window.addEventListener("mousemove", (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });
  window.addEventListener("mouseleave", () => {
    mouse.x = -9999;
    mouse.y = -9999;
  });

  resize();
  window.addEventListener("resize", resize);

  if (!reduceMotion) {
    requestAnimationFrame(loop);
  }
})();

// Chat bot — front-end only. Opens/closes the panel and echoes messages;
// there is no assistant behind it yet, and it says so.
(function () {
  const root = document.getElementById("chat");
  if (!root) return;
  const launcher = document.getElementById("chat-launcher");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");
  const chatForm = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const log = document.getElementById("chat-log");

  function setOpen(open) {
    root.classList.toggle("is-open", open);
    launcher.setAttribute("aria-expanded", String(open));
    panel.setAttribute("aria-hidden", String(!open));
    panel.inert = !open;
    if (open) input.focus();
    else launcher.focus();
  }

  function addMessage(html, who) {
    const p = document.createElement("p");
    p.className = "chat-msg chat-msg-" + who;
    if (who === "bot") p.innerHTML = html;
    else p.textContent = html;
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
  }

  launcher.addEventListener("click", () => setOpen(!root.classList.contains("is-open")));
  closeBtn.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.classList.contains("is-open")) setOpen(false);
  });

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, "user");
    input.value = "";
    setTimeout(() => {
      addMessage(
        "I can't answer yet — there's no live assistant behind this window. Leave your details in the <a href=\"#contact\">contact form</a> and the team will reply.",
        "bot"
      );
    }, 450);
  });
})();

// Join Community popup — opens on clicking the header pill, collects name
// + WhatsApp number, saves the lead, then redirects into the WhatsApp group.
(function () {
  const backdrop = document.getElementById("join-backdrop");
  if (!backdrop) return;
  const trigger = document.getElementById("join-community");
  const closeBtn = document.getElementById("join-pop-close");
  const form = document.getElementById("join-form");
  const note = document.getElementById("join-note");
  const nameInput = document.getElementById("join-name");
  const phoneInput = document.getElementById("join-phone");

  const WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/Cwe20x0k30XId8PNscbXUn?s=cl&p=i&ilr=4&iam=2";
  // TODO: replace with the deployed Google Apps Script web app URL —
  // see GOOGLE-SHEET-SETUP.md for how to get this
  const SHEET_ENDPOINT = "";

  function open() {
    backdrop.classList.add("is-visible");
    backdrop.setAttribute("aria-hidden", "false");
    backdrop.inert = false;
    nameInput.focus();
  }
  function close() {
    backdrop.classList.remove("is-visible");
    backdrop.setAttribute("aria-hidden", "true");
    backdrop.inert = true;
    trigger.focus();
  }

  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    open();
  });
  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && backdrop.classList.contains("is-visible")) close();
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    if (!name || !phone) return;

    if (SHEET_ENDPOINT) {
      // no-cors: Apps Script web apps don't return readable CORS headers,
      // so this is fire-and-forget — we don't wait on or read the response.
      fetch(SHEET_ENDPOINT, {
        method: "POST",
        mode: "no-cors",
        headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({
          name,
          phone,
          page: location.pathname,
          ts: new Date().toISOString(),
        }),
      }).catch(() => {});
    }

    if (WHATSAPP_GROUP_URL && WHATSAPP_GROUP_URL !== "#") {
      window.location.href = WHATSAPP_GROUP_URL;
    } else {
      note.textContent = "Thanks — the WhatsApp group link isn't set yet, so we can't redirect you. We'll add you by hand.";
    }
  });
})();

// Audit pop-up — slides in from the left a few seconds after load; stays
// dismissed for the rest of the browsing session.
(function () {
  const pop = document.getElementById("audit-pop");
  if (!pop) return;
  const KEY = "ilactic-audit-pop-dismissed";

  function dismissed() {
    try { return sessionStorage.getItem(KEY) === "1"; } catch (e) { return false; }
  }
  function remember() {
    try { sessionStorage.setItem(KEY, "1"); } catch (e) { /* private mode — fine */ }
  }
  function hide() {
    pop.classList.remove("is-visible");
    pop.setAttribute("aria-hidden", "true");
    pop.inert = true;
    remember();
  }

  document.getElementById("audit-pop-close").addEventListener("click", hide);
  document.getElementById("audit-pop-link").addEventListener("click", hide);

  if (dismissed()) return;
  setTimeout(() => {
    pop.classList.add("is-visible");
    pop.setAttribute("aria-hidden", "false");
    pop.inert = false;
  }, 3500);
})();
