/**
 * Research Assistant – frontend
 * Talks to the FastAPI backend at /api/research
 */

// Same origin when served by backend on :8000; otherwise point at backend
const API_BASE =
  (window.location.port === "8000")
    ? ""
    : (window.location.protocol === "file:" || window.location.port === "5500")
      ? "http://localhost:8000"
      : "";

const $ = (sel) => document.querySelector(sel);

const els = {
  topic: $("#topic"),
  provider: $("#provider"),
  model: $("#model"),
  maxTurns: $("#max-turns"),
  runBtn: $("#run-btn"),
  btnText: $(".btn-text"),
  btnSpinner: $(".btn-spinner"),
  placeholder: $("#placeholder"),
  error: $("#error"),
  report: $("#report"),
  meta: $("#meta"),
  copyBtn: $("#copy-btn"),
  statusBadge: $("#status-badge"),
  apiUrl: $("#api-url"),
};

els.apiUrl.textContent = API_BASE || window.location.origin;

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      els.statusBadge.textContent = "Backend online";
      els.statusBadge.className = "badge badge-online";
      return true;
    }
  } catch (_) {}
  els.statusBadge.textContent = "Backend offline";
  els.statusBadge.className = "badge badge-offline";
  return false;
}

checkHealth();
setInterval(checkHealth, 15000);

// ---------------------------------------------------------------------------
// Minimal markdown → HTML (headings, lists, links, bold, paragraphs)
// ---------------------------------------------------------------------------

function mdToHtml(md) {
  if (!md) return "";

  // Escape HTML first
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code spans
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Links [text](url) and bare URLs
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>'
  );
  html = html.replace(
    /(^|[\s(])(https?:\/\/[^\s)<]+)/g,
    '$1<a href="$2" target="_blank" rel="noopener">$2</a>'
  );

  // Headings
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Unordered lists
  html = html.replace(/^(?:- |\* )(.+)(?:\n(?:- |\* ).+)*/gm, (block) => {
    const items = block
      .split("\n")
      .map((line) => line.replace(/^(?:- |\* )/, "").trim())
      .filter(Boolean)
      .map((item) => `<li>${item}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  });

  // Numbered lists (simple)
  html = html.replace(/^\d+\. (.+)(?:\n\d+\. .+)*/gm, (block) => {
    const items = block
      .split("\n")
      .map((line) => line.replace(/^\d+\. /, "").trim())
      .filter(Boolean)
      .map((item) => `<li>${item}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  });

  // Paragraphs – split on blank lines, skip blocks that are already tags
  const parts = html.split(/\n{2,}/);
  html = parts
    .map((p) => {
      p = p.trim();
      if (!p) return "";
      if (/^<(h[1-3]|ul|ol|li|p)/.test(p)) return p;
      // single newlines → <br>
      return `<p>${p.replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");

  return html;
}

// ---------------------------------------------------------------------------
// Run research
// ---------------------------------------------------------------------------

async function runResearch() {
  const topic = els.topic.value.trim();
  if (!topic) {
    showError("Please enter a research topic.");
    return;
  }

  setLoading(true);
  hideError();
  els.placeholder.classList.add("hidden");
  els.report.classList.add("hidden");
  els.meta.classList.add("hidden");
  els.copyBtn.classList.add("hidden");

  const body = {
    topic,
    provider: els.provider.value,
    max_turns: Number(els.maxTurns.value) || 12,
    verbose: false,
  };
  if (els.model.value.trim()) {
    body.model = els.model.value.trim();
  }

  try {
    const res = await fetch(`${API_BASE}/api/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const detail = data.detail || res.statusText || "Request failed";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    els.report.innerHTML = mdToHtml(data.report);
    els.report.classList.remove("hidden");
    els.copyBtn.classList.remove("hidden");
    els.copyBtn.dataset.raw = data.report;

    els.meta.innerHTML = `
      <span>Provider: <strong>${escapeHtml(data.provider)}</strong></span>
      <span>Model: <strong>${escapeHtml(data.model || "default")}</strong></span>
    `;
    els.meta.classList.remove("hidden");
  } catch (err) {
    showError(err.message || String(err));
    els.placeholder.classList.remove("hidden");
  } finally {
    setLoading(false);
  }
}

function setLoading(on) {
  els.runBtn.disabled = on;
  els.btnText.textContent = on ? "Researching…" : "Start Research";
  els.btnSpinner.classList.toggle("hidden", !on);
}

function showError(msg) {
  els.error.textContent = msg;
  els.error.classList.remove("hidden");
}

function hideError() {
  els.error.classList.add("hidden");
  els.error.textContent = "";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

els.runBtn.addEventListener("click", runResearch);

els.topic.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    runResearch();
  }
});

els.copyBtn.addEventListener("click", async () => {
  const raw = els.copyBtn.dataset.raw || els.report.innerText;
  try {
    await navigator.clipboard.writeText(raw);
    els.copyBtn.textContent = "Copied!";
    setTimeout(() => (els.copyBtn.textContent = "Copy"), 1500);
  } catch {
    els.copyBtn.textContent = "Failed";
    setTimeout(() => (els.copyBtn.textContent = "Copy"), 1500);
  }
});
