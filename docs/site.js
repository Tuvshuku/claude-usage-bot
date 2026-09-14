(() => {
  "use strict";
  if (new URLSearchParams(location.search).has("press"))
    document.body.classList.add("press-mode");
  const demo = document.querySelector("#demo");
  const pet = document.querySelector("#demo-pet");
  const dashboard = document.querySelector("#demo-dashboard");
  const note = document.querySelector("#pet-note");
  const scenes = {
    happy: {
      session: 32,
      week: 46,
      fable: 12,
      status: "active",
      note: "psst. click me.",
      subtitle: "a little room to keep creating",
      tokens: "1.2M",
    },
    hot: {
      session: 94,
      week: 81,
      fable: 43,
      status: "active",
      note: "big day, huh?",
      subtitle: "getting close to your session limit",
      tokens: "4.8M",
    },
    sleep: {
      session: 18,
      week: 38,
      fable: 8,
      status: "idle",
      note: "just resting my eyes.",
      subtitle: "resting after a quiet spell",
      tokens: "840k",
    },
  };
  let hopTimer;
  let copyTimer;
  function setDashboard(open) {
    dashboard.hidden = !open;
    demo.classList.toggle("dashboard-open", open);
    pet.setAttribute("aria-expanded", String(open));
    pet.setAttribute(
      "aria-label",
      `${open ? "Close" : "Open"} example usage dashboard`,
    );
  }
  function hop() {
    if (
      demo.dataset.mood === "sleep" ||
      matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    clearTimeout(hopTimer);
    pet.classList.remove("hopping");
    void pet.offsetWidth;
    pet.classList.add("hopping");
    hopTimer = setTimeout(() => pet.classList.remove("hopping"), 550);
  }
  pet.addEventListener("click", () => {
    setDashboard(dashboard.hidden);
    hop();
  });
  pet.addEventListener("pointerenter", hop);
  document.querySelectorAll("[data-scene]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.scene;
      const scene = scenes[name];
      demo.dataset.mood = name;
      document
        .querySelectorAll("[data-scene]")
        .forEach((item) =>
          item.setAttribute("aria-pressed", String(item === button)),
        );
      for (const key of ["session", "week", "fable"]) {
        document.querySelector(`#${key}-fill`).style.width = `${scene[key]}%`;
        document.querySelector(`#${key}-percent`).textContent =
          `${scene[key]}%`;
      }
      document.querySelector("#demo-status").textContent = scene.status;
      document.querySelector("#demo-subtitle").textContent = scene.subtitle;
      document.querySelector("#demo-tokens").textContent = scene.tokens;
      note.textContent = scene.note;
      setDashboard(true);
      hop();
    });
  });
  document
    .querySelector("#copy-command")
    .addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const status = document.querySelector("#copy-status");
      const command = document.querySelector("#install-command");
      clearTimeout(copyTimer);
      try {
        await navigator.clipboard.writeText(command.textContent.trim());
        button.textContent = "Copied!";
        status.textContent = "WSL install commands copied.";
      } catch {
        const range = document.createRange();
        range.selectNodeContents(command);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "Select & copy";
        status.textContent =
          "Automatic copying is unavailable. The commands are selected; copy them manually.";
      }
      copyTimer = setTimeout(() => {
        button.textContent = "Copy";
      }, 3500);
    });
})();
