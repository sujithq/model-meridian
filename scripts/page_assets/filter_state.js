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
