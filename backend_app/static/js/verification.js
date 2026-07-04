const verifyForm = document.getElementById("verificationForm");
const verifyMsg = document.getElementById("verifyMsg");
const statusBadge = document.getElementById("statusBadge");
const rejectionBox = document.getElementById("rejectionBox");
const logoutBtn = document.getElementById("logoutBtn");

logoutBtn.addEventListener("click", async () => {
  await apiRequest("/api/auth/logout", { method: "POST" });
  window.location.href = "/login/";
});

async function loadStatus() {
  const result = await apiRequest("/api/verification/status");
  statusBadge.textContent = result.status.replace("_", " ");
  statusBadge.className = `status ${statusClass(result.status)}`;

  if (result.status === "rejected" && result.rejection_reason) {
    rejectionBox.textContent = `Rejected: ${result.rejection_reason}`;
    rejectionBox.classList.remove("hidden");
  }

  if (result.details) {
    verifyForm.work_company.value = result.details.work_company || "";
    verifyForm.work_role.value = result.details.work_role || "";
    verifyForm.work_years.value = result.details.work_years || "";
    verifyForm.education_degree.value = result.details.education_degree || "";
    verifyForm.education_university.value = result.details.education_university || "";
    verifyForm.education_year.value = result.details.education_year || "";
  }
}

verifyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = new FormData(verifyForm);

  try {
    await apiRequest("/api/verification/submit", {
      method: "POST",
      body: payload,
    });
    showMsg(verifyMsg, "success", "Verification submitted. Redirecting to dashboard...");
    setTimeout(() => {
      window.location.href = "/dashboard/";
    }, 900);
  } catch (error) {
    showMsg(verifyMsg, "error", error.message);
  }
});

loadStatus().catch(() => {
  window.location.href = "/login/";
});
