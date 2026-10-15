// Invoice Delivery Agent — plain-JS admin UI. No build step, no
// framework: open index.html (or serve the folder) and point
// config.js at your running backend.

const AUTH_KEY = "ida_auth";

function getAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
  } catch {
    return null;
  }
}
function setAuth(auth) {
  if (auth) localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
  else localStorage.removeItem(AUTH_KEY);
}
function hasRole(...roles) {
  const auth = getAuth();
  if (!auth) return false;
  const mine = (auth.role || "").split(",").map((r) => r.trim());
  return mine.includes("ADMIN") || roles.some((r) => mine.includes(r));
}

async function api(path, { method = "GET", json, form, raw } = {}) {
  const auth = getAuth();
  const headers = {};
  if (auth) headers["Authorization"] = `Bearer ${auth.access_token}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    body = form; // FormData — browser sets content-type with boundary
  }
  const resp = await fetch(window.API_BASE_URL + path, { method, headers, body });
  if (resp.status === 401) {
    setAuth(null);
    location.hash = "#/login";
    throw new Error("Session expired — please log in again.");
  }
  if (raw) {
    if (!resp.ok) throw new Error(`Request failed (${resp.status})`);
    return resp.blob();
  }
  let data = null;
  try {
    data = await resp.json();
  } catch {
    /* no body */
  }
  if (!resp.ok) {
    const detail = data && data.detail !== undefined ? data.detail : data;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = resp.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

// ---------------------------------------------------------------------
// Tiny hash router
// ---------------------------------------------------------------------

const routes = [];
function route(pattern, handler) {
  routes.push({ pattern, handler });
}
function matchRoute(hash) {
  for (const r of routes) {
    const names = [];
    const regex = new RegExp(
      "^" + r.pattern.replace(/:[a-zA-Z]+/g, (m) => {
        names.push(m.slice(1));
        return "([^/]+)";
      }) + "$"
    );
    const m = hash.match(regex);
    if (m) {
      const params = {};
      names.forEach((n, i) => (params[n] = m[i + 1]));
      return { handler: r.handler, params };
    }
  }
  return null;
}
async function render() {
  const hash = (location.hash || "#/login").replace(/^#/, "");
  const auth = getAuth();
  if (!auth && hash !== "/login") {
    location.hash = "#/login";
    return;
  }
  const matched = matchRoute(hash) || matchRoute("/login");
  renderShell(hash);
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="spinner">Loading…</div>';
  try {
    await matched.handler(main, matched.params);
  } catch (e) {
    main.innerHTML = `<div class="alert error">${escapeHtml(e.message || String(e))}</div>`;
  }
}
window.addEventListener("hashchange", render);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtMoney(v) {
  if (v === null || v === undefined) return "—";
  return "₹" + Number(v).toFixed(2);
}
function badgeClass(status) {
  const s = (status || "").toUpperCase();
  if (s.includes("PENDING") || s === "DRAFT") return "pending";
  if (s.includes("REVIEW")) return "review";
  if (s === "QUEUED" || s.includes("COMPLETED") || s === "DELIVERY_QUEUED") return "queued";
  if (s.includes("REJECTED") || s.includes("CANCELLED") || s.includes("FAILED")) return "rejected";
  return "neutral";
}

// ---------------------------------------------------------------------
// Shell (sidebar nav)
// ---------------------------------------------------------------------

function renderShell(currentHash) {
  const auth = getAuth();
  const app = document.getElementById("app");
  const navItems = [
    { href: "#/quick-create", label: "Quick Create", show: auth },
    { href: "#/drafts", label: "Generated-Invoice Drafts", show: auth },
    { href: "#/method-a", label: "Upload Existing Invoice", show: auth },
    { href: "#/catalog", label: "Product Catalog", show: auth },
    { href: "#/customers", label: "Customer Directory", show: auth },
    { href: "#/users", label: "Users", show: hasRole("ADMIN") },
  ];
  const navHtml = navItems
    .filter((i) => i.show)
    .map(
      (i) =>
        `<a href="${i.href}" class="${currentHash === i.href.slice(1) ? "active" : ""}">${i.label}</a>`
    )
    .join("");

  app.innerHTML = `
    ${auth ? `<nav class="sidebar">
      <div class="brand">Invoice Delivery Agent</div>
      ${navHtml}
      <div class="user-box">
        ${escapeHtml(auth.display_name)}<br/>
        <span>${escapeHtml(auth.role)}</span><br/>
        <a href="#" id="logout-link" style="color:#f87171;">Log out</a>
      </div>
    </nav>` : ""}
    <main><div id="main-content"></div></main>
  `;
  const logout = document.getElementById("logout-link");
  if (logout) {
    logout.addEventListener("click", (e) => {
      e.preventDefault();
      setAuth(null);
      location.hash = "#/login";
    });
  }
}

// ---------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------

route("/login", (main) => {
  main.innerHTML = `
    <div class="panel" style="max-width:360px;margin:60px auto;">
      <h1>Log in</h1>
      <div id="login-error"></div>
      <label>Email</label>
      <input id="login-email" type="email" value="admin@example.com" />
      <label>Password</label>
      <input id="login-password" type="password" value="ChangeMe123!" />
      <button id="login-submit">Log in</button>
      <p class="help-text">Default admin is seeded on first backend startup
      from DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD (see backend/.env).</p>
    </div>
  `;
  document.getElementById("login-submit").addEventListener("click", async () => {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    try {
      const resp = await api("/api/v1/auth/login", { method: "POST", json: { email, password } });
      setAuth(resp);
      location.hash = "#/quick-create";
    } catch (e) {
      document.getElementById("login-error").innerHTML =
        `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------
// Quick Create (Mode B1)
// ---------------------------------------------------------------------

route("/quick-create", (main) => {
  main.innerHTML = `
    <h1>Quick Create Invoice Draft</h1>
    <p class="help-text">Give the minimum you have — the agent resolves the
    rest from your product catalog and customer directory, never inventing
    price, tax, or identity data. Switch to the full form any time.</p>
    <div class="panel">
      <div class="row">
        <div class="col">
          <label>Customer email</label>
          <input id="qc-email" placeholder="jane@example.com" />
        </div>
        <div class="col">
          <label>Customer phone (E.164)</label>
          <input id="qc-phone" placeholder="+919876543210" />
        </div>
      </div>
      <div class="row">
        <div class="col">
          <label>Amount paid (₹)</label>
          <input id="qc-amount" type="number" step="0.01" placeholder="2999.00" />
        </div>
        <div class="col">
          <label>Payment / transaction reference</label>
          <input id="qc-ref" placeholder="TXN-9949" />
        </div>
      </div>
      <div class="row">
        <div class="col">
          <label>What was purchased? (optional if we already know)</label>
          <input id="qc-product" placeholder="Annual Plan" />
        </div>
        <div class="col">
          <label>Payment date</label>
          <input id="qc-date" type="date" />
        </div>
      </div>
      <label>Internal note (optional)</label>
      <input id="qc-notes" />
      <div id="qc-clarify"></div>
      <button id="qc-submit">Prepare Invoice Draft</button>
      <button class="secondary" id="qc-detailed">Switch to detailed form</button>
      <div id="qc-result"></div>
    </div>
  `;
  document.getElementById("qc-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("qc-detailed").addEventListener("click", () => (location.hash = "#/detailed-create"));

  function collectPayload() {
    const payload = {
      amount_paid: parseFloat(document.getElementById("qc-amount").value || "0"),
      payment_reference: document.getElementById("qc-ref").value.trim(),
      payment_date: document.getElementById("qc-date").value || undefined,
      notes: document.getElementById("qc-notes").value.trim() || undefined,
    };
    const email = document.getElementById("qc-email").value.trim();
    const phone = document.getElementById("qc-phone").value.trim();
    const product = document.getElementById("qc-product").value.trim();
    if (email) payload.customer_email = email;
    if (phone) payload.customer_phone = phone;
    if (product) payload.product_text = product;
    const extra = main.dataset.extraAnswers;
    if (extra) Object.assign(payload, JSON.parse(extra));
    return payload;
  }

  async function submitDraft() {
    const resultEl = document.getElementById("qc-result");
    resultEl.innerHTML = '<div class="spinner">Resolving…</div>';
    try {
      const resp = await api("/api/v1/quick-create/draft", { method: "POST", json: collectPayload() });
      resultEl.innerHTML = `<div class="alert success">Draft created (status ${resp.status}, grand total ${fmtMoney(resp.grand_total)}).
        <a href="#/draft/${resp.invoice_id}">Open for review →</a></div>`;
      document.getElementById("qc-clarify").innerHTML = "";
    } catch (e) {
      if (e.status === 409 && e.detail && e.detail.outcome) {
        renderClarification(e.detail);
      } else {
        resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
      }
    }
  }

  function renderClarification(detail) {
    const box = document.getElementById("qc-clarify");
    const resultEl = document.getElementById("qc-result");
    resultEl.innerHTML = "";
    if (detail.outcome === "NEEDS_DETAILED_FORM" || !detail.clarification) {
      box.innerHTML = `<div class="alert info">We couldn't resolve this from a quick question —
        please use the detailed form. ${escapeHtml(detail.reviewer_summary || "")}
        <br/><button class="secondary" onclick="location.hash='#/detailed-create'">Open detailed form</button></div>`;
      return;
    }
    const q = detail.clarification;
    let inputHtml = "";
    if (q.answer_type === "SELECT" && q.options && q.options.length) {
      inputHtml = `<select id="qc-clarify-answer">${q.options
        .map((o) => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`)
        .join("")}</select>`;
    } else {
      inputHtml = `<input id="qc-clarify-answer" />`;
    }
    box.innerHTML = `
      <div class="alert info">
        <strong>${escapeHtml(q.question)}</strong>
        <div style="margin-top:8px;">${inputHtml}
        <button id="qc-clarify-submit">Answer</button></div>
      </div>`;
    document.getElementById("qc-clarify-submit").addEventListener("click", () => {
      const answer = document.getElementById("qc-clarify-answer").value;
      const field = q.field_needed;
      const extra = {};
      if (field === "product_or_service") extra.product_text = answer;
      else if (field === "billing_state") extra.billing_state_name = answer;
      else if (field === "recipient_identity") extra.customer_name = answer;
      main.dataset.extraAnswers = JSON.stringify(extra);
      submitDraft();
    });
  }

  document.getElementById("qc-submit").addEventListener("click", () => {
    main.dataset.extraAnswers = "";
    submitDraft();
  });
});

// ---------------------------------------------------------------------
// Detailed create (Mode B2) — the full GeneratedInvoiceDeliveryRequest
// ---------------------------------------------------------------------

route("/detailed-create", (main) => {
  main.innerHTML = `
    <h1>Create with Detailed Fields</h1>
    <p class="help-text">Full control over every field. Use this when Quick
    Create can't resolve the order, or you need complete manual precision.</p>
    <div class="panel">
      <textarea id="detailed-json" style="min-height:420px;font-family:monospace;font-size:12px;">${escapeHtml(
        JSON.stringify(
          {
            idempotency_key: "order-" + Date.now(),
            external_reference: "ORD-1001",
            recipient: {
              name: "Jane Buyer", email: "jane@example.com", phone: "+919876543210",
              billing_address: { line1: "1 MG Road", city: "Mumbai", state: "Maharashtra", state_code: "27", postal_code: "400001", country: "India" },
            },
            payment_or_order_details: {
              payment_reference: "PAY-1001", payment_date: new Date().toISOString().slice(0, 10), currency: "INR",
              tax_inclusive: false, subtotal: 1000.0, discount_total: 0, tax_total: 180.0, grand_total: 1180.0, payment_status: "PAID",
            },
            items: [
              { description: "Professional Plan", product_type: "SERVICE", hsn_or_sac_code: "9983", quantity: 1, unit: "Nos", unit_price: 1000.0, gst_rate: 18.0 },
            ],
            delivery: { requested_channels: ["email"] },
          },
          null,
          2
        )
      )}</textarea>
      <button id="detailed-submit">Create Draft</button>
      <div id="detailed-result"></div>
    </div>
  `;
  document.getElementById("detailed-submit").addEventListener("click", async () => {
    const resultEl = document.getElementById("detailed-result");
    try {
      const payload = JSON.parse(document.getElementById("detailed-json").value);
      const resp = await api("/api/v1/generated-invoice-deliveries", { method: "POST", json: payload });
      resultEl.innerHTML = `<div class="alert success">Draft created.
        <a href="#/draft/${resp.invoice_id}">Open for review →</a></div>`;
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------
// Drafts list (generated invoices)
// ---------------------------------------------------------------------

route("/drafts", async (main) => {
  const data = await api("/api/v1/generated-invoice-deliveries");
  main.innerHTML = `
    <h1>Generated-Invoice Drafts</h1>
    <div class="panel">
      <table>
        <thead><tr><th>Invoice #</th><th>Recipient</th><th>Grand total</th><th>Status</th><th>Version</th><th>Created</th></tr></thead>
        <tbody>
          ${data.generated_invoices
            .map(
              (gi) => `
            <tr class="clickable" onclick="location.hash='#/draft/${gi.invoice_id}'">
              <td>${escapeHtml(gi.invoice_number || "(unassigned)")}</td>
              <td>${escapeHtml(gi.recipient_name || "")}</td>
              <td>${fmtMoney(gi.grand_total)}</td>
              <td><span class="badge ${badgeClass(gi.status)}">${gi.status}</span></td>
              <td>v${gi.current_version_number}</td>
              <td>${gi.created_at ? new Date(gi.created_at).toLocaleString() : ""}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
      ${data.generated_invoices.length === 0 ? '<p class="help-text">No generated invoices yet — try Quick Create.</p>' : ""}
    </div>
  `;
});

// ---------------------------------------------------------------------
// Draft review detail — the heart of the human-approval workflow
// ---------------------------------------------------------------------

route("/draft/:id", async (main, { id }) => {
  const [detail, versions] = await Promise.all([
    api(`/api/v1/generated-invoice-deliveries/${id}`),
    api(`/api/v1/generated-invoice-deliveries/${id}/versions`),
  ]);

  const canEdit = detail.is_editable && hasRole("INVOICE_EDITOR");
  const canApprove = detail.is_approvable && hasRole("INVOICE_APPROVER");

  main.innerHTML = `
    <h1>Invoice Draft — ${escapeHtml(detail.invoice_number || "(number not yet assigned)")}
      <span class="badge ${badgeClass(detail.status)}">${detail.status}</span>
      ${detail.is_editable ? '<span class="watermark-note">DRAFT — NOT FOR DELIVERY</span>' : ""}
    </h1>
    <div class="split">
      <div class="left panel">
        <h3>Draft PDF preview</h3>
        <iframe class="pdf-frame" id="pdf-frame"></iframe>
        <div class="help-text">Version ${detail.current_version_number}${detail.approved_version_number ? ` (approved: v${detail.approved_version_number})` : ""}</div>

        <h3>Version history</h3>
        <table>
          <thead><tr><th>#</th><th>By</th><th>Reason</th><th>Summary</th><th>When</th></tr></thead>
          <tbody>
            ${versions.versions
              .map(
                (v) => `<tr><td>${v.version_number}${v.is_current ? " (current)" : ""}</td>
                  <td>${escapeHtml(v.created_by_type)}</td><td>${escapeHtml(v.creation_reason)}</td>
                  <td>${escapeHtml(v.change_summary || "")}</td><td>${new Date(v.created_at).toLocaleString()}</td></tr>`
              )
              .join("")}
          </tbody>
        </table>

        <h3>Audit timeline</h3>
        <table>
          <tbody>
            ${detail.audit_timeline
              .map(
                (e) => `<tr><td>${new Date(e.created_at).toLocaleString()}</td><td>${escapeHtml(e.event_name)}</td>
                  <td>${escapeHtml(e.actor_type)}${e.actor_id ? " (" + escapeHtml(e.actor_id.slice(0, 8)) + ")" : ""}</td></tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>

      <div class="right">
        <div class="panel">
          <h3>Summary</h3>
          <div>Recipient: <strong>${escapeHtml(detail.recipient_name)}</strong> (${escapeHtml(detail.recipient_email || "")} ${escapeHtml(detail.recipient_phone || "")})</div>
          <div>Payment ref: ${escapeHtml(detail.payment_reference)} · Subtotal ${fmtMoney(detail.subtotal)} · Tax ${fmtMoney(detail.tax_total)}</div>
          <div style="font-size:16px;font-weight:700;margin-top:6px;">Grand total: ${fmtMoney(detail.grand_total)}</div>
          <div class="help-text">${escapeHtml(detail.amount_in_words || "")}</div>

          <h3>Line items</h3>
          <table>
            <thead><tr><th>Description</th><th>Qty</th><th>Rate</th><th>GST%</th><th>Total</th></tr></thead>
            <tbody>
              ${detail.line_items
                .map(
                  (li) => `<tr><td>${escapeHtml(li.description)}</td><td>${li.quantity}</td>
                    <td>${fmtMoney(li.unit_price)}</td><td>${li.gst_rate}%</td><td>${fmtMoney(li.line_total)}</td></tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>

        ${canEdit ? renderEditPanel(detail) : ""}
        ${canEdit ? renderAIPanel(detail) : ""}
        ${renderApprovalPanel(detail, canApprove)}
      </div>
    </div>
  `;

  loadPdfPreview(id, detail.current_version_number);
  wireEditPanel(id, detail);
  wireAIPanel(id, detail);
  wireApprovalPanel(id, detail);
});

async function loadPdfPreview(invoiceId, versionNumber) {
  const frame = document.getElementById("pdf-frame");
  if (!frame) return;
  try {
    const blob = await api(`/api/v1/generated-invoice-deliveries/${invoiceId}/versions/${versionNumber}/pdf`, { raw: true });
    frame.src = URL.createObjectURL(blob);
  } catch {
    frame.outerHTML = '<div class="alert info">No PDF preview available yet (seller identity may not be configured).</div>';
  }
}

function renderEditPanel(detail) {
  return `
    <div class="panel">
      <h3>Manual edit</h3>
      <p class="help-text">Full-replace edit — recalculates totals and creates a new version. Seller identity and invoice number stay read-only.</p>
      <label>Recipient name</label><input id="edit-name" value="${escapeHtml(detail.recipient_name)}" />
      <label>Line item 1 description</label><input id="edit-desc" value="${escapeHtml(detail.line_items[0]?.description || "")}" />
      <label>Line item 1 quantity</label><input id="edit-qty" type="number" step="1" value="${detail.line_items[0]?.quantity || 1}" />
      <label>Notes</label><textarea id="edit-notes"></textarea>
      <button id="edit-submit">Save New Draft Version</button>
      <div id="edit-result"></div>
    </div>`;
}

function wireEditPanel(id, detail) {
  const btn = document.getElementById("edit-submit");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const resultEl = document.getElementById("edit-result");
    try {
      const qty = parseFloat(document.getElementById("edit-qty").value || "1");
      const unitPrice = parseFloat(detail.line_items[0]?.unit_price || 0);
      const gstRate = parseFloat(detail.line_items[0]?.gst_rate || 0);
      const taxable = qty * unitPrice;
      const tax = Math.round(taxable * gstRate) / 100;
      const payload = {
        idempotency_key: "edit-" + id, // ignored by server for PATCH, required by schema shape
        external_reference: detail.external_reference,
        recipient: {
          name: document.getElementById("edit-name").value,
          email: detail.recipient_email, phone: detail.recipient_phone, gstin: detail.recipient_gstin,
          billing_address: detail.billing_address,
          shipping_address: detail.shipping_address,
        },
        payment_or_order_details: {
          payment_reference: detail.payment_reference, payment_date: detail.payment_date, currency: detail.currency,
          tax_inclusive: detail.tax_inclusive, subtotal: taxable, discount_total: 0, tax_total: tax, grand_total: taxable + tax,
          payment_status: "PAID",
        },
        items: [
          {
            description: document.getElementById("edit-desc").value, product_type: "SERVICE",
            hsn_or_sac_code: detail.line_items[0]?.hsn_or_sac_code || "9983", quantity: qty, unit: "Nos",
            unit_price: unitPrice, gst_rate: gstRate,
          },
        ],
        delivery: { requested_channels: detail.requested_channels },
        notes: document.getElementById("edit-notes").value || undefined,
      };
      await api(`/api/v1/generated-invoice-deliveries/${id}`, { method: "PATCH", json: payload });
      location.reload();
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
}

function renderAIPanel(detail) {
  return `
    <div class="panel">
      <h3>AI edit assistant</h3>
      <p class="help-text">Describe the change in plain language. The AI proposes a diff —
      nothing changes until you review and click Apply.</p>
      <textarea id="ai-instruction" placeholder="e.g. Change the first line item description to 'Annual Business Subscription'; do not change any amount or tax."></textarea>
      <button id="ai-generate">Generate Proposal</button>
      <div id="ai-proposal-box"></div>
    </div>`;
}

function wireAIPanel(id, detail) {
  const btn = document.getElementById("ai-generate");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const box = document.getElementById("ai-proposal-box");
    box.innerHTML = '<div class="spinner">Asking the AI assistant…</div>';
    try {
      const instruction = document.getElementById("ai-instruction").value.trim();
      const proposal = await api(`/api/v1/generated-invoice-deliveries/${id}/ai-edit-proposals`, {
        method: "POST", json: { instruction },
      });
      renderProposal(id, proposal, box);
    } catch (e) {
      box.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
}

function renderProposal(invoiceId, proposal, box) {
  const struct = proposal.structured_change_proposal || {};
  const changes = struct.proposed_changes || [];
  const diffHtml = changes
    .map(
      (c) => `<div class="diff-row"><span class="path">${escapeHtml(c.path)}</span>
        <span class="before">${escapeHtml(String(c.current_value ?? "—"))}</span> →
        <span class="after">${escapeHtml(String(c.proposed_value ?? "—"))}</span></div>`
    )
    .join("");

  if (proposal.status === "INVALID" || proposal.status === "FAILED") {
    box.innerHTML = `<div class="alert error">Proposal rejected by backend validation
      (${escapeHtml(proposal.status)}). ${escapeHtml(JSON.stringify(proposal.validation_result || {}))}</div>`;
    return;
  }

  box.innerHTML = `
    <div class="alert info">
      <strong>${escapeHtml(struct.reviewer_summary || proposal.proposed_change_summary || "")}</strong>
      ${struct.requires_clarification ? `<p>${escapeHtml(struct.clarification_question || "")}</p>` : diffHtml}
      ${struct.requires_recalculation ? '<p class="help-text">This will trigger backend recalculation and return to review.</p>' : ""}
      <div style="margin-top:10px;">
        ${!struct.requires_clarification ? `<button class="success" id="ai-apply">Apply Proposal</button>` : ""}
        <button class="danger" id="ai-reject">Reject Proposal</button>
      </div>
    </div>`;

  const applyBtn = document.getElementById("ai-apply");
  if (applyBtn) {
    applyBtn.addEventListener("click", async () => {
      try {
        await api(`/api/v1/generated-invoice-deliveries/${invoiceId}/ai-edit-proposals/${proposal.proposal_id}/apply`, {
          method: "POST",
        });
        location.reload();
      } catch (e) {
        box.innerHTML += `<div class="alert error">${escapeHtml(e.message)}</div>`;
      }
    });
  }
  document.getElementById("ai-reject").addEventListener("click", async () => {
    await api(`/api/v1/generated-invoice-deliveries/${invoiceId}/ai-edit-proposals/${proposal.proposal_id}/reject`, {
      method: "POST", json: { reason: "reviewer rejected" },
    });
    box.innerHTML = '<div class="alert info">Proposal rejected.</div>';
  });
}

function renderApprovalPanel(detail, canApprove) {
  if (!detail.is_approvable) {
    return `<div class="panel"><h3>Approval</h3><p class="help-text">Not available — this invoice is ${escapeHtml(detail.status)}.</p></div>`;
  }
  return `
    <div class="panel">
      <h3>Approval</h3>
      <p class="help-text">Recipient: ${escapeHtml(detail.recipient_name)} · ${escapeHtml(detail.recipient_email || "no email")} ·
        ${escapeHtml(detail.recipient_phone ? detail.recipient_phone.slice(0, 5) + "•••" + detail.recipient_phone.slice(-2) : "no phone")}<br/>
        Channels: ${escapeHtml((detail.requested_channels || []).join(", "))} · Grand total: ${fmtMoney(detail.grand_total)}</p>
      <p class="alert info">Approving locks this version and immediately queues email/WhatsApp delivery. This cannot be undone.</p>
      <textarea id="approve-comment" placeholder="Optional approval comment"></textarea>
      ${canApprove ? `<button class="success" id="approve-btn">Approve &amp; Queue Delivery</button>` :
        `<p class="help-text">Your role cannot approve — needs INVOICE_APPROVER or ADMIN.</p>`}
      <h3>Reject / cancel</h3>
      <input id="reject-reason" placeholder="Reason (required to reject)" />
      <button class="danger" id="reject-btn">Reject</button>
      <button class="secondary" id="cancel-btn">Cancel draft</button>
      <div id="approval-result"></div>
    </div>`;
}

function wireApprovalPanel(id, detail) {
  const approveBtn = document.getElementById("approve-btn");
  if (approveBtn) {
    approveBtn.addEventListener("click", async () => {
      if (!confirm("Approve and queue delivery now? This is irreversible.")) return;
      const resultEl = document.getElementById("approval-result");
      try {
        await api(`/api/v1/generated-invoice-deliveries/${id}/approve`, { method: "POST" });
        resultEl.innerHTML = '<div class="alert success">Approved — delivery queued.</div>';
        setTimeout(() => location.reload(), 800);
      } catch (e) {
        resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
      }
    });
  }
  const rejectBtn = document.getElementById("reject-btn");
  if (rejectBtn) {
    rejectBtn.addEventListener("click", async () => {
      const reason = document.getElementById("reject-reason").value.trim();
      const resultEl = document.getElementById("approval-result");
      if (!reason) {
        resultEl.innerHTML = '<div class="alert error">A reason is required to reject.</div>';
        return;
      }
      try {
        await api(`/api/v1/generated-invoice-deliveries/${id}/reject`, { method: "POST", json: { reason } });
        location.reload();
      } catch (e) {
        resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
      }
    });
  }
  const cancelBtn = document.getElementById("cancel-btn");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", async () => {
      const reason = document.getElementById("reject-reason").value.trim() || undefined;
      try {
        await api(`/api/v1/generated-invoice-deliveries/${id}/cancel`, { method: "POST", json: { reason } });
        location.reload();
      } catch (e) {
        document.getElementById("approval-result").innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
      }
    });
  }
}

// ---------------------------------------------------------------------
// Method A — upload an existing invoice PDF
// ---------------------------------------------------------------------

route("/method-a", async (main) => {
  const data = await api("/api/v1/invoice-deliveries");
  main.innerHTML = `
    <h1>Upload Existing Invoice (Method A)</h1>
    <div class="panel">
      <h3>Upload</h3>
      <label>Invoice PDF</label><input id="ma-file" type="file" accept="application/pdf" />
      <div class="row">
        <div class="col"><label>Recipient name</label><input id="ma-name" /></div>
        <div class="col"><label>Recipient email</label><input id="ma-email" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Recipient phone (E.164)</label><input id="ma-phone" /></div>
        <div class="col"><label>External reference</label><input id="ma-extref" /></div>
      </div>
      <label>Channels</label>
      <div><label style="display:inline;"><input type="checkbox" id="ma-email-ch" checked style="width:auto;" /> Email</label>
      &nbsp;&nbsp;<label style="display:inline;"><input type="checkbox" id="ma-wa-ch" style="width:auto;" /> WhatsApp</label></div>
      <label><input type="checkbox" id="ma-approval" style="width:auto;display:inline;" /> Require human approval before sending</label>
      <button id="ma-submit">Upload &amp; ${""}<span id="ma-submit-label">Send</span></button>
      <div id="ma-result"></div>
    </div>
    <div class="panel">
      <h3>Recent uploads</h3>
      <table>
        <thead><tr><th>Delivery</th><th>Recipient</th><th>Channels</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${data.deliveries
            .map(
              (d) => `<tr>
                <td>${escapeHtml(d.invoice_number || d.delivery_id.slice(0, 8))}</td>
                <td>${escapeHtml(d.recipient_name)} (${escapeHtml(d.recipient_email || "")})</td>
                <td>${escapeHtml((d.requested_channels || []).join(", "))}</td>
                <td><span class="badge ${badgeClass(d.status)}">${d.status}</span></td>
                <td>${d.status === "DRAFT_REVIEW_REQUIRED" && hasRole("DELIVERY_MANAGER") ? `<button data-id="${d.delivery_id}" class="approve-delivery-btn">Approve</button>` : ""}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById("ma-approval").addEventListener("change", (e) => {
    document.getElementById("ma-submit-label").textContent = e.target.checked ? "Hold for Review" : "Send";
  });

  document.querySelectorAll(".approve-delivery-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/v1/invoice-deliveries/${btn.dataset.id}/approve`, { method: "POST" });
      location.reload();
    });
  });

  document.getElementById("ma-submit").addEventListener("click", async () => {
    const resultEl = document.getElementById("ma-result");
    const fileInput = document.getElementById("ma-file");
    if (!fileInput.files.length) {
      resultEl.innerHTML = '<div class="alert error">Choose a PDF file first.</div>';
      return;
    }
    const channels = [];
    if (document.getElementById("ma-email-ch").checked) channels.push("email");
    if (document.getElementById("ma-wa-ch").checked) channels.push("whatsapp");
    const form = new FormData();
    form.append("invoice_file", fileInput.files[0]);
    form.append("recipient_name", document.getElementById("ma-name").value);
    form.append("recipient_email", document.getElementById("ma-email").value);
    form.append("recipient_phone", document.getElementById("ma-phone").value);
    form.append("external_reference", document.getElementById("ma-extref").value);
    form.append("idempotency_key", "ui-" + Date.now());
    form.append("require_human_approval", document.getElementById("ma-approval").checked ? "true" : "false");
    channels.forEach((c) => form.append("requested_channels", c));
    try {
      const resp = await api("/api/v1/invoice-deliveries", { method: "POST", form });
      resultEl.innerHTML = `<div class="alert success">Uploaded — status ${escapeHtml(resp.status)}.</div>`;
      setTimeout(() => location.reload(), 800);
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------
// Product catalog admin
// ---------------------------------------------------------------------

route("/catalog", async (main) => {
  const data = await api("/api/v1/product-catalog?active_only=false");
  main.innerHTML = `
    <h1>Product / Tax Catalog</h1>
    <p class="help-text">This is the only source the AI is allowed to use for HSN/SAC and GST rate —
    it never invents these. Have your GST/finance professional approve every entry.</p>
    <div class="panel">
      <h3>Add item</h3>
      <div class="row">
        <div class="col"><label>Internal reference (code)</label><input id="cat-ref" placeholder="ANNUAL-PLAN" /></div>
        <div class="col"><label>Display description</label><input id="cat-desc" placeholder="Annual Premium Plan" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Type</label><select id="cat-type"><option value="SERVICE">SERVICE</option><option value="GOODS">GOODS</option></select></div>
        <div class="col"><label>HSN/SAC</label><input id="cat-hsn" placeholder="9983" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Unit</label><input id="cat-unit" placeholder="Year" /></div>
        <div class="col"><label>Unit price (₹)</label><input id="cat-price" type="number" step="0.01" placeholder="2999.00" /></div>
        <div class="col"><label>GST rate (%)</label><input id="cat-gst" type="number" step="0.01" placeholder="18.00" /></div>
      </div>
      <label>Aliases (comma-separated)</label><input id="cat-aliases" placeholder="annual plan, premium yearly" />
      <button id="cat-submit">Add to catalog</button>
      <div id="cat-result"></div>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Code</th><th>Description</th><th>HSN/SAC</th><th>Price</th><th>GST%</th><th>Active</th></tr></thead>
        <tbody>
          ${data.items
            .map(
              (i) => `<tr><td>${escapeHtml(i.internal_reference)}</td><td>${escapeHtml(i.display_description)}</td>
                <td>${escapeHtml(i.hsn_or_sac_code)}</td><td>${fmtMoney(i.unit_price)}</td><td>${i.gst_rate}%</td>
                <td>${i.active ? "Yes" : "No"}</td></tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
  document.getElementById("cat-submit").addEventListener("click", async () => {
    const resultEl = document.getElementById("cat-result");
    try {
      await api("/api/v1/product-catalog", {
        method: "POST",
        json: {
          internal_reference: document.getElementById("cat-ref").value,
          display_description: document.getElementById("cat-desc").value,
          product_type: document.getElementById("cat-type").value,
          hsn_or_sac_code: document.getElementById("cat-hsn").value,
          unit: document.getElementById("cat-unit").value,
          unit_price: parseFloat(document.getElementById("cat-price").value || "0"),
          gst_rate: parseFloat(document.getElementById("cat-gst").value || "0"),
          active: true,
          aliases: document.getElementById("cat-aliases").value.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean),
        },
      });
      location.reload();
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------
// Customer directory admin
// ---------------------------------------------------------------------

route("/customers", async (main) => {
  const data = await api("/api/v1/customers");
  main.innerHTML = `
    <h1>Customer Directory</h1>
    <p class="help-text">Not a CRM — just enough to avoid re-typing a returning customer's details into Quick Create.</p>
    <div class="panel">
      <h3>Add customer</h3>
      <div class="row">
        <div class="col"><label>Display name</label><input id="cu-name" /></div>
        <div class="col"><label>Email</label><input id="cu-email" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Phone (E.164)</label><input id="cu-phone" /></div>
        <div class="col"><label>GSTIN (optional)</label><input id="cu-gstin" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Billing address line 1</label><input id="cu-line1" /></div>
        <div class="col"><label>City</label><input id="cu-city" /></div>
      </div>
      <div class="row">
        <div class="col"><label>State</label><input id="cu-state" /></div>
        <div class="col"><label>State code</label><input id="cu-statecode" placeholder="27" /></div>
        <div class="col"><label>Postal code</label><input id="cu-postal" /></div>
      </div>
      <button id="cu-submit">Save customer</button>
      <div id="cu-result"></div>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>State</th></tr></thead>
        <tbody>
          ${data.customers
            .map(
              (c) => `<tr><td>${escapeHtml(c.display_name)}</td><td>${escapeHtml(c.email || "")}</td>
                <td>${escapeHtml(c.phone || "")}</td><td>${escapeHtml(c.state_name || "")}</td></tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
  document.getElementById("cu-submit").addEventListener("click", async () => {
    const resultEl = document.getElementById("cu-result");
    try {
      await api("/api/v1/customers", {
        method: "POST",
        json: {
          display_name: document.getElementById("cu-name").value,
          email: document.getElementById("cu-email").value || undefined,
          phone: document.getElementById("cu-phone").value || undefined,
          gstin: document.getElementById("cu-gstin").value || undefined,
          state_name: document.getElementById("cu-state").value || undefined,
          state_code: document.getElementById("cu-statecode").value || undefined,
          billing_address: {
            line1: document.getElementById("cu-line1").value,
            city: document.getElementById("cu-city").value,
            state: document.getElementById("cu-state").value,
            state_code: document.getElementById("cu-statecode").value,
            postal_code: document.getElementById("cu-postal").value,
            country: "India",
          },
        },
      });
      location.reload();
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------
// Users admin (ADMIN only)
// ---------------------------------------------------------------------

route("/users", async (main) => {
  if (!hasRole("ADMIN")) {
    main.innerHTML = '<div class="alert error">Admins only.</div>';
    return;
  }
  const data = await api("/api/v1/users");
  const allRoles = ["ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER", "INVOICE_EDITOR", "INVOICE_APPROVER"];
  main.innerHTML = `
    <h1>Users</h1>
    <div class="panel">
      <h3>Create user</h3>
      <div class="row">
        <div class="col"><label>Email</label><input id="u-email" /></div>
        <div class="col"><label>Display name</label><input id="u-name" /></div>
      </div>
      <label>Password (min 8 chars)</label><input id="u-password" type="password" />
      <label>Roles</label>
      <div>${allRoles.map((r) => `<label style="display:inline-block;margin-right:12px;"><input type="checkbox" class="u-role" value="${r}" style="width:auto;" /> ${r}</label>`).join("")}</div>
      <button id="u-submit">Create user</button>
      <div id="u-result"></div>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Email</th><th>Name</th><th>Roles</th></tr></thead>
        <tbody>
          ${data.users.map((u) => `<tr><td>${escapeHtml(u.email)}</td><td>${escapeHtml(u.display_name)}</td><td>${escapeHtml(u.roles.join(", "))}</td></tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
  document.getElementById("u-submit").addEventListener("click", async () => {
    const resultEl = document.getElementById("u-result");
    const roles = Array.from(document.querySelectorAll(".u-role:checked")).map((el) => el.value);
    try {
      await api("/api/v1/users", {
        method: "POST",
        json: {
          email: document.getElementById("u-email").value,
          display_name: document.getElementById("u-name").value,
          password: document.getElementById("u-password").value,
          roles,
        },
      });
      location.reload();
    } catch (e) {
      resultEl.innerHTML = `<div class="alert error">${escapeHtml(e.message)}</div>`;
    }
  });
});

// ---------------------------------------------------------------------

render();
