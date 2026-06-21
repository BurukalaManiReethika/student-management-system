// Auto-dismiss alerts after 4 second
document.addEventListener("DOMContentLoaded", function () {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 4000);
  });
});

// Dark mode toggle
document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("themeToggle");
  if (!toggle) return;

  const root = document.documentElement;
  const icon = toggle.querySelector("i");

  function syncIcon() {
    const isDark = root.getAttribute("data-theme") === "dark";
    icon.classList.toggle("fa-moon", !isDark);
    icon.classList.toggle("fa-sun", isDark);
  }
  syncIcon();

  toggle.addEventListener("click", function () {
    const isDark = root.getAttribute("data-theme") === "dark";
    const next = isDark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("sms-theme", next);
    syncIcon();
  });
});
