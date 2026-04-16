// app.js — навигация, параметры, анализ, whitelist, история, настройки

let currentCompanyId = null;
let selectedFile     = null;
let allRows          = [];
let showAll          = false;
let wlTab            = 'doc';
let docTypes         = [];
let accounts         = [];

// ── Инициализация ──

document.addEventListener('DOMContentLoaded', async () => {
  // Загружаем автокомплит
  apiGetAutocomplete().then(d => {
    docTypes = d.doc_types || [];
    accounts = d.accounts  || [];
  }).catch(() => {});

  // Загружаем компании и показываем селектор
  await loadCompanies();
});

// ── Компании ──

async function loadCompanies() {
  try {
    const companies = await apiGetCompanies();
    renderCompanySelector(companies, currentCompanyId);

    if (companies.length === 0) {
      showCompanyModal();
    } else if (!currentCompanyId) {
      currentCompanyId = companies[0].id;
      document.getElementById('company-select').value = currentCompanyId;
      updateCompanyBadge(companies[0].name);
    }
  } catch (e) {
    console.error('Не удалось загрузить компании:', e);
  }
}

function onCompanyChange(sel) {
  currentCompanyId = parseInt(sel.value);
  updateCompanyBadge(sel.options[sel.selectedIndex].text);
  allRows = [];
  document.getElementById('results').classList.remove('show');
  refreshCurrentPage();
}

function refreshCurrentPage() {
  const pageId = document.querySelector('.page.active')?.id;
  if (pageId === 'page-whitelist') loadWhitelist();
  else if (pageId === 'page-history')   loadHistory();
  else if (pageId === 'page-settings')  loadSettings();
}

function updateCompanyBadge(name) {
  const badge = document.getElementById('company-badge');
  if (badge) badge.textContent = name;
}

function showCompanyModal() {
  document.getElementById('company-modal').style.display = 'flex';
}

function hideCompanyModal() {
  document.getElementById('company-modal').style.display = 'none';
}

async function createCompanyFromModal() {
  const name = document.getElementById('new-company-name').value.trim();
  if (!name) return;
  const company = await apiCreateCompany(name);
  currentCompanyId = company.id;
  hideCompanyModal();
  await loadCompanies();
  updateCompanyBadge(company.name);
}

async function addNewCompany() {
  const name = prompt('Название юрлица:');
  if (!name || !name.trim()) return;
  const company = await apiCreateCompany(name.trim());
  await loadCompanies();
  currentCompanyId = company.id;
  document.getElementById('company-select').value = currentCompanyId;
  updateCompanyBadge(company.name);
}

// ── Навигация ──

function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  if (name === 'whitelist') loadWhitelist();
  if (name === 'history')   loadHistory();
  if (name === 'settings')  loadSettings();
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
  const btn = document.getElementById('allBtn');
  btn.classList.toggle('on', showAll);
  btn.textContent = showAll ? '✓ Все аномалии' : 'Все аномалии';

  document.getElementById('minRisk').classList.toggle('frozen', showAll);
  document.getElementById('topN').classList.toggle('frozen', showAll);
  document.getElementById('frozen-label').style.display = showAll ? 'block' : 'none';

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
  selectedFile = null; allRows = [];
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
  if (!selectedFile || !currentCompanyId) return;

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
    const bytes = await apiAnalyze(currentCompanyId, selectedFile);
    const wb    = XLSX.read(bytes, { type: 'array' });
    const ws    = wb.Sheets[wb.SheetNames[0]];
    allRows     = XLSX.utils.sheet_to_json(ws, { defval: '' });

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
  const f  = getFiltered();
  const ws = XLSX.utils.json_to_sheet(f);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Аномалии');
  XLSX.writeFile(wb, 'anomalies_filtered.xlsx');
}

// ── Whitelist ──

async function loadWhitelist() {
  if (!currentCompanyId) return;
  try {
    const data = await apiGetWhitelist(currentCompanyId);
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
  if (!currentCompanyId) return;
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
    ['wl-acct-dt', 'wl-acct-kt', 'wl-pair-doc'].forEach(id => document.getElementById(id).value = '');
  }
  await apiAddWhitelistRule(currentCompanyId, rule);
  loadWhitelist();
}

async function addToWhitelist(btn, docType, acctDt, acctKt) {
  if (!currentCompanyId || btn.classList.contains('added')) return;
  const rule = acctDt && acctKt
    ? { type: 'pair', account_pair: acctDt + '_' + acctKt, doc_type: docType }
    : { type: 'doc_type', doc_type: docType };
  await apiAddWhitelistRule(currentCompanyId, rule);
  btn.textContent = '✓ Добавлено';
  btn.classList.add('added');
}

async function deleteWlRule(ruleId) {
  await apiDeleteWhitelistRule(ruleId);
  loadWhitelist();
}

function exportWhitelist() {
  if (!currentCompanyId) return;
  window.open(apiExportWhitelistUrl(currentCompanyId), '_blank');
}

async function importWhitelist(input) {
  if (!currentCompanyId) return;
  const file = input.files[0];
  if (!file) return;
  try {
    const result = await apiImportWhitelist(currentCompanyId, file);
    if (result.ok) {
      alert(`✓ Загружено ${result.added} правил`);
      loadWhitelist();
    }
  } catch (e) {
    alert('Ошибка импорта: ' + e.message);
  }
  input.value = '';
}

// ── История ──

async function loadHistory() {
  if (!currentCompanyId) return;
  try {
    const data = await apiGetHistory(currentCompanyId);
    renderHistory(data.runs || []);
  } catch (e) {
    document.getElementById('hist-list').innerHTML = `<div class="empty-hint">Ошибка: ${e.message}</div>`;
  }
}

async function deleteHistRun(recordId) {
  await apiDeleteHistoryRun(recordId);
  loadHistory();
}

// ── Настройки ──

async function loadSettings() {
  if (!currentCompanyId) return;
  try {
    const b = await apiGetBoosters(currentCompanyId);
    renderBoosters(b);
    loadApiKeys();
  } catch (e) {
    console.error('Ошибка загрузки настроек:', e);
  }
}

async function saveBoosters() {
  if (!currentCompanyId) return;
  const keys = ['boost_manual', 'boost_amount_outlier', 'boost_night', 'boost_first_operation', 'boost_suspicious_pair'];
  const boosters = {};
  keys.forEach(k => {
    boosters[k] = parseFloat(document.getElementById('bslider-' + k).value);
  });
  await apiUpdateBoosters(currentCompanyId, boosters);
  const btn = document.getElementById('save-boosters-btn');
  btn.textContent = '✓ Сохранено';
  setTimeout(() => btn.textContent = 'Сохранить', 2000);
}

async function loadApiKeys() {
  if (!currentCompanyId) return;
  try {
    const keys = await apiGetApiKeys(currentCompanyId);
    const list  = document.getElementById('api-keys-list');
    if (!keys.length) {
      list.innerHTML = '<div class="empty-hint" style="padding:12px;">Нет ключей. Создайте первый.</div>';
      return;
    }
    list.innerHTML = keys.map(k => `
      <div class="api-key-row">
        <code class="api-key-val">${k.key}</code>
        <span class="api-key-date">${new Date(k.created_at).toLocaleDateString('ru')}</span>
        <button class="api-key-copy" onclick="copyKey('${k.key}')" title="Копировать">⎘</button>
        <button class="wl-del" onclick="deleteApiKey(${k.id})" title="Удалить">✕</button>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

async function createApiKey() {
  if (!currentCompanyId) return;
  await apiCreateApiKey(currentCompanyId);
  loadApiKeys();
}

async function deleteApiKey(keyId) {
  await apiDeleteApiKey(keyId);
  loadApiKeys();
}

function copyKey(key) {
  navigator.clipboard.writeText(key).then(() => {
    alert('Ключ скопирован');
  });
}

async function deleteCurrentCompany() {
  if (!currentCompanyId) return;
  const name = document.getElementById('company-select')
    .options[document.getElementById('company-select').selectedIndex].text;
  if (!confirm(`Удалить «${name}» и все связанные данные?`)) return;
  await apiDeleteCompany(currentCompanyId);
  currentCompanyId = null;
  await loadCompanies();
}