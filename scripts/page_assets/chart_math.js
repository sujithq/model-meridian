const TICK_LADDER = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                     1, 2, 5, 10, 20, 50, 100, 200, 500];

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
