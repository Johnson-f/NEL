(() => {
  const chart = document.querySelector('#chart');
  const metricControls = document.querySelector('#controls');
  const chartHead = document.querySelector('.chart-head');
  if (!chart || !metricControls || !chartHead || typeof rows === 'undefined' || typeof views === 'undefined') return;

  let selectedMetric = 'daily';
  let selectedRange = 66;
  const rangeControls = document.createElement('div');
  rangeControls.className = 'controls';
  rangeControls.setAttribute('aria-label', 'Chart range');
  chartHead.append(rangeControls);

  metricControls.innerHTML = '';
  Object.entries(views).forEach(([key, view]) => {
    const button = document.createElement('button');
    button.textContent = view.label;
    button.addEventListener('click', () => { selectedMetric = key; renderEnhancedChart(); });
    metricControls.append(button);
  });
  [[66, '3M'], [132, '6M'], [0, 'All']].forEach(([count, label]) => {
    const button = document.createElement('button');
    button.textContent = label;
    button.dataset.range = String(count);
    button.addEventListener('click', () => { selectedRange = count; renderEnhancedChart(); });
    rangeControls.append(button);
  });

  const svgText = (x, y, value, options = '') => `<text x="${x}" y="${y}" ${options}>${value}</text>`;
  const linePath = (data, key, x, y) => data.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');

  function significantT2108Points(data) {
    const windowSize = 4;
    const candidates = [];
    for (let index = windowSize; index < data.length - windowSize; index += 1) {
      const value = data[index].t2108;
      const neighborhood = data.slice(index - windowSize, index + windowSize + 1).map(row => row.t2108);
      const edgeAverage = (data[index - windowSize].t2108 + data[index + windowSize].t2108) / 2;
      if (value === Math.max(...neighborhood) && value - edgeAverage >= 4) candidates.push({ index, value, kind: 'Swing high', score: value - edgeAverage });
      if (value === Math.min(...neighborhood) && edgeAverage - value >= 4) candidates.push({ index, value, kind: 'Swing low', score: edgeAverage - value });
    }
    const highValue = Math.max(...data.map(row => row.t2108));
    const lowValue = Math.min(...data.map(row => row.t2108));
    const highIndex = data.findIndex(row => row.t2108 === highValue);
    const lowIndex = data.findIndex(row => row.t2108 === lowValue);
    const selected = [
      { index: highIndex, value: highValue, kind: 'Range high', score: Infinity },
      { index: lowIndex, value: lowValue, kind: 'Range low', score: Infinity },
      ...candidates.sort((a, b) => b.score - a.score),
    ];
    const result = [];
    for (const point of selected) {
      if (result.some(existing => Math.abs(existing.index - point.index) < 8)) continue;
      result.push(point);
      if (result.length === 8) break;
    }
    return result.sort((a, b) => a.index - b.index);
  }

  function renderEnhancedChart() {
    [...metricControls.children].forEach((button, index) => button.classList.toggle('active', Object.keys(views)[index] === selectedMetric));
    [...rangeControls.children].forEach(button => button.classList.toggle('active', Number(button.dataset.range) === selectedRange));
    const view = views[selectedMetric];
    const source = selectedRange ? rows.slice(0, selectedRange) : rows;
    const data = source.slice().reverse();
    const values = data.flatMap(row => view.keys.map(key => row[key]));
    let minimum = Math.min(...values);
    let maximum = Math.max(...values);
    if (selectedMetric !== 'ratios' && selectedMetric !== 't2108') minimum = 0;
    if (selectedMetric === 't2108') { minimum = 0; maximum = 100; }
    const padding = selectedMetric === 'ratios' ? Math.max((maximum - minimum) * 0.12, 0.05) : maximum * 0.07;
    if (selectedMetric !== 't2108') { minimum = Math.max(0, minimum - padding); maximum += padding; }
    const left = 60, right = 930, top = 24, bottom = 294;
    const x = index => left + index * ((right - left) / Math.max(data.length - 1, 1));
    const y = value => bottom - (value - minimum) / Math.max(maximum - minimum, 1) * (bottom - top);
    const colors = selectedMetric === 'ratios' ? ['#e9c46a', '#75baff'] : ['#62d6b4', '#ff6b8a'];
    let markup = '';

    for (let step = 0; step <= 4; step += 1) {
      const value = minimum + (maximum - minimum) * (4 - step) / 4;
      const position = top + (bottom - top) * step / 4;
      markup += `<path d="M${left},${position}H${right}" stroke="#414141" stroke-width="1"/>`;
      markup += svgText(7, position + 4, selectedMetric === 't2108' ? `${value.toFixed(0)}%` : value.toFixed(maximum < 10 ? 2 : 0), 'fill="#c8c4b9" font-size="12"');
    }
    if (selectedMetric === 'ratios') markup += `<path d="M${left},${y(1)}H${right}" stroke="#F5F2E8" stroke-dasharray="5 5" opacity=".8"/>${svgText(left + 5, y(1) - 6, 'Balance = 1.0', 'fill="#F5F2E8" font-size="11"')}`;
    if (selectedMetric === 't2108') {
      [[20, '20 — washed out'], [80, '80 — broad strength']].forEach(([level, label]) => {
        markup += `<path d="M${left},${y(level)}H${right}" stroke="#e9c46a" stroke-dasharray="6 5" opacity=".8"/>${svgText(left + 5, y(level) - 6, label, 'fill="#e9c46a" font-size="11"')}`;
      });
    }
    markup += view.keys.map((key, index) => `<path d="${linePath(data, key, x, y)}" stroke="${selectedMetric === 't2108' ? '#75baff' : colors[index]}" stroke-width="3" stroke-linejoin="round" fill="none"/>`).join('');

    if (selectedMetric === 't2108') {
      significantT2108Points(data).forEach(point => {
        const px = x(point.index), py = y(point.value), isHigh = point.kind.includes('high');
        const pointLabel = !selectedRange && point.kind.startsWith('Range') ? point.kind.replace('Range', 'History') : point.kind;
        const anchor = px > right - 120 ? 'end' : px < left + 70 ? 'start' : 'middle';
        const tx = anchor === 'end' ? px - 7 : anchor === 'start' ? px + 7 : px;
        const ty = isHigh ? py + 20 : py - 12;
        markup += `<circle cx="${px}" cy="${py}" r="5" fill="${isHigh ? '#e9c46a' : '#ff6b8a'}" stroke="#141414" stroke-width="2"><title>${pointLabel}: ${point.value.toFixed(2)}% on ${data[point.index].date}</title></circle>`;
        markup += svgText(tx, ty, `${pointLabel} ${point.value.toFixed(1)}%`, `text-anchor="${anchor}" fill="${isHigh ? '#e9c46a' : '#ff9bb0'}" font-size="11" font-weight="700"`);
      });
    } else {
      view.keys.forEach((key, index) => {
        const latest = data.at(-1), py = y(latest[key]), color = colors[index];
        markup += `<circle cx="${right}" cy="${py}" r="5" fill="${color}" stroke="#141414" stroke-width="2"><title>${view.label}: ${latest[key]} on ${latest.date}</title></circle>`;
        markup += svgText(right - 8, py + (index ? 16 : -9), latest[key].toFixed(maximum < 10 ? 2 : 0), `text-anchor="end" fill="${color}" font-size="12" font-weight="700"`);
      });
    }
    markup += svgText(left, 327, data[0].date, 'fill="#c8c4b9" font-size="12"');
    markup += svgText(right, 327, data.at(-1).date, 'text-anchor="end" fill="#c8c4b9" font-size="12"');
    chart.innerHTML = markup;
    document.querySelector('#chart-title').textContent = view.label;
    document.querySelector('#chart-note').textContent = selectedMetric === 't2108'
      ? 'Markers identify the visible range high/low and locally significant swings. The 20/80 lines are context zones, not automatic signals.'
      : `${view.note} Lines show the two sides through time; labels show the latest values.`;
  }

  renderEnhancedChart();
})();
