/**
 * Vidnex API Module
 * Connects the static frontend to the Django REST API backend.
 * Replaces auth.js localStorage implementation with real HTTP calls.
 *
 * Token stored as: localStorage.vidnex_token
 * Cached user:     localStorage.vidnex_user  (JSON)
 */

const AuthModule = (() => {
  const BASE_URL = window.VIDNEX_API_URL || "http://127.0.0.1:8000";
  const TOKEN_KEY = "vidnex_token";
  const USER_KEY = "vidnex_user";

  // ─── Helpers ────────────────────────────────────────────────────────────────

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || null;
  }

  function authHeaders() {
    const token = getToken();
    const h = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = "Token " + token;
    return h;
  }

  async function apiFetch(path, options = {}) {
    const url = BASE_URL + path;
    const res = await fetch(url, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) },
    });
    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await res.json();
    }
    if (!res.ok) {
      const msg =
        data && (data.error || data.detail || data.message) ||
        "Request failed (" + res.status + ")";
      return { success: false, error: msg, status: res.status, data };
    }
    return { success: true, data };
  }

  function readCachedUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  function cacheUser(userObj) {
    if (userObj) {
      localStorage.setItem(USER_KEY, JSON.stringify(userObj));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  // ─── Sync helpers (read from cache only) ────────────────────────────────────

  function getCurrentUser() {
    return readCachedUser();
  }

  function isLoggedIn() {
    return !!(getToken() && readCachedUser());
  }

  function getUserProfile(email) {
    // Synchronous: returns cached user if email matches, else null
    const u = readCachedUser();
    if (!u) return null;
    if (email && u.email.toLowerCase() !== email.toLowerCase()) return null;
    return u;
  }

  function isResearcherVerified(user) {
    const u = user || readCachedUser();
    return u && u.status === "approved";
  }

  function canBidOnProjects(user) {
    const u = user || readCachedUser();
    return !!(u && u.status === "approved" && u.role !== "admin");
  }

  function isValidGmail(email) {
    if (typeof email !== "string") return false;
    return /^[a-zA-Z0-9._%-]+@gmail\.com$/.test(email.toLowerCase());
  }

  // ─── Auth ───────────────────────────────────────────────────────────────────

  async function register(data) {
    const res = await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: data.fullName || data.full_name || data.name || "",
        email: data.email || "",
        password: data.password || "",
        password_confirm: data.passwordConfirm || data.password_confirm || data.password || "",
        role: data.role || "researcher",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  async function login(email, password) {
    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (!res.success) return { success: false, error: res.error };
    const { token, user } = res.data;
    localStorage.setItem(TOKEN_KEY, token);
    cacheUser(user);
    return { success: true, user };
  }

  async function logout() {
    await apiFetch("/api/auth/logout", { method: "POST" });
    clearSession();
    return { success: true };
  }

  async function refreshMe() {
    const res = await apiFetch("/api/auth/me");
    if (!res.success) return null;
    cacheUser(res.data);
    return res.data;
  }

  async function updateProfile(data) {
    const res = await apiFetch("/api/profile/update", {
      method: "POST",
      body: JSON.stringify({
        bio: data.bio || "",
        phone: data.phone || "",
        full_name: data.fullName || data.full_name || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    await refreshMe();
    return { success: true };
  }

  // ─── Verification ────────────────────────────────────────────────────────────

  async function submitResearcherVerification(formData) {
    // formData: { workCompany, workRole, workYears, educationDegree, educationUniversity, educationYear,
    //             resumeFile, certificatesFile, idProofFile }
    const toBase64 = (file) => new Promise((resolve, reject) => {
      if (!file) { resolve(null); return; }
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

    let resumeData = null, certData = null, idData = null;
    if (formData.resumeFile) resumeData = await toBase64(formData.resumeFile);
    if (formData.certificatesFile) certData = await toBase64(formData.certificatesFile);
    if (formData.idProofFile) idData = await toBase64(formData.idProofFile);

    const res = await apiFetch("/api/verification/submit", {
      method: "POST",
      body: JSON.stringify({
        work_company: formData.workCompany || "",
        work_role: formData.workRole || "",
        work_years: parseInt(formData.workYears, 10) || 0,
        education_degree: formData.educationDegree || "",
        education_university: formData.educationUniversity || "",
        education_year: parseInt(formData.educationYear, 10) || 0,
        resume_data: resumeData,
        resume_name: formData.resumeFile ? formData.resumeFile.name : null,
        certificates_data: certData,
        certificates_name: formData.certificatesFile ? formData.certificatesFile.name : null,
        id_proof_data: idData,
        id_proof_name: formData.idProofFile ? formData.idProofFile.name : null,
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    await refreshMe();
    return { success: true };
  }

  // ─── Projects ───────────────────────────────────────────────────────────────

  async function getProjects() {
    const res = await apiFetch("/api/projects");
    if (!res.success) return [];
    return res.data || [];
  }

  // ─── Bids ────────────────────────────────────────────────────────────────────

  async function placeBid(projectId, amount, proposalNote) {
    const res = await apiFetch("/api/bids/place", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        amount: parseFloat(amount),
        proposal_note: proposalNote || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true, bid: res.data };
  }

  async function getUserBids() {
    const res = await apiFetch("/api/bids/my");
    if (!res.success) return [];
    return res.data || [];
  }

  async function getAllBids() {
    const res = await apiFetch("/api/bids/all");
    if (!res.success) return [];
    return res.data || [];
  }

  async function updateBidStatus(bidId, status, extra = {}) {
    const res = await apiFetch("/api/bids/" + bidId + "/status", {
      method: "POST",
      body: JSON.stringify({
        status,
        timeline: extra.timeline || "",
        project_details: extra.projectDetails || extra.project_details || "",
        expected_submission_date: extra.expectedSubmissionDate || extra.expected_submission_date || "",
        allocated_earning: extra.allocatedEarning != null ? parseFloat(extra.allocatedEarning) : undefined,
        rejection_reason: extra.rejectionReason || extra.rejection_reason || "",
        review_comment: extra.reviewComment || extra.review_comment || "",
        review_status: extra.reviewStatus || extra.review_status || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true, data: res.data };
  }

  // ─── Assignments ─────────────────────────────────────────────────────────────

  async function getAssignedProjects() {
    const res = await apiFetch("/api/assignments/my");
    if (!res.success) return [];
    return res.data || [];
  }

  async function submitProjectDeliverable(assignmentId, responseText, file) {
    let fileData = null, fileName = null;
    if (file) {
      fileName = file.name;
      fileData = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }
    const res = await apiFetch("/api/assignments/" + assignmentId + "/submit", {
      method: "POST",
      body: JSON.stringify({
        response: responseText || "",
        file_name: fileName,
        file_data: fileData,
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  async function reviewProjectSubmission(assignmentId, reviewStatus, reviewComment, earningAmount) {
    const res = await apiFetch("/api/assignments/" + assignmentId + "/review", {
      method: "POST",
      body: JSON.stringify({
        review_status: reviewStatus,
        review_comment: reviewComment || "",
        earning_amount: earningAmount != null ? parseFloat(earningAmount) : undefined,
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  // ─── Earnings & Withdrawals ──────────────────────────────────────────────────

  async function getEarningsSummary() {
    const res = await apiFetch("/api/earnings");
    if (!res.success) return { total: 0, pending: 0, withdrawn: 0, available: 0 };
    return res.data.summary || res.data;
  }

  async function getTransactions() {
    const res = await apiFetch("/api/earnings");
    if (!res.success) return [];
    return res.data.transactions || [];
  }

  async function createWithdrawRequest(amount, paymentMethod, paymentDetails) {
    const res = await apiFetch("/api/withdraw/request", {
      method: "POST",
      body: JSON.stringify({
        amount: parseFloat(amount),
        payment_method: paymentMethod,
        payment_details: paymentDetails || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  async function getWithdrawRequests() {
    const res = await apiFetch("/api/withdraw/my");
    if (!res.success) return [];
    return res.data || [];
  }

  async function getAllWithdrawRequests() {
    const res = await apiFetch("/api/admin/withdrawals");
    if (!res.success) return [];
    return res.data || [];
  }

  async function processWithdrawRequest(withdrawId, action, rejectionReason) {
    const res = await apiFetch("/api/admin/withdrawals/" + withdrawId + "/process", {
      method: "POST",
      body: JSON.stringify({
        action,
        rejection_reason: rejectionReason || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  // ─── System Mails ───────────────────────────────────────────────────────────

  async function getUserMails() {
    const res = await apiFetch("/api/mails");
    if (!res.success) return [];
    return res.data || [];
  }

  async function markMailRead(email, mailId) {
    const res = await apiFetch("/api/mails/" + mailId + "/read", { method: "POST" });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  async function markAllMailsRead() {
    const res = await apiFetch("/api/mails/read-all", { method: "POST" });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  // ─── Admin ───────────────────────────────────────────────────────────────────

  async function getPendingResearchers() {
    const res = await apiFetch("/api/admin/pending-users");
    if (!res.success) return [];
    return res.data || [];
  }

  async function verifyResearcher(email, action, rejectionReason) {
    // action: "approve" | "reject"
    const res = await apiFetch("/api/admin/verify-user", {
      method: "POST",
      body: JSON.stringify({
        email,
        action,
        rejection_reason: rejectionReason || "",
      }),
    });
    if (!res.success) return { success: false, error: res.error };
    return { success: true };
  }

  // ─── Public API ─────────────────────────────────────────────────────────────

  return {
    // Sync (cache-based)
    getCurrentUser,
    isLoggedIn,
    getUserProfile,
    isResearcherVerified,
    canBidOnProjects,
    isValidGmail,

    // Async auth
    register,
    login,
    logout,
    refreshMe,
    updateProfile,

    // Async verification
    submitResearcherVerification,

    // Async projects
    getProjects,

    // Async bids
    placeBid,
    getUserBids,
    getAllBids,
    updateBidStatus,

    // Async assignments
    getAssignedProjects,
    submitProjectDeliverable,
    reviewProjectSubmission,

    // Async earnings & withdrawals
    getEarningsSummary,
    getTransactions,
    createWithdrawRequest,
    getWithdrawRequests,
    getAllWithdrawRequests,
    processWithdrawRequest,

    // Async mails
    getUserMails,
    markMailRead,
    markAllMailsRead,

    // Async admin
    getPendingResearchers,
    verifyResearcher,
  };
})();
