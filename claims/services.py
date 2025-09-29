import json
from sqlalchemy.orm import Session

from shared import models, schemas


def get_claim(db: Session, claim_id: str):
    db_claim = db.query(models.MasterTable).filter(models.MasterTable.claim_id == claim_id).first()
    if db_claim:
        db_claim.error_explanation = _parse_error_explanation(db_claim.error_explanation or "")
    return db_claim


def get_claims(db: Session, skip: int = 0, limit: int = 100):
    db_claims = db.query(models.MasterTable).offset(skip).limit(limit).all()
    for claim in db_claims:
        claim.error_explanation = _parse_error_explanation(claim.error_explanation or "")
    return db_claims


def _parse_error_explanation(error_text):
    """Parse error_explanation: try JSON first, fallback to \n split for old data"""
    if not error_text:
        return []
    # Try JSON
    try:
        parsed = json.loads(error_text)
        # If it's already list (old API response?), return as is
        if isinstance(parsed, list):
            return [e.lstrip("• ") if isinstance(e, str) else str(e) for e in parsed]
        # If dict or other, convert to list
        return [error_text]
    except json.JSONDecodeError:
        # Not JSON, split by \n for old string format
        if "\n" in error_text:
            return [line.lstrip("• ") for line in error_text.split("\n") if line.strip()]
        else:
            # Single error, make list
            return [error_text.lstrip("• ")]


def create_claim(db: Session, claim: schemas.ClaimCreate):
    db_claim = models.MasterTable(**claim.dict())
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim


def update_claim(db: Session, claim_id: str, claim: schemas.ClaimCreate):
    db_claim = db.query(models.MasterTable).filter(models.MasterTable.claim_id == claim_id).first()
    if db_claim:
        for key, value in claim.dict().items():
            setattr(db_claim, key, value)
        db.commit()
        db.refresh(db_claim)
    return db_claim


def delete_claim(db: Session, claim_id: str):
    db_claim = db.query(models.MasterTable).filter(models.MasterTable.claim_id == claim_id).first()
    if db_claim:
        db.delete(db_claim)
        db.commit()
    return db_claim
