import logging
from typing import Any, Dict, List

from google import genai
from pydantic import BaseModel, Field

from shared.config import settings

logger = logging.getLogger(__name__)


class MedicalAnalysisResponse(BaseModel):
    """Structured response model for medical claim analysis"""

    is_medically_appropriate: bool = Field(description="Whether the claim is medically appropriate")
    medical_necessity_concerns: List[str] = Field(description="List of medical necessity concerns")
    alignment_with_standards: str = Field(
        description="Explanation of alignment with medical standards"
    )
    recommendations: List[str] = Field(description="Actionable recommendations")
    confidence_score: float = Field(
        description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0
    )


class KeyValuePair(BaseModel):
    key: str
    value: str


class TechnicalRulesResponse(BaseModel):
    """Structured response for technical rules extraction"""
    paid_amount_threshold: int = Field(description="AED threshold for paid amounts")
    approval_required_services: List[str] = Field(description="Service codes requiring approval")
    approval_required_diagnoses: List[str] = Field(description="Diagnosis codes requiring approval")
    required_fields: List[str] = Field(description="Required claim fields")
    unique_id_format: str = Field(description="unique_id structure description")
    case_format: str = Field(description="Case requirements")


class MedicalRulesResponse(BaseModel):
    """Structured response for medical rules extraction"""
    inpatient_services: List[str] = Field(description="Services limited to inpatient")
    outpatient_services: List[str] = Field(description="Services limited to outpatient")
    facility_registry: List[KeyValuePair] = Field(description="Facility registry as key-value pairs")
    diagnosis_service_mappings: List[KeyValuePair] = Field(description="Diagnosis-service mappings as key-value pairs")
    mutually_exclusive: List[KeyValuePair] = Field(description="Mutually exclusive diagnoses as key-value pairs")


class LLMService:
    """Service for LLM-based medical rule evaluation using Google Gemini"""

    def __init__(self):
        # The client automatically uses GEMINI_API_KEY from environment
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

    def evaluate_medical_claim(
        self, claim_data: Dict[str, Any], medical_rules: List[str]
    ) -> Dict[str, Any]:
        """Evaluate medical claim using LLM with structured output"""
        claim_id = claim_data.get("claim_id", "unknown")
        logger.info(f"[LLM] Starting evaluation for claim {claim_id}")

        try:
            prompt = self._build_medical_analysis_prompt(claim_data, medical_rules)
            logger.debug(f"[LLM] Prompt built for claim {claim_id}")

            analysis = self._call_gemini_with_structured_output(prompt, claim_id)
            return self._format_analysis_result(analysis, claim_id)

        except Exception as e:
            return self._handle_llm_error(e, claim_id)

    def _build_medical_analysis_prompt(
        self, claim_data: Dict[str, Any], medical_rules: List[str]
    ) -> str:
        """Build the medical analysis prompt"""
        claim_context = self._format_claim_for_llm(claim_data)
        rules_context = "\n".join([f"- {rule}" for rule in medical_rules])

        return f"""You are a medical claims reviewer evaluating a healthcare claim for compliance with medical guidelines.

CLAIM INFORMATION:
{claim_context}

MEDICAL GUIDELINES TO APPLY:
{rules_context}

Please analyze this claim and determine if medically appropriate. Return:
- medical_necessity_concerns as list of bullet-point strings (each bullet explains one error based on guidelines, e.g. "• Service not eligible at this facility type per guidelines")
- alignment_with_standards explanation
- actionable recommendations list

Be thorough. Err on side of caution for medical concerns."""

    def _call_gemini_with_structured_output(
        self, prompt: str, claim_id: str
    ) -> MedicalAnalysisResponse:
        """Call Gemini API with structured output using Pydantic model"""
        logger.info(f"[LLM] Making structured API call for claim {claim_id}")

        response = self.client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1000,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
                response_mime_type="application/json",
                response_schema=MedicalAnalysisResponse,
            ),
        )

        logger.info(f"[LLM] API call successful for claim {claim_id}")
        return MedicalAnalysisResponse.model_validate_json(response.text)

    def _format_analysis_result(
        self, analysis: MedicalAnalysisResponse, claim_id: str
    ) -> Dict[str, Any]:
        """Format the structured analysis result"""
        result = {
            "valid": analysis.is_medically_appropriate,
            "errors": analysis.medical_necessity_concerns,
            "type": "Medical error" if not analysis.is_medically_appropriate else "No error",
            "llm_analysis": analysis.alignment_with_standards,
            "recommendations": analysis.recommendations,
            "confidence": analysis.confidence_score,
        }

        logger.info(f"[LLM] Evaluation complete for claim {claim_id}: {result['type']}")
        return result

    def _handle_llm_error(self, error: Exception, claim_id: str) -> Dict[str, Any]:
        """Handle LLM evaluation errors with appropriate fallbacks"""
        error_msg = str(error)
        logger.error(f"[LLM] API call failed for claim {claim_id}: {error_msg}")

        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            logger.warning(f"[LLM] Rate limit hit for claim {claim_id}")
            return self._create_rate_limit_result()
        else:
            return self._create_error_result(error_msg)

    def _create_rate_limit_result(self) -> Dict[str, Any]:
        """Create result for rate limit scenarios"""
        return {
            "valid": True,
            "errors": ["Rate limit exceeded - using basic analysis"],
            "type": "No error",
            "llm_analysis": "Analysis deferred due to API rate limits",
            "recommendations": ["Re-run validation after rate limit reset"],
            "confidence": 0.1,
        }

    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """Create result for general API errors"""
        return {
            "valid": True,
            "errors": [f"LLM evaluation failed: {error_msg}"],
            "type": "No error",
            "llm_analysis": "Unable to perform LLM analysis",
            "recommendations": ["Manual review recommended"],
            "confidence": 0.0,
        }

    def _format_claim_for_llm(self, claim_data: Dict[str, Any]) -> str:
        """Format claim data for LLM consumption"""
        formatted = []
        formatted.append(f"Diagnosis Codes: {claim_data.get('diagnosis_codes', 'Not specified')}")
        formatted.append(f"Service Code: {claim_data.get('service_code', 'Not specified')}")
        formatted.append(f"Encounter Type: {claim_data.get('encounter_type', 'Not specified')}")
        formatted.append(f"Service Date: {claim_data.get('service_date', 'Not specified')}")
        formatted.append(f"Facility: {claim_data.get('facility_id', 'Not specified')}")
        formatted.append(f"Paid Amount: AED {claim_data.get('paid_amount_aed', 'Not specified')}")

        return "\n".join(formatted)

    def extract_rules_from_pdf(self, pdf_text: str, rule_type: str) -> Dict[str, Any]:
        """Extract structured rules from PDF text using LLM"""
        try:
            prompt = self._build_rules_extraction_prompt(pdf_text, rule_type)
            logger.info(f"[LLM] Extracting {rule_type} rules from PDF")

            if rule_type == "technical":
                schema = TechnicalRulesResponse
            else:
                schema = MedicalRulesResponse

            response = self.client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2000,
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

            rules = schema.model_validate_json(response.text).model_dump()
            logger.info(f"[LLM] Successfully extracted {rule_type} rules")
            return rules

        except Exception as e:
            logger.error(f"[LLM] Failed to extract {rule_type} rules: {str(e)}")
            return {}

    def _build_rules_extraction_prompt(self, pdf_text: str, rule_type: str) -> str:
        """Build prompt for rules extraction"""
        if rule_type == "technical":
            return f"""Extract technical adjudication rules from this document text. Return a JSON object with the following structure:

{{
  "paid_amount_threshold": number (the AED threshold for paid amounts, e.g. 250),
  "approval_required_services": array of service codes requiring pre-approval,
  "approval_required_diagnoses": array of diagnosis codes requiring pre-approval,
  "required_fields": array of required claim fields,
  "unique_id_format": string describing the unique_id structure,
  "case_format": string describing case requirements (UPPERCASE/any)
}}

Focus on sections about thresholds, approvals, ID formatting, and required fields. Ignore example claims.

Document Text:
{pdf_text}
"""
        else:
            return f"""Extract medical adjudication rules from this document text. Return a JSON object with the following structure:

{{
  "inpatient_services": array of service codes limited to inpatient encounters,
  "outpatient_services": array of service codes limited to outpatient encounters,
  "facility_registry": array of objects with "key" and "value" fields (facility ID to type),
  "diagnosis_service_mappings": array of objects with "key" and "value" fields (diagnosis to required service),
  "mutually_exclusive": array of objects with "key" and "value" fields (diagnosis pairs that cannot coexist)
}}

Focus on sections A, B, C, D about encounter types, facility types, diagnosis requirements, and exclusions.

Document Text:
{pdf_text}
"""

    def validate_llm_response(self, response: Dict[str, Any]) -> bool:
        """Validate LLM response structure"""
        required_keys = [
            "is_medically_appropriate",
            "medical_necessity_concerns",
            "alignment_with_standards",
            "recommendations",
            "confidence_score",
        ]

        return all(key in response for key in required_keys)
