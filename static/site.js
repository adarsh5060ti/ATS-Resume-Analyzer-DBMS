document.addEventListener("DOMContentLoaded", () => {
  const chooseButton = document.getElementById("chooseBtn");
  const resumeInput = document.getElementById("resume");
  const fileName = document.getElementById("fileName");
  const uploadBox = document.getElementById("uploadBox");

  if (chooseButton && resumeInput) {
    chooseButton.addEventListener("click", () => resumeInput.click());
  }
  if (uploadBox && resumeInput) {
    uploadBox.addEventListener("click", (event) => {
      if (event.target !== resumeInput) resumeInput.click();
    });
  }
  if (resumeInput) {
    resumeInput.addEventListener("change", () => {
      const selected = resumeInput.files && resumeInput.files[0];
      if (fileName) {
        fileName.textContent = selected ? selected.name : "No file selected";
        fileName.classList.toggle("selected", Boolean(selected));
      }
      if (uploadBox) uploadBox.classList.toggle("has-file", Boolean(selected));
    });
  }
  document.querySelectorAll("[data-print-ai]").forEach((button) => {
    button.addEventListener("click", () => {
      const recommendations = document.getElementById("aiRecommendations");
      if (recommendations && recommendations.innerText.trim()) window.print();
    });
  });
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const selector = link.getAttribute("href");
      if (!selector || selector === "#") return;
      const target = document.querySelector(selector);
      if (target) {
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
});
