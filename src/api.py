import json
from pathlib import Path
from datetime import datetime
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
from src.config import MIN_AMOUNT, DOC_TYPES_AUTOCOMPLETE, ACCOUNTS_AUTOCOMPLETE, REPORT_TOP_N

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
    boosters = crud.get_boosters(db, company_id)
    data = train_and_score(data, X, boosters.lof_n_neighbors if boosters else 50)
    global_whitelist = crud.get_global_whitelist(db)
    whitelist = crud.get_whitelist(db, company_id)
    data = apply_score(data, boosters=boosters, whitelist_rules=whitelist + global_whitelist)

    top_n = min(int(len(data) * 0.01), 2000)
    report_bytes = generate_report(data, top_n)

    report_df = data[data["abs_amount"] >= MIN_AMOUNT].query("boosted_score > 0")
    total     = min(len(report_df), top_n)
    high_risk = int((report_df["boosted_score"] >= 80).sum())

    crud.add_history(db, company_id, file.filename, len(data), total, high_risk)

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=anomalies.xlsx",
            "X-Total-Anomalies": str(total),
            "X-Top-N": str(top_n),
            "Access-Control-Expose-Headers": "X-Total-Anomalies, X-Top-N",
        },
)


# ── Анализ (внешний API — по API ключу из 1С) ──

@app.post("/api/analyze/")
async def analyze_external(
    file: UploadFile = File(...),
    company=Depends(get_company_from_key),
    db: Session = Depends(get_db),
):
    return await analyze(company.id, file, db)


@app.post("/api/analyze/json/")
async def analyze_external_json(
    file: UploadFile = File(...),
    company=Depends(get_company_from_key),
    db: Session = Depends(get_db),
):
    data = load_data(file.file)
    data = clean_data(data)
    data, X = build_features(data)
    boosters = crud.get_boosters(db, company.id)
    data = train_and_score(data, X, boosters.lof_n_neighbors if boosters else 50)

    whitelist = crud.get_whitelist(db, company.id)
    data = apply_score(data, boosters=boosters, whitelist_rules=whitelist)

    report_df = (
        data[data["abs_amount"] >= MIN_AMOUNT]
        .query("boosted_score > 0")
        .nlargest(REPORT_TOP_N, "boosted_score")
    )

    anomalies = [
        {
            "date":        str(row.get("period", "")),
            "account_dt":  row.get("СчетДт", ""),
            "account_kt":  row.get("СчетКт", ""),
            "amount":      float(row.get("abs_amount", 0)),
            "contractor":  row.get("Контрагент", ""),
            "doc_type":    row.get("ТипДокумента", ""),
            "risk_score":  float(row.get("boosted_score", 0)),
            "reason":      row.get("explanation", ""),
        }
        for row in report_df.to_dict(orient="records")
    ]

    total     = len(anomalies)
    high_risk = sum(1 for a in anomalies if a["risk_score"] >= 80)

    crud.add_history(db, company.id, file.filename, len(data), total, high_risk)

    return {
        "company":        company.name,
        "analyzed_at":    datetime.now().isoformat(),
        "total_rows":     len(data),
        "anomalies_found": total,
        "high_risk":      high_risk,
        "anomalies":      anomalies,
    }


# ── Whitelist ──

class WhitelistRuleBody(BaseModel):
    type: str
    doc_type: str = ""
    account_pair: str = ""

@app.get("/whitelist/global/")
def get_global_whitelist(db: Session = Depends(get_db)):
    rules = crud.get_global_whitelist(db)
    return {"rules": [
        {"id": r.id, "type": r.type, "doc_type": r.doc_type, "account_pair": r.account_pair}
        for r in rules
    ]}

@app.post("/whitelist/global/")
def add_global_whitelist_rule(body: WhitelistRuleBody, db: Session = Depends(get_db)):
    rule = crud.add_global_whitelist_rule(db, body.type, body.doc_type, body.account_pair)
    return {"id": rule.id, "type": rule.type, "doc_type": rule.doc_type, "account_pair": rule.account_pair}

@app.delete("/whitelist/global/{rule_id}")
def delete_global_whitelist_rule(rule_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_global_whitelist_rule(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return {"ok": True}

@app.get("/companies/{company_id}/whitelist/")
def get_whitelist(company_id: int, db: Session = Depends(get_db)):
    rules = crud.get_whitelist(db, company_id)
    return {"rules": [
        {"id": r.id, "type": r.type, "doc_type": r.doc_type, "account_pair": r.account_pair, "is_global": r.is_global}
        for r in rules
    ]}

@app.post("/companies/{company_id}/whitelist/")
def add_whitelist_rule(company_id: int, body: WhitelistRuleBody, db: Session = Depends(get_db)):
    rule = crud.add_whitelist_rule(db, company_id, body.type, body.doc_type, body.account_pair)
    return {"id": rule.id, "type": rule.type, "doc_type": rule.doc_type, "account_pair": rule.account_pair, "is_global": rule.is_global}

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
    lof_n_neighbors: int = 50

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
        "lof_n_neighbors": b.lof_n_neighbors,
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