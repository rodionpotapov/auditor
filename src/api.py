import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.data_processing import load_data, clean_data
from src.build_features import build_features
from src.model import train_and_score
from src.scoring import score as apply_score
from src.report_generator import generate_report
from src.config import MIN_AMOUNT, DOC_TYPES_AUTOCOMPLETE, ACCOUNTS_AUTOCOMPLETE

app = FastAPI(title="Аудитор проводок")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR       = Path(__file__).parent.parent
WHITELIST_PATH = BASE_DIR / "data" / "whitelist_dynamic.json"
HISTORY_PATH   = BASE_DIR / "data" / "history.json"

def _load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/analyze/")
async def analyze(file: UploadFile = File(...)):
    data = load_data(file.file)
    data = clean_data(data)
    data, X = build_features(data)
    data = train_and_score(data, X)
    data = apply_score(data)
    report_bytes = generate_report(data)

    report_df = data[data["abs_amount"] >= MIN_AMOUNT].query("boosted_score > 0")
    total     = min(len(report_df), 2000)
    high_risk = int((report_df["boosted_score"] >= 80).sum())

    history = _load_json(HISTORY_PATH, {"runs": []})
    history["runs"].append({
        "timestamp":    datetime.now().isoformat(),
        "filename":     file.filename,
        "total":        total,
        "high_risk":    high_risk,
        "dataset_rows": len(data),
    })
    _save_json(HISTORY_PATH, history)

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=anomalies.xlsx"},
    )


@app.get("/autocomplete/")
def get_autocomplete():
    return {"doc_types": DOC_TYPES_AUTOCOMPLETE, "accounts": ACCOUNTS_AUTOCOMPLETE}


class WhitelistRule(BaseModel):
    type: str
    doc_type: str = ""
    account_pair: str = ""

@app.get("/whitelist/")
def get_whitelist():
    return _load_json(WHITELIST_PATH, {"rules": []})

@app.post("/whitelist/")
def add_whitelist_rule(rule: WhitelistRule):
    wl = _load_json(WHITELIST_PATH, {"rules": []})
    r = rule.dict()
    if r not in wl["rules"]:
        wl["rules"].append(r)
        _save_json(WHITELIST_PATH, wl)
    return {"ok": True}

@app.delete("/whitelist/{idx}")
def delete_whitelist_rule(idx: int):
    wl = _load_json(WHITELIST_PATH, {"rules": []})
    if 0 <= idx < len(wl["rules"]):
        wl["rules"].pop(idx)
        _save_json(WHITELIST_PATH, wl)
    return {"ok": True}


# ── Whitelist экспорт / импорт ──

@app.get("/whitelist/export/")
def export_whitelist():
    """Скачать whitelist как JSON-файл."""
    wl = _load_json(WHITELIST_PATH, {"rules": []})
    return Response(
        content=json.dumps(wl, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=whitelist.json"},
    )

@app.post("/whitelist/import/")
async def import_whitelist(file: UploadFile = File(...)):
    """Загрузить whitelist из JSON-файла. Правила объединяются с существующими."""
    content = await file.read()
    try:
        incoming = json.loads(content.decode("utf-8"))
        new_rules = incoming.get("rules", [])
    except Exception:
        return {"ok": False, "error": "Неверный формат файла"}

    wl = _load_json(WHITELIST_PATH, {"rules": []})
    added = 0
    for rule in new_rules:
        if rule not in wl["rules"]:
            wl["rules"].append(rule)
            added += 1
    _save_json(WHITELIST_PATH, wl)
    return {"ok": True, "added": added, "total": len(wl["rules"])}


@app.get("/history/")
def get_history():
    return _load_json(HISTORY_PATH, {"runs": []})

@app.delete("/history/{idx}")
def delete_history_run(idx: int):
    history = _load_json(HISTORY_PATH, {"runs": []})
    # фронт показывает в обратном порядке, поэтому конвертируем индекс
    original_idx = len(history["runs"]) - 1 - idx
    if 0 <= original_idx < len(history["runs"]):
        history["runs"].pop(original_idx)
        _save_json(HISTORY_PATH, history)
    return {"ok": True}


static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")