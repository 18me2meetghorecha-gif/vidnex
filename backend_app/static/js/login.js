const loginForm = document.getElementById("loginForm");
const loginMsg = document.getElementById("loginMsg");

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginForm);

  try {
    const result = await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });

    showMsg(loginMsg, "success", "Login successful.");
    if (result.role === "admin") {
      window.location.href = "/admin-dashboard/";
      return;
    }

    if (result.status !== "verified") {
      window.location.href = "/verification/";
      return;
    }

    window.location.href = "/dashboard/";
  } catch (error) {
    showMsg(loginMsg, "error", error.message);
  }
});
