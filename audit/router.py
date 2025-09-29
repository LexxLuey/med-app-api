from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.router import get_current_user
from shared.database import get_db
from shared.models import AuditLog as AuditLogModel
from shared.schemas import AuditLog

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["Audit"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[AuditLog])
def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get audit logs"""
    logs = db.query(AuditLogModel).offset(skip).limit(limit).all()
    return logs
