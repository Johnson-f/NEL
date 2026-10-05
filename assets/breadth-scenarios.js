(() => {
  if (typeof rows === 'undefined' || !rows.length) return;
  const cycle = document.querySelector('#cycle');
  if (!cycle) return;

  const section = document.createElement('section');
  section.id = 'spx-scenarios';
  section.className = 'panel scenario-panel';
  cycle.after(section);
  const styles = document.createElement('link');
  styles.rel = 'stylesheet';
  styles.href = 'assets/breadth-scenarios.css?v=1';
  document.head.append(styles);

  const horizons = [
    { label: '1 week', sessions: 5, threshold: .02 },
    { label: '1 month', sessions: 21, threshold: .05 },
    { label: '3 months', sessions: 63, threshold: .10 },
  ];
  const scenarios = [
    { key: 'up', label: 'Strong upside', color: '#62d6b4' },
    { key: 'range', label: 'Range / modest move', color: '#e9c46a' },
    { key: 'down', label: 'Meaningful downside', color: '#ff6b8a' },
  ];
  const featureCache = new Map();
  const available = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const clamp = value => Math.max(-1, Math.min(1, value));
  const pct = value => `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;

  function balance(up, down) {
    if (!available(up) || !available(down) || Number(up) + Number(down) <= 0) return null;
    return (Number(up) - Number(down)) / (Number(up) + Number(down));
  }

  function ratioBalance(value) {
    return available(value) && Number(value) >= 0 ? (Number(value) - 1) / (Number(value) + 1) : null;
  }

  function breadthStrength(row) {
    const values = [
      [balance(row.up4, row.down4), .15],
      [ratioBalance(row.ratio5), .20],
      [ratioBalance(row.ratio10), .20],
      [balance(row.up25q, row.down25q), .15],
      [balance(row.up13d34, row.down13d34), .15],
      [available(row.t2108) ? (Number(row.t2108) - 50) / 50 : null, .15],
    ].filter(item => available(item[0]));
    const weight = values.reduce((sum, item) => sum + item[1], 0);
    return weight ? values.reduce((sum, item) => sum + clamp(item[0]) * item[1], 0) / weight : null;
  }

  function pastReturn(index, sessions) {
    const older = rows[index + sessions];
    return older && available(rows[index].sp) && available(older.sp) ? Number(rows[index].sp) / Number(older.sp) - 1 : null;
  }

  function movingAverageDistance(index, sessions) {
    const sample = rows.slice(index, index + sessions).map(row => row.sp).filter(available).map(Number);
    if (sample.length < sessions || !available(rows[index].sp)) return null;
    return Number(rows[index].sp) / (sample.reduce((sum, value) => sum + value, 0) / sample.length) - 1;
  }

  function realizedVolatility(index, sessions = 21) {
    const returns = [];
    for (let offset = 0; offset < sessions; offset += 1) {
      const recent = rows[index + offset], older = rows[index + offset + 1];
      if (!recent || !older || !available(recent.sp) || !available(older.sp)) return null;
      returns.push(Math.log(Number(recent.sp) / Number(older.sp)));
    }
    const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
    const variance = returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / Math.max(returns.length - 1, 1);
    return Math.sqrt(variance * 252);
  }

  function features(index) {
    if (featureCache.has(index)) return featureCache.get(index);
    const row = rows[index], strength = breadthStrength(row);
    const olderStrength = rows[index + 5] ? breadthStrength(rows[index + 5]) : null;
    const result = [
      strength,
      available(strength) && available(olderStrength) ? strength - olderStrength : null,
      ratioBalance(row.ratio5),
      ratioBalance(row.ratio10),
      available(row.t2108) ? Number(row.t2108) / 100 : null,
      pastReturn(index, 21),
      pastReturn(index, 63),
      realizedVolatility(index),
      movingAverageDistance(index, 50),
      movingAverageDistance(index, 200),
    ];
    featureCache.set(index, result);
    return result;
  }

  function quantile(values, probability) {
    if (!values.length) return null;
    const sorted = values.slice().sort((a, b) => a - b);
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position), upper = Math.ceil(position);
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
  }

  function scenarioFor(value, threshold) {
    if (value >= threshold) return 'up';
    if (value <= -threshold) return 'down';
    return 'range';
  }

  function modelHorizon(asOfIndex, horizon) {
    const target = features(asOfIndex);
    const dimensions = target.map((value, index) => available(value) ? index : null).filter(value => value !== null);
    if (dimensions.length < 7) return null;

    const candidates = [];
    for (let index = asOfIndex + horizon.sessions; index < rows.length - 200; index += 1) {
      const vector = features(index);
      if (!dimensions.every(dimension => available(vector[dimension]))) continue;
      const endpoint = rows[index - horizon.sessions];
      if (!endpoint || !available(rows[index].sp) || !available(endpoint.sp)) continue;
      candidates.push({ index, vector, outcome: Number(endpoint.sp) / Number(rows[index].sp) - 1 });
    }
    if (candidates.length < 35) return null;

    const scales = dimensions.map(dimension => {
      const values = candidates.map(candidate => candidate.vector[dimension]);
      const spread = quantile(values, .75) - quantile(values, .25);
      return Math.max(spread / 1.349, .015);
    });
    candidates.forEach(candidate => {
      candidate.distance = Math.sqrt(dimensions.reduce((sum, dimension, position) => {
        const difference = (candidate.vector[dimension] - target[dimension]) / scales[position];
        return sum + difference ** 2;
      }, 0) / dimensions.length);
    });
    candidates.sort((a, b) => a.distance - b.distance);

    const analogs = [], spacing = Math.max(5, Math.round(horizon.sessions / 3));
    for (const candidate of candidates) {
      if (analogs.some(analog => Math.abs(analog.index - candidate.index) < spacing)) continue;
      analogs.push(candidate);
      if (analogs.length === 80) break;
    }
    if (analogs.length < 25) return null;

    const medianDistance = quantile(analogs.map(analog => analog.distance), .5) || 1;
    analogs.forEach(analog => { analog.weight = Math.exp(-analog.distance / medianDistance); });
    const categoryWeights = { up: 1, range: 1, down: 1 };
    analogs.forEach(analog => { categoryWeights[scenarioFor(analog.outcome, horizon.threshold)] += analog.weight; });
    const totalWeight = Object.values(categoryWeights).reduce((sum, value) => sum + value, 0);
    const probabilities = Object.fromEntries(Object.entries(categoryWeights).map(([key, value]) => [key, value / totalWeight]));
    const outcomes = analogs.map(analog => analog.outcome);
    return {
      analogs: analogs.length,
      probabilities,
      median: quantile(outcomes, .5),
      low: quantile(outcomes, .25),
      high: quantile(outcomes, .75),
      winner: scenarios.slice().sort((a, b) => probabilities[b.key] - probabilities[a.key])[0],
    };
  }

  function renderCard(horizon, result) {
    if (!result) return `<article class="scenario-card"><div class="scenario-card-head"><h3>${horizon.label}</h3><span class="scenario-sessions">${horizon.sessions} sessions</span></div><div class="scenario-empty">Not enough earlier, complete market history for this date.</div></article>`;
    const winnerProbability = result.probabilities[result.winner.key];
    return `<article class="scenario-card" style="--scenario-color:${result.winner.color}"><div class="scenario-card-head"><h3>${horizon.label}</h3><span class="scenario-sessions">${horizon.sessions} sessions</span></div><div class="scenario-winner"><div class="scenario-winner-label">Most likely · ${result.winner.label}</div><div class="scenario-probability">${Math.round(winnerProbability * 100)}%</div><div class="scenario-probability-note">Weighted share of similar historical setups</div></div><div class="scenario-bars">${scenarios.map(scenario => `<div class="scenario-row"><span>${scenario.label}</span><div class="scenario-track"><div class="scenario-fill" style="width:${result.probabilities[scenario.key] * 100}%;background:${scenario.color}"></div></div><span>${Math.round(result.probabilities[scenario.key] * 100)}%</span></div>`).join('')}</div><div class="scenario-stats"><div class="scenario-stat"><span>Median SPX return</span><b>${pct(result.median)}</b></div><div class="scenario-stat"><span>Middle 50% range</span><b>${pct(result.low)} to ${pct(result.high)}</b></div></div><div class="scenario-stats"><div class="scenario-stat"><span>Independent analogs</span><b>${result.analogs}</b></div><div class="scenario-stat"><span>Scenario threshold</span><b>±${(horizon.threshold * 100).toFixed(0)}%</b></div></div></article>`;
  }

  function render(index = Number(window.BREADTH_ASOF_INDEX || 0)) {
    const asOf = rows[index];
    const results = horizons.map(horizon => modelHorizon(index, horizon));
    section.innerHTML = `<div class="scenario-head"><div><div class="eyebrow">SPX historical scenario engine · ${asOf.date}</div><h2>What tended to happen next?</h2><p>Probabilities come from earlier market setups with similar breadth, breadth direction, SPX momentum, trend and volatility. Every historical Time Machine view uses only information and completed outcomes available by that selected date.</p></div><span class="scenario-badge">Historical analog odds</span></div><div class="scenario-grid">${horizons.map((horizon, position) => renderCard(horizon, results[position])).join('')}</div><div class="scenario-foot"><span>Adjacent dates are spaced apart so one market episode cannot dominate the analog sample.</span><span>Scenario odds are historical frequencies, not guaranteed forecasts.</span></div>`;
  }

  window.addEventListener('breadth-asof-change', event => render(event.detail.index));
  render();
})();
