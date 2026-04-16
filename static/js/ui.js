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
        const highlighted = m.replace(
          new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
          s => `<b>${s}</b>`
        );
        return `<div class="ac-item" onmousedown="acSelect('${input.id}','${dropId}','${safe}')">${highlighted}</div>`;
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
  const valPanel = document.getElementById('col-validation');
  const chips    = document.getElementById('col-chips');
  const msg      = document.getElementById('col-val-msg');

  valPanel.style.display = 'block';

  // CSV с кодировкой cp1251 нельзя надёжно прочитать в браузере
  if (file.name.toLowerCase().endsWith('.csv')) {
    chips.innerHTML = REQUIRED_COLS.map(c =>
      `<span class="col-chip warn">? ${c}</span>`
    ).join('');
    msg.textContent = 'CSV-файл — проверка колонок выполнится на сервере';
    msg.className   = 'col-val-msg';
    msg.style.color = 'var(--orange)';
    document.getElementById('analyze-btn').disabled = false;
    return true;
  }

  chips.innerHTML = '<span style="font-size:12px;color:var(--muted);">Читаем файл...</span>';
  msg.textContent = '';

  try {
    const buf = await file.arrayBuffer();
    const wb  = XLSX.read(buf, { type: 'array', sheetRows: 2 });
    const ws  = wb.Sheets[wb.SheetNames[0]];
    const range = XLSX.utils.decode_range(ws['!ref'] || 'A1:A1');

    const headers = [];
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r: 0, c })];
      if (cell && cell.v) headers.push(String(cell.v).trim());
    }

    const missing = [];
    let allOk = true;

    chips.innerHTML = REQUIRED_COLS.map(col => {
      const found = headers.includes(col);
      if (!found) { allOk = false; missing.push(col); }
      return `<span class="col-chip ${found ? 'ok' : 'err'}">${found ? '✓' : '✗'} ${col}</span>`;
    }).join('');

    if (allOk) {
      msg.textContent = '✓ Все обязательные колонки найдены';
      msg.className   = 'col-val-msg ok';
      document.getElementById('analyze-btn').disabled = false;
      return true;
    } else {
      msg.textContent = `✗ Отсутствуют: ${missing.join(', ')}. Анализ невозможен.`;
      msg.className   = 'col-val-msg';
      document.getElementById('analyze-btn').disabled = true;
      return false;
    }

  } catch (e) {
    chips.innerHTML = REQUIRED_COLS.map(c =>
      `<span class="col-chip warn">? ${c}</span>`
    ).join('');
    msg.textContent = 'Не удалось проверить колонки — проверка выполнится на сервере';
    msg.style.color = 'var(--orange)';
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
      if (c === 'Дата' && val) {
        try { val = new Date(val).toLocaleString('ru'); } catch (e) {}
      }
      if ((c === 'Сумма' || c === 'Средняя сумма по паре') && val !== '') {
        val = Number(val).toLocaleString('ru');
      }
      return `<td>${val}</td>`;
    });

    const dt  = (row['Тип документа'] || '').replace(/'/g, "\\'");
    const ddt = (row['Счет Дт'] || '');
    const kkt = (row['Счет Кт'] || '');
    cells.push(`<td><button class="wl-btn" id="wlb-${idx}" 
      onclick="addToWhitelist(this,'${dt}','${ddt}','${kkt}')">В whitelist</button></td>`);

    return `<tr>${cells.join('')}</tr>`;
  }).join('');
}

function updateMetrics(rows) {
  const total = rows.length;
  const high  = rows.filter(r => r['Риск (0-100)'] >= 80).length;
  const med   = rows.filter(r => r['Риск (0-100)'] >= 60 && r['Риск (0-100)'] < 80).length;
  const maxR  = rows.length ? Math.max(...rows.map(r => r['Риск (0-100)'] || 0)) : 0;

  document.getElementById('m-total').textContent = total;
  document.getElementById('m-high').textContent  = high;
  document.getElementById('m-med').textContent   = med;
  document.getElementById('m-max').textContent   = maxR.toFixed(0);
}

// ── Whitelist рендер ──

function renderWhitelist(rules) {
  const list = document.getElementById('wl-list');
  document.getElementById('wl-count').textContent = rules.length ? `(${rules.length})` : '';

  if (!rules.length) {
    list.innerHTML = '<div class="wl-empty">Whitelist пуст. Добавляйте правила из таблицы кнопкой «В whitelist», или вручную ниже.</div>';
    return;
  }

  list.innerHTML = rules.map((r, i) => {
    const isDoc  = r.type === 'doc_type';
    const badge  = isDoc
      ? `<span class="wl-badge doc">Тип документа</span>`
      : `<span class="wl-badge pair">Пара счетов</span>`;
    const text   = isDoc
      ? `<div class="wl-rule-text">${r.doc_type}</div>`
      : `<div class="wl-rule-text">${r.account_pair.replace('_', '→')}<div class="wl-rule-sub">${r.doc_type}</div></div>`;
    return `<div class="wl-rule">${badge}${text}
      <button class="wl-del" onclick="deleteWlRule(${i})" title="Удалить">✕</button>
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

  list.innerHTML = [...runs].reverse().map((r, i) => `
    <div class="hist-item" id="hist-${i}">
      <div class="hist-date">${new Date(r.timestamp).toLocaleString('ru')}</div>
      <div class="hist-file">📄 ${r.filename}</div>
      ${r.dataset_rows ? `<div class="hist-rows">${r.dataset_rows.toLocaleString('ru')} строк</div>` : ''}
      <span class="hist-count">${r.total} аномалий</span>
      <span class="hist-high">${r.high_risk} высокий риск</span>
      <button class="hist-del" onclick="deleteHistRun(${i})" title="Удалить запись">✕</button>
    </div>`).join('');
}