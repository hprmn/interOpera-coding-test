"""
Transaction database models (Capital Calls, Distributions, Adjustments)
"""
from sqlalchemy import Column, Integer, String, Date, Numeric, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class CapitalCall(Base):
    """Capital Call model"""

    __tablename__ = "capital_calls"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    call_date = Column(Date, nullable=False, index=True)
    call_type = Column(String(100), index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    fund = relationship("Fund", back_populates="capital_calls")

    # Indexes for performance
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class Distribution(Base):
    """Distribution model"""

    __tablename__ = "distributions"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    distribution_date = Column(Date, nullable=False, index=True)
    distribution_type = Column(String(100), index=True)
    is_recallable = Column(Boolean, default=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    fund = relationship("Fund", back_populates="distributions")

    # Indexes for performance
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class Adjustment(Base):
    """Adjustment model"""

    __tablename__ = "adjustments"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    adjustment_date = Column(Date, nullable=False, index=True)
    adjustment_type = Column(String(100), index=True)
    category = Column(String(100))
    amount = Column(Numeric(15, 2), nullable=False)
    is_contribution_adjustment = Column(Boolean, default=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    fund = relationship("Fund", back_populates="adjustments")

    # Indexes for performance
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
