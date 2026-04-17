import secrets
from datetime import datetime, timezone

def _utcnow():
    return datetime.now(timezone.utc)

from sqlalchemy import (
    Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Company(Base):
    __tablename__ = "companies"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    name:       Mapped[str]      = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Связи
    api_keys:         Mapped[list["ApiKey"]]          = relationship(back_populates="company", cascade="all, delete-orphan")
    whitelist_rules:  Mapped[list["WhitelistRule"]]   = relationship(back_populates="company", cascade="all, delete-orphan")
    booster_settings: Mapped["BoosterSettings"]       = relationship(back_populates="company", cascade="all, delete-orphan", uselist=False)
    analysis_history: Mapped[list["AnalysisHistory"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int]      = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    key:        Mapped[str]      = mapped_column(String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped["Company"] = relationship(back_populates="api_keys")


class WhitelistRule(Base):
    __tablename__ = "whitelist_rules"
    __table_args__ = (
        UniqueConstraint("company_id", "type", "doc_type", "account_pair", name="uq_whitelist_rule"),
    )

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    company_id:   Mapped[int]      = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    type:         Mapped[str]      = mapped_column(String(20), nullable=False)   # "doc_type" | "pair"
    doc_type:     Mapped[str]      = mapped_column(String(255), default="")
    account_pair: Mapped[str]      = mapped_column(String(50),  default="")
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped["Company"] = relationship(back_populates="whitelist_rules")


class BoosterSettings(Base):
    __tablename__ = "booster_settings"

    id:                     Mapped[int]   = mapped_column(Integer, primary_key=True, index=True)
    company_id:             Mapped[int]   = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    boost_manual:           Mapped[float] = mapped_column(Float, default=1.5)
    boost_amount_outlier:   Mapped[float] = mapped_column(Float, default=1.3)
    boost_night:            Mapped[float] = mapped_column(Float, default=1.3)
    boost_first_operation:  Mapped[float] = mapped_column(Float, default=1.2)
    boost_suspicious_pair:  Mapped[float] = mapped_column(Float, default=1.5)
    lof_n_neighbors: Mapped[int] = mapped_column(Integer, default=50)

    company: Mapped["Company"] = relationship(back_populates="booster_settings")


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id:               Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    company_id:       Mapped[int]      = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    filename:         Mapped[str]      = mapped_column(String(255), nullable=False)
    dataset_rows:     Mapped[int]      = mapped_column(Integer, default=0)
    total_anomalies:  Mapped[int]      = mapped_column(Integer, default=0)
    high_risk:        Mapped[int]      = mapped_column(Integer, default=0)
    timestamp:        Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped["Company"] = relationship(back_populates="analysis_history")