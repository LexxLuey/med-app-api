import json
import re
from typing import Any, Dict, Optional

import redis
from PyPDF2 import PdfReader

from shared.config import settings
from .llm import LLMService


class RuleParser:
    """Parse technical and medical rule documents"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)
        self.llm_service = LLMService()

    def parse_technical_rules(self, pdf_path: str) -> Dict[str, Any]:
        """Parse technical rules from PDF document using LLM"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

            # Extract rules using LLM
            rules = self.llm_service.extract_rules_from_pdf(text, "technical")
            if not rules:
                # Fallback to basic extraction if LLM fails
                rules = {
                    "paid_amount_threshold": self._extract_threshold(text, "paid.amount", 1000),
                    "approval_required_services": [],
                    "approval_required_diagnoses": [],
                    "required_fields": ["national_id", "member_id", "facility_id", "unique_id"],
                }

            # Cache parsed rules
            cache_key = f"rules:technical:{settings.tenant_id}"
            self.redis_client.setex(cache_key, 3600, json.dumps(rules))  # Cache for 1 hour

            return rules

        except Exception as e:
            raise ValueError(f"Failed to parse technical rules: {str(e)}")

    def parse_medical_rules(self, pdf_path: str) -> Dict[str, Any]:
        """Parse medical rules from PDF document using LLM"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

            # Extract rules using LLM
            rules = self.llm_service.extract_rules_from_pdf(text, "medical")
            if not rules:
                # Fallback to basic extraction
                rules = {
                    "inpatient_services": self._extract_list(text, "inpatient.services"),
                    "outpatient_services": self._extract_list(text, "outpatient.services"),
                    "facility_registry": {},
                    "diagnosis_service_mappings": self._extract_mappings(text, "diagnosis.services"),
                    "mutually_exclusive": {},
                    "medical_validation_rules": self._extract_medical_rules(text),
                }

            # Cache parsed rules
            cache_key = f"rules:medical:{settings.tenant_id}"
            self.redis_client.setex(cache_key, 3600, json.dumps(rules))

            return rules

        except Exception as e:
            raise ValueError(f"Failed to parse medical rules: {str(e)}")

    def get_cached_rules(self, rule_type: str) -> Optional[Dict[str, Any]]:
        """Get cached rules"""
        cache_key = f"rules:{rule_type}:{settings.tenant_id}"
        cached = self.redis_client.get(cache_key)
        return json.loads(cached) if cached else None

    def _extract_threshold(self, text: str, pattern: str, default: float) -> float:
        """Extract numeric threshold from text"""
        match = re.search(rf"{pattern}[\s:]*\$?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        return float(match.group(1)) if match else default

    def _extract_list(self, text: str, pattern: str) -> list:
        """Extract list items from text"""
        # Simple extraction - in production, use more sophisticated NLP
        section = re.search(
            rf"{pattern}[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)", text, re.DOTALL | re.IGNORECASE
        )
        if section:
            items = re.findall(r"\b\w+\b", section.group(1))
            return [item for item in items if len(item) > 2]
        return []

    def _extract_patterns(self, text: str, pattern: str) -> list:
        """Extract regex patterns for validation"""
        # Placeholder - extract diagnosis code patterns
        patterns = []
        matches = re.findall(r"\b[A-Z]\d{2}(?:\.\d+)?\b", text)
        patterns.extend(matches)
        return list(set(patterns))  # Remove duplicates

    def _extract_mappings(self, text: str, pattern: str) -> Dict[str, str]:
        """Extract service code mappings"""
        # Placeholder - simple key-value extraction
        mappings = {}
        lines = text.split("\n")
        for line in lines:
            if ":" in line and len(line.split(":")) == 2:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if len(key) > 0 and len(value) > 0:
                    mappings[key] = value
        return mappings

    def _extract_medical_rules(self, text: str) -> list:
        """Extract medical validation rules"""
        # Placeholder - extract bullet points or numbered rules
        rules = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("•", "-", "*")) or re.match(r"^\d+\.", line):
                rules.append(line.lstrip("•-*123456789. "))
        return rules


class RuleEvaluator:
    """Evaluate claims against parsed rules"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)

    def evaluate_technical_rules(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate claim against technical rules with bullet-point explanations"""
        technical_rules = self.redis_client.get(f"rules:technical:{settings.tenant_id}")
        if not technical_rules:
            return {"valid": True, "errors": [], "type": "No rules loaded"}

        rules = json.loads(technical_rules)
        errors = []
        error_type = "No error"

        # Check required fields
        required_fields = rules.get("required_fields", [])
        for field in required_fields:
            if field not in claim_data or not claim_data.get(field):
                errors.append(
                    f"• Required field '{field}' is missing or empty per Technical Adjudication Guide section 4."
                )
                error_type = "Technical error"

        # Check paid amount threshold
        paid_amount = claim_data.get("paid_amount_aed")
        threshold = rules.get("paid_amount_threshold", 1000)
        if paid_amount and paid_amount > threshold:
            errors.append(
                f"• Paid amount AED {paid_amount} exceeds policy threshold of AED {threshold} per section 3."
            )
            error_type = "Technical error"

        # Check approval for services requiring it
        service_code = claim_data.get("service_code")
        approval_required_services = rules.get("approval_required_services", [])
        if service_code in approval_required_services:
            approval_number = claim_data.get("approval_number")
            if not approval_number:
                errors.append(
                    f"• Service code {service_code} requires prior approval per section 1, but no approval provided."
                )
                error_type = "Technical error"

        # Check approval for diagnoses requiring it
        diagnosis_codes = claim_data.get("diagnosis_codes", "").split(",")
        approval_required_diagnoses = rules.get("approval_required_diagnoses", [])
        for diag in diagnosis_codes:
            diag = diag.strip()
            if diag in approval_required_diagnoses:
                if not claim_data.get("approval_number"):
                    errors.append(
                        f"• Diagnosis code {diag} requires prior approval per section 2, but no approval provided."
                    )
                    error_type = "Technical error"
                    break  # One error is enough

        return {"valid": len(errors) == 0, "errors": errors, "type": error_type}

    def evaluate_medical_rules(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate claim against medical rules using LLM"""
        medical_rules_data = self.redis_client.get(f"rules:medical:{settings.tenant_id}")
        if not medical_rules_data:
            return {"valid": True, "errors": [], "type": "No error", "llm_analysis": ""}

        medical_rules = json.loads(medical_rules_data)

        # Parse structured fields from List[KeyValuePair] to dicts if needed
        facility_registry = self._parse_key_value_list(medical_rules.get("facility_registry", []))
        diagnosis_service_mappings = self._parse_key_value_list(medical_rules.get("diagnosis_service_mappings", []))
        mutually_exclusive = self._parse_key_value_list(medical_rules.get("mutually_exclusive", []))

        # Build list of medical rules for LLM context
        medical_validation_rules = medical_rules.get("medical_validation_rules", [])
        inpatient_services = medical_rules.get("inpatient_services", [])
        outpatient_services = medical_rules.get("outpatient_services", [])

        # Construct rules list for LLM
        rules_list = medical_validation_rules

        # Add structured rules as strings
        if inpatient_services:
            rules_list.append(f"Inpatient services: {', '.join(inpatient_services)}")
        if outpatient_services:
            rules_list.append(f"Outpatient services: {', '.join(outpatient_services)}")
        if facility_registry:
            rules_list.append(f"Facility types: {facility_registry}")
        if diagnosis_service_mappings:
            mappings = [f"{diag}: {svc}" for diag, svc in diagnosis_service_mappings.items()]
            rules_list.append(f"Diagnosis-service mappings: {'; '.join(mappings)}")
        if mutually_exclusive:
            mutuals = [f"{diag1} cannot coexist with {diag2}" for diag1, diag2 in mutually_exclusive.items()]
            rules_list.append(f"Mutually exclusive diagnoses: {'; '.join(mutuals)}")

        # Use LLM for evaluation
        llm_service = LLMService()
        return llm_service.evaluate_medical_claim(claim_data, rules_list)

    def _parse_key_value_list(self, kv_list):
        """Parse List[KeyValuePair] to dict, handling fallback for older formats"""
        if isinstance(kv_list, list) and kv_list:
            if hasattr(kv_list[0], 'key'):  # KeyValuePair objects
                return {pair.key: pair.value for pair in kv_list}
            elif isinstance(kv_list[0], dict):  # JSON objects
                return {item['key']: item['value'] for item in kv_list}
        elif isinstance(kv_list, dict):  # Old dict format
            return kv_list
        return {}
