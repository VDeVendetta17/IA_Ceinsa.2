from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(32), unique=True, index=True, nullable=False)
    rut_hash = Column(String(128), nullable=True)
    rut_masked = Column(String(32), nullable=True)
    consent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def give_consent(self):
        self.consent_at = datetime.utcnow()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    action = Column(String(64))
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
