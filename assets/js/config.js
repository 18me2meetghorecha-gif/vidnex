// Environment-aware API configuration
// This file is loaded before api.js to set the correct backend URL

// Default to localhost for development
window.VIDNEX_API_URL = window.VIDNEX_API_URL || "http://127.0.0.1:8000";

// In production, set this to your Railway backend URL
// window.VIDNEX_API_URL = "https://your-railway-app.up.railway.app";
