function money(value) {
  if (value === 0) return "$0.00";
  const decimals = Math.max(2, Math.min(12, 2 - Math.floor(Math.log10(value))));
  return "$" + value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

function preciseMoney(value) {
  if (value >= 1) return "$" + value.toFixed(2);
  if (value >= 0.01) return "$" + value.toFixed(3);
  return "$" + value.toFixed(4);
}

function costTicks(lo, hi, scale) {
  if (scale === "logarithmic") {
    const ticks = [];
    for (let exponent = Math.floor(Math.log10(lo)); exponent <= Math.ceil(Math.log10(hi)); exponent++) {
      for (const multiplier of [1, 2, 5]) {
        const tick = multiplier * (10 ** exponent);
        if (tick >= lo && tick <= hi) ticks.push(tick);
      }
    }
    return ticks.length ? ticks : [lo, hi];
  }

  const rawStep = (hi - lo) / 5;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 5, 10].find((size) => size >= rawStep / magnitude) * magnitude;
  const ticks = [];
  for (let index = Math.ceil(lo / step); index <= Math.floor(hi / step); index++) {
    ticks.push(index * step);
  }
  return ticks;
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
