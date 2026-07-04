const pendingUsersList = document.getElementById("pendingUsersList");
const logoutBtn = document.getElementById("logoutBtn");

logoutBtn.addEventListener("click", async () => {
  await apiRequest("/api/auth/logout", { method: "POST" });
  window.location.href = "/login/";
});

async function processUser(id, action, reason, feedbackNode) {
  try {
    const payload = action === "reject" ? { reason } : {};

    await apiRequest(`/api/admin/users/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    feedbackNode.className = "form-message success";
    feedbackNode.textContent = action === "approve" ? "User approved successfully." : "User rejected successfully.";
    await loadPendingUsers();
  } catch (error) {
    feedbackNode.className = "form-message error";
    feedbackNode.textContent = error.message;
  }
}

async function loadPendingUsers() {
  const rows = await apiRequest("/api/admin/pending-users");
  pendingUsersList.innerHTML = "";

  if (!rows.length) {
    pendingUsersList.innerHTML = "<p class='muted'>No users pending verification.</p>";
    return;
  }

  rows.forEach((row) => {
    const item = document.createElement("article");
    item.className = "pending-item";
    const u = row.user;
    const v = row.verification;

    item.innerHTML = `
      <h3>${u.full_name}</h3>
      <p>${u.email}</p>
      <p class="muted">Applied: ${new Date(u.date_joined).toLocaleString()}</p>
      ${v ? `
        <p><strong>Work:</strong> ${v.work_company} | ${v.work_role} (${v.work_years} years)</p>
        <p><strong>Education:</strong> ${v.education_degree}, ${v.education_university} (${v.education_year})</p>
        <p><a href="${v.resume}" target="_blank">Resume</a> | <a href="${v.certificates}" target="_blank">Certificates</a> | <a href="${v.id_proof}" target="_blank">ID Proof</a></p>
      ` : "<p class='muted'>No verification submission yet.</p>"}
      <div class="admin-action-form stack">
        <label>Rejection reason (required only when rejecting)
          <textarea class="reject-reason" rows="2" placeholder="Reason for rejection"></textarea>
        </label>
        <div class="inline">
          <button class="btn btn-primary approve-btn" type="button">Approve</button>
          <button class="btn btn-ghost reject-btn" type="button">Reject</button>
        </div>
        <div class="action-feedback hidden"></div>
      </div>
    `;

    const reasonBox = item.querySelector(".reject-reason");
    const feedback = item.querySelector(".action-feedback");

    item.querySelector(".approve-btn").addEventListener("click", () => {
      processUser(u.id, "approve", "", feedback);
    });

    item.querySelector(".reject-btn").addEventListener("click", () => {
      const reason = reasonBox.value.trim();
      if (!reason) {
        feedback.className = "form-message error";
        feedback.textContent = "Please enter rejection reason before rejecting.";
        return;
      }
      processUser(u.id, "reject", reason, feedback);
    });

    pendingUsersList.appendChild(item);
  });
}

loadPendingUsers().catch(() => {
  window.location.href = "/login/";
});
