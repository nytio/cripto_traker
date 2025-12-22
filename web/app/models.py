from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .db import Base


class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    symbol = Column(String(20))
    coingecko_id = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    prices = relationship("Price", back_populates="crypto", cascade="all, delete-orphan")


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    date = Column(Date, nullable=False)
    price = Column(Numeric(18, 8), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    crypto = relationship("Cryptocurrency", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("crypto_id", "date", name="uq_price_crypto_date"),
        Index("ix_prices_crypto_date", "crypto_id", "date"),
    )
