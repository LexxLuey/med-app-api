from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import MasterTable, RefinedTable, MetricsTable
from shared.schemas import ValidationResult
from shared.config import settings

from auth.router import get_current_user

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
    """Trigger validation process for all claims"""
    # Get all claims that haven't been validated yet
    claims = db.query(MasterTable).filter(MasterTable.status == "Not validated").all()

    validated_count = 0
    error_counts = {"No error": 0, "Medical error": 0, "Technical error": 0, "both": 0}
    total_paid_by_error = {"No error": 0.0, "Medical error": 0.0, "Technical error": 0.0, "both": 0.0}

    for claim in claims:
        # Perform validation
        result = perform_basic_validation(claim)

        # Update master table
        claim.status = result.status
        claim.error_type = result.error_type
        claim.error_explanation = result.error_explanation
        claim.recommended_action = result.recommended_action

        # Create refined table entry
        refined_claim = RefinedTable(
            claim_id=claim.claim_id,
            encounter_type=claim.encounter_type,
            service_date=claim.service_date,
            national_id=claim.national_id,
            member_id=claim.member_id,
            facility_id=claim.facility_id,
            unique_id=claim.unique_id,
            diagnosis_codes=claim.diagnosis_codes,
            service_code=claim.service_code,
            paid_amount_aed=claim.paid_amount_aed,
            approval_number=claim.approval_number,
            status=result.status,
            error_type=result.error_type,
            error_explanation=result.error_explanation,
            recommended_action=result.recommended_action
        )
        db.add(refined_claim)

        # Update metrics
        error_counts[result.error_type] += 1
        if claim.paid_amount_aed:
            total_paid_by_error[result.error_type] += claim.paid_amount_aed

        validated_count += 1

    # Create metrics entries
    for error_type, count in error_counts.items():
        if count > 0:
            metric = MetricsTable(
                error_type=error_type,
                claim_count=count,
                total_paid_amount=total_paid_by_error[error_type],
                tenant_id=settings.tenant_id
            )
            db.add(metric)

    db.commit()

    return {
        "message": f"Validation completed for {validated_count} claims",
        "metrics": {
            "error_counts": error_counts,
            "total_paid_by_error": total_paid_by_error
        }
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
