// Shows the delay-reason field only when the project status is "Delayed".
// Progressive enhancement: with JS disabled the field stays visible and the
// server-side validation in ProjectForm.clean() still enforces the rule.
(function () {
  "use strict";

  function syncVisibility() {
    var status = document.getElementById("id_status");
    var container = document.getElementById("delay-reason-field");
    if (!status || !container) {
      return;
    }
    container.style.display = status.value === "delayed" ? "" : "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var status = document.getElementById("id_status");
    if (status) {
      status.addEventListener("change", syncVisibility);
    }
    syncVisibility();
  });
})();
