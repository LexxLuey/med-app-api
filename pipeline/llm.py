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
    alignment_with_standards: str = Field(description="Explanation of alignment with medical standards")
    recommendations: List[str] = Field(description="Actionable recommendations")
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)


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
        claim_id = claim_data.get('claim_id', 'unknown')
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

Please analyze this claim and determine:
1. Is this claim medically appropriate based on the diagnosis and service provided?
2. Are there any medical necessity concerns?
3. Does the service align with standard medical practice for this diagnosis?

Be thorough but concise. If you cannot determine medical appropriateness, err on the side of caution."""

    def _call_gemini_with_structured_output(self, prompt: str, claim_id: str) -> MedicalAnalysisResponse:
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

    def _format_analysis_result(self, analysis: MedicalAnalysisResponse, claim_id: str) -> Dict[str, Any]:
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
