import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class QueryGuard:
    """
    Pre-retrieval enterprise governance layer to filter out malicious,
    adversarial, or policy-violating queries.
    """

    def __init__(self) -> None:
        # Define strict blocking regex patterns (triggers 'blocked' / 'high' risk)
        self.block_patterns = {
            "prompt_injection_jailbreak": re.compile(
                r"(ignore\s+(?:previous|above|the)\s+instructions|system\s+override|jailbreak|dan\s+mode|bypass\s+safety|do\s+anything\s+now|developer\s+mode|override\s+rules)",
                re.IGNORECASE
            ),
            "system_prompt_extraction": re.compile(
                r"(system\s+prompt|initial\s+instructions|hidden\s+rules|system\s+instructions|dump\s+prompt|reveal\s+instructions|what\s+rules\s+do\s+you\s+follow)",
                re.IGNORECASE
            ),
            "credential_extraction": re.compile(
                r"(api\s*key|apikey|secret\s*key|private\s*key|password|credentials|login\s+details|login\s+token|database\s+password)",
                re.IGNORECASE
            ),
            "role_escalation_admin_override": re.compile(
                r"(sudo\s+bypass|admin\s+override|escalate\s+role|admin\s+mode|as\s+admin|superadmin|root\s+access|grant\s+admin|enable\s+god\s+mode)",
                re.IGNORECASE
            ),
            "document_dumping": re.compile(
                r"(dump\s+all|print\s+all\s+chunks|show\s+all\s+text|list\s+all\s+pdfs|retrieve\s+everything|select\s+\*\s+from|show\s+all\s+document|dump\s+database|show\s+all\s+chunks|display\s+entire\s+manual)",
                re.IGNORECASE
            ),
            "employee_data_extraction": re.compile(
                r"(employee\s+salary|employee\s+home\s+address|employee\s+contact|reliance\s+employee|staff\s+details|staff\s+salary|employee\s+personal)",
                re.IGNORECASE
            )
        }

        # Define soft warning patterns (triggers 'suspicious' / 'medium' risk)
        self.suspicious_patterns = {
            "possible_data_probing": re.compile(
                r"(\bkey\b|\btoken\b|\bsalary\b|\bprivate\b|\badmin\b|\bpolicy\b)",
                re.IGNORECASE
            )
        }

    def evaluate_query(self, query: str) -> Dict[str, Any]:
        """
        Evaluates the query for governance compliance.
        
        Returns:
            Dict[str, Any] containing:
                status (str): "allowed" | "suspicious" | "blocked"
                risk_level (str): "low" | "medium" | "high"
                matched_rule (str or None): Name of the matching rule
                reason (str or None): Text description of the threat
        """
        if not query or not query.strip():
            return {
                "status": "allowed",
                "risk_level": "low",
                "matched_rule": None,
                "reason": "Empty query"
            }

        normalized_query = query.strip()

        # 1. Check strict block patterns
        for rule_name, pattern in self.block_patterns.items():
            match = pattern.search(normalized_query)
            if match:
                reason = f"Blocked by rule '{rule_name}': detected pattern '{match.group(0)}'"
                logger.warning(f"QueryGuard BLOCKED query: '{query}' | Reason: {reason}")
                return {
                    "status": "blocked",
                    "risk_level": "high",
                    "matched_rule": rule_name,
                    "reason": reason
                }

        # 2. Check soft suspicious patterns
        for rule_name, pattern in self.suspicious_patterns.items():
            match = pattern.search(normalized_query)
            if match:
                reason = f"Suspicious activity flags by rule '{rule_name}': detected pattern '{match.group(0)}'"
                logger.info(f"QueryGuard flagged query as SUSPICIOUS: '{query}' | Reason: {reason}")
                return {
                    "status": "suspicious",
                    "risk_level": "medium",
                    "matched_rule": rule_name,
                    "reason": reason
                }

        # 3. Safe / Allowed query
        return {
            "status": "allowed",
            "risk_level": "low",
            "matched_rule": None,
            "reason": "Query complies with enterprise security policies."
        }
