import json
import re
from typing import Any, Dict, Optional

import redis
from PyPDF2 import PdfReader

from shared.config import settings


class RuleParser:
    """Parse technical and medical rule documents"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)

    def parse_technical_rules(self, pdf_path: str) -> Dict[str, Any]:
        """Parse technical rules from PDF document"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

            # Extract thresholds and rules using regex patterns
            rules = {
                "paid_amount_threshold": self._extract_threshold(text, "paid.amount", 1000),
                "approval_number_min": self._extract_threshold(text, "approval.number", 100000),
                "valid_encounter_types": self._extract_list(text, "encounter.types"),
                "required_fields": self._extract_list(text, "required.fields"),
            }

            # Cache parsed rules
            cache_key = f"rules:technical:{settings.tenant_id}"
            self.redis_client.setex(cache_key, 3600, json.dumps(rules))  # Cache for 1 hour

            return rules

        except Exception as e:
            raise ValueError(f"Failed to parse technical rules: {str(e)}")

    def parse_medical_rules(self, pdf_path: str) -> Dict[str, Any]:
        """Parse medical rules from PDF document"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

            # Extract medical validation rules
            rules = {
                "diagnosis_code_patterns": self._extract_patterns(text, "diagnosis.codes"),
                "service_code_mappings": self._extract_mappings(text, "service.codes"),
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
        """Evaluate claim against technical rules"""
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
                errors.append(f"Required field '{field}' is missing or empty")
                error_type = "Technical error"

        # Check paid amount threshold
        paid_amount = claim_data.get("paid_amount_aed")
        threshold = rules.get("paid_amount_threshold", 1000)
        if paid_amount and paid_amount > threshold:
            errors.append(f"Paid amount {paid_amount} exceeds threshold {threshold}")
            error_type = "Technical error"

        # Check approval number
        approval_number = claim_data.get("approval_number")
        min_approval = rules.get("approval_number_min", 100000)
        if approval_number and len(str(approval_number)) < len(str(min_approval)):
            errors.append(
                f"Approval number {approval_number} is too short (min length {len(str(min_approval))})"
            )
            error_type = "Technical error"

        return {"valid": len(errors) == 0, "errors": errors, "type": error_type}

    def evaluate_medical_rules(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate claim against medical rules using LLM"""
        medical_rules = self.redis_client.get(f"rules:medical:{settings.tenant_id}")
        if not medical_rules:
            return {"valid": True, "errors": [], "type": "No error", "llm_analysis": ""}

        rules = json.loads(medical_rules)

        # For now, return placeholder - full LLM integration in next step
        return {
            "valid": True,
            "errors": [],
            "type": "No error",
            "llm_analysis": "Medical rules evaluation pending LLM integration",
        }
