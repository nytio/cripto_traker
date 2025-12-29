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
    Boolean,
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
    prophet_forecasts = relationship(
        "ProphetForecast", back_populates="crypto", cascade="all, delete-orphan"
    )
    lstm_forecasts = relationship(
        "LstmForecast", back_populates="crypto", cascade="all, delete-orphan"
    )
    gru_forecasts = relationship(
        "GruForecast", back_populates="crypto", cascade="all, delete-orphan"
    )
    user_cryptos = relationship(
        "UserCrypto", back_populates="crypto", cascade="all, delete-orphan"
    )


class UserCrypto(Base):
    __tablename__ = "user_cryptos"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="user_cryptos")
    crypto = relationship("Cryptocurrency", back_populates="user_cryptos")

    __table_args__ = (
        UniqueConstraint("user_id", "crypto_id", name="uq_user_crypto"),
        Index("ix_user_cryptos_user_id", "user_id"),
        Index("ix_user_cryptos_crypto_id", "crypto_id"),
    )


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


class ProphetForecast(Base):
    __tablename__ = "prophet_forecasts"

    id = Column(Integer, primary_key=True)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    date = Column(Date, nullable=False)
    yhat = Column(Numeric(18, 8))
    yhat_lower = Column(Numeric(18, 8))
    yhat_upper = Column(Numeric(18, 8))
    cutoff_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    crypto = relationship("Cryptocurrency", back_populates="prophet_forecasts")

    __table_args__ = (
        UniqueConstraint("crypto_id", "date", name="uq_prophet_crypto_date"),
        Index("ix_prophet_crypto_date", "crypto_id", "date"),
    )


class LstmForecast(Base):
    __tablename__ = "lstm_forecasts"

    id = Column(Integer, primary_key=True)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    date = Column(Date, nullable=False)
    yhat = Column(Numeric(18, 8))
    yhat_lower = Column(Numeric(18, 8))
    yhat_upper = Column(Numeric(18, 8))
    cutoff_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    crypto = relationship("Cryptocurrency", back_populates="lstm_forecasts")

    __table_args__ = (
        UniqueConstraint("crypto_id", "date", name="uq_lstm_crypto_date"),
        Index("ix_lstm_crypto_date", "crypto_id", "date"),
    )


class GruForecast(Base):
    __tablename__ = "gru_forecasts"

    id = Column(Integer, primary_key=True)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    date = Column(Date, nullable=False)
    yhat = Column(Numeric(18, 8))
    yhat_lower = Column(Numeric(18, 8))
    yhat_upper = Column(Numeric(18, 8))
    cutoff_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    crypto = relationship("Cryptocurrency", back_populates="gru_forecasts")

    __table_args__ = (
        UniqueConstraint("crypto_id", "date", name="uq_gru_crypto_date"),
        Index("ix_gru_crypto_date", "crypto_id", "date"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    user_cryptos = relationship(
        "UserCrypto", back_populates="user", cascade="all, delete-orphan"
    )
