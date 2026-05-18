window.PERSONAL_OFFICE_ASSISTANT_CONFIG = {
  // Same-origin by default. Set to "https://api.example.com" only when the API is on another origin.
  apiBaseUrl: "",
  appBasePath: window.location.pathname === "/personal-office-assistant" || window.location.pathname.startsWith("/personal-office-assistant/")
    ? "/personal-office-assistant"
    : ""
};
