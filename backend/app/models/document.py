"""
Document database model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Document(Base):
    """Document model"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500))
    upload_date = Column(DateTime, default=datetime.utcnow, index=True)
    parsing_status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed
    error_message = Column(Text)

    # Relationships
    fund = relationship("Fund", back_populates="documents")

    # Indexes for performance
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
