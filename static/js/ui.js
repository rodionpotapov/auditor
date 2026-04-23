// ui.js — рендер таблицы, метрики, валидация колонок, автокомплит

const REQUIRED_COLS = ['Период', 'СчетДт', 'СчетКт', 'ВалютнаяСуммаДт'];

// ── Автокомплит ──

function acFilter(input, dropId, list) {
  const drop = document.getElementById(dropId);
  const q = input.value.toLowerCase().trim();
  const matches = q
    ? list.filter(x => x.toLowerCase().includes(q)).slice(0, 10)
    : list.slice(0, 10);

  drop.innerHTML = matches.length
    ? matches.map(m => {
        const safe = m.replace(/'/g, "\\'");
        const hl   = m.replace(
          new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
          s => `<b>${s}</b>`
        );
        return `<div class="ac-item" onmousedown="acSelect('${input.id}','${dropId}','${safe}')">${hl}</div>`;
      }).join('')
    : '<div class="ac-empty">Не найдено — введите своё значение</div>';

  drop.classList.add('show');
}

function acSelect(inputId, dropId, val) {
  document.getElementById(inputId).value = val;
  setTimeout(() => acHide(dropId), 100);
}

function acHide(dropId) {
  setTimeout(() => document.getElementById(dropId).classList.remove('show'), 150);
}

// ── Валидация колонок ──

async function validateColumns(file) {
  if (file.name.toLowerCase().endsWith('.csv')) {
    document.getElementById('analyze-btn').disabled = false;
    return true;
  }

  try {
    const buf   = await file.arrayBuffer();
    const wb    = XLSX.read(buf, { type: 'array', sheetRows: 2 });
    const ws    = wb.Sheets[wb.SheetNames[0]];
    const range = XLSX.utils.decode_range(ws['!ref'] || 'A1:A1');
    const headers = [];
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r: 0, c })];
      if (cell && cell.v) headers.push(String(cell.v).trim());
    }

    const missing = REQUIRED_COLS.filter(col => !headers.includes(col));

    if (missing.length > 0) {
      const valPanel = document.getElementById('col-validation');
      const chips    = document.getElementById('col-chips');
      const msg      = document.getElementById('col-val-msg');
      valPanel.style.display = 'block';
      chips.innerHTML = REQUIRED_COLS.map(col => {
        const found = headers.includes(col);
        return `<span class="col-chip ${found ? 'ok' : 'err'}">${found ? '✓' : '✗'} ${col}</span>`;
      }).join('');
      msg.textContent = `✗ Отсутствуют: ${missing.join(', ')}. Анализ невозможен.`;
      msg.className   = 'col-val-msg';
      document.getElementById('analyze-btn').disabled = true;
      return false;
    }

    document.getElementById('analyze-btn').disabled = false;
    return true;

  } catch (e) {
    document.getElementById('analyze-btn').disabled = false;
    return true;
  }
}

// ── Таблица ──

function renderTable(rows) {
  const cols = [
    'Дата', 'Счет Дт', 'Счет Кт', 'Сумма', 'Средняя сумма по паре',
    'Контрагент', 'Тип документа', 'Риск (0-100)', 'Причина'
  ];

  document.getElementById('table-head').innerHTML =
    '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '<th>Действие</th></tr>';

  document.getElementById('table-body').innerHTML = rows.map((row, idx) => {
    const risk = row['Риск (0-100)'] || 0;
    const cls  = risk >= 80 ? 'risk-high' : risk >= 60 ? 'risk-med' : 'risk-low';

    const cells = cols.map(c => {
      if (c === 'Риск (0-100)') return `<td><span class="risk-badge ${cls}">${risk}</span></td>`;
      let val = row[c] || '';
      if (typeof val === 'number') {
        const d = new Date(Math.round((val - 25569) * 86400 * 1000));
        val = isNaN(d) ? val : d.toLocaleDateString('ru') + ' ' + d.toLocaleTimeString('ru', {hour:'2-digit',minute:'2-digit'});
      } else {
        val = String(val);
      }
      if ((c === 'Сумма' || c === 'Средняя сумма по паре') && val !== '' && val != null) {
        const n = Number(val);
        val = isNaN(n) ? val : n.toLocaleString('ru');
      }
      return `<td>${val}</td>`;
    });

    const dt  = (row['Тип документа'] || '').replace(/'/g, "\\'");
    const ddt = row['Счет Дт'] || '';
    const kkt = row['Счет Кт'] || '';
    cells.push(`<td><button class="wl-btn" id="wlb-${idx}"
      onclick="addToWhitelist(this,'${dt}','${ddt}','${kkt}')">В whitelist</button></td>`);

    return `<tr>${cells.join('')}</tr>`;
  }).join('');
}

function updateMetrics(rows) {
  document.getElementById('m-total').textContent = rows.length;
  document.getElementById('m-high').textContent  = rows.filter(r => r['Риск (0-100)'] >= 80).length;
  document.getElementById('m-med').textContent   = rows.filter(r => r['Риск (0-100)'] >= 60 && r['Риск (0-100)'] < 80).length;
  document.getElementById('m-max').textContent   = rows.length
    ? Math.max(...rows.map(r => r['Риск (0-100)'] || 0)).toFixed(0) : '—';
}

// ── Whitelist рендер ──

function renderWhitelist(rules) {
  const list = document.getElementById('wl-list');
  document.getElementById('wl-count').textContent = rules.length ? `(${rules.length})` : '';

  if (!rules.length) {
    list.innerHTML = '<div class="wl-empty">Whitelist пуст. Добавляйте правила из таблицы кнопкой «В whitelist», или вручную ниже.</div>';
    return;
  }

  list.innerHTML = rules.map(r => {
    const isDoc = r.type === 'doc_type';
    const isGlobal = !!r.is_global;
    const badge = isDoc
      ? `<span class="wl-badge doc">Тип документа</span>`
      : `<span class="wl-badge pair">Пара счетов</span>`;
    const text = isDoc
      ? `<div class="wl-rule-text">${r.doc_type}</div>`
      : `<div class="wl-rule-text">${r.account_pair.replace('_', '→')}<div class="wl-rule-sub">${r.doc_type}</div></div>`;
    const globalBtn = `<button class="wl-global-btn ${isGlobal ? 'active' : ''}"
      onclick="toggleGlobalRule(${r.id},'${r.type}','${r.doc_type}','${r.account_pair}',${isGlobal})"
      title="${isGlobal ? 'Убрать из глобального' : 'Сделать глобальным'}">🌐</button>`;
    return `<div class="wl-rule">${badge}${text}
      ${globalBtn}
      <button class="wl-del" onclick="deleteWlRule(${r.id}, ${isGlobal === true})" title="Удалить">✕</button>
    </div>`;
  }).join('');
}

// ── История рендер ──

function renderHistory(runs) {
  const list = document.getElementById('hist-list');
  if (!runs.length) {
    list.innerHTML = '<div class="empty-hint">История пуста. Запустите анализ чтобы появилась первая запись.</div>';
    return;
  }
  list.innerHTML = runs.map(r => `
    <div class="hist-item">
      <div class="hist-date">${new Date(r.timestamp).toLocaleString('ru')}</div>
      <div class="hist-file">📄 ${r.filename}</div>
      ${r.dataset_rows ? `<div class="hist-rows">${r.dataset_rows.toLocaleString('ru')} строк</div>` : ''}
      <span class="hist-count">${r.total} аномалий</span>
      <span class="hist-high">${r.high_risk} высокий риск</span>
      <button class="hist-del" onclick="deleteHistRun(${r.id})" title="Удалить">✕</button>
    </div>`).join('');
}
// ── Компании рендер ──


function renderBoosters(b) {
  const fields = [
    { key: 'boost_manual',          label: 'Ручная проводка',               max: 1.7, tip: 'Коэффициент для ручных проводок (is_manual=1)' },
    { key: 'boost_suspicious_pair', label: 'Подозрительная пара счетов',    max: 1.7, tip: 'Пара из списка заведомо проблемных' },
    { key: 'boost_amount_outlier',  label: 'Крупная сумма',                 max: 1.4, tip: 'Сумма выбивается из нормы для данной пары счетов' },
    { key: 'boost_night',           label: 'Нерабочее время',               max: 1.4, tip: 'Операция сделана ночью или в выходной' },
    { key: 'boost_first_operation', label: 'Первая операция с контрагентом', max: 1.3, tip: 'Контрагент встречается впервые' },
    { key: 'lof_n_neighbors', label: 'Чувствительность модели', min: 5, max: 100, step: 5, tip: 'Больше значение — строже. Меньше — мягче. По умолчанию: 50' },
  ];

  document.getElementById('boosters-form').innerHTML = fields.map(f => `
    <div class="booster-row">
      <div class="booster-label">
        ${f.label}
        <div class="tip-wrap"><button class="tip-btn">?</button><div class="tip-text">${f.tip}</div></div>
      </div>
      <div class="booster-val-row">
        <input type="range" class="booster-slider" id="bslider-${f.key}"
          min="${f.min ?? 1.0}" max="${f.max}" step="${f.step ?? 0.05}" value="${b[f.key] || (f.min ?? 1.0)}">
        <div class="booster-minmax" style="display: flex; justify-content: space-between; width: 100%; font-size: 12px; color: gray; margin-top: 4px;"><span>Стандарт.</span>		-->		<span>Макс.</span></div>
      </div>
    </div>`).join('');
}


function renderCompanySelector(companies, currentId) {
  const sel = document.getElementById('company-select');
  sel.innerHTML = companies.map(c =>
    `<option value="${c.id}" ${c.id === currentId ? 'selected' : ''}>${c.name}</option>`
  ).join('');
}