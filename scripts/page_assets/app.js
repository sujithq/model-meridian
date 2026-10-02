const TICK_LADDER = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                     1, 2, 5, 10, 20, 50, 100, 200, 500];
const SVG_NS = "http://www.w3.org/2000/svg";
const PAD = { top: 56, right: 40, bottom: 78, left: 86 };
const BASE_W = 1600, H = 900;
let W = BASE_W;

function syncResponsiveChart() {
  const compact = window.matchMedia(
    "(min-width: 1200px) and (min-aspect-ratio: 2/1)"
  ).matches;
  const nextWidth = compact && svg.clientHeight
    ? Math.max(BASE_W, Math.round((H * svg.clientWidth) / svg.clientHeight))
    : BASE_W;
  if (nextWidth === W) return false;
  W = nextWidth;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  return true;
}

const svg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const statusEl = document.getElementById("status");
const emptyEl = document.getElementById("empty");

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
};

function money(value) {
  if (value >= 1) return "$" + value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (value >= 0.01) return "$" + value.toFixed(2);
  return "$" + value.toFixed(3);
}

function preciseMoney(value) {
  if (value >= 1) return "$" + value.toFixed(2);
  if (value >= 0.01) return "$" + value.toFixed(3);
  return "$" + value.toFixed(4);
}

function el(name, attrs, text) {
  const node = document.createElementNS(SVG_NS, name);
  for (const key in attrs) node.setAttribute(key, attrs[key]);
  if (text !== undefined) node.textContent = text;
  return node;
}

const fullScoreBounds = [CONFIG.minScore, CONFIG.maxScore];
const fullCostBounds = [CONFIG.minCost, CONFIG.maxCost];
const COST_STEPS = 1000;
let scoreBounds = fullScoreBounds.slice();
let costBounds = fullCostBounds.slice();
let costLo = Math.log10(costBounds[0]);
let costHi = Math.log10(costBounds[1]);
let requestedMinScore = Math.floor(fullScoreBounds[0]);
let requestedMaxCost = Infinity;

// The cost slider runs on a normalized integer scale mapped into log space, so
// its top position lands exactly on the most expensive model.
function sliderToCost(step) {
  return Math.pow(10, costLo + ((costHi - costLo) * step) / COST_STEPS);
}

function costToSlider(cost) {
  if (costHi === costLo) return COST_STEPS;
  return Math.round(
    ((Math.log10(cost) - costLo) / (costHi - costLo)) * COST_STEPS
  );
}

function applyRangeControls() {
  els.minScore.min = Math.floor(scoreBounds[0]);
  els.minScore.max = Math.ceil(scoreBounds[1]);
  els.minScore.step = 0.5;
  els.minScore.value = Math.min(
    parseFloat(els.minScore.max),
    Math.max(parseFloat(els.minScore.min), requestedMinScore)
  );

  els.maxCost.min = 0;
  els.maxCost.max = COST_STEPS;
  els.maxCost.step = 1;
  const boundedCost = Math.min(
    costBounds[1],
    Math.max(costBounds[0], requestedMaxCost)
  );
  els.maxCost.value =
    !Number.isFinite(requestedMaxCost) || requestedMaxCost >= costBounds[1]
      ? COST_STEPS
      : Math.max(0, Math.min(COST_STEPS, costToSlider(boundedCost)));
}

function setupRanges() {
  scoreBounds = fullScoreBounds.slice();
  costBounds = fullCostBounds.slice();
  costLo = Math.log10(costBounds[0]);
  costHi = Math.log10(costBounds[1]);
  requestedMinScore = Math.floor(fullScoreBounds[0]);
  requestedMaxCost = Infinity;
  applyRangeControls();
}

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

function checkedValues(container) {
  return new Set(
    Array.from(container.querySelectorAll("input:checked")).map((i) => i.value)
  );
}

function currentFilters() {
  const costStep = parseFloat(els.maxCost.value);
  // At the top of the range, keep the bound open so float rounding cannot drop
  // the most expensive model.
  const atMax = costStep >= COST_STEPS;
  return {
    queries: parseQueries(els.search.value),
    minScore: parseFloat(els.minScore.value),
    maxCost: atMax ? Infinity : sliderToCost(costStep),
    efforts: checkedValues(els.effortChecks),
    families: checkedValues(els.familyChecks),
  };
}

// Model names contain spaces, so commas separate terms. Any term may match.
function parseQueries(value) {
  return value
    .split(",")
    .map((term) => term.trim().toLowerCase())
    .filter((term) => term.length > 0);
}

function matchesSearch(point, queries) {
  if (!queries.length) return true;
  const haystack = (point.model + " " + point.family).toLowerCase();
  return queries.some((term) => haystack.includes(term));
}

function matches(point, f) {
  if (point.score < f.minScore) return false;
  if (point.cost > f.maxCost) return false;
  if (!f.efforts.has(point.effort || "(none)")) return false;
  if (!f.families.has(point.family)) return false;
  if (!matchesSearch(point, f.queries)) return false;
  return true;
}

function matchesBoundsAndSearch(point, f) {
  return point.score >= f.minScore
    && point.cost <= f.maxCost
    && matchesSearch(point, f.queries);
}

function syncFilterOptions(f) {
  const effortCandidates = DATA.filter((point) =>
    matchesBoundsAndSearch(point, f)
    && (!f.families.size || f.families.has(point.family))
  );
  const familyCandidates = DATA.filter((point) =>
    matchesBoundsAndSearch(point, f)
    && (!f.efforts.size || f.efforts.has(point.effort || "(none)"))
  );
  const availableEfforts = new Set(
    effortCandidates.map((point) => point.effort || "(none)")
  );
  const availableFamilies = new Set(
    familyCandidates.map((point) => point.family)
  );

  for (const [container, available] of [
    [els.effortChecks, availableEfforts],
    [els.familyChecks, availableFamilies],
  ]) {
    container.querySelectorAll("label").forEach((label) => {
      const input = label.querySelector("input");
      const isAvailable = available.has(input.value);
      label.hidden = !isAvailable;
      input.disabled = !isAvailable;
    });
  }
}

function syncSliderRanges(f) {
  const candidates = DATA.filter((point) =>
    matchesSearch(point, f.queries)
    && (!f.efforts.size || f.efforts.has(point.effort || "(none)"))
    && (!f.families.size || f.families.has(point.family))
  );
  if (!candidates.length) return;

  scoreBounds = [
    Math.min(...candidates.map((point) => point.score)),
    Math.max(
      ...candidates.map((point) => point.score),
      requestedMinScore
    ),
  ];
  const candidateMinCost = Math.min(...candidates.map((point) => point.cost));
  costBounds = [
    Number.isFinite(requestedMaxCost)
      ? Math.min(candidateMinCost, requestedMaxCost)
      : candidateMinCost,
    Math.max(...candidates.map((point) => point.cost)),
  ];
  costLo = Math.log10(costBounds[0]);
  costHi = Math.log10(costBounds[1]);
  applyRangeControls();
}

function costTicks(lo, hi) {
  const ticks = TICK_LADDER.filter((t) => t >= lo && t <= hi);
  return ticks.length ? ticks : [lo, hi];
}

function scoreTicks(lo, hi) {
  const span = hi - lo;
  const step = span > 40 ? 10 : span > 18 ? 5 : span > 8 ? 2 : 1;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
  return ticks;
}

function overlaps(a, b) {
  return !(a.x1 < b.x0 || b.x1 < a.x0 || a.y1 < b.y0 || b.y1 < a.y0);
}

function placeLabel(box, occupied, offsets) {
  for (const [dx, dy, anchor] of offsets) {
    const x0 = anchor === "end" ? box.x + dx - box.w : anchor === "middle"
      ? box.x + dx - box.w / 2 : box.x + dx;
    const candidate = { x0, x1: x0 + box.w, y0: box.y + dy - box.h, y1: box.y + dy };
    if (candidate.x0 < PAD.left || candidate.x1 > W - PAD.right) continue;
    if (candidate.y0 < PAD.top || candidate.y1 > H - PAD.bottom) continue;
    if (occupied.some((o) => overlaps(candidate, o))) continue;
    occupied.push(candidate);
    return { dx, dy, anchor };
  }
  return null;
}

function showTooltip(event, point) {
  const parts = [`<div class="tip-title">${point.model}</div>`];
  parts.push(`<div class="tip-row"><b>Score</b> ${point.score.toFixed(2)}</div>`);
  parts.push(`<div class="tip-row"><b>Cost per task</b> ${preciseMoney(point.cost)}</div>`);
  parts.push(`<div class="tip-row"><b>Family</b> ${point.family}</div>`);
  if (point.effort) {
    parts.push(`<div class="tip-row"><b>Reasoning effort</b> ${point.effort}</div>`);
  }
  if (point.fallback) parts.push(`<div class="tip-row"><b>Fallback</b> yes</div>`);
  if (point.url) parts.push(`<div class="tip-row">${point.url}</div>`);
  tooltip.innerHTML = parts.join("");
  tooltip.classList.add("visible");
  moveTooltip(event);
}

function moveTooltip(event) {
  const rect = tooltip.getBoundingClientRect();
  let x = event.clientX + 14;
  let y = event.clientY + 14;
  if (x + rect.width > window.innerWidth - 8) x = event.clientX - rect.width - 14;
  if (y + rect.height > window.innerHeight - 8) y = event.clientY - rect.height - 14;
  tooltip.style.left = Math.max(8, x) + "px";
  tooltip.style.top = Math.max(8, y) + "px";
}

function hideTooltip() {
  tooltip.classList.remove("visible");
}

function render() {
  let f = currentFilters();
  syncSliderRanges(f);
  f = currentFilters();
  syncFilterOptions(f);
  els.minScoreOut.textContent = f.minScore.toFixed(1);
  els.maxCostOut.textContent = money(
    Number.isFinite(f.maxCost) ? f.maxCost : costBounds[1]
  );

  const visible = DATA.filter((p) => matches(p, f));
  svg.textContent = "";
  statusEl.textContent =
    `Showing ${visible.length} of ${DATA.length} models · ` +
    `${new Set(visible.map((p) => p.family)).size} families`;
  emptyEl.hidden = visible.length > 0;
  if (!visible.length) return;

  const costs = visible.map((p) => p.cost);
  const scores = visible.map((p) => p.score);
  const xLo = Math.min(...costs) / 1.9;
  const xHi = Math.max(...costs) * 2.2;
  const scorePad = Math.max(2, (Math.max(...scores) - Math.min(...scores)) * 0.08);
  const yLo = Math.min(...scores) - scorePad;
  const yHi = Math.max(...scores) + scorePad;

  const lx = Math.log10(xLo), lxSpan = Math.log10(xHi) - lx;
  const xScale = (cost) =>
    PAD.left + ((Math.log10(cost) - lx) / lxSpan) * (W - PAD.left - PAD.right);
  const yScale = (score) =>
    H - PAD.bottom - ((score - yLo) / (yHi - yLo)) * (H - PAD.top - PAD.bottom);

  // Gridlines and axes.
  for (const tick of scoreTicks(yLo, yHi)) {
    const y = yScale(tick);
    svg.appendChild(el("line", {
      x1: PAD.left, x2: W - PAD.right, y1: y, y2: y, stroke: "#e2e2e2", "stroke-width": 1.2,
    }));
    svg.appendChild(el("text", {
      x: PAD.left - 12, y: y + 4, "text-anchor": "end", class: "tick-label",
    }, String(tick)));
  }
  for (const tick of costTicks(xLo, xHi)) {
    const x = xScale(tick);
    svg.appendChild(el("text", {
      x, y: H - PAD.bottom + 26, "text-anchor": "middle", class: "tick-label",
    }, money(tick)));
  }
  svg.appendChild(el("line", {
    x1: PAD.left, x2: W - PAD.right, y1: H - PAD.bottom, y2: H - PAD.bottom,
    stroke: "#bdbdbd", "stroke-width": 1.2,
  }));
  svg.appendChild(el("line", {
    x1: PAD.left, x2: PAD.left, y1: PAD.top, y2: H - PAD.bottom,
    stroke: "#bdbdbd", "stroke-width": 1.2,
  }));
  svg.appendChild(el("text", {
    x: PAD.left, y: PAD.top - 24, class: "note",
  }, "HIGHER SCORES ARE BETTER"));
  svg.appendChild(el("text", {
    x: W - PAD.right, y: PAD.top - 24, "text-anchor": "end", class: "note",
  }, "LOGARITHMIC COST SCALE"));
  svg.appendChild(el("text", {
    x: (PAD.left + W - PAD.right) / 2, y: H - 22, "text-anchor": "middle", class: "axis-label",
  }, CONFIG.xlabel));
  const yTitle = el("text", {
    x: 24, y: (PAD.top + H - PAD.bottom) / 2, "text-anchor": "middle", class: "axis-label",
    transform: `rotate(-90 24 ${(PAD.top + H - PAD.bottom) / 2})`,
  }, CONFIG.ylabel);
  svg.appendChild(yTitle);

  // Group visible points back into families.
  const families = new Map();
  for (const point of visible) {
    if (!families.has(point.family)) families.set(point.family, []);
    families.get(point.family).push(point);
  }

  const occupied = [];
  for (const point of visible) {
    occupied.push({
      x0: xScale(point.cost) - 6, x1: xScale(point.cost) + 6,
      y0: yScale(point.score) - 6, y1: yScale(point.score) + 6,
    });
  }

  const ordered = Array.from(families.entries()).sort(
    (a, b) => Math.max(...b[1].map((p) => p.score)) - Math.max(...a[1].map((p) => p.score))
  );

  for (const [family, points] of ordered) {
    const color = points[0].color;
    const sorted = points.slice().sort((a, b) => a.cost - b.cost);

    if (els.showLines.checked && sorted.length > 1) {
      const d = sorted
        .map((p, i) => `${i ? "L" : "M"}${xScale(p.cost).toFixed(1)} ${yScale(p.score).toFixed(1)}`)
        .join(" ");
      svg.appendChild(el("path", {
        d, fill: "none", stroke: color, "stroke-width": 2,
        "stroke-dasharray": points[0].dash || "",
        "stroke-linecap": "round", "stroke-linejoin": "round",
      }));
    }

    for (const point of sorted) {
      const single = sorted.length === 1;
      const cx = xScale(point.cost), cy = yScale(point.score);
      const dot = single
        ? el("rect", {
            x: cx - 5.5, y: cy - 5.5, width: 11, height: 11, fill: color,
            transform: `rotate(45 ${cx} ${cy})`, class: "dot",
          })
        : el("circle", { cx, cy, r: 5, fill: color, class: "dot" });
      dot.addEventListener("mouseenter", (e) => showTooltip(e, point));
      dot.addEventListener("mousemove", moveTooltip);
      dot.addEventListener("mouseleave", hideTooltip);
      const title = el("title", {});
      title.textContent = `${point.model} — ${point.score.toFixed(2)} @ ${preciseMoney(point.cost)}`;
      dot.appendChild(title);
      svg.appendChild(dot);

      if (els.showEffortLabels.checked && point.effort) {
        const text = point.fallback ? `${point.effort} · fallback` : point.effort;
        const box = { x: cx, y: cy, w: text.length * 5.2 + 4, h: 11 };
        const spot = placeLabel(box, occupied, [
          [7, -4, "start"], [-7, -4, "end"], [7, 14, "start"], [-7, 14, "end"],
          [0, -12, "middle"], [0, 20, "middle"],
        ]);
        if (spot) {
          svg.appendChild(el("text", {
            x: cx + spot.dx, y: cy + spot.dy, "text-anchor": spot.anchor, class: "effort-label",
          }, text));
        }
      }
    }

    if (els.showFamilyLabels.checked) {
      const anchorPoint = sorted.reduce((best, p) =>
        p.score > best.score || (p.score === best.score && p.cost < best.cost) ? p : best
      );
      const cx = xScale(anchorPoint.cost), cy = yScale(anchorPoint.score);
      const box = { x: cx, y: cy, w: family.length * 6.6 + 6, h: 13 };
      const spot = placeLabel(box, occupied, [
        [10, -6, "start"], [-10, -6, "end"], [10, 16, "start"], [-10, 16, "end"],
        [0, -16, "middle"], [0, 24, "middle"], [18, 4, "start"], [-18, 4, "end"],
        [22, -20, "start"], [-22, -20, "end"], [22, 26, "start"], [-22, 26, "end"],
      ]);
      if (spot) {
        svg.appendChild(el("text", {
          x: cx + spot.dx, y: cy + spot.dy, "text-anchor": spot.anchor,
          class: "family-label", fill: color,
        }, family));
      }
    }
  }
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
