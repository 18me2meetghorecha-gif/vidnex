const statusBadge = document.getElementById("statusBadge");
const verificationNotice = document.getElementById("verificationNotice");
const welcomeName = document.getElementById("welcomeName");
const projectsList = document.getElementById("projectsList");
const myBidsList = document.getElementById("myBidsList");
const transactionsList = document.getElementById("transactionsList");
const withdrawList = document.getElementById("withdrawList");
const withdrawForm = document.getElementById("withdrawForm");
const withdrawMsg = document.getElementById("withdrawMsg");
const logoutBtn = document.getElementById("logoutBtn");

const tabButtons = document.querySelectorAll(".side-link");
const tabs = document.querySelectorAll(".tab-content");

let currentUser = null;

function currency(v) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(v || 0));
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const tab = button.getAttribute("data-tab");
    tabButtons.forEach((b) => b.classList.remove("active"));
    tabs.forEach((t) => t.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`tab-${tab}`).classList.add("active");
  });
});

logoutBtn.addEventListener("click", async () => {
  await apiRequest("/api/auth/logout", { method: "POST" });
  window.location.href = "/login/";
});

async function loadUser() {
  currentUser = await apiRequest("/api/auth/me");
  welcomeName.textContent = `Welcome, ${currentUser.full_name}`;
  statusBadge.textContent = currentUser.status.replace("_", " ");
  statusBadge.className = `status ${statusClass(currentUser.status)}`;

  if (currentUser.role === "admin") {
    window.location.href = "/admin-dashboard/";
    return;
  }

  const verified = currentUser.status === "verified";
  if (!verified) {
    verificationNotice.classList.remove("hidden");
  }

  return verified;
}

async function loadProjects(verified) {
  const items = await apiRequest("/api/projects");
  projectsList.innerHTML = "";

  if (!items.length) {
    projectsList.innerHTML = "<p class='muted'>No active projects.</p>";
    return;
  }

  items.forEach((project) => {
    const card = document.createElement("article");
    card.className = "project-card";
    card.innerHTML = `
      <h4>${project.title}</h4>
      <p>${project.description}</p>
      <p class="muted">Budget: ${currency(project.min_budget)} - ${currency(project.max_budget)}</p>
      <form class="bid-form">
        <div class="inline">
          <input type="number" name="amount" step="0.01" min="1" placeholder="Bid Amount" required ${verified ? "" : "disabled"} />
          <button class="btn btn-primary" type="submit" ${verified ? "" : "disabled"}>Place Bid</button>
        </div>
        <textarea name="proposal_note" rows="2" placeholder="Proposal note" ${verified ? "" : "disabled"}></textarea>
      </form>
    `;

    const form = card.querySelector(".bid-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      try {
        await apiRequest("/api/bids/place", {
          method: "POST",
          body: JSON.stringify({
            project_id: project.id,
            amount: data.get("amount"),
            proposal_note: data.get("proposal_note"),
          }),
        });
        await loadMyBids();
      } catch (error) {
        alert(error.message);
      }
    });

    projectsList.appendChild(card);
  });
}

async function loadMyBids() {
  const bids = await apiRequest("/api/bids/my");
  myBidsList.innerHTML = "";
  if (!bids.length) {
    myBidsList.innerHTML = "<p class='muted'>No bids yet.</p>";
    return;
  }

  bids.forEach((bid) => {
    const row = document.createElement("article");
    row.className = "bid-item";
    row.innerHTML = `<strong>${bid.project_title}</strong><p>Amount: ${currency(bid.amount)} | Status: ${bid.status}</p>`;
    myBidsList.appendChild(row);
  });
}

async function loadEarnings(verified) {
  if (!verified) {
    document.getElementById("earnTotal").textContent = "0";
    document.getElementById("earnPending").textContent = "0";
    document.getElementById("earnWithdrawn").textContent = "0";
    transactionsList.innerHTML = "<p class='muted'>Your account is under verification.</p>";
    return;
  }

  const result = await apiRequest("/api/earnings");
  document.getElementById("earnTotal").textContent = currency(result.summary.total);
  document.getElementById("earnPending").textContent = currency(result.summary.pending);
  document.getElementById("earnWithdrawn").textContent = currency(result.summary.withdrawn);

  transactionsList.innerHTML = "";
  if (!result.transactions.length) {
    transactionsList.innerHTML = "<p class='muted'>No transactions yet.</p>";
  } else {
    result.transactions.forEach((t) => {
      const node = document.createElement("article");
      node.className = "tx-item";
      node.innerHTML = `<strong>${t.txn_type.toUpperCase()}</strong><p>${currency(t.amount)} | ${t.status}</p>`;
      transactionsList.appendChild(node);
    });
  }
}

async function loadWithdrawRequests() {
  const rows = await apiRequest("/api/withdraw/my");
  withdrawList.innerHTML = "";
  if (!rows.length) {
    withdrawList.innerHTML = "<p class='muted'>No withdraw requests yet.</p>";
    return;
  }
  rows.forEach((r) => {
    const node = document.createElement("article");
    node.className = "withdraw-item";
    node.innerHTML = `<strong>${currency(r.amount)}</strong><p>${r.payment_method.toUpperCase()} | ${r.status}</p>`;
    withdrawList.appendChild(node);
  });
}

withdrawForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(withdrawForm);
  try {
    await apiRequest("/api/withdraw/request", {
      method: "POST",
      body: JSON.stringify({
        amount: data.get("amount"),
        payment_method: data.get("payment_method"),
        payment_details: data.get("payment_details"),
      }),
    });
    showMsg(withdrawMsg, "success", "Withdraw request submitted.");
    withdrawForm.reset();
    await loadEarnings(true);
    await loadWithdrawRequests();
  } catch (error) {
    showMsg(withdrawMsg, "error", error.message);
  }
});

(async function init() {
  try {
    const verified = await loadUser();
    await loadProjects(verified);
    await loadMyBids();
    await loadEarnings(verified);
    await loadWithdrawRequests();

    if (!verified) {
      withdrawForm.querySelectorAll("input, textarea, select, button").forEach((el) => {
        el.disabled = true;
      });
    }
  } catch (error) {
    window.location.href = "/login/";
  }
})();
