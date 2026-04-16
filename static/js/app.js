// app.js — навигация, параметры, анализ, whitelist, история

let selectedFile = null;
let allRows      = [];
let showAll      = false;
let wlTab        = 'doc';
let docTypes     = [];
let accounts     = [];

// ── Инициализация ──

document.addEventListener('DOMContentLoaded', () => {
  apiGetAutocomplete().then(d => {
    docTypes = d.doc_types || [];
    accounts = d.accounts  || [];
  }).catch(() => {});
});

// ── Навигация ──

function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  if (name === 'whitelist') loadWhitelist();
  if (name === 'history')   loadHistory();
}

// ── Параметры анализа ──

function onMinRiskChange(val) {
  if (showAll) return;
  document.getElementById('minRiskVal').textContent = val;
  updateAvailCount();
  if (allRows.length) { renderTable(getFiltered()); updateMetrics(getFiltered()); }
}

function onTopNChange(val) {
  if (showAll) return;
  document.getElementById('topNVal').textContent = val;
  if (allRows.length) { renderTable(getFiltered()); updateMetrics(getFiltered()); }
}

function updateAvailCount() {
  if (!allRows.length) return;
  const minRisk = parseInt(document.getElementById('minRisk').value);
  const avail   = allRows.filter(r => (r['Риск (0-100)'] || 0) >= minRisk).length;
  const slider  = document.getElementById('topN');
  const curVal  = parseInt(slider.value);

  slider.max = Math.max(avail, 1);
  document.getElementById('topN-max-label').textContent = avail;
  document.getElementById('topN-of').textContent = avail > 0 ? 'из ' + avail : '';

  if (curVal > avail) {
    slider.value = avail;
    document.getElementById('topNVal').textContent = avail;
  }

  document.getElementById('avail-hint').innerHTML = avail > 0
    ? `<b>${avail}</b> аномалий с риском ≥ ${minRisk}`
    : `<span style="color:var(--red)">Нет аномалий с риском ≥ ${minRisk}</span>`;
}

function toggleAll() {
  showAll = !showAll;
  const btn          = document.getElementById('allBtn');
  const minRiskSlider = document.getElementById('minRisk');
  const topNSlider    = document.getElementById('topN');
  const frozenLabel   = document.getElementById('frozen-label');

  btn.classList.toggle('on', showAll);
  btn.textContent = showAll ? '✓ Все аномалии' : 'Все аномалии';

  minRiskSlider.classList.toggle('frozen', showAll);
  topNSlider.classList.toggle('frozen', showAll);
  frozenLabel.style.display = showAll ? 'block' : 'none';

  if (allRows.length) { renderTable(getFiltered()); updateMetrics(getFiltered()); }
}

function getFiltered() {
  if (showAll) return allRows;
  const topN    = parseInt(document.getElementById('topN').value);
  const minRisk = parseInt(document.getElementById('minRisk').value);
  return allRows.filter(r => (r['Риск (0-100)'] || 0) >= minRisk).slice(0, topN);
}

// ── Файл ──

function handleFile(file) {
  if (!file) return;
  selectedFile = file;
  document.getElementById('drop-zone').style.display  = 'none';
  document.getElementById('file-info').style.display  = 'flex';
  document.getElementById('file-name-text').textContent = file.name;
  document.getElementById('file-size-text').textContent = (file.size / 1024).toFixed(0) + ' КБ';
  validateColumns(file);
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  handleFile(e.dataTransfer.files[0]);
}

function removeFile() {
  selectedFile = null;
  allRows      = [];

  document.getElementById('file-info').style.display      = 'none';
  document.getElementById('drop-zone').style.display      = 'block';
  document.getElementById('col-validation').style.display = 'none';
  document.getElementById('analyze-btn').disabled          = true;
  document.getElementById('results').classList.remove('show');
  document.getElementById('file-input').value              = '';
  document.getElementById('avail-hint').textContent        = 'Запустите анализ';
  document.getElementById('topN-of').textContent           = '';
  document.getElementById('topN-max-label').textContent    = '—';
}

// ── Анализ ──

async function runAnalysis() {
  if (!selectedFile) return;

  const btn      = document.getElementById('analyze-btn');
  const loader   = document.getElementById('loader');
  const progress = document.getElementById('progress-bar');
  const errorBar = document.getElementById('error-bar');

  btn.disabled = true;
  loader.classList.add('show');
  progress.classList.add('show');
  errorBar.classList.remove('show');
  document.getElementById('results').classList.remove('show');

  try {
    const bytes = await apiAnalyze(selectedFile);
    const wb    = XLSX.read(bytes, { type: 'array' });
    const ws    = wb.Sheets[wb.SheetNames[0]];
    allRows     = XLSX.utils.sheet_to_json(ws, { defval: '' });

    // Инициализируем слайдер топа по реальным данным
    document.getElementById('topN').max = allRows.length;
    updateAvailCount();

    const filtered = getFiltered();
    renderTable(filtered);
    updateMetrics(filtered);

    const okBar = document.getElementById('ok-bar');
    okBar.style.display = 'flex';
    document.getElementById('ok-file').textContent  = selectedFile.name;
    document.getElementById('ok-total').textContent = 'Всего аномалий: ' + allRows.length;
    document.getElementById('ok-high').textContent  = 'Показано: ' + filtered.length;

    document.getElementById('results').classList.add('show');
    document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (e) {
    errorBar.textContent = '❌ ' + e.message;
    errorBar.classList.add('show');
  } finally {
    btn.disabled = false;
    loader.classList.remove('show');
    progress.classList.remove('show');
  }
}

function downloadFiltered() {
  const filtered = getFiltered();
  const ws = XLSX.utils.json_to_sheet(filtered);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Аномалии');
  XLSX.writeFile(wb, 'anomalies_filtered.xlsx');
}

// ── Whitelist ──

async function loadWhitelist() {
  try {
    const data = await apiGetWhitelist();
    renderWhitelist(data.rules || []);
  } catch (e) {
    document.getElementById('wl-list').innerHTML = `<div class="empty-hint">Ошибка: ${e.message}</div>`;
  }
}

function switchWlTab(tab, el) {
  wlTab = tab;
  document.querySelectorAll('.wl-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('wl-tab-doc').style.display  = tab === 'doc'  ? 'block' : 'none';
  document.getElementById('wl-tab-pair').style.display = tab === 'pair' ? 'block' : 'none';
}

async function submitWlRule() {
  let rule;
  if (wlTab === 'doc') {
    const val = document.getElementById('wl-doc-type').value.trim();
    if (!val) return;
    rule = { type: 'doc_type', doc_type: val };
    document.getElementById('wl-doc-type').value = '';
  } else {
    const dt  = document.getElementById('wl-acct-dt').value.trim();
    const kt  = document.getElementById('wl-acct-kt').value.trim();
    const doc = document.getElementById('wl-pair-doc').value.trim();
    if (!dt || !kt) return;
    rule = { type: 'pair', account_pair: dt + '_' + kt, doc_type: doc };
    ['wl-acct-dt', 'wl-acct-kt', 'wl-pair-doc'].forEach(id => {
      document.getElementById(id).value = '';
    });
  }
  await apiAddWhitelistRule(rule);
  loadWhitelist();
}

async function addToWhitelist(btn, docType, acctDt, acctKt) {
  if (btn.classList.contains('added')) return;
  const rule = acctDt && acctKt
    ? { type: 'pair', account_pair: acctDt + '_' + acctKt, doc_type: docType }
    : { type: 'doc_type', doc_type: docType };
  await apiAddWhitelistRule(rule);
  btn.textContent = '✓ Добавлено';
  btn.classList.add('added');
}

async function deleteWlRule(idx) {
  await apiDeleteWhitelistRule(idx);
  loadWhitelist();
}

function exportWhitelist() {
  window.open(apiExportWhitelistUrl(), '_blank');
}

async function importWhitelist(input) {
  const file = input.files[0];
  if (!file) return;
  try {
    const result = await apiImportWhitelist(file);
    if (result.ok) {
      alert(`✓ Загружено ${result.added} новых правил. Всего: ${result.total}`);
      loadWhitelist();
    } else {
      alert('Ошибка: ' + result.error);
    }
  } catch (e) {
    alert('Ошибка импорта: ' + e.message);
  }
  input.value = '';
}

// ── История ──

async function loadHistory() {
  try {
    const data = await apiGetHistory();
    renderHistory(data.runs || []);
  } catch (e) {
    document.getElementById('hist-list').innerHTML = `<div class="empty-hint">Ошибка: ${e.message}</div>`;
  }
}

async function deleteHistRun(idx) {
  await apiDeleteHistoryRun(idx);
  loadHistory();
}