// api.js — все запросы к серверу

const API = 'http://localhost:8000';

// ── Companies ──

async function apiGetCompanies() {
  const resp = await fetch(`${API}/companies/`);
  return await resp.json();
}

async function apiCreateCompany(name) {
  const resp = await fetch(`${API}/companies/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return await resp.json();
}

async function apiDeleteCompany(companyId) {
  await fetch(`${API}/companies/${companyId}`, { method: 'DELETE' });
}

// ── API Keys ──

async function apiGetApiKeys(companyId) {
  const resp = await fetch(`${API}/companies/${companyId}/api-keys/`);
  return await resp.json();
}

async function apiCreateApiKey(companyId) {
  const resp = await fetch(`${API}/companies/${companyId}/api-keys/`, { method: 'POST' });
  return await resp.json();
}

async function apiDeleteApiKey(keyId) {
  await fetch(`${API}/api-keys/${keyId}`, { method: 'DELETE' });
}

// ── Анализ ──

async function apiAnalyze(companyId, file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const resp = await fetch(`${API}/analyze/${companyId}/`, { method: 'POST', body: fd });
  if (!resp.ok) throw new Error(`Ошибка сервера ${resp.status}: ${await resp.text()}`);
  const bytes = await resp.arrayBuffer();
  const total = resp.headers.get('X-Total-Anomalies');
  const topN  = resp.headers.get('X-Top-N');
  return { bytes, total: parseInt(total), topN: parseInt(topN) };
}

// ── Autocomplete ──

async function apiGetAutocomplete() {
  const resp = await fetch(`${API}/autocomplete/`);
  return await resp.json();
}

// ── Whitelist ──

async function apiGetWhitelist(companyId) {
  const resp = await fetch(`${API}/companies/${companyId}/whitelist/`);
  return await resp.json();
}

async function apiAddWhitelistRule(companyId, rule) {
  const resp = await fetch(`${API}/companies/${companyId}/whitelist/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  });
  return await resp.json();
}

async function apiGetGlobalWhitelist() {
  const resp = await fetch(`${API}/whitelist/global/`);
  return await resp.json();
}

async function apiAddGlobalWhitelistRule(rule) {
  const resp = await fetch(`${API}/whitelist/global/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  });
  return await resp.json();
}

async function apiDeleteGlobalWhitelistRule(ruleId) {
  await fetch(`${API}/whitelist/global/${ruleId}`, { method: 'DELETE' });
}

async function apiDeleteWhitelistRule(ruleId) {
  await fetch(`${API}/whitelist/${ruleId}`, { method: 'DELETE' });
}

function apiExportWhitelistUrl(companyId) {
  return `${API}/companies/${companyId}/whitelist/export/`;
}

async function apiImportWhitelist(companyId, file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const resp = await fetch(`${API}/companies/${companyId}/whitelist/import/`, {
    method: 'POST',
    body: fd,
  });
  return await resp.json();
}

// ── Бустеры ──

async function apiGetBoosters(companyId) {
  const resp = await fetch(`${API}/companies/${companyId}/boosters/`);
  return await resp.json();
}

async function apiUpdateBoosters(companyId, boosters) {
  const resp = await fetch(`${API}/companies/${companyId}/boosters/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(boosters),
  });
  return await resp.json();
}

// ── История ──

async function apiGetHistory(companyId) {
  const resp = await fetch(`${API}/companies/${companyId}/history/`);
  return await resp.json();
}

async function apiDeleteHistoryRun(recordId) {
  await fetch(`${API}/history/${recordId}`, { method: 'DELETE' });
}