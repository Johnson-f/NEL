(() => {
  if (typeof rows === 'undefined' || !rows.length) return;

  const picker = document.querySelector('#asof-date');
  const pickerButton = document.querySelector('#asof-button');
  const pickerLabel = document.querySelector('#asof-label');
  const status = document.querySelector('#date');
  const overview = document.querySelector('#overview');
  const cycle = document.createElement('section');
  cycle.id = 'cycle';
  cycle.className = 'panel cycle-panel';
  overview.before(cycle);
  const cycleStyles = document.createElement('link');
  cycleStyles.rel = 'stylesheet';
  cycleStyles.href = 'assets/breadth-cycle.css?v=1';
  document.head.append(cycleStyles);
  const balances = document.querySelector('#balances');
  const table = document.querySelector('#table');
  const available = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => available(value)
    ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits })
    : '—';
  const fixed = (value, digits = 2) => available(value) ? Number(value).toFixed(digits) : '—';
  const signed = value => available(value) ? `${Number(value) > 0 ? '+' : ''}${fmt(value)}` : '—';
  const percent = value => available(value) ? `${fixed(value, 2)}%` : '—';

  function breadthStrength(row) {
    const components = [];
    const add = (value, weight) => {
      if (available(value)) components.push([Math.max(-1, Math.min(1, value)), weight]);
    };
    const balance = (up, down) => available(up) && available(down) && Number(up) + Number(down) > 0
      ? (Number(up) - Number(down)) / (Number(up) + Number(down))
      : null;
    const ratioBalance = value => available(value) && Number(value) >= 0
      ? (Number(value) - 1) / (Number(value) + 1)
      : null;
    add(balance(row.up4, row.down4), .15);
    add(ratioBalance(row.ratio5), .20);
    add(ratioBalance(row.ratio10), .20);
    add(balance(row.up25q, row.down25q), .15);
    add(balance(row.up13d34, row.down13d34), .15);
    add(available(row.t2108) ? (Number(row.t2108) - 50) / 50 : null, .15);
    const weight = components.reduce((sum, component) => sum + component[1], 0);
    return weight ? components.reduce((sum, component) => sum + component[0] * component[1], 0) / weight : 0;
  }

  function renderCycle(latest, index) {
    const strength = breadthStrength(latest);
    const older = rows[Math.min(index + 5, rows.length - 1)];
    const change = (strength - breadthStrength(older)) * 50;
    let phase;
    if (strength >= .16) phase = change < -4 ? 'Distribution' : 'Expansion';
    else if (strength <= -.16) phase = change > 4 ? 'Repair' : 'Contraction';
    else phase = change >= 0 ? 'Repair' : 'Distribution';
    const settings = {
      Expansion: { angle: 45, color: '#62d6b4', text: 'Participation is broadly positive. Upside pressure is established across several breadth windows.' },
      Distribution: { angle: 135, color: '#e9c46a', text: 'Participation is weakening. Index strength may hide a narrowing market, so watch whether selling pressure spreads.' },
      Contraction: { angle: 225, color: '#ff6b8a', text: 'Downside participation is dominant. Breadth remains under pressure until the short-term measures begin to repair.' },
      Repair: { angle: 315, color: '#75baff', text: 'Breadth is transitioning upward from weak or mixed conditions. Improvement is visible, but broad confirmation is still developing.' },
    }[phase];
    const direction = change > 1 ? ['↑', 'Improving'] : change < -1 ? ['↓', 'Weakening'] : ['→', 'Stable'];
    const score = Math.round(50 + strength * 50);
    cycle.style.setProperty('--cycle-color', settings.color);
    cycle.style.setProperty('--cycle-angle', `${settings.angle}deg`);
    cycle.innerHTML = `<div class="cycle-visual"><div class="cycle-wheel"><span class="cycle-name expansion">Expansion</span><span class="cycle-name distribution">Distribution</span><span class="cycle-name contraction">Contraction</span><span class="cycle-name repair">Repair</span><span class="cycle-dot" title="Current phase: ${phase}"></span><div class="cycle-center"><strong class="cycle-score">${score}</strong><span class="cycle-score-label">Breadth strength</span></div></div></div><div class="cycle-copy"><div class="eyebrow">Breadth cycle · ${latest.date}</div><h2>${phase}</h2><p>${settings.text}</p><div class="cycle-direction">${direction[0]} ${direction[1]} versus five sessions ago</div><div class="cycle-grid"><div class="cycle-stat"><span>Strength</span><b>${score} / 100</b></div><div class="cycle-stat"><span>5-session change</span><b>${change > 0 ? '+' : ''}${change.toFixed(1)} pts</b></div><div class="cycle-stat"><span>T2108</span><b>${percent(latest.t2108)}</b></div></div><div class="metric-note" style="margin-top:12px">Cycle estimate combines daily ±4% breadth, 5- and 10-day pressure, quarter and 34-day participation, and T2108. Use it as context—not a mechanical signal.</div></div>`;
  }

  picker.min = rows.at(-1).date;
  picker.max = rows[0].date;
  picker.value = rows[0].date;
  pickerLabel.textContent = rows[0].date;
  window.BREADTH_ASOF_INDEX = 0;

  pickerButton.addEventListener('click', () => {
    if (typeof picker.showPicker === 'function') picker.showPicker();
    else {
      picker.focus();
      picker.click();
    }
  });

  const pairs = [
    ['Quarter ±25%', 'up25q', 'down25q', 'Stocks ≥25% from a 65-day low vs ≤−25% from a 65-day high.'],
    ['Month ±25%', 'up25m', 'down25m', 'Strong one-month gainers versus strong one-month decliners.'],
    ['Month ±50%', 'up50m', 'down50m', 'Rare, high-velocity one-month moves; useful for spotting extremes.'],
    ['34 days ±13%', 'up13d34', 'down13d34', 'A broader intermediate-momentum participation measure.'],
  ];

  function renderSummary(latest) {
    const hasDaily = available(latest.up4) && available(latest.down4);
    const net = hasDaily ? Number(latest.up4) - Number(latest.down4) : null;
    const hasRatios = available(latest.ratio5) && available(latest.ratio10);
    const bothUp = hasRatios && latest.ratio5 > 1 && latest.ratio10 > 1;
    const bothDown = hasRatios && latest.ratio5 < 1 && latest.ratio10 < 1;
    const regime = bothUp && net > 0
      ? ['Buying pressure', 'up', 'Up/down pressure is positive today and across both rolling windows.']
      : bothDown && net < 0
        ? ['Selling pressure', 'down', 'Downside pressure leads today and across both rolling windows.']
        : ['Mixed / transition', 'gold', hasRatios ? 'Daily and rolling breadth are not aligned yet.' : 'Some historical measures are unavailable; use the visible readings together.'];
    const ratioCard = (label, key, note) => {
      const value = latest[key];
      const color = available(value) ? (value >= 1 ? 'up' : 'down') : '';
      return `<article class="panel"><div class="eyebrow">${label}</div><div class="big ${color}">${fixed(value)}</div><div class="metric-note">${note}</div></article>`;
    };
    overview.innerHTML = `<article class="panel regime"><div class="eyebrow">Read on ${latest.date}</div><div class="big ${regime[1]}">${regime[0]}</div><div class="metric-note">${regime[2]}</div></article><article class="panel"><div class="eyebrow">Up 4% / down 4%</div><div class="big"><span class="up">${fmt(latest.up4)}</span> / <span class="down">${fmt(latest.down4)}</span></div><div class="metric-note">Net breadth: ${signed(net)}</div></article>${ratioCard('5-day pressure ratio', 'ratio5', '5 sessions of up-4% events ÷ down-4% events')}${ratioCard('10-day pressure ratio', 'ratio10', '10 sessions; smoother confirmation of the short-term tape')}`;

    balances.innerHTML = pairs.map(([title, upKey, downKey, note]) => {
      const up = latest[upKey], down = latest[downKey];
      const total = available(up) && available(down) ? Math.max(Number(up) + Number(down), 1) : null;
      const upWidth = total ? Number(up) / total * 100 : 0;
      const downWidth = total ? Number(down) / total * 100 : 0;
      return `<article class="panel"><strong>${title}</strong><div class="metric-note">${note}</div><div class="pair"><span class="up">Up<b>${fmt(up)}</b></span><span class="down">Down<b>${fmt(down)}</b></span></div><div class="bar"><i style="width:${upWidth}%"></i><i style="width:${downWidth}%"></i></div></article>`;
    }).join('');
  }

  function renderTable(index) {
    table.innerHTML = rows.slice(index, index + 60).map(row => {
      const net = available(row.up4) && available(row.down4) ? row.up4 - row.down4 : null;
      return `<tr><td>${row.date}</td><td class="up">${fmt(row.up4)}</td><td class="down">${fmt(row.down4)}</td><td>${signed(net)}</td><td>${fixed(row.ratio5)}</td><td>${fixed(row.ratio10)}</td><td>${fmt(row.up25q)}</td><td>${fmt(row.down25q)}</td><td>${percent(row.t2108)}</td><td>${fmt(row.sp)}</td></tr>`;
    }).join('');
  }

  function selectDate(requestedDate) {
    let index = rows.findIndex(row => row.date <= requestedDate);
    if (index < 0) index = rows.length - 1;
    const latest = rows[index];
    window.BREADTH_ASOF_INDEX = index;
    picker.value = latest.date;
    pickerLabel.textContent = latest.date;
    status.textContent = latest.date === requestedDate ? 'Market close' : `Nearest prior market close`;
    renderCycle(latest, index);
    renderSummary(latest);
    renderTable(index);
    window.dispatchEvent(new CustomEvent('breadth-asof-change', { detail: { index, row: latest } }));
  }

  picker.addEventListener('change', () => {
    if (picker.value) selectDate(picker.value);
  });
  selectDate(rows[0].date);
})();
