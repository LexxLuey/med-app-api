import json
from typing import Dict, Any, List

import openai
from openai import OpenAI

from shared.config import settings


class LLMService:
    """Service for LLM-based medical rule evaluation"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def evaluate_medical_claim(self, claim_data: Dict[str, Any], medical_rules: List[str]) -> Dict[str, Any]:
        """Evaluate medical claim using LLM"""
        try:
            # Prepare context from claim data
            claim_context = self._format_claim_for_llm(claim_data)

            # Prepare medical rules context
            rules_context = "\n".join([f"- {rule}" for rule in medical_rules])

            # Create prompt for LLM
            prompt = f"""
You are a medical claims reviewer evaluating a healthcare claim for compliance with medical guidelines.

CLAIM INFORMATION:
{claim_context}

MEDICAL GUIDELINES TO APPLY:
{rules_context}

Please analyze this claim and determine:
1. Is this claim medically appropriate based on the diagnosis and service provided?
2. Are there any medical necessity concerns?
3. Does the service align with standard medical practice for this diagnosis?

Provide your analysis in the following JSON format:
{{
    "is_medically_appropriate": true/false,
    "medical_necessity_concerns": ["concern1", "concern2"],
    "alignment_with_standards": "brief explanation",
    "recommendations": ["recommendation1", "recommendation2"],
    "confidence_score": 0.0-1.0
}}

Be thorough but concise. If you cannot determine medical appropriateness, err on the side of caution.
"""

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert medical claims reviewer. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1  # Low temperature for consistent medical analysis
            )

            # Parse LLM response
            llm_response = response.choices[0].message.content.strip()

            # Extract JSON from response
            try:
                result = json.loads(llm_response)
                return {
                    "valid": result.get("is_medically_appropriate", True),
                    "errors": result.get("medical_necessity_concerns", []),
                    "type": "Medical error" if not result.get("is_medically_appropriate", True) else "No error",
                    "llm_analysis": result.get("alignment_with_standards", ""),
                    "recommendations": result.get("recommendations", []),
                    "confidence": result.get("confidence_score", 0.5)
                }
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "valid": True,
                    "errors": ["LLM analysis incomplete"],
                    "type": "No error",
                    "llm_analysis": llm_response[:200] + "..." if len(llm_response) > 200 else llm_response,
                    "recommendations": [],
                    "confidence": 0.5
                }

        except Exception as e:
            # Fallback for API errors
            return {
                "valid": True,
                "errors": [f"LLM evaluation failed: {str(e)}"],
                "type": "No error",
                "llm_analysis": "Unable to perform LLM analysis",
                "recommendations": ["Manual review recommended"],
                "confidence": 0.0
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
        required_keys = ["is_medically_appropriate", "medical_necessity_concerns",
                        "alignment_with_standards", "recommendations", "confidence_score"]

        return all(key in response for key in required_keys)
