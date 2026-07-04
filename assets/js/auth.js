/**
 * Vidnex Authentication Module
 * Main-site local data/auth module.
 * Handles registration/login, profile verification, project bids, earnings, and withdrawals.
 */

const AuthModule = (() => {
  const STORAGE_KEY = "vidnex_user";
  const USERS_KEY = "vidnex_users";
  const PROJECTS_KEY = "vidnex_projects";
  const BIDS_KEY = "vidnex_bids";
  const ASSIGNMENTS_KEY = "vidnex_project_assignments";
  const MAILS_KEY = "vidnex_mails";
  const LOGIN_GUARD_KEY = "vidnex_login_guard";
  const EARNINGS_KEY = "vidnex_earnings";
  const TRANSACTIONS_KEY = "vidnex_transactions";
  const WITHDRAW_REQUESTS_KEY = "vidnex_withdraw_requests";

  const BID_STATUS = {
    pending: "pending",
    shortlisted: "shortlisted",
    selected: "selected",
    rejected: "rejected",
    allocated: "allocated",
    in_progress: "in_progress",
    submitted: "submitted",
    completed: "completed",
  };

  const MAX_LOGIN_ATTEMPTS = 5;
  const LOGIN_LOCK_MINUTES = 15;

  function uid(prefix) {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function safeText(value, maxLength = 2000) {
    return String(value || "")
      .replace(/[<>]/g, "")
      .trim()
      .slice(0, maxLength);
  }

  function safeEmail(email) {
    return safeText(email, 120).toLowerCase();
  }

  function readList(key) {
    const stored = localStorage.getItem(key);
    if (!stored) return [];
    try {
      return JSON.parse(stored);
    } catch (error) {
      return [];
    }
  }

  function writeList(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function readObject(key) {
    const stored = localStorage.getItem(key);
    if (!stored) return {};
    try {
      const parsed = JSON.parse(stored);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function writeObject(key, value) {
    localStorage.setItem(key, JSON.stringify(value || {}));
  }

  function isValidGmail(email) {
    if (typeof email !== "string") return false;
    const gmailRegex = /^[a-zA-Z0-9._%-]+@gmail\.com$/;
    return gmailRegex.test(email.toLowerCase());
  }

  // Demo-only hashing for local storage. Replace with backend auth in production.
  function hashPassword(password) {
    let hash = 0;
    if (!password) return String(hash);
    for (let i = 0; i < password.length; i++) {
      const char = password.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash &= hash;
    }
    return Math.abs(hash).toString(16);
  }

  function getAllUsers() {
    return readList(USERS_KEY);
  }

  function saveUsers(users) {
    writeList(USERS_KEY, users);
  }

  function saveUser(user) {
    const users = getAllUsers();
    const index = users.findIndex((u) => u.email.toLowerCase() === user.email.toLowerCase());
    if (index >= 0) {
      users[index] = user;
    } else {
      users.push(user);
    }
    saveUsers(users);
  }

  function getUserProfile(email) {
    const users = getAllUsers();
    const targetEmail = safeEmail(email);
    return users.find((u) => u.email.toLowerCase() === targetEmail) || null;
  }

  function getMailStore() {
    return readList(MAILS_KEY);
  }

  function saveMailStore(items) {
    writeList(MAILS_KEY, items);
  }

  function sendSystemMail(email, subject, body, meta = {}) {
    const to = safeEmail(email);
    if (!to) return;

    const items = getMailStore();
    items.push({
      id: uid("mail"),
      to,
      subject: safeText(subject, 150),
      body: safeText(body, 8000),
      read: false,
      createdAt: nowIso(),
      meta,
    });
    saveMailStore(items);
  }

  function getUserMails(email, unreadOnly = false) {
    const to = safeEmail(email);
    return getMailStore()
      .filter((item) => item.to === to && (!unreadOnly || !item.read))
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function markMailRead(email, mailId) {
    const to = safeEmail(email);
    const id = safeText(mailId, 120);
    const items = getMailStore();
    const target = items.find((item) => item.id === id && item.to === to);
    if (!target) {
      return { success: false, error: "Mail not found." };
    }
    target.read = true;
    saveMailStore(items);
    return { success: true };
  }

  function markAllMailsRead(email) {
    const to = safeEmail(email);
    const items = getMailStore();
    items.forEach((item) => {
      if (item.to === to) {
        item.read = true;
      }
    });
    saveMailStore(items);
    return { success: true };
  }

  function getLoginGuardMap() {
    return readObject(LOGIN_GUARD_KEY);
  }

  function saveLoginGuardMap(map) {
    writeObject(LOGIN_GUARD_KEY, map);
  }

  function getGuardEntry(email) {
    const map = getLoginGuardMap();
    return map[safeEmail(email)] || { failedAttempts: 0, lockUntil: null };
  }

  function setGuardEntry(email, entry) {
    const map = getLoginGuardMap();
    map[safeEmail(email)] = entry;
    saveLoginGuardMap(map);
  }

  function resetGuardEntry(email) {
    setGuardEntry(email, { failedAttempts: 0, lockUntil: null });
  }

  function isAccountLocked(email) {
    const entry = getGuardEntry(email);
    if (!entry.lockUntil) {
      return { locked: false, retryAfterMinutes: 0 };
    }

    const now = Date.now();
    const lockUntil = new Date(entry.lockUntil).getTime();
    if (Number.isNaN(lockUntil) || lockUntil <= now) {
      resetGuardEntry(email);
      return { locked: false, retryAfterMinutes: 0 };
    }

    const diff = Math.ceil((lockUntil - now) / 60000);
    return { locked: true, retryAfterMinutes: diff };
  }

  function recordFailedLogin(email) {
    const entry = getGuardEntry(email);
    const nextAttempts = Number(entry.failedAttempts || 0) + 1;

    if (nextAttempts >= MAX_LOGIN_ATTEMPTS) {
      const lockUntil = new Date(Date.now() + LOGIN_LOCK_MINUTES * 60000).toISOString();
      setGuardEntry(email, { failedAttempts: nextAttempts, lockUntil });
      return { locked: true, retryAfterMinutes: LOGIN_LOCK_MINUTES };
    }

    setGuardEntry(email, { failedAttempts: nextAttempts, lockUntil: null });
    return { locked: false, remaining: MAX_LOGIN_ATTEMPTS - nextAttempts };
  }

  function getAssignments() {
    return readList(ASSIGNMENTS_KEY);
  }

  function saveAssignments(items) {
    writeList(ASSIGNMENTS_KEY, items);
  }

  function getProjectById(projectId) {
    const all = readList(PROJECTS_KEY);
    return all.find((project) => project.id === projectId) || null;
  }

  function seedProjects() {
    if (readList(PROJECTS_KEY).length > 0) {
      return;
    }

    const projects = [
      {
        id: uid("proj"),
        title: "AI Defect Detection for Production Line",
        category: "Manufacturing",
        budget: "INR 80,000 - INR 1,50,000",
        description: "Create a defect detection model for conveyor camera images.",
        status: "open",
        documents: [
          { name: "Production Camera Data Sheet.pdf", url: "#" },
          { name: "Factory Line SOP.pdf", url: "#" },
        ],
        defaultTimeline: "8 weeks",
        createdAt: nowIso(),
      },
      {
        id: uid("proj"),
        title: "Low-cost Composite Material Optimization",
        category: "Materials",
        budget: "INR 50,000 - INR 1,20,000",
        description: "Identify alternative low-cost material combinations with test strategy.",
        status: "open",
        documents: [
          { name: "Material Test Matrix.xlsx", url: "#" },
          { name: "Composite Specs.pdf", url: "#" },
        ],
        defaultTimeline: "10 weeks",
        createdAt: nowIso(),
      },
      {
        id: uid("proj"),
        title: "Plant Energy Optimization Study",
        category: "Process Improvement",
        budget: "INR 40,000 - INR 90,000",
        description: "Recommend practical interventions to reduce plant energy usage by at least 10%.",
        status: "open",
        documents: [
          { name: "Energy Consumption Snapshot.csv", url: "#" },
          { name: "Baseline Operations Guide.pdf", url: "#" },
        ],
        defaultTimeline: "6 weeks",
        createdAt: nowIso(),
      },
    ];

    writeList(PROJECTS_KEY, projects);
  }

  function getEarningsRecord(email) {
    const items = readList(EARNINGS_KEY);
    let record = items.find((item) => item.email.toLowerCase() === email.toLowerCase());
    if (!record) {
      record = {
        email: email.toLowerCase(),
        total: 0,
        pending: 0,
        withdrawn: 0,
        updatedAt: nowIso(),
      };
      items.push(record);
      writeList(EARNINGS_KEY, items);
    }
    return record;
  }

  function saveEarningsRecord(record) {
    const items = readList(EARNINGS_KEY);
    const index = items.findIndex((item) => item.email.toLowerCase() === record.email.toLowerCase());
    if (index >= 0) {
      items[index] = record;
    } else {
      items.push(record);
    }
    writeList(EARNINGS_KEY, items);
  }

  function addTransaction(email, txn) {
    const items = readList(TRANSACTIONS_KEY);
    items.push({
      id: uid("txn"),
      email: email.toLowerCase(),
      createdAt: nowIso(),
      ...txn,
    });
    writeList(TRANSACTIONS_KEY, items);
  }

  function getAllBids() {
    return readList(BIDS_KEY).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function getBidsForProject(projectId) {
    const target = safeText(projectId, 120);
    return getAllBids().filter((bid) => bid.projectId === target);
  }

  function register(formData) {
    const name = safeText(formData?.name, 120);
    const email = safeEmail(formData?.email);
    const password = String(formData?.password || "");
    const passwordConfirm = String(formData?.passwordConfirm || "");

    if (!name || name.length < 2) {
      return { success: false, error: "Name must be at least 2 characters." };
    }

    if (!isValidGmail(email)) {
      return { success: false, error: "Please use a valid Gmail address (e.g., yourname@gmail.com)." };
    }

    if (!password || password.length < 6) {
      return { success: false, error: "Password must be at least 6 characters." };
    }

    if (password !== passwordConfirm) {
      return { success: false, error: "Passwords do not match." };
    }

    const users = getAllUsers();
    if (users.some((u) => u.email.toLowerCase() === email.toLowerCase())) {
      return { success: false, error: "Email already registered." };
    }

    const user = {
      id: uid("usr"),
      name,
      email,
      role: "researcher",
      passwordHash: hashPassword(password),
      createdAt: nowIso(),
      profile: {
        bio: "",
        phone: "",
      },
      verificationStatus: "pending_verification", // pending_verification | verified | rejected
      rejectionReason: "",
      researcherDetails: null,
      verificationReviewedAt: null,
    };

    saveUser(user);
    getEarningsRecord(user.email);
    sendSystemMail(
      user.email,
      "Vidnex Registration Successful",
      "Your registration is complete. Please log in and submit education, work experience, and required documents for verification.",
      { event: "registration" }
    );

    return {
      success: true,
      user,
      message: "Registration successful! A confirmation mail has been sent. Please log in and complete your verification profile.",
    };
  }

  function ensureApprovedDemoResearcher() {
    const demoEmail = "approved.researcher@gmail.com";
    const users = getAllUsers();
    const exists = users.some((u) => u.email.toLowerCase() === demoEmail);
    if (exists) {
      return;
    }

    const demoUser = {
      id: uid("usr"),
      name: "Approved Researcher",
      email: demoEmail,
      role: "researcher",
      passwordHash: hashPassword("Research@123"),
      createdAt: nowIso(),
      profile: {
        bio: "Verified researcher profile for demo workflow testing.",
        phone: "+91-9000000000",
      },
      verificationStatus: "verified",
      rejectionReason: "",
      researcherDetails: {
        work: {
          company: "Demo Research Labs",
          role: "Senior Research Engineer",
          years: 5,
        },
        education: {
          degree: "M.Tech",
          university: "National Institute of Technology",
          year: 2020,
        },
        documents: {
          resume: { name: "resume.pdf", data: "" },
          certificates: { name: "degree-proof.pdf", data: "" },
          idProof: { name: "id-proof.pdf", data: "" },
        },
        uploadedAt: nowIso(),
      },
      verificationReviewedAt: nowIso(),
    };

    users.push(demoUser);
    saveUsers(users);

    const earnings = getEarningsRecord(demoEmail);
    if (earnings.total <= 0) {
      earnings.total = 75000;
      earnings.pending = 0;
      earnings.withdrawn = 5000;
      earnings.updatedAt = nowIso();
      saveEarningsRecord(earnings);
      addTransaction(demoEmail, {
        type: "credit",
        amount: 75000,
        status: "completed",
        description: "Demo approved profile initial credit",
      });
    }
  }

  function login(email, password) {
    const normalizedEmail = safeEmail(email);
    const lockCheck = isAccountLocked(normalizedEmail);
    if (lockCheck.locked) {
      return {
        success: false,
        error: `Too many failed attempts. Try again in ${lockCheck.retryAfterMinutes} minute(s).`,
      };
    }

    const users = getAllUsers();
    const user = users.find((u) => u.email.toLowerCase() === normalizedEmail);

    if (!user) {
      recordFailedLogin(normalizedEmail);
      return { success: false, error: "Email not found." };
    }

    const passwordHash = hashPassword(password);
    if (user.passwordHash !== passwordHash) {
      const guard = recordFailedLogin(normalizedEmail);
      if (guard.locked) {
        return {
          success: false,
          error: `Too many failed attempts. Try again in ${guard.retryAfterMinutes} minute(s).`,
        };
      }
      return { success: false, error: "Incorrect password." };
    }

    resetGuardEntry(normalizedEmail);

    const session = {
      userId: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
      loginTime: nowIso(),
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    return { success: true, user: session, message: "Login successful!" };
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    return { success: true, message: "Logged out." };
  }

  function getCurrentUser() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  }

  function isLoggedIn() {
    return getCurrentUser() !== null;
  }

  function updateProfile(email, updates) {
    const user = getUserProfile(email);
    if (!user) {
      return { success: false, error: "User not found." };
    }

    const nextProfile = {
      bio: safeText(updates?.profile?.bio, 500),
      phone: safeText(updates?.profile?.phone, 50),
    };
    user.profile = {
      ...(user.profile || {}),
      ...nextProfile,
    };
    saveUser(user);
    return { success: true, user, message: "Profile updated." };
  }

  function submitResearcherVerification(email, details) {
    const user = getUserProfile(email);
    if (!user) {
      return { success: false, error: "User not found." };
    }

    if (user.role !== "researcher") {
      return { success: false, error: "Only researchers can submit verification." };
    }

    const workCompany = safeText(details?.workCompany, 140);
    const workRole = safeText(details?.workRole, 140);
    const workYears = Number(details?.workYears || 0);

    const educationDegree = safeText(details?.educationDegree, 140);
    const educationUniversity = safeText(details?.educationUniversity, 180);
    const educationYear = Number(details?.educationYear || 0);

    const resumeName = safeText(details?.resumeName, 180);
    const resumeData = details?.resumeData || null;
    const certificateName = safeText(details?.certificateName, 180);
    const certificateData = details?.certificateData || null;
    const idProofName = safeText(details?.idProofName, 180);
    const idProofData = details?.idProofData || null;

    if (!workCompany || !workRole || !workYears || workYears < 0 || workYears > 60) {
      return { success: false, error: "Please complete work experience details." };
    }

    if (!educationDegree || !educationUniversity || !educationYear || educationYear < 1950 || educationYear > 2100) {
      return { success: false, error: "Please complete education details." };
    }

    if (!resumeName || !resumeData || !certificateName || !certificateData || !idProofName || !idProofData) {
      return { success: false, error: "Please upload resume, certificate proof, and ID proof." };
    }

    user.researcherDetails = {
      work: {
        company: workCompany,
        role: workRole,
        years: workYears,
      },
      education: {
        degree: educationDegree,
        university: educationUniversity,
        year: educationYear,
      },
      documents: {
        resume: { name: resumeName, data: resumeData },
        certificates: { name: certificateName, data: certificateData },
        idProof: { name: idProofName, data: idProofData },
      },
      uploadedAt: nowIso(),
    };
    user.verificationStatus = "pending_verification";
    user.rejectionReason = "";
    user.verificationReviewedAt = null;

    saveUser(user);
    sendSystemMail(
      user.email,
      "Verification Submitted",
      "Your profile documents and details were submitted for verification. You will receive another mail after review.",
      { event: "verification_submitted" }
    );

    return {
      success: true,
      user,
      message: "Verification submitted. Mail sent and awaiting approval.",
    };
  }

  function verifyResearcher(email, status, reason = "") {
    const user = getUserProfile(email);
    if (!user) {
      return { success: false, error: "User not found." };
    }

    if (user.role !== "researcher") {
      return { success: false, error: "User is not a researcher." };
    }

    if (!["verified", "rejected"].includes(status)) {
      return { success: false, error: "Invalid verification status." };
    }

    user.verificationStatus = status;
    user.rejectionReason = status === "rejected"
      ? safeText(reason || "Profile does not meet verification requirements.", 500)
      : "";
    user.verificationReviewedAt = nowIso();

    // Seed usable balance for verified researcher demo workflow.
    if (status === "verified") {
      const earnings = getEarningsRecord(user.email);
      if (earnings.total <= 0) {
        earnings.total = 50000;
        earnings.updatedAt = nowIso();
        saveEarningsRecord(earnings);
        addTransaction(user.email, {
          type: "credit",
          amount: 50000,
          status: "completed",
          description: "Initial verified researcher credit",
        });
      }

      sendSystemMail(
        user.email,
        "Verification Approved",
        "Your researcher verification is approved. You can now bid on projects and request withdrawals from your dashboard.",
        { event: "verification_approved" }
      );
    } else {
      sendSystemMail(
        user.email,
        "Verification Rejected",
        `Your verification was rejected. Reason: ${user.rejectionReason}`,
        { event: "verification_rejected" }
      );
    }

    saveUser(user);
    return { success: true, user, message: `Researcher ${status}.` };
  }

  function getPendingResearchers() {
    return getAllUsers().filter(
      (u) =>
        u.role === "researcher" &&
        u.verificationStatus === "pending_verification" &&
        u.researcherDetails &&
        u.researcherDetails.documents &&
        u.researcherDetails.documents.resume &&
        u.researcherDetails.documents.certificates &&
        u.researcherDetails.documents.idProof
    );
  }

  function isResearcherVerified(email) {
    const user = getUserProfile(email);
    return !!user && user.role === "researcher" && user.verificationStatus === "verified";
  }

  function canBidOnProjects(email) {
    return isResearcherVerified(email);
  }

  function getProjects() {
    seedProjects();
    return readList(PROJECTS_KEY).filter((project) => project.status === "open");
  }

  function getUserBids(email) {
    return readList(BIDS_KEY)
      .filter((bid) => bid.email.toLowerCase() === safeEmail(email))
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function placeBid(email, payload) {
    if (!canBidOnProjects(email)) {
      return { success: false, error: "Your account is under verification." };
    }

    const projectId = safeText(payload?.projectId, 120);
    const amount = Number(payload?.amount || 0);
    const proposalNote = safeText(payload?.proposalNote, 3000);

    if (!projectId) {
      return { success: false, error: "Please select a valid project." };
    }

    if (!amount || amount <= 0) {
      return { success: false, error: "Please enter a valid bid amount." };
    }

    if (!proposalNote || proposalNote.length < 20) {
      return { success: false, error: "Proposal note must be at least 20 characters." };
    }

    const project = getProjects().find((item) => item.id === projectId);
    if (!project) {
      return { success: false, error: "Project not found." };
    }

    const bids = readList(BIDS_KEY);
    const existingIndex = bids.findIndex(
      (bid) => bid.email.toLowerCase() === email.toLowerCase() && bid.projectId === projectId
    );

    const bid = {
      id: existingIndex >= 0 ? bids[existingIndex].id : uid("bid"),
      email: safeEmail(email),
      projectId,
      projectTitle: project.title,
      amount,
      proposalNote,
      status: existingIndex >= 0 ? bids[existingIndex].status : BID_STATUS.pending,
      createdAt: existingIndex >= 0 ? bids[existingIndex].createdAt : nowIso(),
      updatedAt: nowIso(),
    };

    if (existingIndex >= 0 && ![BID_STATUS.pending, BID_STATUS.shortlisted, BID_STATUS.rejected].includes(bids[existingIndex].status)) {
      return { success: false, error: "This bid can no longer be changed." };
    }

    if (existingIndex >= 0) {
      bids[existingIndex] = bid;
    } else {
      bids.push(bid);
    }

    writeList(BIDS_KEY, bids);
    sendSystemMail(
      email,
      existingIndex >= 0 ? "Bid Updated" : "Bid Submitted",
      `Your bid for '${project.title}' has been ${existingIndex >= 0 ? "updated" : "submitted"}.`,
      { event: existingIndex >= 0 ? "bid_updated" : "bid_submitted", projectId }
    );

    return { success: true, bid, message: existingIndex >= 0 ? "Bid updated successfully." : "Bid placed successfully." };
  }

  function getNextAllowedStatuses(currentStatus) {
    const map = {
      [BID_STATUS.pending]: [BID_STATUS.shortlisted, BID_STATUS.selected, BID_STATUS.rejected],
      [BID_STATUS.shortlisted]: [BID_STATUS.selected, BID_STATUS.rejected],
      [BID_STATUS.selected]: [BID_STATUS.allocated],
      [BID_STATUS.allocated]: [BID_STATUS.in_progress, BID_STATUS.submitted],
      [BID_STATUS.in_progress]: [BID_STATUS.submitted],
      [BID_STATUS.submitted]: [BID_STATUS.completed],
      [BID_STATUS.rejected]: [],
      [BID_STATUS.completed]: [],
    };

    return map[currentStatus] || [];
  }

  function ensureAllocationForBid(bid, payload = {}) {
    const assignments = getAssignments();
    const existing = assignments.find((item) => item.bidId === bid.id);
    if (existing) {
      return existing;
    }

    const project = getProjectById(bid.projectId);
    const timeline = safeText(payload.timeline || project?.defaultTimeline || "8 weeks", 120);
    const projectDetails = safeText(payload.projectDetails || project?.description || "Project allocated.", 4000);
    const expectedSubmissionDate = safeText(payload.expectedSubmissionDate || "", 32);
    const allocatedEarning = Number(payload.allocatedEarning || bid.amount || 0);

    const assignment = {
      id: uid("asg"),
      bidId: bid.id,
      researcherEmail: bid.email,
      projectId: bid.projectId,
      projectTitle: bid.projectTitle,
      allocatedAt: nowIso(),
      status: BID_STATUS.allocated,
      allocation: {
        projectDetails,
        timeline,
        expectedSubmissionDate,
        projectDocuments: Array.isArray(project?.documents) ? project.documents : [],
      },
      submission: {
        status: "pending",
        submittedAt: null,
        submissionDate: null,
        response: "",
        data: null,
        fileName: "",
      },
      review: {
        status: "pending",
        comment: "",
        reviewedAt: null,
      },
      earnings: {
        allocated: allocatedEarning > 0 ? allocatedEarning : 0,
        released: 0,
      },
      updatedAt: nowIso(),
    };

    assignments.push(assignment);
    saveAssignments(assignments);
    return assignment;
  }

  function updateBidStatus(email, bidId, status, payload = {}) {
    const normalizedEmail = safeEmail(email);
    const targetBidId = safeText(bidId, 120);
    const nextStatus = safeText(status, 40);
    const bids = readList(BIDS_KEY);
    const index = bids.findIndex((bid) => bid.id === targetBidId && bid.email.toLowerCase() === normalizedEmail);

    if (index < 0) {
      return { success: false, error: "Bid not found." };
    }

    const bid = bids[index];
    const allowed = getNextAllowedStatuses(bid.status);
    if (!allowed.includes(nextStatus)) {
      return { success: false, error: `Invalid status transition from '${bid.status}' to '${nextStatus}'.` };
    }

    bid.status = nextStatus;
    bid.updatedAt = nowIso();
    bids[index] = bid;
    writeList(BIDS_KEY, bids);

    if (nextStatus === BID_STATUS.selected || nextStatus === BID_STATUS.allocated) {
      const assignment = ensureAllocationForBid(bid, payload);
      if (nextStatus === BID_STATUS.selected) {
        bid.status = BID_STATUS.allocated;
        bid.updatedAt = nowIso();
        bids[index] = bid;
        writeList(BIDS_KEY, bids);
      }
      sendSystemMail(
        normalizedEmail,
        "Bid Selected and Project Allocated",
        `Congratulations. Your bid for '${bid.projectTitle}' is selected and project allocation details are available in your dashboard.`,
        { event: "bid_selected", bidId: bid.id, assignmentId: assignment.id }
      );
      return { success: true, bid, assignment, message: "Bid selected and project allocated." };
    }

    sendSystemMail(
      normalizedEmail,
      "Bid Status Updated",
      `Your bid for '${bid.projectTitle}' is now '${nextStatus}'.`,
      { event: "bid_status_updated", bidId: bid.id }
    );

    return { success: true, bid, message: "Bid status updated." };
  }

  function getAssignedProjects(email) {
    const normalizedEmail = safeEmail(email);
    return getAssignments()
      .filter((item) => item.researcherEmail === normalizedEmail)
      .sort((a, b) => new Date(b.allocatedAt) - new Date(a.allocatedAt));
  }

  function submitProjectDeliverable(email, assignmentId, payload) {
    const normalizedEmail = safeEmail(email);
    const targetAssignmentId = safeText(assignmentId, 120);
    const assignments = getAssignments();
    const index = assignments.findIndex(
      (item) => item.id === targetAssignmentId && item.researcherEmail === normalizedEmail
    );

    if (index < 0) {
      return { success: false, error: "Project assignment not found." };
    }

    const assignment = assignments[index];
    const response = safeText(payload?.response, 3000);
    const submissionData = payload?.submissionData || null;
    const fileName = safeText(payload?.fileName, 180);
    const submissionDate = safeText(payload?.submissionDate, 32) || nowIso().slice(0, 10);

    if (!response) {
      return { success: false, error: "Submission response is required." };
    }

    if (!submissionData || !fileName) {
      return { success: false, error: "Please attach submission data/file." };
    }

    assignment.status = BID_STATUS.submitted;
    assignment.submission = {
      status: "submitted",
      submittedAt: nowIso(),
      submissionDate,
      response,
      data: submissionData,
      fileName,
    };
    assignment.updatedAt = nowIso();
    assignments[index] = assignment;
    saveAssignments(assignments);

    const bids = readList(BIDS_KEY);
    const bidIndex = bids.findIndex((item) => item.id === assignment.bidId);
    if (bidIndex >= 0) {
      bids[bidIndex].status = BID_STATUS.submitted;
      bids[bidIndex].updatedAt = nowIso();
      writeList(BIDS_KEY, bids);
    }

    sendSystemMail(
      normalizedEmail,
      "Project Submission Received",
      `Your submission for '${assignment.projectTitle}' has been recorded and is awaiting review.`,
      { event: "project_submitted", assignmentId: assignment.id }
    );

    return { success: true, assignment, message: "Project submitted successfully." };
  }

  function reviewProjectSubmission(email, assignmentId, payload = {}) {
    const normalizedEmail = safeEmail(email);
    const targetAssignmentId = safeText(assignmentId, 120);
    const assignments = getAssignments();
    const index = assignments.findIndex(
      (item) => item.id === targetAssignmentId && item.researcherEmail === normalizedEmail
    );

    if (index < 0) {
      return { success: false, error: "Project assignment not found." };
    }

    const assignment = assignments[index];
    if (!assignment.submission || assignment.submission.status !== "submitted") {
      return { success: false, error: "No submitted work available for review." };
    }

    const reviewStatus = safeText(payload.reviewStatus || "approved", 40);
    const reviewComment = safeText(payload.reviewComment || "", 1500);
    const earningAmount = Number(payload.earningAmount || assignment.earnings?.allocated || 0);

    if (!["approved", "changes_requested"].includes(reviewStatus)) {
      return { success: false, error: "Invalid review status." };
    }

    assignment.review = {
      status: reviewStatus,
      comment: reviewComment,
      reviewedAt: nowIso(),
    };

    if (reviewStatus === "approved") {
      assignment.status = BID_STATUS.completed;
      assignment.earnings.released = Math.max(0, earningAmount);

      const earnings = getEarningsRecord(normalizedEmail);
      earnings.total = Number(earnings.total) + Math.max(0, earningAmount);
      earnings.updatedAt = nowIso();
      saveEarningsRecord(earnings);

      addTransaction(normalizedEmail, {
        type: "credit",
        amount: Math.max(0, earningAmount),
        status: "completed",
        description: `Project earning credit for ${assignment.projectTitle}`,
      });

      sendSystemMail(
        normalizedEmail,
        "Project Review Approved",
        `Your submission for '${assignment.projectTitle}' has been approved. Earnings credited: INR ${Math.max(0, earningAmount).toLocaleString("en-IN")}.`,
        { event: "project_review_approved", assignmentId: assignment.id }
      );
    } else {
      assignment.status = BID_STATUS.in_progress;
      assignment.submission.status = "changes_requested";
      sendSystemMail(
        normalizedEmail,
        "Project Review: Changes Requested",
        `Your submission for '${assignment.projectTitle}' needs changes. Review comment: ${reviewComment || "Please update and resubmit."}`,
        { event: "project_review_changes", assignmentId: assignment.id }
      );
    }

    assignment.updatedAt = nowIso();
    assignments[index] = assignment;
    saveAssignments(assignments);

    const bids = readList(BIDS_KEY);
    const bidIndex = bids.findIndex((item) => item.id === assignment.bidId);
    if (bidIndex >= 0) {
      bids[bidIndex].status = assignment.status;
      bids[bidIndex].updatedAt = nowIso();
      writeList(BIDS_KEY, bids);
    }

    return { success: true, assignment, message: "Review updated." };
  }

  function getEarningsSummary(email) {
    const record = getEarningsRecord(email);
    const available = Math.max(0, Number(record.total) - Number(record.pending) - Number(record.withdrawn));
    return {
      total: Number(record.total),
      pending: Number(record.pending),
      withdrawn: Number(record.withdrawn),
      available,
      updatedAt: record.updatedAt,
    };
  }

  function getTransactions(email) {
    return readList(TRANSACTIONS_KEY)
      .filter((item) => item.email.toLowerCase() === safeEmail(email))
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function getWithdrawRequests(email) {
    return readList(WITHDRAW_REQUESTS_KEY)
      .filter((item) => item.email.toLowerCase() === safeEmail(email))
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function createWithdrawRequest(email, payload) {
    if (!isResearcherVerified(email)) {
      return { success: false, error: "Your account is under verification." };
    }

    const amount = Number(payload?.amount || 0);
    const paymentMethod = String(payload?.paymentMethod || "").trim().toLowerCase();
    const paymentDetails = safeText(payload?.paymentDetails, 600);

    if (!amount || amount <= 0) {
      return { success: false, error: "Enter a valid withdrawal amount." };
    }

    if (!paymentMethod || !["upi", "bank"].includes(paymentMethod)) {
      return { success: false, error: "Select a valid payment method." };
    }

    if (!paymentDetails) {
      return { success: false, error: "Enter payment details." };
    }

    const earnings = getEarningsRecord(email);
    const available = Math.max(0, Number(earnings.total) - Number(earnings.pending) - Number(earnings.withdrawn));
    if (amount > available) {
      return { success: false, error: "Cannot withdraw more than available balance." };
    }

    const requests = readList(WITHDRAW_REQUESTS_KEY);
    const request = {
      id: uid("wr"),
      email: safeEmail(email),
      amount,
      paymentMethod,
      paymentDetails,
      status: "pending",
      createdAt: nowIso(),
    };
    requests.push(request);
    writeList(WITHDRAW_REQUESTS_KEY, requests);

    earnings.pending = Number(earnings.pending) + amount;
    earnings.updatedAt = nowIso();
    saveEarningsRecord(earnings);

    addTransaction(email, {
      type: "withdrawal",
      amount,
      status: "pending",
      description: `Withdrawal request ${request.id}`,
    });

    sendSystemMail(
      email,
      "Withdrawal Request Submitted",
      `Your withdrawal request (${request.id}) for INR ${amount.toLocaleString("en-IN")} is submitted and under review.`,
      { event: "withdraw_request", requestId: request.id }
    );

    return { success: true, request, message: "Withdrawal request submitted." };
  }

  function processWithdrawRequest(requestId, action) {
    // action: "completed" | "rejected"
    if (!["completed", "rejected"].includes(action)) {
      return { success: false, error: "Invalid action. Use 'completed' or 'rejected'." };
    }

    const requests = readList(WITHDRAW_REQUESTS_KEY);
    const index = requests.findIndex((r) => r.id === safeText(requestId, 120));
    if (index < 0) {
      return { success: false, error: "Withdrawal request not found." };
    }

    const request = requests[index];
    if (request.status !== "pending") {
      return { success: false, error: "Request is already processed." };
    }

    const earnings = getEarningsRecord(request.email);
    // Move amount from pending → withdrawn (if completed) or just release pending (if rejected)
    earnings.pending = Math.max(0, Number(earnings.pending) - request.amount);
    if (action === "completed") {
      earnings.withdrawn = Number(earnings.withdrawn) + request.amount;
    }
    earnings.updatedAt = nowIso();
    saveEarningsRecord(earnings);

    requests[index].status = action;
    requests[index].processedAt = nowIso();
    writeList(WITHDRAW_REQUESTS_KEY, requests);

    addTransaction(request.email, {
      type: "withdrawal_" + action,
      amount: request.amount,
      status: action,
      description: `Withdrawal ${request.id} ${action}`,
    });

    sendSystemMail(
      request.email,
      action === "completed" ? "Withdrawal Processed" : "Withdrawal Rejected",
      action === "completed"
        ? `Your withdrawal request (${request.id}) for INR ${request.amount.toLocaleString("en-IN")} has been processed successfully.`
        : `Your withdrawal request (${request.id}) for INR ${request.amount.toLocaleString("en-IN")} was rejected. Funds returned to your available balance.`,
      { event: "withdraw_" + action, requestId: request.id }
    );

    return { success: true, request: requests[index], message: `Withdrawal ${action}.` };
  }

  function getAllWithdrawRequests() {
    return readList(WITHDRAW_REQUESTS_KEY)
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  seedProjects();
  ensureApprovedDemoResearcher();

  return {
    register,
    login,
    logout,
    getCurrentUser,
    isLoggedIn,
    getUserProfile,
    updateProfile,
    isValidGmail,
    submitResearcherVerification,
    verifyResearcher,
    getPendingResearchers,
    isResearcherVerified,
    canBidOnProjects,
    getAllBids,
    getBidsForProject,
    getProjects,
    getUserBids,
    placeBid,
    updateBidStatus,
    getAssignedProjects,
    submitProjectDeliverable,
    reviewProjectSubmission,
    getUserMails,
    markMailRead,
    markAllMailsRead,
    bidStatus: BID_STATUS,
    getEarningsSummary,
    getTransactions,
    getWithdrawRequests,
    createWithdrawRequest,
    processWithdrawRequest,
    getAllWithdrawRequests,
  };
})();
