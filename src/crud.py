# src/crud.py

import secrets
from sqlalchemy.orm import Session
from src.models import Company, ApiKey, WhitelistRule, BoosterSettings, AnalysisHistory
from src.config import (
    BOOST_MANUAL, BOOST_AMOUNT_OUTLIER, BOOST_NIGHT,
    BOOST_FIRST_OPERATION, BOOST_SUSPICIOUS_PAIR,
    WHITELIST_DOC_TYPES, WHITELIST_PAIRS,
)


# ── Companies ──

def get_companies(db: Session) -> list[Company]:
    return db.query(Company).order_by(Company.name).all()

def get_company(db: Session, company_id: int) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).first()

def get_company_by_name(db: Session, name: str) -> Company | None:
    return db.query(Company).filter(Company.name == name).first()

def create_company(db: Session, name: str) -> Company:
    """Создаёт компанию с дефолтными бустерами и whitelist из config."""
    company = Company(name=name)
    db.add(company)
    db.flush()  # получаем id до commit

    # Дефолтные бустеры из config
    boosters = BoosterSettings(
        company_id=company.id,
        boost_manual=BOOST_MANUAL,
        boost_amount_outlier=BOOST_AMOUNT_OUTLIER,
        boost_night=BOOST_NIGHT,
        boost_first_operation=BOOST_FIRST_OPERATION,
        boost_suspicious_pair=BOOST_SUSPICIOUS_PAIR,
    )
    db.add(boosters)

    # Whitelist из config
    for doc_type in WHITELIST_DOC_TYPES:
        db.add(WhitelistRule(company_id=company.id, type="doc_type", doc_type=doc_type))
    for pair in WHITELIST_PAIRS:
        db.add(WhitelistRule(
            company_id=company.id,
            type="pair",
            doc_type=pair["doc_type"],
            account_pair=pair["account_pair"],
        ))

    # API ключ
    db.add(ApiKey(company_id=company.id, key=secrets.token_hex(32)))

    db.commit()
    db.refresh(company)
    return company

def delete_company(db: Session, company_id: int) -> bool:
    company = get_company(db, company_id)
    if not company:
        return False
    db.delete(company)
    db.commit()
    return True


# ── API Keys ──

def get_api_keys(db: Session, company_id: int) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.company_id == company_id).all()

def create_api_key(db: Session, company_id: int) -> ApiKey:
    key = ApiKey(company_id=company_id, key=secrets.token_hex(32))
    db.add(key)
    db.commit()
    db.refresh(key)
    return key

def delete_api_key(db: Session, key_id: int) -> bool:
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        return False
    db.delete(key)
    db.commit()
    return True

def get_company_by_api_key(db: Session, api_key: str) -> Company | None:
    key = db.query(ApiKey).filter(ApiKey.key == api_key).first()
    return key.company if key else None


# ── Whitelist ──

def get_whitelist(db: Session, company_id: int) -> list[WhitelistRule]:
    return db.query(WhitelistRule).filter(WhitelistRule.company_id == company_id).all()

def add_whitelist_rule(db: Session, company_id: int, type: str, doc_type: str = "", account_pair: str = "") -> WhitelistRule | None:
    # Проверяем дубли
    existing = db.query(WhitelistRule).filter(
        WhitelistRule.company_id == company_id,
        WhitelistRule.type == type,
        WhitelistRule.doc_type == doc_type,
        WhitelistRule.account_pair == account_pair,
    ).first()
    if existing:
        return existing

    rule = WhitelistRule(company_id=company_id, type=type, doc_type=doc_type, account_pair=account_pair)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

def delete_whitelist_rule(db: Session, rule_id: int) -> bool:
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


# ── Booster Settings ──

def get_boosters(db: Session, company_id: int) -> BoosterSettings | None:
    return db.query(BoosterSettings).filter(BoosterSettings.company_id == company_id).first()

def update_boosters(db: Session, company_id: int, **kwargs) -> BoosterSettings:
    boosters = get_boosters(db, company_id)
    if not boosters:
        boosters = BoosterSettings(company_id=company_id)
        db.add(boosters)

    allowed = {"boost_manual", "boost_amount_outlier", "boost_night", "boost_first_operation", "boost_suspicious_pair"}
    for key, val in kwargs.items():
        if key in allowed:
            setattr(boosters, key, float(val))

    db.commit()
    db.refresh(boosters)
    return boosters


# ── Analysis History ──

def add_history(db: Session, company_id: int, filename: str, dataset_rows: int, total_anomalies: int, high_risk: int) -> AnalysisHistory:
    record = AnalysisHistory(
        company_id=company_id,
        filename=filename,
        dataset_rows=dataset_rows,
        total_anomalies=total_anomalies,
        high_risk=high_risk,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def get_history(db: Session, company_id: int) -> list[AnalysisHistory]:
    return db.query(AnalysisHistory).filter(
        AnalysisHistory.company_id == company_id
    ).order_by(AnalysisHistory.timestamp.desc()).all()

def delete_history_record(db: Session, record_id: int) -> bool:
    record = db.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True