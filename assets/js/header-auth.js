/**
 * Header Auth Management
 * Updates header to show login/register or user menu based on auth state
 */

function updateHeaderAuth() {
  const currentUser = AuthModule.getCurrentUser();
  const header = document.querySelector(".site-header");

  // Remove existing auth elements if any
  const existingAuth = header.querySelector(".auth-links") || header.querySelector(".user-menu");
  if (existingAuth) {
    existingAuth.remove();
  }

  if (currentUser) {
    // User is logged in - hide static login link, show user menu
    const navLoginLink = document.getElementById("navLoginLink");
    if (navLoginLink) navLoginLink.style.display = "none";

    const userMenu = document.createElement("div");
    userMenu.className = "user-menu";
    userMenu.innerHTML = `
      <button class="user-menu-button" id="userMenuBtn">${currentUser.name} ▼</button>
      <div class="user-menu-dropdown" id="userMenuDropdown">
        <a href="profile.html">My Profile</a>
        <button id="logoutBtnHeader">Log Out</button>
      </div>
    `;

    header.appendChild(userMenu);

    // Toggle dropdown
    document.getElementById("userMenuBtn").addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("userMenuDropdown").classList.toggle("active");
    });

    // Close dropdown when clicking elsewhere
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".user-menu")) {
        document.getElementById("userMenuDropdown").classList.remove("active");
      }
    });

    // Logout handler
    document.getElementById("logoutBtnHeader").addEventListener("click", (e) => {
      e.preventDefault();
      AuthModule.logout();
      window.location.href = "index.html";
    });
  } else {
    // User is not logged in - ensure static login link is visible, add Register link
    const navLoginLink = document.getElementById("navLoginLink");
    if (navLoginLink) navLoginLink.style.display = "";

    const authLinks = document.createElement("div");
    authLinks.className = "auth-links";
    authLinks.innerHTML = `
      <a href="register.html" class="register-link">Register</a>
    `;

    header.appendChild(authLinks);
  }
}

// Update header when page loads
document.addEventListener("DOMContentLoaded", updateHeaderAuth);
