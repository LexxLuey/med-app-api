from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import MasterTable, RefinedTable, MetricsTable
from shared.schemas import ValidationResult
from shared.config import settings

from auth.router import get_current_user
from pipeline.tasks import process_claim_batch

router = APIRouter(
    prefix="/api/v1/validation",
    tags=["Validation"],
    responses={404: {"description": "Not found"}},
)


def perform_basic_validation(claim: MasterTable) -> ValidationResult:
    """Perform basic validation on a claim"""
    errors = []
    error_type = "No error"

    # Basic validation rules (placeholder - full rules in Phase 4)
    if not claim.claim_id:
        errors.append("Claim ID is required")
        error_type = "Technical error"

    if claim.paid_amount_aed and claim.paid_amount_aed > settings.paid_amount_threshold:
        errors.append(f"Paid amount {claim.paid_amount_aed} exceeds threshold {settings.paid_amount_threshold}")
        error_type = "Technical error"

    if claim.approval_number and len(str(claim.approval_number)) < settings.approval_number_min:
        errors.append(f"Approval number {claim.approval_number} is too short (min {settings.approval_number_min})")
        error_type = "Technical error"

    status = "Validated" if not errors else "Not validated"
    explanation = "; ".join(errors) if errors else ""
    recommendation = "Review claim details" if errors else ""

    return ValidationResult(
        claim_id=claim.claim_id,
        status=status,
        error_type=error_type,
        error_explanation=explanation,
        recommended_action=recommendation
    )


@router.post("/run")
async def run_validation(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Trigger validation process for all claims using the pipeline"""
    # Get all claims that haven't been validated yet
    claims = db.query(MasterTable).filter(MasterTable.status == "Not validated").limit(50).all()

    if not claims:
        return {"message": "No claims to validate", "processed_count": 0}

    claim_ids = [claim.claim_id for claim in claims]

    # Add background task for processing
    background_tasks.add_task(process_claim_batch, claim_ids)

    return {
        "message": f"Validation pipeline started for {len(claim_ids)} claims",
        "claim_ids": claim_ids,
        "status": "processing"
    }


@router.get("/results")
async def get_validation_results(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get validation results and metrics"""
    # Get metrics
    metrics = db.query(MetricsTable).filter(MetricsTable.tenant_id == settings.tenant_id).all()

    # Get sample validated claims
    claims = db.query(MasterTable).filter(MasterTable.status == "Validated").limit(10).all()

    return {
        "metrics": [
            {
                "error_type": m.error_type,
                "claim_count": m.claim_count,
                "total_paid_amount": m.total_paid_amount
            } for m in metrics
        ],
        "sample_claims": [
            {
                "claim_id": c.claim_id,
                "status": c.status,
                "error_type": c.error_type,
                "error_explanation": c.error_explanation,
                "recommended_action": c.recommended_action
            } for c in claims
        ]
    }
