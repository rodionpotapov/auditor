# src/api.py

import json
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Header
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import engine, get_db
from src.models import Base
from src import crud
from src.data_processing import load_data, clean_data
from src.build_features import build_features
from src.model import train_and_score
from src.scoring import score as apply_score
from src.report_generator import generate_report
from src.config import MIN_AMOUNT, DOC_TYPES_AUTOCOMPLETE, ACCOUNTS_AUTOCOMPLETE

# Создаём таблицы при старте если не существуют
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Аудитор проводок")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent


# ── Dependency: компания по API ключу (для запросов из 1С) ──

def get_company_from_key(x_api_key: str = Header(...), db: Session = Depends(get_db)):
    company = crud.get_company_by_api_key(db, x_api_key)
    if not company:
        raise HTTPException(status_code=401, detail="Неверный API ключ")
    return company


# ── Companies ──

class CompanyCreate(BaseModel):
    name: str

@app.get("/companies/")
def list_companies(db: Session = Depends(get_db)):
    companies = crud.get_companies(db)
    return [{"id": c.id, "name": c.name, "created_at": c.created_at} for c in companies]

@app.post("/companies/")
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    existing = crud.get_company_by_name(db, body.name)
    if existing:
        return {"id": existing.id, "name": existing.name, "created_at": existing.created_at}
    company = crud.create_company(db, body.name)
    return {"id": company.id, "name": company.name, "created_at": company.created_at}

@app.delete("/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_company(db, company_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return {"ok": True}


# ── API Keys ──

@app.get("/companies/{company_id}/api-keys/")
def get_api_keys(company_id: int, db: Session = Depends(get_db)):
    keys = crud.get_api_keys(db, company_id)
    return [{"id": k.id, "key": k.key, "created_at": k.created_at} for k in keys]

@app.post("/companies/{company_id}/api-keys/")
def create_api_key(company_id: int, db: Session = Depends(get_db)):
    key = crud.create_api_key(db, company_id)
    return {"id": key.id, "key": key.key, "created_at": key.created_at}

@app.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_api_key(db, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Ключ не найден")
    return {"ok": True}


# ── Анализ (UI — по company_id) ──

@app.post("/analyze/{company_id}/")
async def analyze(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    company = crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    data = load_data(file.file)
    data = clean_data(data)
    data, X = build_features(data)
    data = train_and_score(data, X)

    boosters = crud.get_boosters(db, company_id)
    whitelist = crud.get_whitelist(db, company_id)
    data = apply_score(data, boosters=boosters, whitelist_rules=whitelist)

    report_bytes = generate_report(data)

    report_df = data[data["abs_amount"] >= MIN_AMOUNT].query("boosted_score > 0")
    total     = min(len(report_df), 2000)
    high_risk = int((report_df["boosted_score"] >= 80).sum())

    crud.add_history(db, company_id, file.filename, len(data), total, high_risk)

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=anomalies.xlsx"},
    )


# ── Анализ (внешний API — по API ключу из 1С) ──

@app.post("/api/analyze/")
async def analyze_external(
    file: UploadFile = File(...),
    company=Depends(get_company_from_key),
    db: Session = Depends(get_db),
):
    return await analyze(company.id, file, db)


# ── Whitelist ──

class WhitelistRuleBody(BaseModel):
    type: str
    doc_type: str = ""
    account_pair: str = ""

@app.get("/companies/{company_id}/whitelist/")
def get_whitelist(company_id: int, db: Session = Depends(get_db)):
    rules = crud.get_whitelist(db, company_id)
    return {"rules": [
        {"id": r.id, "type": r.type, "doc_type": r.doc_type, "account_pair": r.account_pair}
        for r in rules
    ]}

@app.post("/companies/{company_id}/whitelist/")
def add_whitelist_rule(company_id: int, body: WhitelistRuleBody, db: Session = Depends(get_db)):
    rule = crud.add_whitelist_rule(db, company_id, body.type, body.doc_type, body.account_pair)
    return {"id": rule.id, "type": rule.type, "doc_type": rule.doc_type, "account_pair": rule.account_pair}

@app.delete("/whitelist/{rule_id}")
def delete_whitelist_rule(rule_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_whitelist_rule(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return {"ok": True}

@app.get("/companies/{company_id}/whitelist/export/")
def export_whitelist(company_id: int, db: Session = Depends(get_db)):
    rules = crud.get_whitelist(db, company_id)
    data = {"rules": [{"type": r.type, "doc_type": r.doc_type, "account_pair": r.account_pair} for r in rules]}
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=whitelist.json"},
    )

@app.post("/companies/{company_id}/whitelist/import/")
async def import_whitelist(company_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        incoming = json.loads(content.decode("utf-8"))
        new_rules = incoming.get("rules", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный формат файла")
    added = 0
    for r in new_rules:
        crud.add_whitelist_rule(db, company_id, r.get("type", ""), r.get("doc_type", ""), r.get("account_pair", ""))
        added += 1
    return {"ok": True, "added": added}


# ── Бустеры ──

class BoostersBody(BaseModel):
    boost_manual: float = 1.5
    boost_amount_outlier: float = 1.3
    boost_night: float = 1.3
    boost_first_operation: float = 1.2
    boost_suspicious_pair: float = 1.5

@app.get("/companies/{company_id}/boosters/")
def get_boosters(company_id: int, db: Session = Depends(get_db)):
    b = crud.get_boosters(db, company_id)
    if not b:
        raise HTTPException(status_code=404, detail="Настройки не найдены")
    return {
        "boost_manual": b.boost_manual,
        "boost_amount_outlier": b.boost_amount_outlier,
        "boost_night": b.boost_night,
        "boost_first_operation": b.boost_first_operation,
        "boost_suspicious_pair": b.boost_suspicious_pair,
    }

@app.put("/companies/{company_id}/boosters/")
def update_boosters(company_id: int, body: BoostersBody, db: Session = Depends(get_db)):
    b = crud.update_boosters(db, company_id, **body.model_dump())
    return {"ok": True, "boost_manual": b.boost_manual}


# ── История ──

@app.get("/companies/{company_id}/history/")
def get_history(company_id: int, db: Session = Depends(get_db)):
    records = crud.get_history(db, company_id)
    return {"runs": [
        {
            "id": r.id,
            "filename": r.filename,
            "dataset_rows": r.dataset_rows,
            "total": r.total_anomalies,
            "high_risk": r.high_risk,
            "timestamp": r.timestamp.isoformat(),
        } for r in records
    ]}

@app.delete("/history/{record_id}")
def delete_history(record_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_history_record(db, record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"ok": True}


# ── Автокомплит ──

@app.get("/autocomplete/")
def get_autocomplete():
    return {"doc_types": DOC_TYPES_AUTOCOMPLETE, "accounts": ACCOUNTS_AUTOCOMPLETE}


# ── Статика — ПОСЛЕДНЕЙ ──

static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")