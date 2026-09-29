"""Render interactive Theme and Sector ETF leadership pages."""

from __future__ import annotations

import json
from pathlib import Path

from etf_strength import OUTPUT_DIR, PROJECT_DIR, UNIVERSES


def render_dashboard(payload: dict, active_key: str) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    title = payload["title"]
    leader_label = "Theme Leaders" if active_key == "themes" else "Sector Leaders"
    return r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__ | Liquid Leadership</title>
  <meta name="description" content="Track leading market groups, non-extended ETFs, tight coils, and underlying stock holdings.">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <style>
    :root { color-scheme:dark; --bg:#141414; --panel:#2A2A2A; --track:#1b1b1b; --line:#454545; --text:#F5F2E8; --orange:#ff9900; --cyan:#00ffff; --pink:#ff3366; --lime:#ccff00; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:100%; max-width:2200px; margin:auto; padding:22px 34px 44px; }
    .site-nav { display:flex; justify-content:center; gap:7px; margin:0 0 18px; }
    .site-nav a { min-width:92px; padding:7px 13px; border:1px solid var(--line); border-radius:7px; color:var(--text); text-align:center; text-decoration:none; font-weight:650; }
    .site-nav a:hover,.site-nav a.active { background:var(--text); color:var(--bg); border-color:var(--text); }
    .topbar { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin-bottom:18px; }
    h1 { margin:0; font-size:20px; letter-spacing:-.01em; }
    h2 { margin:0; font-size:19px; }
    select,.button { width:128px; height:34px; border:0; border-radius:7px; padding:7px 9px; background:var(--text); color:var(--bg); font:650 13px/1 system-ui; }
    .button { cursor:pointer; }
    #snapshot { justify-self:end; }
    .section-heading { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin:27px 0 13px; }
    .section-heading h2 { grid-column:2; text-align:center; }
    .section-heading .button { grid-column:3; justify-self:end; }
    .windows { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:22px; align-items:start; }
    .card { min-width:0; background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--orange); border-radius:10px; padding:16px; }
    .card[data-frame="3m"] { border-top-color:var(--cyan); } .card[data-frame="6m"] { border-top-color:var(--pink); }
    .card h3 { color:var(--orange); margin:0 0 12px; font-size:14px; } .card[data-frame="3m"] h3 { color:var(--cyan); } .card[data-frame="6m"] h3 { color:var(--pink); }
    .table-wrap { width:100%; overflow:visible; }
    table { width:100%; table-layout:fixed; border-collapse:collapse; font-variant-numeric:tabular-nums; }
    th,td { padding:8px 5px; border-bottom:1px solid var(--line); text-align:right; vertical-align:middle; white-space:nowrap; }
    th { color:var(--text); font-size:11px; font-weight:650; }
    th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) { text-align:left; }
    td:first-child { font-weight:700; }
    .leaders-table th:nth-child(1) { width:8%; } .leaders-table th:nth-child(2) { width:31%; } .leaders-table th:nth-child(3) { width:15%; } .leaders-table th:nth-child(4) { width:17%; } .leaders-table th:nth-child(5) { width:14%; } .leaders-table th:nth-child(6) { width:15%; }
    .etf-table th:nth-child(1) { width:14%; } .etf-table th:nth-child(2) { width:29%; } .etf-table th:nth-child(3) { width:14%; } .etf-table th:nth-child(4) { width:11%; } .etf-table th:nth-child(5) { width:18%; } .etf-table th:nth-child(6) { width:14%; }
    .tight-table th:nth-child(1) { width:13%; } .tight-table th:nth-child(2) { width:27%; } .tight-table th:nth-child(3) { width:13%; } .tight-table th:nth-child(4) { width:13%; } .tight-table th:nth-child(5) { width:11%; } .tight-table th:nth-child(6) { width:12%; } .tight-table th:nth-child(7) { width:11%; }
    td:nth-child(2) { white-space:normal; overflow-wrap:anywhere; }
    .clickable { cursor:pointer; } .clickable:hover { background:#343434; }
    .ticker-button,.group-button { all:unset; color:inherit; cursor:pointer; font-weight:700; }
    .ticker-button:hover,.group-button:hover { text-decoration:underline; }
    .high-liquidity { color:var(--lime); }
    .muted { opacity:.72; } .empty { padding:28px 6px; text-align:left; }
    dialog { width:min(1040px,calc(100vw - 32px)); max-height:88vh; padding:0; border:1px solid var(--line); border-radius:12px; background:var(--panel); color:var(--text); box-shadow:0 24px 80px #000b; }
    dialog::backdrop { background:#000b; }
    .drawer-head { position:sticky; top:0; z-index:4; display:flex; align-items:center; justify-content:space-between; padding:16px 18px; background:var(--panel); border-bottom:1px solid var(--line); }
    .drawer-head h2 { font-size:18px; } .close { width:34px; height:34px; border:0; border-radius:50%; background:var(--text); color:var(--bg); cursor:pointer; font-size:20px; }
    .drawer-body { padding:18px; overflow:auto; }
    .drawer-subtitle { margin:18px 0 8px; font-size:14px; }
    .member-table th:nth-child(1) { width:13%; } .member-table th:nth-child(2) { width:28%; } .member-table th:nth-child(n+3) { width:auto; }
    .tabs { display:flex; flex-wrap:wrap; gap:7px; margin:10px 0 12px; }
    .tab { border:1px solid var(--line); border-radius:999px; background:var(--bg); color:var(--text); padding:7px 12px; cursor:pointer; font-weight:650; }
    .tab.active { color:var(--bg); background:var(--text); border-color:var(--text); }
    .holdings-table th:nth-child(1) { width:16%; } .holdings-table th:nth-child(2) { width:39%; } .holdings-table th:nth-child(3) { width:15%; } .holdings-table th:nth-child(4) { width:17%; } .holdings-table th:nth-child(5) { width:13%; }
    .footnote { margin:14px 0 0; font-size:12px; opacity:.72; }
    @media (max-width:1700px) { .windows { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:1120px) { main { padding:18px 14px 36px; } .windows { grid-template-columns:1fr; } }
    @media (max-width:640px) { .topbar { grid-template-columns:1fr; gap:10px; } #snapshot { justify-self:start; } .section-heading { grid-template-columns:1fr auto; } .section-heading h2 { grid-column:1; text-align:left; } .section-heading .button { grid-column:2; } .site-nav { justify-content:flex-start; overflow-x:auto; } }
  </style>
</head>
<body>
<main>
  <nav class="site-nav" aria-label="Dashboard pages"><a href="index.html">Stocks</a><a href="themes.html" data-page="themes">Themes</a><a href="sectors.html" data-page="sectors">Sectors</a></nav>
  <div class="topbar"><select id="date" aria-label="Snapshot date"></select><h1>__TITLE__</h1><button id="snapshot" class="button">Snapshot</button></div>
  <div class="section-heading"><h2 id="leaders-title">__LEADER_LABEL__</h2><button id="export-leaders" class="button">Export Leaders</button></div>
  <div id="leader-windows" class="windows"></div>
  <div class="section-heading"><h2 id="nel-title">Non-Extended ETF Leaders (NEL)</h2><button id="export-nel" class="button">Export NEL</button></div>
  <div id="nel-windows" class="windows"></div>
  <div class="section-heading"><h2 id="tight-title">Tight Non-Extended ETF Leaders (T-NEL)</h2><button id="export-tight" class="button">Export T-NEL</button></div>
  <div id="tight-windows" class="windows"></div>
</main>
<dialog id="holdings-dialog"><div class="drawer-head"><h2 id="drawer-title">Holdings</h2><button id="drawer-close" class="close" aria-label="Close">×</button></div><div id="drawer-body" class="drawer-body"></div></dialog>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const data = __DATA__;
const frames = { '1m':'1 month', '3m':'3 months', '6m':'6 months' };
const accents = { '1m':'#ff9900', '3m':'#00ffff', '6m':'#ff3366' };
const dateSelect = document.getElementById('date');
const leaderWindows = document.getElementById('leader-windows');
const nelWindows = document.getElementById('nel-windows');
const tightWindows = document.getElementById('tight-windows');
const dialog = document.getElementById('holdings-dialog');
const drawerTitle = document.getElementById('drawer-title');
const drawerBody = document.getElementById('drawer-body');
document.querySelector(`[data-page="${data.kind}"]`)?.classList.add('active');

function esc(value) { return String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function num(value, digits=1) { return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—'; }
function pct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function dollars(value) { const n=Number(value); if (!Number.isFinite(n)||n<=0) return '—'; if(n>=1e9) return `$${(n/1e9).toFixed(n>=10e9?0:1)}B`; return `$${Math.ceil(n/1e7)*10}M`; }
function current() { return data.snapshots[Number(dateSelect.value)] || null; }
function windowGroups(frame) { return current()?.windows?.[frame] || []; }
function members(frame) { return windowGroups(frame).flatMap(group => group.members); }
function uniqueMembers(filter) { const map=new Map(); Object.keys(frames).flatMap(frame => members(frame).filter(filter)).forEach(row => map.set(row.symbol,row)); return [...map.values()]; }
function isNEL(row) { return Number.isFinite(Number(row.extension)) && Number(row.extension) <= 4; }
function isTight(row) { return isNEL(row) && row.is_tight === true; }
function liquidityClass(row) { return Number(row.average_dollar_volume_30d)>450e6?'high-liquidity':''; }
function themeStyle(frame,row) { const leader=windowGroups(frame)[0]?.group; return row.group===leader?` style="color:${accents[frame]};font-weight:650"`:''; }

function renderLeaders(frame) {
  const rows=windowGroups(frame);
  const body=rows.map(group=>`<tr class="clickable group-row" data-frame="${frame}" data-group="${esc(group.group)}"><td>${group.rank}</td><td><button class="group-button">${esc(group.group)}</button></td><td>${num(group.score)}</td><td>${pct(group.median_performance)}</td><td>${esc(group.leader_etf)}</td><td>${group.confirmation}/${group.member_count}</td></tr>`).join('');
  return `<section class="card" data-frame="${frame}"><h3>${frames[frame]} top ${data.top_n}</h3><div class="table-wrap"><table class="leaders-table"><thead><tr><th>#</th><th>Group</th><th>Strength</th><th>Median</th><th>Leader</th><th>Confirmed</th></tr></thead><tbody>${body||'<tr><td colspan="6" class="empty">No ranking data.</td></tr>'}</tbody></table></div></section>`;
}
function renderETFTable(frame, tight=false) {
  const rows=members(frame).filter(tight?isTight:isNEL).sort((a,b)=>Number(b.performance)-Number(a.performance));
  const body=rows.map(row=>tight
    ? `<tr class="clickable etf-row" data-frame="${frame}" data-symbol="${esc(row.symbol)}"><td class="${liquidityClass(row)}"><button class="ticker-button">${esc(row.symbol)}</button></td><td${themeStyle(frame,row)}>${esc(row.group)}</td><td>${pct(row.performance)}</td><td>${esc(row.coil_setup)}</td><td>${num(row.rmv_15d)}</td><td>${pct(row.adrp)}</td><td>${num(row.extension)}×</td></tr>`
    : `<tr class="clickable etf-row" data-frame="${frame}" data-symbol="${esc(row.symbol)}"><td class="${liquidityClass(row)}"><button class="ticker-button">${esc(row.symbol)}</button></td><td${themeStyle(frame,row)}>${esc(row.group)}</td><td>${pct(row.performance)}</td><td>${pct(row.adrp)}</td><td class="${liquidityClass(row)}">${dollars(row.average_dollar_volume_30d)}</td><td>${num(row.extension)}×</td></tr>`).join('');
  const head=tight?'<tr><th>ETF</th><th>Group</th><th>Performance</th><th>Coil</th><th>RMV</th><th>ADR</th><th>Extension</th></tr>':'<tr><th>ETF</th><th>Group</th><th>Performance</th><th>ADR</th><th>Avg $ Vol</th><th>Extension</th></tr>';
  return `<section class="card" data-frame="${frame}"><h3>${frames[frame]} ${tight?'T-NEL':'NEL'}</h3><div class="table-wrap"><table class="${tight?'tight-table':'etf-table'}"><thead>${head}</thead><tbody>${body||`<tr><td colspan="${tight?7:6}" class="empty">No qualifying ETFs.</td></tr>`}</tbody></table></div></section>`;
}
function render() {
  leaderWindows.innerHTML=Object.keys(frames).map(renderLeaders).join('');
  nelWindows.innerHTML=Object.keys(frames).map(frame=>renderETFTable(frame,false)).join('');
  tightWindows.innerHTML=Object.keys(frames).map(frame=>renderETFTable(frame,true)).join('');
  document.getElementById('leaders-title').textContent=`__LEADER_LABEL__ - ${new Set(Object.keys(frames).flatMap(frame=>windowGroups(frame).map(g=>g.group))).size} Groups`;
  document.getElementById('nel-title').textContent=`Non-Extended ETF Leaders (NEL) - ${uniqueMembers(isNEL).length} Tickers`;
  document.getElementById('tight-title').textContent=`Tight Non-Extended ETF Leaders (T-NEL) - ${uniqueMembers(isTight).length} Tickers`;
}
function combinedHoldings(etfs) {
  const map=new Map(), denominator=Math.max(1,etfs.length);
  etfs.forEach(etf=>(data.holdings[etf]||[]).forEach(item=>{ const old=map.get(item.symbol)||{...item,weight:0,held_by:[]}; old.weight+=Number(item.weight||0)/denominator; old.held_by.push(etf); if(!old.average_dollar_volume_30d&&item.average_dollar_volume_30d) old.average_dollar_volume_30d=item.average_dollar_volume_30d; if(old.extension==null&&item.extension!=null) old.extension=item.extension; map.set(item.symbol,old); }));
  return [...map.values()].sort((a,b)=>b.weight-a.weight).slice(0,10);
}
function holdingRows(items) {
  return items.length?items.map(item=>`<tr><td>${esc(item.symbol)}</td><td>${esc(item.name)}</td><td>${pct(Number(item.weight)*100)}</td><td>${dollars(item.average_dollar_volume_30d)}</td><td>${num(item.extension)}×</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No qualifying stock holdings were reported.</td></tr>';
}
function holdingsTable(items) { return `<table class="holdings-table"><thead><tr><th>Ticker</th><th>Company</th><th>Weight</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody>${holdingRows(items)}</tbody></table>`; }
function openDrawer(groupName, groupMembers, initialSymbol=null) {
  const symbols=groupMembers.map(row=>row.symbol), combined=combinedHoldings(symbols);
  drawerTitle.textContent=initialSymbol?`${initialSymbol} Holdings`:`${groupName} Holdings`;
  const memberRows=groupMembers.map(row=>`<tr><td>${esc(row.symbol)}</td><td>${esc(row.description)}</td><td>${pct(row.performance)}</td><td>${pct(row.adrp)}</td><td>${dollars(row.average_dollar_volume_30d)}</td><td>${num(row.extension)}×</td></tr>`).join('');
  const tabs=initialSymbol?[initialSymbol]:['Combined',...symbols];
  drawerBody.innerHTML=`<h3 class="drawer-subtitle">ETF statistics</h3><table class="member-table"><thead><tr><th>ETF</th><th>Description</th><th>Performance</th><th>ADR</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody>${memberRows}</tbody></table><h3 class="drawer-subtitle">Top stock holdings</h3><div class="tabs">${tabs.map((tab,i)=>`<button class="tab ${i===0?'active':''}" data-tab="${esc(tab)}">${esc(tab)}</button>`).join('')}</div><div id="holding-content">${holdingsTable(initialSymbol?(data.holdings[initialSymbol]||[]):combined)}</div><p class="footnote">Current disclosed holdings retrieved ${esc(data.holdings_as_of)}. Cash, bonds, swaps, futures, options, collateral, commodities, crypto assets, and fund holdings are excluded. Average dollar volume and extension use the latest completed regular-session close.</p>`;
  drawerBody.querySelector('.tabs').addEventListener('click',event=>{ const button=event.target.closest('.tab'); if(!button)return; drawerBody.querySelectorAll('.tab').forEach(tab=>tab.classList.remove('active')); button.classList.add('active'); const key=button.dataset.tab; document.getElementById('holding-content').innerHTML=holdingsTable(key==='Combined'?combined:(data.holdings[key]||[])); });
  dialog.showModal();
}
document.addEventListener('click',event=>{
  const groupRow=event.target.closest('.group-row'); if(groupRow){ const group=windowGroups(groupRow.dataset.frame).find(item=>item.group===groupRow.dataset.group); if(group)openDrawer(group.group,group.members); return; }
  const etfRow=event.target.closest('.etf-row'); if(etfRow){ const row=members(etfRow.dataset.frame).find(item=>item.symbol===etfRow.dataset.symbol); if(row)openDrawer(row.group,[row],row.symbol); }
});
function exportSymbols(filter,prefix){ const rows=uniqueMembers(filter),csv=['symbol',...rows.map(row=>`"${row.symbol.replaceAll('"','""')}"`)].join('\n')+'\n'; const blob=new Blob([csv],{type:'text/csv'}),link=document.createElement('a'); link.download=`${prefix}_${current().date}.csv`; link.href=URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href); }
async function snapshot(){ const button=document.getElementById('snapshot'); if(typeof html2canvas!=='function'){alert('Snapshot exporter could not load.');return;} button.disabled=true; try{const canvas=await html2canvas(document.querySelector('main'),{backgroundColor:'#141414',scale:2,useCORS:true});const link=document.createElement('a');link.download=`${data.kind}-leadership-${current().date}.png`;link.href=canvas.toDataURL('image/png');link.click();}finally{button.disabled=false;} }
dateSelect.innerHTML=data.snapshots.map((snapshot,index)=>`<option value="${index}">${snapshot.date}</option>`).join(''); dateSelect.value=Math.max(0,data.snapshots.length-1); dateSelect.addEventListener('change',render);
document.getElementById('drawer-close').addEventListener('click',()=>dialog.close()); dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
document.getElementById('export-leaders').addEventListener('click',()=>exportSymbols(()=>true,`${data.kind}_leaders`));
document.getElementById('export-nel').addEventListener('click',()=>exportSymbols(isNEL,`${data.kind}_nel`));
document.getElementById('export-tight').addEventListener('click',()=>exportSymbols(isTight,`${data.kind}_tight_nel`));
document.getElementById('snapshot').addEventListener('click',snapshot); render();
</script>
</body>
</html>'''.replace("__TITLE__", title).replace("__LEADER_LABEL__", leader_label).replace("__DATA__", data)


def write_etf_dashboards() -> list[Path]:
    paths = []
    for config in UNIVERSES:
        payload_path = OUTPUT_DIR / f"{config.key}_snapshots.json"
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        config.page.write_text(render_dashboard(payload, config.key), encoding="utf-8")
        paths.append(config.page)
    return paths


if __name__ == "__main__":
    for path in write_etf_dashboards():
        print(f"Saved {path}")
