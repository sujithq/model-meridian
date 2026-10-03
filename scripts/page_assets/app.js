const els = {
  search: document.getElementById("search"),
  minScore: document.getElementById("minScore"),
  minScoreOut: document.getElementById("minScoreOut"),
  maxCost: document.getElementById("maxCost"),
  maxCostOut: document.getElementById("maxCostOut"),
  effortChecks: document.getElementById("effortChecks"),
  familyChecks: document.getElementById("familyChecks"),
  showLines: document.getElementById("showLines"),
  showFamilyLabels: document.getElementById("showFamilyLabels"),
  showEffortLabels: document.getElementById("showEffortLabels"),
  selectAll: document.getElementById("selectAll"),
  reset: document.getElementById("reset"),
  themeToggle: document.getElementById("themeToggle"),
};

function buildChecks(container, items, nameKey) {
  container.textContent = "";
  for (const item of items) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    input.value = item.value;
    input.dataset.group = nameKey;
    label.appendChild(input);
    if (item.color) {
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = item.color;
      label.appendChild(swatch);
    }
    label.appendChild(document.createTextNode(item.label));
    container.appendChild(label);
  }
  container.addEventListener("change", render);
}

function selectAllChecks() {
  document
    .querySelectorAll('.checks input[type="checkbox"]')
    .forEach((input) => { input.checked = true; });
  render();
}

function resetFilters() {
  els.search.value = "";
  setupRanges();
  els.showLines.checked = true;
  els.showFamilyLabels.checked = true;
  els.showEffortLabels.checked = false;
  document
    .querySelectorAll('.checks input[type="checkbox"]')
    .forEach((input) => { input.checked = true; });
  render();
}

buildChecks(
  els.effortChecks,
  CONFIG.efforts.map((e) => ({ value: e, label: e })),
  "effort"
);
buildChecks(
  els.familyChecks,
  CONFIG.families.map((f) => ({ value: f.name, label: f.name, color: f.color })),
  "family"
);
setupRanges();

["input", "change"].forEach((evt) => {
  els.search.addEventListener(evt, render);
  els.minScore.addEventListener(evt, () => {
    requestedMinScore = parseFloat(els.minScore.value);
    render();
  });
  els.maxCost.addEventListener(evt, () => {
    const step = parseFloat(els.maxCost.value);
    requestedMaxCost = step >= COST_STEPS ? Infinity : sliderToCost(step);
    render();
  });
});
els.showLines.addEventListener("change", render);
els.showFamilyLabels.addEventListener("change", render);
els.showEffortLabels.addEventListener("change", render);
els.selectAll.addEventListener("click", selectAllChecks);
els.reset.addEventListener("click", resetFilters);
els.themeToggle.addEventListener("click", () => {
  const isDark = document.documentElement.dataset.colorMode !== "dark";
  document.documentElement.dataset.colorMode = isDark ? "dark" : "light";
  els.themeToggle.textContent = isDark ? "Light mode" : "Dark mode";
  els.themeToggle.setAttribute("aria-pressed", String(isDark));
});
window.addEventListener("scroll", hideTooltip, { passive: true });
let resizeFrame = 0;
window.addEventListener("resize", () => {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => {
    if (syncResponsiveChart()) render();
  });
}, { passive: true });

// Scrolling the filter panel must not nudge a slider sitting under the cursor.
[els.minScore, els.maxCost].forEach((slider) => {
  slider.addEventListener("wheel", () => {
    const before = slider.value;
    requestAnimationFrame(() => {
      if (slider.value !== before) {
        slider.value = before;
        syncResponsiveChart();
        render();
      }
    });
  }, { passive: true });
});

render();
