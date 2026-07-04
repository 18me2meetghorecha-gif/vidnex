const registerForm = document.getElementById("registerForm");
const registerMsg = document.getElementById("registerMsg");

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registerForm);
  const payload = {
    full_name: formData.get("full_name"),
    email: formData.get("email"),
    password: formData.get("password"),
  };

  try {
    await apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showMsg(registerMsg, "success", "Registration complete. Redirecting to login...");
    setTimeout(() => {
      window.location.href = "/login/";
    }, 1000);
  } catch (error) {
    showMsg(registerMsg, "error", error.message);
  }
});
