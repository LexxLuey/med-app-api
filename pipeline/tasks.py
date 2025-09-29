import json
import logging
from typing import Any, Dict, List

from shared.config import settings
from shared.database import SessionLocal
from shared.models import MasterTable, MetricsTable, RefinedTable

from .llm import LLMService
from .rules import RuleEvaluator

logger = logging.getLogger(__name__)


def process_claim_batch(claim_ids: List[str]) -> Dict[str, Any]:
    """Process a batch of claims through the validation pipeline"""
    db = SessionLocal()
    try:
        # Initialize services
        rule_evaluator = RuleEvaluator()
        llm_service = LLMService()

        processed_count = 0
        error_counts = {"No error": 0, "Medical error": 0, "Technical error": 0, "both": 0}
        total_paid_by_error = {
            "No error": 0.0,
            "Medical error": 0.0,
            "Technical error": 0.0,
            "both": 0.0,
        }

        # Get claims to process
        claims = db.query(MasterTable).filter(MasterTable.claim_id.in_(claim_ids)).all()

        for claim in claims:
            try:
                # Convert claim to dict for processing
                claim_data = {
                    "claim_id": claim.claim_id,
                    "encounter_type": claim.encounter_type,
                    "service_date": claim.service_date.isoformat() if claim.service_date else None,
                    "national_id": claim.national_id,
                    "member_id": claim.member_id,
                    "facility_id": claim.facility_id,
                    "unique_id": claim.unique_id,
                    "diagnosis_codes": claim.diagnosis_codes,
                    "service_code": claim.service_code,
                    "paid_amount_aed": claim.paid_amount_aed,
                    "approval_number": claim.approval_number,
                }

                # Step 1: Technical rule evaluation
                technical_result = rule_evaluator.evaluate_technical_rules(claim_data)

                # Step 2: Medical rule evaluation (LLM)
                logger.info(f"Evaluating medical rules for claim {claim.claim_id}")
                medical_result = rule_evaluator.evaluate_medical_rules(claim_data)
                logger.info(f"Medical evaluation result: {medical_result.get('type', 'unknown')}")

                if (
                    medical_result.get("llm_analysis")
                    == "Medical rules evaluation pending LLM integration"
                ):
                    # Load medical rules from cache
                    cached_medical_rules = rule_evaluator.redis_client.get(
                        f"rules:medical:{settings.tenant_id}"
                    )
                    medical_rules = []
                    if cached_medical_rules:
                        cached_data = json.loads(cached_medical_rules)
                        medical_rules = cached_data.get("medical_validation_rules", [])
                        logger.info(f"Loaded {len(medical_rules)} medical rules from cache")
                    else:
                        logger.warning("No medical rules found in cache - using empty rules")

                    # Use LLM service for actual evaluation
                    logger.info(
                        f"Calling LLM service for claim {claim.claim_id} with {len(medical_rules)} rules"
                    )
                    medical_result = llm_service.evaluate_medical_claim(claim_data, medical_rules)
                    logger.info(
                        f"LLM evaluation completed: {medical_result.get('type', 'unknown')}"
                    )

                # Step 3: Combine results
                combined_errors = technical_result["errors"] + medical_result["errors"]
                combined_type = _combine_error_types(
                    technical_result["type"], medical_result["type"]
                )

                # Step 4: Update master table
                claim.status = "Validated"
                claim.error_type = combined_type
                claim.error_explanation = "; ".join(combined_errors) if combined_errors else ""
                claim.recommended_action = _generate_recommendations(combined_errors)

                # Step 5: Create refined table entry
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
                    status=claim.status,
                    error_type=combined_type,
                    error_explanation=claim.error_explanation,
                    recommended_action=claim.recommended_action,
                )
                db.add(refined_claim)

                # Step 6: Update metrics
                error_counts[combined_type] += 1
                if claim.paid_amount_aed:
                    total_paid_by_error[combined_type] += claim.paid_amount_aed

                processed_count += 1
                logger.info(f"Processed claim {claim.claim_id}")

            except Exception as e:
                logger.error(f"Error processing claim {claim.claim_id}: {str(e)}")
                continue

        # Create/update metrics entries
        for error_type, count in error_counts.items():
            if count > 0:
                # Check if metric already exists
                existing_metric = (
                    db.query(MetricsTable)
                    .filter(
                        MetricsTable.error_type == error_type,
                        MetricsTable.tenant_id == settings.tenant_id,
                    )
                    .first()
                )

                if existing_metric:
                    existing_metric.claim_count += count
                    existing_metric.total_paid_amount += total_paid_by_error[error_type]
                else:
                    metric = MetricsTable(
                        error_type=error_type,
                        claim_count=count,
                        total_paid_amount=total_paid_by_error[error_type],
                        tenant_id=settings.tenant_id,
                    )
                    db.add(metric)

        db.commit()

        logger.info(f"Completed processing {processed_count} claims")
        return {
            "processed_count": processed_count,
            "error_counts": error_counts,
            "total_paid_by_error": total_paid_by_error,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Pipeline processing failed: {str(e)}")
        raise
    finally:
        db.close()


def _combine_error_types(technical_type: str, medical_type: str) -> str:
    """Combine technical and medical error types"""
    if technical_type == "No error" and medical_type == "No error":
        return "No error"
    elif technical_type != "No error" and medical_type != "No error":
        return "both"
    elif technical_type != "No error":
        return technical_type
    else:
        return medical_type


def _generate_recommendations(errors: List[str]) -> str:
    """Generate actionable recommendations based on errors"""
    recommendations = []

    for error in errors:
        if "threshold" in error.lower():
            recommendations.append("Review payment amount against policy limits")
        elif "required" in error.lower():
            recommendations.append("Complete missing required fields")
        elif "approval" in error.lower():
            recommendations.append("Verify approval number format and validity")
        elif "medical" in error.lower():
            recommendations.append("Consult medical guidelines for service necessity")
        else:
            recommendations.append("Manual review required")

    return "; ".join(list(set(recommendations)))  # Remove duplicates


def trigger_pipeline_for_tenant(tenant_id: str) -> Dict[str, Any]:
    """Trigger pipeline processing for all unprocessed claims in a tenant"""
    db = SessionLocal()
    try:
        # Get all unvalidated claims for tenant
        claims = (
            db.query(MasterTable).filter(MasterTable.status == "Not validated").limit(100).all()
        )  # Process in batches

        if not claims:
            return {"message": "No claims to process", "processed_count": 0}

        claim_ids = [claim.claim_id for claim in claims]

        # Process the batch
        result = process_claim_batch(claim_ids)

        return {"message": f"Processed {result['processed_count']} claims", "details": result}

    finally:
        db.close()
