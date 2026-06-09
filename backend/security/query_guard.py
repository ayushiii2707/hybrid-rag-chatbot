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
            # ─ Existing rules (preserved exactly) ────────────────────────────────
            "prompt_injection_jailbreak": re.compile(
                r"(ignore\s+(?:previous|above|the)\s+instructions"
                r"|override\s+instructions"
                r"|override\s+query_guard"
                r"|system\s+override"
                r"|jailbreak"
                r"|dan\s+mode"
                r"|bypass\s+(?:safety|restrictions|security\s+filter)"
                r"|do\s+anything\s+now"
                r"|developer\s+mode"
                r"|override\s+rules)",
                re.IGNORECASE
            ),
            "system_prompt_extraction": re.compile(
                r"(system\s+prompt"
                r"|initial\s+instructions"
                r"|hidden\s+rules"
                r"|system\s+instructions"
                r"|dump\s+prompt"
                r"|reveal\s+instructions"
                r"|base\s+instructions"
                r"|what\s+rules\s+do\s+you\s+follow)",
                re.IGNORECASE
            ),
            # Q067 fix: narrowed to explicit dump/show/list intent so that
            # legitimate 'credentials to access the portal' queries are NOT blocked.
            # Preserved: api key, apikey, secret key, private key, password,
            # login details, login token, database password.
            "credential_extraction": re.compile(
                r"(api\s*key"
                r"|apikey"
                r"|secret\s*key"
                r"|private\s*key"
                r"|\bpassword\b"
                r"|login\s+details"
                r"|login\s+token"
                r"|database\s+password"
                r"|credentials\s+dump"
                r"|dump\s+credentials"
                r"|show\s+credentials"
                r"|list\s+credentials"
                r"|retrieve\s+(?:database\s+)?credentials"
                r"|(?:api|access)\s+token"
                r"|dump\s+(?:api|access)\s+"
                r"|secret\s+key\b)",
                re.IGNORECASE
            ),
            "role_escalation_admin_override": re.compile(
                r"(sudo\s+bypass"
                r"|admin\s+override"
                r"|escalate\s+(?:role|privilege|user)"
                r"|elevate\s+privilege"
                r"|admin\s+mode"
                r"|as\s+admin"
                r"|superadmin"
                r"|superuser"
                r"|root\s+access"
                r"|grant\s+admin"
                r"|enable\s+god\s+mode"
                r"|admin\s+(?:view|access)"
                r"|role\s+(?:override|to\s+admin)"
                r"|privilege\s+level\s+to\s+superuser)",
                re.IGNORECASE
            ),
            "document_dumping": re.compile(
                r"(dump\s+all"
                r"|print\s+all\s+chunks"
                r"|show\s+all\s+text"
                r"|list\s+all\s+pdfs"
                r"|retrieve\s+everything"
                r"|select\s+\*\s+from"
                r"|show\s+all\s+document"
                r"|dump\s+database"
                r"|show\s+all\s+chunks"
                r"|display\s+entire\s+manual)",
                re.IGNORECASE
            ),
            "employee_data_extraction": re.compile(
                r"(employee\s+salary"
                r"|employee\s+home\s+address"
                r"|employee\s+(?:contact|details|emails|personal)"
                r"|reliance\s+employee"
                r"|staff\s+(?:details|salary)"
                r"|customer\s+data"
                r"|dump\s+(?:private|employee)"
                r"|private\s+employee\s+details)",
                re.IGNORECASE
            ),
            # ─ New rules (Fix 4) ─────────────────────────────────────────────
            "sql_injection": re.compile(
                r"(\bsql\s+injection\b"
                r"|\bselect\b.{0,30}\bfrom\b"
                r"|\bunion\s+select\b"
                r"|\bdrop\s+table\b"
                r"|\binsert\s+into\b"
                r"|\bdelete\s+from\b"
                r"|\bupdate\b.{0,20}\bset\b)",
                re.IGNORECASE
            ),
            "secrets_extraction": re.compile(
                r"(environment\s+variables"
                r"|env\s+variables"
                r"|list\s+(?:all\s+)?(?:env|environment)"
                r"|print\s+(?:env|environment)"
                r"|\bsecrets\b)",
                re.IGNORECASE
            ),
            "sensitive_data_probing": re.compile(
                r"(audit\s+(?:logs?|table)"
                r"|system\s+logs?"
                r"|view\s+(?:system|audit)\s+logs?"
                r"|database\s+schemas?"
                r"|inject\s+prompt"
                r"|print\s+(?:original\s+)?database)",
                re.IGNORECASE
            ),
            "xss_script_injection": re.compile(
                r"(javascript\s*(?::|alert)"
                r"|\balert\s*[\(\s]"
                r"|document[.\s]+cookie"
                r"|<\s*script"
                r"|script\s*>"
                r"|on(?:load|error|click)\s*=)",
                re.IGNORECASE
            ),
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
