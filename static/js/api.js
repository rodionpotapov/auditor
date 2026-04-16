// api.js — все запросы к серверу

const API = 'http://localhost:8000';

async function apiAnalyze(file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const resp = await fetch(`${API}/analyze/`, { method: 'POST', body: fd });
  if (!resp.ok) throw new Error(`Ошибка сервера ${resp.status}: ${await resp.text()}`);
  return await resp.arrayBuffer();
}

async function apiGetAutocomplete() {
  const resp = await fetch(`${API}/autocomplete/`);
  return await resp.json();
}

async function apiGetWhitelist() {
  const resp = await fetch(`${API}/whitelist/`);
  return await resp.json();
}

async function apiAddWhitelistRule(rule) {
  await fetch(`${API}/whitelist/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  });
}

async function apiDeleteWhitelistRule(idx) {
  await fetch(`${API}/whitelist/${idx}`, { method: 'DELETE' });
}

async function apiGetHistory() {
  const resp = await fetch(`${API}/history/`);
  return await resp.json();
}

async function apiDeleteHistoryRun(idx) {
  await fetch(`${API}/history/${idx}`, { method: 'DELETE' });
}

function apiExportWhitelistUrl() {
  return `${API}/whitelist/export/`;
}

async function apiImportWhitelist(file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const resp = await fetch(`${API}/whitelist/import/`, { method: 'POST', body: fd });
  return await resp.json();
}