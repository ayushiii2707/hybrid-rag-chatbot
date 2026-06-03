"""
backend/logging/query_logger.py
────────────────────────────────────────────────────────────────────────────────
Phase 1 — Enterprise Query Audit Logging
────────────────────────────────────────────────────────────────────────────────

QueryAuditLogger
  • Appends one JSON object per query to  backend/logs/query_logs.jsonl
  • Auto-creates the log directory if missing
  • Thread-safe file append (one open/write/close per call)
  • Non-critical: a logging failure NEVER crashes the retrieval pipeline
  • Fully extensible for future governance / security phases

Log format (one JSONL line per query):
{
    "query_id":           "<uuid4>",
    "timestamp":          "<ISO-8601 UTC>",
    "query":              "<raw user query>",
    "corrected_query":    "<preprocessed query>",
    "query_granularity":  "factual | explanatory | procedural | workflow",
    "answer_found":       true | false,
    "partial_match_found": false,
    "confidence":         0.0,
    "confidence_band":    "High confidence | Partial answer | Uncertain | No answer",
    "top_source_file":    "<filename or null>",
    "top_page_number":    <int or null>,
    "top_chunk_id":       "<chunk_id or null>",
    "retrieved_sources":  ["<file1>", "<file2>"],
    "response_length":    <int>,
    "processing_time_ms": <int>,
    "blocked":            false,
    "risk_level":         "low",
    "system_status":      "success | logging_failed"
}
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ── Default paths ─────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LOG_DIR  = os.path.join(_BACKEND_DIR, "logs")
_DEFAULT_LOG_FILE = os.path.join(_DEFAULT_LOG_DIR, "query_logs.jsonl")


class QueryAuditLogger:
    """
    Append-only JSONL audit logger for the enterprise RAG query pipeline.
    Also handles asynchronous persistency to PostgreSQL.

    Usage
    -----
    logger = QueryAuditLogger()
    logger.log_query(
        query="...",
        corrected_query="...",
        query_granularity="factual",
        answer_found=True,
        partial_match_found=False,
        confidence=0.89,
        confidence_band="High confidence",
        top_source_file="registration manual.pdf",
        top_page_number=4,
        top_chunk_id="abc123_c10",
        retrieved_sources=["registration manual.pdf"],
        synthesized_answer="...",
        processing_time_ms=420,
    )
    """

    # Shared thread pool executor for background DB logging tasks
    _executor = ThreadPoolExecutor(max_workers=5)

    def __init__(
        self,
        log_dir: str  = _DEFAULT_LOG_DIR,
        log_file: str = _DEFAULT_LOG_FILE,
    ) -> None:
        """
        Parameters
        ----------
        log_dir  : Directory where log files are stored. Created if absent.
        log_file : Full path to the append-only JSONL log file.
        """
        self.log_file = log_file
        self._ensure_log_dir(log_dir)
        logger.info(f"QueryAuditLogger initialized. Log file: {self.log_file}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _ensure_log_dir(log_dir: str) -> None:
        """Creates the log directory if it does not already exist."""
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as exc:
            # Non-fatal — log the warning but do not raise.
            logger.warning(f"QueryAuditLogger: could not create log directory '{log_dir}': {exc}")

    @staticmethod
    def _generate_query_id() -> str:
        """Returns a fresh UUID4 string."""
        return str(uuid.uuid4())

    @staticmethod
    def _utc_now_iso() -> str:
        """Returns current UTC time in ISO-8601 format (e.g. 2026-05-26T11:47:17Z)."""
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _unique_sources(retrieved_sources: List[str]) -> List[str]:
        """Deduplicates source files while preserving insertion order."""
        seen = set()
        result = []
        for src in retrieved_sources:
            if src and src not in seen:
                seen.add(src)
                result.append(src)
        return result

    # ── Public API ────────────────────────────────────────────────────────────

    def log_query(
        self,
        query:              str,
        corrected_query:    str,
        query_granularity:  str,
        answer_found:       bool,
        partial_match_found: bool,
        confidence:         float,
        confidence_band:    str,
        top_source_file:    Optional[str],
        top_page_number:    Optional[int],
        top_chunk_id:       Optional[str],
        retrieved_sources:  List[str],
        synthesized_answer: str,
        processing_time_ms: int,
        user_id:            Optional[str] = None,
        email:              Optional[str] = None,
        role:               Optional[str] = None,
        blocked:            bool = False,
        risk_level:         str = "low",
        security_reason:    Optional[str] = None,
    ) -> Optional[str]:
        """
        Builds and appends one audit log entry to the JSONL file.
        Also submits a task to write the log to the PostgreSQL database in the background.

        Parameters
        ----------
        All parameters map 1-to-1 to the required log schema fields.
        synthesized_answer is used only to compute response_length — it is
        NOT stored in the log to keep log files lightweight.

        Returns
        -------
        The generated query_id on success, or None if logging failed.
        """
        query_id  = self._generate_query_id()
        timestamp = self._utc_now_iso()

        entry: Dict[str, Any] = {
            "query_id":            query_id,
            "timestamp":           timestamp,
            "user_id":             user_id,
            "email":               email,
            "role":                role,
            "query":               query,
            "corrected_query":     corrected_query,
            "query_granularity":   query_granularity,
            "answer_found":        answer_found,
            "partial_match_found": partial_match_found,
            "confidence":          round(float(confidence), 6),
            "confidence_band":     confidence_band,
            "top_source_file":     top_source_file,
            "top_page_number":     top_page_number,
            "top_chunk_id":        top_chunk_id,
            "retrieved_sources":   self._unique_sources(retrieved_sources),
            "response_length":     len(synthesized_answer) if synthesized_answer else 0,
            "processing_time_ms":  int(processing_time_ms),
            "blocked":             blocked,
            "risk_level":          risk_level,
            "security_reason":     security_reason,
            "system_status":       "success",
        }

        # 1. Sync file logging
        try:
            with open(self.log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.debug(f"Audit log written: query_id={query_id}")
        except Exception as exc:
            # ── CRITICAL: logging must never crash the pipeline ───────────────
            logger.error(f"QueryAuditLogger: failed to write log entry: {exc}")
            # Attempt to write a minimal failure marker
            try:
                failure_entry = {
                    "query_id":     query_id,
                    "timestamp":    timestamp,
                    "query":        query[:200],
                    "system_status": "logging_failed",
                    "error":        str(exc),
                }
                with open(self.log_file, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(failure_entry, ensure_ascii=False) + "\n")
            except Exception:
                pass  # Fully silenced — pipeline must not be affected

        # 2. Async database logging
        try:
            self._executor.submit(
                self._db_log_query,
                query_id=query_id,
                user_id=user_id,
                email=email,
                role=role,
                query=query,
                corrected_query=corrected_query,
                query_granularity=query_granularity,
                answer_found=answer_found,
                partial_match_found=partial_match_found,
                confidence=confidence,
                confidence_band=confidence_band,
                top_source_file=top_source_file,
                top_page_number=top_page_number,
                top_chunk_id=top_chunk_id,
                retrieved_sources=self._unique_sources(retrieved_sources),
                response_length=len(synthesized_answer) if synthesized_answer else 0,
                processing_time_ms=processing_time_ms,
                blocked=blocked,
                risk_level=risk_level,
                security_reason=security_reason,
            )
        except Exception as db_exc:
            logger.error(f"QueryAuditLogger: failed to submit background DB logging task: {db_exc}")

        return query_id

    @staticmethod
    def _db_log_query(**kwargs) -> None:
        """
        Background task worker to persist query log inside PostgreSQL database.
        Completely isolated to never crash the main retrieval pipeline.
        """
        try:
            try:
                from backend.database.db import SessionLocal
                from backend.auth.auth_models import QueryLog
            except ImportError:
                import sys
                import os
                # Find parent directory of backend (workspace root)
                # This file is in backend/logging/query_logger.py
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                workspace_dir = os.path.dirname(backend_dir)
                if workspace_dir not in sys.path:
                    sys.path.insert(0, workspace_dir)
                from backend.database.db import SessionLocal
                from backend.auth.auth_models import QueryLog

            import uuid

            db = SessionLocal()
            try:
                u_id = None
                if kwargs.get("user_id"):
                    try:
                        u_id = uuid.UUID(str(kwargs["user_id"]))
                    except ValueError:
                        pass

                db_log = QueryLog(
                    query_id=kwargs["query_id"],
                    user_id=u_id,
                    email=kwargs.get("email"),
                    role=kwargs.get("role"),
                    query=kwargs["query"],
                    corrected_query=kwargs.get("corrected_query"),
                    query_granularity=kwargs.get("query_granularity"),
                    answer_found=kwargs.get("answer_found", False),
                    partial_match_found=kwargs.get("partial_match_found", False),
                    confidence=kwargs.get("confidence", 0.0),
                    confidence_band=kwargs.get("confidence_band"),
                    top_source_file=kwargs.get("top_source_file"),
                    top_page_number=kwargs.get("top_page_number"),
                    top_chunk_id=kwargs.get("top_chunk_id"),
                    retrieved_sources=kwargs.get("retrieved_sources"),
                    response_length=kwargs.get("response_length", 0),
                    processing_time_ms=kwargs.get("processing_time_ms", 0),
                    blocked=kwargs.get("blocked", False),
                    risk_level=kwargs.get("risk_level", "low"),
                    security_reason=kwargs.get("security_reason"),
                    system_status="success",
                )
                db.add(db_log)
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"PostgreSQL DB query logging failed: {db_err}")
            finally:
                db.close()
        except Exception as init_err:
            logger.error(f"PostgreSQL DB logging task initialization failed: {init_err}")

    def read_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Returns the last N log entries as parsed dicts.
        Convenience method for diagnostics and verification.
        """
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            recent = lines[-n:] if len(lines) >= n else lines
            return [json.loads(line.strip()) for line in recent if line.strip()]
        except Exception as exc:
            logger.warning(f"QueryAuditLogger.read_recent: could not read log: {exc}")
            return []
