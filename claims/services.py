from sqlalchemy.orm import Session

from shared import models, schemas


def get_claim(db: Session, claim_id: str):
    return db.query(models.MasterTable).filter(models.MasterTable.claim_id == claim_id).first()


def get_claims(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.MasterTable).offset(skip).limit(limit).all()


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
