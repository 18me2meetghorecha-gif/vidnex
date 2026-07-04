function csrfToken() {
  const node = document.querySelector('meta[name="csrf-token"]');
  return node ? node.getAttribute("content") : "";
}

async function apiRequest(url, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  headers["X-CSRFToken"] = csrfToken();

  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers,
  });

  let payload = {};
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (_) {
      payload = { detail: text };
    }
  }

  if (!response.ok) {
    const detail = payload.detail || payload.error || "Request failed";
    throw new Error(detail);
  }

  return payload;
}

function showMsg(node, type, text) {
  node.className = `form-message ${type}`;
  node.textContent = text;
}

function statusClass(value) {
  if (value === "verified") return "verified";
  if (value === "rejected") return "rejected";
  return "pending";
}
