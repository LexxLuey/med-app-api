from sqlalchemy import Column, Date, Float, Integer, String, Text

from .database import Base


class MasterTable(Base):
    __tablename__ = "master_table"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String, unique=True, index=True)
    encounter_type = Column(String)
    service_date = Column(Date)
    national_id = Column(String)
    member_id = Column(String)
    facility_id = Column(String)
    unique_id = Column(String)
    diagnosis_codes = Column(Text)
    service_code = Column(String)
    paid_amount_aed = Column(Float)
    approval_number = Column(String)
    status = Column(String)  # Validated / Not validated
    error_type = Column(String)  # No error / Medical error / Technical
    error_explanation = Column(Text)
    recommended_action = Column(Text)


class RefinedTable(Base):
    __tablename__ = "refined_table"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String, unique=True, index=True)
    encounter_type = Column(String)
    service_date = Column(Date)
    national_id = Column(String)
    member_id = Column(String)
    facility_id = Column(String)
    unique_id = Column(String)
    diagnosis_codes = Column(Text)
    service_code = Column(String)
    paid_amount_aed = Column(Float)
    approval_number = Column(String)
    status = Column(String)
    error_type = Column(String)
    error_explanation = Column(Text)
    recommended_action = Column(Text)


class MetricsTable(Base):
    __tablename__ = "metrics_table"

    id = Column(Integer, primary_key=True, index=True)
    error_type = Column(String, index=True)
    claim_count = Column(Integer)
    total_paid_amount = Column(Float)
    tenant_id = Column(String, default="default")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    user_id = Column(String)
    timestamp = Column(String)
    details = Column(Text)
