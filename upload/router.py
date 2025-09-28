import os
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import AuditLog, MasterTable
from shared.schemas import FileUploadResponse

from auth.router import get_current_user
from pipeline.rules import RuleParser

router = APIRouter(
    prefix="/api/v1/upload",
    tags=["Upload"],
    responses={404: {"description": "Not found"}},
)


def log_audit_action(db: Session, action: str, user_id: str, details: str):
    """Log audit action to database"""
    audit_log = AuditLog(
        action=action,
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat(),
        details=details
    )
    db.add(audit_log)
    db.commit()


@router.post("/claims", response_model=FileUploadResponse)
async def upload_claims_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Upload claims data file (CSV or Excel)"""
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    try:
        # Read file content
        content = await file.read()

        # Parse file based on extension
        if file.filename.endswith('.csv'):
            df = pd.read_csv(pd.io.common.BytesIO(content))
        else:
            df = pd.read_excel(pd.io.common.BytesIO(content))

        # Validate required columns
        required_columns = [
            'claim_id', 'encounter_type', 'service_date', 'national_id',
            'member_id', 'facility_id', 'unique_id', 'diagnosis_codes',
            'service_code', 'paid_amount_aed', 'approval_number'
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        # Process and insert claims
        records_processed = 0
        for _, row in df.iterrows():
            try:
                # Convert date string to date object
                service_date = pd.to_datetime(row['service_date']).date() if pd.notna(row['service_date']) else None

                claim_data = {
                    'claim_id': str(row['claim_id']),
                    'encounter_type': str(row['encounter_type']) if pd.notna(row['encounter_type']) else None,
                    'service_date': service_date,
                    'national_id': str(row['national_id']) if pd.notna(row['national_id']) else None,
                    'member_id': str(row['member_id']) if pd.notna(row['member_id']) else None,
                    'facility_id': str(row['facility_id']) if pd.notna(row['facility_id']) else None,
                    'unique_id': str(row['unique_id']) if pd.notna(row['unique_id']) else None,
                    'diagnosis_codes': str(row['diagnosis_codes']) if pd.notna(row['diagnosis_codes']) else None,
                    'service_code': str(row['service_code']) if pd.notna(row['service_code']) else None,
                    'paid_amount_aed': float(row['paid_amount_aed']) if pd.notna(row['paid_amount_aed']) else None,
                    'approval_number': str(row['approval_number']) if pd.notna(row['approval_number']) else None,
                    'status': 'Not validated',
                    'error_type': 'No error',
                    'error_explanation': '',
                    'recommended_action': ''
                }

                # Check if claim already exists
                existing_claim = db.query(MasterTable).filter(
                    MasterTable.claim_id == claim_data['claim_id']
                ).first()

                if existing_claim:
                    # Update existing claim
                    for key, value in claim_data.items():
                        setattr(existing_claim, key, value)
                else:
                    # Create new claim
                    db_claim = MasterTable(**claim_data)
                    db.add(db_claim)

                records_processed += 1

            except Exception as e:
                # Log error but continue processing
                print(f"Error processing row: {e}")
                continue

        db.commit()

        # Log audit action
        log_audit_action(
            db=db,
            action="UPLOAD_CLAIMS",
            user_id=current_user.username,
            details=f"Uploaded {records_processed} claims from {file.filename}"
        )

        return FileUploadResponse(
            filename=file.filename,
            message="Claims file uploaded successfully",
            records_processed=records_processed
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/rules/technical", response_model=FileUploadResponse)
async def upload_technical_rules(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Upload technical rules document (PDF) and parse rules"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be PDF format")

    try:
        content = await file.read()

        # Save file temporarily for parsing
        file_path = f"/tmp/{file.filename}"
        with open(file_path, 'wb') as f:
            f.write(content)

        # Parse technical rules
        rule_parser = RuleParser()
        parsed_rules = rule_parser.parse_technical_rules(file_path)

        # Log audit action
        log_audit_action(
            db=db,
            action="UPLOAD_TECHNICAL_RULES",
            user_id=current_user.username,
            details=f"Uploaded and parsed technical rules document: {file.filename}. "
                   f"Rules extracted: {len(parsed_rules)}"
        )

        return FileUploadResponse(
            filename=file.filename,
            message="Technical rules document uploaded and parsed successfully",
            records_processed=len(parsed_rules)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing rules: {str(e)}")


@router.post("/rules/medical", response_model=FileUploadResponse)
async def upload_medical_rules(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Upload medical rules document (PDF) and parse rules"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be PDF format")

    try:
        content = await file.read()

        # Save file temporarily for parsing
        file_path = f"/tmp/{file.filename}"
        with open(file_path, 'wb') as f:
            f.write(content)

        # Parse medical rules
        rule_parser = RuleParser()
        parsed_rules = rule_parser.parse_medical_rules(file_path)

        # Log audit action
        log_audit_action(
            db=db,
            action="UPLOAD_MEDICAL_RULES",
            user_id=current_user.username,
            details=f"Uploaded and parsed medical rules document: {file.filename}. "
                   f"Rules extracted: {len(parsed_rules)}"
        )

        return FileUploadResponse(
            filename=file.filename,
            message="Medical rules document uploaded and parsed successfully",
            records_processed=len(parsed_rules)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing rules: {str(e)}")
