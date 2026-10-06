(() => {
  if (typeof rows === 'undefined' || !rows.length) return;
  const cycle = document.querySelector('#cycle');
  if (!cycle) return;

  const section = document.createElement('section');
  section.id = 'spx-scenarios';
  section.className = 'panel scenario-panel';
  const readingsTable = document.querySelector('.table-card');
  if (readingsTable) readingsTable.before(section);
  else cycle.after(section);
  const styles = document.createElement('link');
  styles.rel = 'stylesheet';
  styles.href = 'assets/breadth-scenarios.css?v=4';
  document.head.append(styles);

  const horizons = [
    { label: '1 month', sessions: 21, threshold: .05 },
    { label: '3 months', sessions: 63, threshold: .10 },
    { label: '6 months', sessions: 126, threshold: .15 },
    { label: '1 year', sessions: 252, threshold: .20 },
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
      pastReturn(index, 5),
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

  function weightedQuantile(items, probability) {
    if (!items.length) return null;
    const ordered = items.slice().sort((a, b) => a.value - b.value);
    const total = ordered.reduce((sum, item) => sum + item.weight, 0);
    const target = total * probability;
    let cumulative = 0;
    for (const item of ordered) {
      cumulative += item.weight;
      if (cumulative >= target) return item.value;
    }
    return ordered.at(-1).value;
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
      const sharedDimensions = dimensions.filter(dimension => available(vector[dimension]));
      if (sharedDimensions.length < 7) continue;
      const endpoint = rows[index - horizon.sessions];
      if (!endpoint || !available(rows[index].sp) || !available(endpoint.sp)) continue;
      candidates.push({ index, vector, sharedDimensions, outcome: Number(endpoint.sp) / Number(rows[index].sp) - 1 });
    }
    if (candidates.length < 35) return null;

    const scales = dimensions.map(dimension => {
      const values = candidates.map(candidate => candidate.vector[dimension]).filter(available);
      const spread = quantile(values, .75) - quantile(values, .25);
      return Math.max(spread / 1.349, .015);
    });
    candidates.forEach(candidate => {
      const squaredDistance = candidate.sharedDimensions.reduce((sum, dimension) => {
        const position = dimensions.indexOf(dimension);
        const difference = (candidate.vector[dimension] - target[dimension]) / scales[position];
        return sum + difference ** 2;
      }, 0) / candidate.sharedDimensions.length;
      const missingPenalty = Math.sqrt(dimensions.length / candidate.sharedDimensions.length);
      candidate.distance = Math.sqrt(squaredDistance) * missingPenalty;
    });
    candidates.sort((a, b) => a.distance - b.distance);

    // Every eligible historical date contributes, but distant matches decay quickly.
    // The bandwidth is adaptive, so a selected date is compared with its own historical neighborhood.
    const bandwidth = Math.max(quantile(candidates.map(candidate => candidate.distance), .15), .05);
    candidates.forEach(candidate => {
      candidate.rawWeight = Math.exp(-.5 * (candidate.distance / bandwidth) ** 2);
    });

    // Forward outcomes overlap. Divide each observation by the nearby kernel mass so a long,
    // persistent market episode cannot count as dozens of independent confirmations.
    const chronological = candidates.slice().sort((a, b) => a.index - b.index);
    const prefix = [0];
    chronological.forEach(candidate => prefix.push(prefix.at(-1) + candidate.rawWeight));
    let lower = 0, upper = 0;
    chronological.forEach((candidate, position) => {
      while (chronological[lower].index < candidate.index - horizon.sessions + 1) lower += 1;
      if (upper < position) upper = position;
      while (upper + 1 < chronological.length && chronological[upper + 1].index <= candidate.index + horizon.sessions - 1) upper += 1;
      const localMass = prefix[upper + 1] - prefix[lower];
      candidate.weight = candidate.rawWeight / Math.max(localMass, candidate.rawWeight);
      candidate.baseWeight = 1 / (upper - lower + 1);
    });

    const categoryWeights = { up: 1, range: 1, down: 1 };
    const baseCategoryWeights = { up: 1, range: 1, down: 1 };
    candidates.forEach(candidate => { categoryWeights[scenarioFor(candidate.outcome, horizon.threshold)] += candidate.weight; });
    candidates.forEach(candidate => { baseCategoryWeights[scenarioFor(candidate.outcome, horizon.threshold)] += candidate.baseWeight; });
    const totalWeight = Object.values(categoryWeights).reduce((sum, value) => sum + value, 0);
    const baseTotalWeight = Object.values(baseCategoryWeights).reduce((sum, value) => sum + value, 0);
    const conditionalProbabilities = Object.fromEntries(Object.entries(categoryWeights).map(([key, value]) => [key, value / totalWeight]));
    const baseProbabilities = Object.fromEntries(Object.entries(baseCategoryWeights).map(([key, value]) => [key, value / baseTotalWeight]));
    // Similarity contributes a measured tilt, while the broader historical base rate prevents
    // a noisy neighborhood from creating overconfident probabilities.
    const similarityInfluence = horizon.sessions === 21 ? .75 : 1;
    const probabilities = Object.fromEntries(Object.keys(categoryWeights).map(key => [
      key,
      baseProbabilities[key] + similarityInfluence * (conditionalProbabilities[key] - baseProbabilities[key]),
    ]));
    const weightedOutcomes = candidates.map(candidate => ({ value: candidate.outcome, weight: candidate.weight }));
    const weightSum = candidates.reduce((sum, candidate) => sum + candidate.weight, 0);
    return {
      eligible: candidates.length,
      coreMatches: candidates.filter(candidate => candidate.distance <= bandwidth).length,
      effectiveEpisodes: weightSum,
      probabilities,
      baseProbabilities,
      edgeStrength: Math.max(...Object.keys(probabilities).map(key => Math.abs(probabilities[key] - baseProbabilities[key]))),
      median: weightedQuantile(weightedOutcomes, .5),
      low: weightedQuantile(weightedOutcomes, .25),
      high: weightedQuantile(weightedOutcomes, .75),
      winner: scenarios.slice().sort((a, b) => probabilities[b.key] - probabilities[a.key])[0],
    };
  }

  function renderCard(horizon, result) {
    if (!result) return `<article class="scenario-card"><div class="scenario-card-head"><h3>${horizon.label}</h3><span class="scenario-sessions">${horizon.sessions} sessions</span></div><div class="scenario-empty">Not enough earlier, complete market history for this date.</div></article>`;
    const winnerProbability = result.probabilities[result.winner.key];
    const hasMeasurableEdge = result.edgeStrength >= .01;
    const edge = winnerProbability - result.baseProbabilities[result.winner.key];
    const headline = hasMeasurableEdge ? `Most likely · ${result.winner.label}` : 'No measurable analog edge';
    const probabilityNote = hasMeasurableEdge
      ? `${edge >= 0 ? '+' : ''}${(edge * 100).toFixed(1)} pts versus the historical base rate`
      : `Similar setups remain near the ${result.winner.label.toLowerCase()} base rate`;
    return `<article class="scenario-card" style="--scenario-color:${result.winner.color}"><div class="scenario-card-head"><h3>${horizon.label}</h3><span class="scenario-sessions">${horizon.sessions} sessions</span></div><div class="scenario-winner"><div class="scenario-winner-label">${headline}</div><div class="scenario-probability">${(winnerProbability * 100).toFixed(1)}%</div><div class="scenario-probability-note">${probabilityNote}</div></div><div class="scenario-bars">${scenarios.map(scenario => `<div class="scenario-row"><span>${scenario.label}</span><div class="scenario-track"><div class="scenario-fill" style="width:${result.probabilities[scenario.key] * 100}%;background:${scenario.color}"></div></div><span>${(result.probabilities[scenario.key] * 100).toFixed(1)}%</span></div>`).join('')}</div><div class="scenario-stats"><div class="scenario-stat"><span>Median SPX return</span><b>${pct(result.median)}</b></div><div class="scenario-stat"><span>Middle 50% range</span><b>${pct(result.low)} to ${pct(result.high)}</b></div></div><div class="scenario-stats"><div class="scenario-stat"><span>Effective episodes</span><b>${Math.round(result.effectiveEpisodes)}</b></div><div class="scenario-stat"><span>Eligible history</span><b>${result.eligible.toLocaleString()} dates</b></div></div><div class="scenario-stats"><div class="scenario-stat"><span>Core similar dates</span><b>${result.coreMatches.toLocaleString()}</b></div><div class="scenario-stat"><span>Scenario threshold</span><b>±${(horizon.threshold * 100).toFixed(0)}%</b></div></div></article>`;
  }

  function render(index = Number(window.BREADTH_ASOF_INDEX || 0)) {
    const asOf = rows[index];
    const results = horizons.map(horizon => modelHorizon(index, horizon));
    section.innerHTML = `<div class="scenario-head"><div><div class="eyebrow">SPX historical scenario engine · ${asOf.date}</div><h2>What tended to happen next?</h2><p>Every eligible earlier setup contributes according to similarity in breadth, SPX momentum, trend and volatility. Overlapping forward periods are down-weighted so one persistent episode cannot dominate. Time Machine calculations use only information and completed outcomes available by the selected date.</p></div><span class="scenario-badge">Historical analog odds</span></div><div class="scenario-grid">${horizons.map((horizon, position) => renderCard(horizon, results[position])).join('')}</div><div class="scenario-foot"><span>Effective episodes reflect similarity weights and overlapping-outcome adjustment—not a fixed sample cap.</span><span>Scenario odds are historical frequencies, not guaranteed forecasts.</span></div>`;
  }

  window.addEventListener('breadth-asof-change', event => render(event.detail.index));
  render();
})();
