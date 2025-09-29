from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from auth.router import get_current_user
from pipeline.tasks import process_claim_batch
from shared.config import settings
from shared.database import SessionLocal, get_db
from shared.models import MasterTable, MetricsTable
from shared.schemas import TaskStatusCreate, ValidationResult
from shared.task_manager import get_task_manager

router = APIRouter(
    prefix="/api/v1/validation",
    tags=["Validation"],
    responses={404: {"description": "Not found"}},
)


def process_claim_batch_with_tracking(claim_ids: list, task_id: str, task_manager):
    """Process claims with task status tracking"""
    try:
        # Update task to running
        db = SessionLocal()
        task_manager.update_task_status(
            db, task_id, "running", progress=10, message=f"Processing {len(claim_ids)} claims..."
        )

        # Process the claims
        result = process_claim_batch(claim_ids)

        # Update task as completed
        task_manager.update_task_status(
            db,
            task_id,
            "completed",
            progress=100,
            message=f"Successfully processed {result['processed_count']} claims",
            details=result,
        )

    except Exception as e:
        # Update task as failed
        db = SessionLocal()
        task_manager.update_task_status(
            db, task_id, "failed", message=f"Validation failed: {str(e)}"
        )
        raise
    finally:
        db.close()


def perform_basic_validation(claim: MasterTable) -> ValidationResult:
    """Perform basic validation on a claim"""
    errors = []
    error_type = "No error"

    # Basic validation rules (placeholder - full rules in Phase 4)
    if not claim.claim_id:
        errors.append("Claim ID is required")
        error_type = "Technical error"

    if claim.paid_amount_aed and claim.paid_amount_aed > settings.paid_amount_threshold:
        errors.append(
            f"Paid amount {claim.paid_amount_aed} exceeds threshold {settings.paid_amount_threshold}"
        )
        error_type = "Technical error"

    if claim.approval_number and len(str(claim.approval_number)) < settings.approval_number_min:
        errors.append(
            f"Approval number {claim.approval_number} is too short (min {settings.approval_number_min})"
        )
        error_type = "Technical error"

    status = "Validated" if not errors else "Not validated"
    explanation = "; ".join(errors) if errors else ""
    recommendation = "Review claim details" if errors else ""

    return ValidationResult(
        claim_id=claim.claim_id,
        status=status,
        error_type=error_type,
        error_explanation=explanation,
        recommended_action=recommendation,
    )


@router.post("/run")
async def run_validation(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    task_manager=Depends(get_task_manager),
):
    """Trigger validation process for all claims using the pipeline"""
    # Check if validation can be started
    can_start, reason = task_manager.can_start_task(db, "validation", current_user.username)
    if not can_start:
        raise HTTPException(status_code=409, detail=reason)

    # Get all claims that haven't been validated yet
    claims = db.query(MasterTable).filter(MasterTable.status == "Not validated").limit(50).all()

    if not claims:
        return {"message": "No claims to validate", "processed_count": 0}

    claim_ids = [claim.claim_id for claim in claims]
    task_id = task_manager.generate_task_id("validation")

    # Create task status record
    task_data = TaskStatusCreate(
        task_id=task_id,
        task_type="validation",
        user_id=current_user.username,
        message=f"Starting validation of {len(claim_ids)} claims",
    )
    task_status = task_manager.create_task(db, task_data)

    # Add background task for processing with task tracking
    background_tasks.add_task(process_claim_batch_with_tracking, claim_ids, task_id, task_manager)

    return {
        "message": f"Validation pipeline started for {len(claim_ids)} claims",
        "task_id": task_id,
        "claim_ids": claim_ids,
        "status": "processing",
    }


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    task_manager=Depends(get_task_manager),
):
    """Get status of a specific validation task"""
    task_status = task_manager.get_task_status(db, task_id)

    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if user owns this task
    if task_status.user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "task_id": task_status.task_id,
        "task_type": task_status.task_type,
        "status": task_status.status,
        "progress": task_status.progress,
        "message": task_status.message,
        "created_at": task_status.created_at,
        "updated_at": task_status.updated_at,
        "details": task_status.details,
    }


@router.get("/tasks")
async def get_user_tasks(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    task_manager=Depends(get_task_manager),
):
    """Get all tasks for the current user"""
    from shared.models import TaskStatus as TaskStatusModel

    tasks = (
        db.query(TaskStatusModel)
        .filter(TaskStatusModel.user_id == current_user.username)
        .order_by(TaskStatusModel.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "message": task.message,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        for task in tasks
    ]


@router.get("/results")
async def get_validation_results(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
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
                "total_paid_amount": m.total_paid_amount,
            }
            for m in metrics
        ],
        "sample_claims": [
            {
                "claim_id": c.claim_id,
                "status": c.status,
                "error_type": c.error_type,
                "error_explanation": c.error_explanation,
                "recommended_action": c.recommended_action,
            }
            for c in claims
        ],
    }


@router.get("/claims-validated")
async def get_paginated_validation_results(
    skip: int = 0,
    limit: int = 50,
    error_type: str = None,
    search: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get paginated validation results with filtering and search"""
    # Base query for validated claims
    query = db.query(MasterTable)

    # Apply filters
    if error_type and error_type != "all":
        query = query.filter(MasterTable.error_type == error_type)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                MasterTable.claim_id.ilike(search_term),
                MasterTable.error_explanation.ilike(search_term),
                MasterTable.recommended_action.ilike(search_term),
            )
        )

    # Get total count for pagination
    total_count = query.count()

    # Apply pagination and get results
    claims = (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Get available error types for filtering
    error_types = (
        db.query(MasterTable.error_type)
        .filter(MasterTable.error_type.isnot(None))
        .distinct()
        .all()
    )
    available_error_types = [et[0] for et in error_types]

    import json as json_module

    def parse_error_explanation(error_text):
        """Parse error_explanation: try JSON first, fallback to \n split for old data"""
        if not error_text:
            return []
        # Try JSON
        try:
            parsed = json_module.loads(error_text)
            # If it's already list, return
            if isinstance(parsed, list):
                return [e.lstrip("• ") if isinstance(e, str) else str(e) for e in parsed]
            return [error_text]
        except json_module.JSONDecodeError:
            # Split by \n for old string format
            if "\n" in error_text:
                return [line.lstrip("• ") for line in error_text.split("\n") if line.strip()]
            else:
                return [error_text.lstrip("• ")]

    return {
        "claims": [
            {
                "id": c.id,
                "claim_id": c.claim_id,
                "status": c.status,
                "error_type": c.error_type,
                "error_explanation": parse_error_explanation(c.error_explanation),
                "recommended_action": c.recommended_action,
                "paid_amount_aed": c.paid_amount_aed,
                "service_date": c.service_date,
                "encounter_type": c.encounter_type,
            }
            for c in claims
        ],
        "pagination": {
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": skip + limit < total_count,
        },
        "filters": {
            "available_error_types": available_error_types,
        },
    }
