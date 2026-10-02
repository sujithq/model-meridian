"""Generate a self-contained Model Meridian page from a CSV export.

Usage:
    python scripts/generate_page.py data/data.csv
    python scripts/generate_page.py data/data.csv -o src/index.html --min-score 30

The page mirrors `generate_chart.py`: same CSV columns, same family and
reasoning-effort parsing, same colours and ordering. It adds hover tooltips with
the full record for each data point, plus live filtering by search text, score,
cost, vendor, family and reasoning effort.

The output file embeds its data and has no external dependencies, so it can be
opened directly from disk or published as a static page.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from chart_data import (
    DEFAULT_COLOR,
    EFFORT_ORDER,
    build_series,
    filter_points,
    parse_model_name,
    read_family_colors,
    read_points,
)

DASH_PATTERNS = ["", "7 4", "9 3 2 3", "3 2 1 2"]

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --bg: #ffffff;
    --ink: #1f1f1f;
    --muted: #5a5a5a;
    --line: #e2e2e2;
    --panel: #f7f7f8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif;
  }
  header {
    padding: 24px 28px 12px;
  }
  h1 { font-size: 26px; margin: 0 0 6px; }
  .subtitle { color: var(--muted); font-size: 15px; margin: 0; }
  .layout {
    display: grid;
    grid-template-columns: 290px minmax(0, 1fr);
    gap: 20px;
    padding: 12px 28px 28px;
    align-items: start;
  }
  @media (max-width: 960px) { .layout { grid-template-columns: 1fr; } }
  .panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 16px;
  }
  .panel h2 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin: 0 0 10px;
  }
  .field { margin-bottom: 16px; }
  .field label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .field output { font-weight: 400; color: var(--muted); }
  .field .hint {
    margin: 6px 0 0;
    font-size: 11.5px;
    font-weight: 400;
    color: var(--muted);
  }
  input[type="search"], input[type="number"] {
    width: 100%;
    padding: 7px 9px;
    border: 1px solid #cfcfd3;
    border-radius: 6px;
    font: inherit;
    font-size: 13px;
    background: #fff;
    color: inherit;
  }
  input[type="range"] { width: 100%; }
  .checks {
    max-height: 210px;
    overflow-y: auto;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #fff;
    padding: 6px 8px;
  }
  .checks label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 400;
    padding: 3px 0;
    cursor: pointer;
  }
  .checks label[hidden] { display: none; }
  .swatch {
    width: 11px;
    height: 11px;
    border-radius: 3px;
    flex: 0 0 auto;
  }
  .toggles label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 400;
    padding: 3px 0;
    cursor: pointer;
  }
  .row { display: flex; gap: 8px; }
  .row > * { flex: 1 1 0; min-width: 0; }
  button {
    font: inherit;
    font-size: 13px;
    padding: 7px 10px;
    border: 1px solid #cfcfd3;
    border-radius: 6px;
    background: #fff;
    color: inherit;
    cursor: pointer;
  }
  button:hover { background: #ececf0; }
  .chart-wrap {
    position: relative;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 8px;
    background: #fff;
  }
  svg { width: 100%; height: auto; display: block; }
  .status {
    font-size: 13px;
    color: var(--muted);
    padding: 8px 2px 0;
  }
  .axis-label { font-size: 15px; font-weight: 700; fill: var(--ink); }
  .tick-label { font-size: 12px; fill: #444; }
  .note { font-size: 10px; font-weight: 700; fill: #555; letter-spacing: 0.04em; }
  .family-label { font-size: 11.5px; font-weight: 700; }
  .effort-label { font-size: 9.5px; fill: #4a4a4a; }
  .dot { cursor: pointer; }
  .dot:hover { stroke: #1f1f1f; stroke-width: 2; }
  #tooltip {
    position: fixed;
    z-index: 10;
    pointer-events: none;
    background: #1f1f1f;
    color: #fff;
    border-radius: 8px;
    padding: 9px 11px;
    font-size: 12.5px;
    line-height: 1.5;
    max-width: 290px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    opacity: 0;
    transition: opacity 0.08s linear;
  }
  #tooltip.visible { opacity: 1; }
  #tooltip .tip-title { font-weight: 700; margin-bottom: 3px; }
  #tooltip .tip-row { color: #d9d9d9; }
  #tooltip .tip-row b { color: #fff; font-weight: 600; }
  footer { padding: 0 28px 28px; color: var(--muted); font-size: 13px; }
  .empty {
    padding: 40px;
    text-align: center;
    color: var(--muted);
    font-size: 14px;
  }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p class="subtitle">__SUBTITLE__</p>
</header>

<div class="layout">
  <aside class="panel">
    <h2>Filters</h2>

    <div class="field">
      <label for="search">Search models or families</label>
      <input type="search" id="search" placeholder="e.g. opus, gpt-6, gemini" autocomplete="off">
      <p class="hint">Separate multiple terms with commas to combine them.</p>
    </div>

    <div class="field">
      <label for="minScore">Minimum score <output id="minScoreOut"></output></label>
      <input type="range" id="minScore">
    </div>

    <div class="field">
      <label for="maxCost">Maximum cost per task <output id="maxCostOut"></output></label>
      <input type="range" id="maxCost">
    </div>

    <div class="field">
      <label>Reasoning effort</label>
      <div class="checks" id="effortChecks"></div>
    </div>

    <div class="field">
      <label>Model family</label>
      <div class="checks" id="familyChecks"></div>
    </div>

    <div class="field toggles">
      <label><input type="checkbox" id="showLines" checked> Connect efforts within a family</label>
      <label><input type="checkbox" id="showFamilyLabels" checked> Show family labels</label>
      <label><input type="checkbox" id="showEffortLabels"> Show effort labels</label>
    </div>

    <div class="row">
      <button type="button" id="selectAll">Select all</button>
      <button type="button" id="reset">Reset</button>
    </div>
  </aside>

  <main>
    <div class="chart-wrap">
      <svg id="chart" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Intelligence score versus cost per task"></svg>
      <div class="empty" id="empty" hidden>No models match the current filters.</div>
    </div>
    <p class="status" id="status"></p>
  </main>
</div>

<footer>__FOOTNOTE__</footer>
<div id="tooltip" role="tooltip"></div>

<script>
const DATA = __DATA__;
const CONFIG = __CONFIG__;
const TICK_LADDER = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                     1, 2, 5, 10, 20, 50, 100, 200, 500];
const SVG_NS = "http://www.w3.org/2000/svg";
const PAD = { top: 56, right: 40, bottom: 78, left: 86 };
const W = 1600, H = 900;

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

// Scrolling the filter panel must not nudge a slider sitting under the cursor.
[els.minScore, els.maxCost].forEach((slider) => {
  slider.addEventListener("wheel", () => {
    const before = slider.value;
    requestAnimationFrame(() => {
      if (slider.value !== before) {
        slider.value = before;
        render();
      }
    });
  }, { passive: true });
});

render();
</script>
</body>
</html>
"""


def dash_for(linestyle: object, index: int) -> str:
    """Translate a matplotlib-style line style into an SVG dash array."""
    if linestyle == "-":
        return ""
    if linestyle == "--":
        return DASH_PATTERNS[1]
    if linestyle == "-.":
        return DASH_PATTERNS[2]
    return DASH_PATTERNS[index % len(DASH_PATTERNS)]


def read_model_urls(path: Path) -> dict[str, str]:
    urls: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("model") or "").strip()
            if name:
                urls.setdefault(name, (row.get("model_url") or "").strip())
    return urls


def build_payload(args: argparse.Namespace) -> tuple[list[dict], dict]:
    source = Path(args.csv)
    points = read_points(source)
    if not points:
        raise SystemExit(f"No usable rows found in {source}")

    colors = read_family_colors(source)
    urls = read_model_urls(source)

    points = filter_points(points, args.min_score, args.max_cost, args.families)
    if not points:
        raise SystemExit("All rows were filtered out; relax --min-score/--max-cost/--families")

    series_list = build_series(points, colors)
    if args.top:
        series_list = series_list[: args.top]

    records: list[dict] = []
    family_meta: list[dict] = []
    for index, series in enumerate(series_list):
        dash = dash_for(series.linestyle, index)
        family_meta.append({"name": series.family, "color": series.color})
        for point in series.points:
            records.append(
                {
                    "model": point.model,
                    "family": point.family,
                    "effort": point.effort,
                    "fallback": point.fallback,
                    "cost": round(point.cost, 6),
                    "score": round(point.score, 4),
                    "color": series.color,
                    "dash": dash,
                    "url": urls.get(point.model, ""),
                }
            )

    if not records:
        raise SystemExit("No models remain after filtering")

    efforts = sorted(
        {r["effort"] or "(none)" for r in records},
        key=lambda e: (EFFORT_ORDER.get(e.lower(), 99), e),
    )
    config = {
        "xlabel": args.xlabel,
        "ylabel": args.ylabel,
        "efforts": efforts,
        "families": sorted(family_meta, key=lambda f: f["name"].lower()),
        "minScore": min(r["score"] for r in records),
        "maxScore": max(r["score"] for r in records),
        "minCost": min(r["cost"] for r in records),
        "maxCost": max(r["cost"] for r in records),
    }
    return records, config


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_page(args: argparse.Namespace) -> Path:
    records, config = build_payload(args)

    html = TEMPLATE
    html = html.replace("__DATA__", json.dumps(records, separators=(",", ":")))
    html = html.replace("__CONFIG__", json.dumps(config, separators=(",", ":")))
    html = html.replace("__TITLE__", escape_html(args.title))
    html = html.replace("__SUBTITLE__", escape_html(args.subtitle))
    html = html.replace("__FOOTNOTE__", escape_html(args.footnote))

    source = Path(args.csv)
    output = Path(args.output) if args.output else source.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("csv", help="Path to the CSV file with the model data")
    parser.add_argument("-o", "--output", help="Output HTML path (default: <csv>.html)")
    parser.add_argument("--title", default="Model Meridian")
    parser.add_argument(
        "--subtitle",
        default="Hover a data point for the full record. Use the filters to narrow the view.",
    )
    parser.add_argument("--xlabel", default="Cost per benchmark task (USD)")
    parser.add_argument("--ylabel", default="Intelligence Index Score")
    parser.add_argument(
        "--footnote",
        default="Data source: Artificial Analysis · Scores and task costs from the source dataset.",
    )
    parser.add_argument("--min-score", type=float, help="Only include models at or above this score")
    parser.add_argument("--max-cost", type=float, help="Only include models at or below this cost")
    parser.add_argument(
        "--families", nargs="+", help="Only include families whose name contains one of these substrings"
    )
    parser.add_argument("--top", type=int, help="Only include the N highest scoring families")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = build_page(args)
    print(f"Page written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
