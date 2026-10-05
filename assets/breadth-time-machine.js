(() => {
  if (typeof rows === 'undefined' || !rows.length) return;

  const picker = document.querySelector('#asof-date');
  const status = document.querySelector('#date');
  const overview = document.querySelector('#overview');
  const balances = document.querySelector('#balances');
  const table = document.querySelector('#table');
  const available = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => available(value)
    ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits })
    : '—';
  const fixed = (value, digits = 2) => available(value) ? Number(value).toFixed(digits) : '—';
  const signed = value => available(value) ? `${Number(value) > 0 ? '+' : ''}${fmt(value)}` : '—';
  const percent = value => available(value) ? `${fixed(value, 2)}%` : '—';

  picker.min = rows.at(-1).date;
  picker.max = rows[0].date;
  picker.value = rows[0].date;
  window.BREADTH_ASOF_INDEX = 0;

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
    status.textContent = latest.date === requestedDate ? 'Market close' : `Nearest prior market close`;
    renderSummary(latest);
    renderTable(index);
    window.dispatchEvent(new CustomEvent('breadth-asof-change', { detail: { index, row: latest } }));
  }

  picker.addEventListener('change', () => {
    if (picker.value) selectDate(picker.value);
  });
  selectDate(rows[0].date);
})();
