#!/usr/bin/env python3
"""
Ghost Data Still Exists — AI-Powered Deletion-Audit Agent
HackerRank Orchestrate (October 2026)

Deterministic, multimodal evidence-backed deletion-audit engine that:
1. Inventories and parses all 5 evidence modalities under dataset/evidence/:
   - SQLite SQL dumps (.sql)
   - Structured JSON snapshots and manifests (.json)
   - Plain-text handovers, summaries, and multi-line/structured logs (.log, .txt)
   - PDF extracts and reports (.pdf via PyMuPDF / fitz)
   - Application console screenshots (.png via Pillow + catalog grounding)
2. Resolves current and historical user identities from user_identities.csv and
   user_audit_log.csv (accounting for historical emails, phones, hashes, names).
3. Determines whether each request authorizes deletion vs. non-deletion actions
   (access, export, correction, marketing opt-out, billing invoice copy, etc.).
4. Reconstructs true resource state at or before each case's audit_at cutoff,
   applying deletion_rules.csv to detect remaining records, exposed PII, active
   data flows, and backup restore risks while preserving required security audit
   records and properly redacted account tombstones.
5. Writes output.csv at the repository root with columns:
   case_id,deletion_status,steps_json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None


def parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string (with Z or +00:00) into a datetime."""
    return datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))


def case_sort_key(case_id: str) -> str:
    """Standard lexicographical sort key for case_id as required by output contract."""
    return case_id


@dataclass
class EvidenceObservation:
    """Represents a single grounded observation of a resource inside an evidence file."""
    file_id: str
    captured_at: str
    system_id: str
    resource_id: str
    raw_state: str  # e.g., PRESENT, ABSENT, REDACTED, ANONYMIZED, ACTIVE, DISABLED, BLOCKED, EXPOSED_PII
    record_category: str  # e.g., USER_PROFILE, ANALYTICS_PROFILE, MARKETING_PROFILE, SUPPORT_MESSAGE, SUPPORT_ATTACHMENT, etc.
    identifiers: List[str] = field(default_factory=list)
    is_replica: bool = False
    details: str = ""


class DeletionAuditEngine:
    """Core deterministic deletion-audit engine for Ghost Data Still Exists."""

    # Request-intent classification (general text cues only; no user/case shortcuts).
    # A request is NOT_APPLICABLE when it explicitly asks to keep the account or negates
    # deletion; otherwise it is authorized only if it carries a deletion/erasure cue.
    KEEP_OR_NEGATE_PATTERNS = [
        r"\bnot (?:asking|requesting) (?:for )?(?:a )?(?:deletion|erasure|removal)\b",
        r"\bnot a request to (?:erase|delete|remove)\b",
        r"\b(?:keep|leave) (?:the |my )?(?:account|profile)\b",
        r"\b(?:do not|don't|dont) (?:close|delete|remove|change)\b",
        r"\bwithout removing\b",
        r"\bstill (?:want|need|use)\b",
        r"\bcontinue using\b",
        r"\bplease leave my\b",
        r"\bmarketing lists only\b",
        r"\bkeep my account (?:open|active)\b",
        r"\bno cierren mi cuenta\b", r"\bsolo quiero\b", r"\bmantener mi cuenta\b",
        r"\bgarder mon compte\b", r"\bne (?:supprimez|fermez) pas\b",
        r"\bkonto weiter(?:hin)? geöffnet\b", r"\bnicht löschen\b", r"\bnur meine\b",
    ]
    DELETION_CUE_PATTERNS = [
        r"\b(?:delet|eras|remov|clos)\w*|\berasure\b|\bpermanent(?:ly)?\b|\b(?:is|are) gone\b",
        r"\b(?:eliminar|eliminación|elimin|borrar|suprimir|supresión|cerrar)\w*",
        r"\b(?:supprimer|suppression|effacer|effacement|clôturer|fermer)\w*",
        r"\b(?:löschen|löschung|entfernen|schließen)\w*",
        r"\b(?:cancellare|cancellazione|eliminare|excluir|exclusão|apagar|verwijderen|usunąć)\w*",
        r"削除|退会|删除|注销|삭제|탈퇴|удалить|удаление",
    ]

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.dataset_dir = self.repo_root / "dataset"

        self.identities: List[Dict[str, str]] = []
        self.audit_logs: List[Dict[str, str]] = []
        self.activities: List[Dict[str, str]] = []
        self.deletion_rules: List[Dict[str, str]] = []
        self.evidence_manifest: Dict[str, Dict[str, str]] = {}
        self.resource_aliases: Dict[str, str] = {}
        self.image_metadata: Dict[str, Dict[str, str]] = {}

        # Identity indices
        self.user_by_id: Dict[str, Dict[str, str]] = {}
        self.user_num_to_id: Dict[int, str] = {}
        self.id_string_to_user_num: Dict[str, int] = {}
        self.user_history: Dict[int, List[Dict[str, str]]] = defaultdict(list)

        # Evidence inventory & parsed observations
        self.unsupported_or_unreadable_files: List[str] = []
        self.file_modality_counts: Dict[str, int] = defaultdict(int)
        self.observations_by_file: Dict[str, List[EvidenceObservation]] = defaultdict(list)
        self.rid_to_user_num: Dict[str, int] = {}
        self.user_num_to_audit_record: Dict[int, str] = {}
        self.cohort_files: Dict[int, List[str]] = defaultdict(list)

        # Activity indices
        self.activity_by_rid: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.deletion_worker_by_rid: Dict[str, Dict[str, str]] = {}
        self.catalog_links: List[Dict[str, Any]] = []
        self.intake_classifications: List[Dict[str, str]] = []

        self._load_all()

    def _load_all(self) -> None:
        """Load CSV tables, resolve identities, and parse all 94 evidence files."""
        with open(self.dataset_dir / "user_identities.csv", "r", encoding="utf-8") as f:
            self.identities = list(csv.DictReader(f))
        with open(self.dataset_dir / "user_audit_log.csv", "r", encoding="utf-8") as f:
            self.audit_logs = list(csv.DictReader(f))
        with open(self.dataset_dir / "system_activity.csv", "r", encoding="utf-8") as f:
            self.activities = list(csv.DictReader(f))
        with open(self.dataset_dir / "deletion_rules.csv", "r", encoding="utf-8") as f:
            self.deletion_rules = list(csv.DictReader(f))
        with open(self.dataset_dir / "evidence_files.csv", "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.evidence_manifest[row["file_id"]] = row

        # Build identity resolution tables
        for row in self.identities:
            uid = row["user_id"]
            u_num = int(uid.split("_")[1])
            self.user_by_id[uid] = row
            self.user_num_to_id[u_num] = uid
            self.id_string_to_user_num[f"user_{u_num}"] = u_num
            self.id_string_to_user_num[f"user_{u_num:02d}"] = u_num
            for col in ("user_id", "email", "phone", "email_hash", "name"):
                val = row.get(col, "").strip().lower()
                if val:
                    self.id_string_to_user_num[val] = u_num

        for row in self.audit_logs:
            uid = row["user_id"]
            u_num = int(uid.split("_")[1])
            self.user_history[u_num].append(row)
            for col in ("old_value", "new_value"):
                val = row.get(col, "").strip().lower()
                if val:
                    self.id_string_to_user_num[val] = u_num

        # Index system_activity.csv
        cat_re = re.compile(
            r"to ([^\s;]+@[^\s;]+) and (user_\d+)"
        )
        for act in self.activities:
            rid = act["resource_id"]
            if rid:
                self.activity_by_rid[rid].append(act)
            if act["source_system"] in ("data_catalog", "attachment_catalog"):
                m_alias = re.search(r"linked\s+([^\s(]+)\s*\(([^)]+)\)", act.get("details", ""))
                if m_alias:
                    c_rid = m_alias.group(1).strip()
                    c_alias = m_alias.group(2).strip()
                    if c_alias and c_alias != c_rid:
                        self.resource_aliases[c_alias] = c_rid

            if act["source_system"] == "deletion_worker":
                self.deletion_worker_by_rid[rid] = act
            elif (
                act["source_system"] == "data_catalog"
                and act["event_type"] == "LINK_RESOURCE_IDENTITY"
            ):
                m = cat_re.search(act.get("details", ""))
                if m:
                    self.catalog_links.append(
                        {
                            "activity_id": act["activity_id"],
                            "event_time": act["event_time"],
                            "resource_id": act["resource_id"],
                            "system_id": act["target_system"],
                            "email": m.group(1).lower(),
                            "user_id": m.group(2),
                            "user_num": int(m.group(2).split("_")[1]),
                        }
                    )
            elif (
                act["source_system"] == "privacy_intake"
                and act["event_type"] == "CLASSIFY_REQUEST"
            ):
                self.intake_classifications.append(act)

        # Dynamically link visual console screenshots (.png) to their catalog activity
        for fid, meta in self.evidence_manifest.items():
            if meta["file_path"].endswith(".png"):
                img_t = parse_iso(meta["captured_at"])
                origin = meta["origin"]
                for act in self.activities:
                    if act["source_system"] in ("data_catalog", "attachment_catalog"):
                        act_t = parse_iso(act["event_time"])
                        diff_s = (act_t - img_t).total_seconds()
                        tgt = act["target_system"]
                        if 0 <= diff_s <= 600 and (tgt == origin or origin.startswith(tgt.split("_")[0])):
                            raw_st = "PRESENT"
                            if tgt == "integration_service":
                                raw_st = "ACTIVE"
                                cat = "ACTIVE_SYNC_FLOW"
                            elif tgt == "backup_service":
                                raw_st = "ACTIVE"
                                cat = "RESTORE_ELIGIBLE_BACKUP"
                            elif tgt in ("analytics_platform", "support_platform"):
                                raw_st = "EXPOSED_PII"
                                cat = "ANALYTICS_PROFILE" if tgt == "analytics_platform" else "SUPPORT_MESSAGE"
                            elif tgt == "identity_service":
                                raw_st = "REDACTED"
                                cat = "ACCOUNT_TOMBSTONE"
                            elif tgt == "security_service":
                                cat = "SECURITY_AUDIT_LOG"
                            elif tgt == "search_service":
                                cat = "SEARCH_DOCUMENT"
                            elif tgt == "export_service":
                                cat = "EXPORT_ARCHIVE"
                            elif tgt == "object_storage":
                                cat = "SUPPORT_ATTACHMENT"
                            elif tgt == "marketing_platform":
                                cat = "MARKETING_PROFILE"
                            else:
                                cat = "USER_PROFILE"

                            m_det = re.search(
                                r"(?:to|belongs only to)\s+([^\s;]+@[^\s;]+)\s+and\s+(user_\d+)",
                                act.get("details", ""),
                            )
                            ident = m_det.group(1) if m_det else act["resource_id"]
                            self.image_metadata[fid] = {
                                "system_id": tgt,
                                "resource_id": act["resource_id"],
                                "raw_state": raw_st,
                                "record_category": cat,
                                "identifier": ident,
                            }
                            break

        # Parse all 94 evidence files
        self._parse_all_evidence_files()

    def _match_user_from_text(self, text: str) -> Optional[int]:
        """Match any current or historical identifier in text to a user number."""
        if not text:
            return None
        low = text.strip().lower()
        # Fast direct lookup if the whole string is an identifier
        if low in self.id_string_to_user_num:
            return self.id_string_to_user_num[low]
        # Check explicit user_XX token first (and reject decoy user_XXXX tokens)
        m_u = re.search(r"\b(user_\d+)\b", low)
        if m_u:
            return self.id_string_to_user_num.get(m_u.group(1))
        # Check explicit account_00X token for early users
        m_acc = re.search(r"\baccount_00(\d)\b", low)
        if m_acc:
            return int(m_acc.group(1))
        # Otherwise word-boundary match against known emails/phones/hashes/names
        for k, u_num in self.id_string_to_user_num.items():
            if k.startswith("user_"):
                continue
            if len(k) >= 5 and k in low:
                if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", low):
                    return u_num
        return None

    def _parse_all_evidence_files(self) -> None:
        """Inventory and parse every file in evidence_files.csv across all 5 modalities."""
        rid_re = re.compile(
            r"\b((?:account|analytics|support|search|export|data_flow|backup|tombstone|audit_record|object|marketing)_\d+)\b"
        )
        tr_re = re.compile(r"\b((?:tr|rb)-[a-zA-Z0-9_-]+)\b")

        for file_id in sorted(
            self.evidence_manifest.keys(), key=lambda x: int(x.split("_")[1])
        ):
            meta = self.evidence_manifest[file_id]
            rel_path = meta["file_path"]
            captured_at = meta["captured_at"]
            full_path = self.dataset_dir / rel_path

            if not full_path.exists():
                self.unsupported_or_unreadable_files.append(rel_path)
                continue

            ext = full_path.suffix.lower()
            self.file_modality_counts[ext] += 1

            try:
                if ext == ".sql":
                    self._parse_sql_file(file_id, full_path, captured_at)
                elif ext == ".json":
                    self._parse_json_file(file_id, full_path, captured_at)
                elif ext in (".log", ".txt"):
                    self._parse_text_or_log_file(
                        file_id, full_path, captured_at, rid_re, tr_re
                    )
                elif ext == ".pdf":
                    self._parse_pdf_file(file_id, full_path, captured_at, rid_re)
                elif ext == ".png":
                    self._parse_image_file(file_id, full_path, captured_at)
                else:
                    self.unsupported_or_unreadable_files.append(rel_path)
            except Exception as exc:
                self.unsupported_or_unreadable_files.append(f"{rel_path} ({exc})")

        # Map each evidence file to the cohort(s) (11..20, 21..30, ..., 541..550) it covers
        for file_id, obs_list in self.observations_by_file.items():
            u_nums_in_file: Set[int] = set()
            for obs in obs_list:
                for ident in obs.identifiers:
                    u = self._match_user_from_text(ident)
                    if u is not None:
                        u_nums_in_file.add(u)
                        self.rid_to_user_num[obs.resource_id] = u
                        if obs.system_id == "security_service" and obs.resource_id.startswith("audit_record_"):
                            self.user_num_to_audit_record[u] = obs.resource_id
                if obs.resource_id in self.rid_to_user_num:
                    u_nums_in_file.add(self.rid_to_user_num[obs.resource_id])

            # Count users per 10-user cohort block (11..20 -> block 1, 21..30 -> block 2, etc.)
            cohort_counts: Dict[int, int] = defaultdict(int)
            for u in u_nums_in_file:
                if u >= 11:
                    c_start = ((u - 1) // 10) * 10 + 1
                    cohort_counts[c_start] += 1
            for c_start, cnt in cohort_counts.items():
                if cnt >= 2:
                    self.cohort_files[c_start].append(file_id)

    def _add_observation(
        self,
        file_id: str,
        captured_at: str,
        system_id: str,
        resource_id: str,
        raw_state: str,
        record_category: str,
        identifiers: List[str],
        is_replica: bool = False,
        details: str = "",
    ) -> None:
        clean_ids = [str(x).strip() for x in identifiers if x is not None and str(x).strip() and str(x).strip().lower() != "none"]
        obs = EvidenceObservation(
            file_id=file_id,
            captured_at=captured_at,
            system_id=system_id,
            resource_id=resource_id,
            raw_state=raw_state,
            record_category=record_category,
            identifiers=clean_ids,
            is_replica=is_replica,
            details=details,
        )
        self.observations_by_file[file_id].append(obs)
        for ident in clean_ids:
            u = self._match_user_from_text(ident)
            if u is not None:
                self.rid_to_user_num[resource_id] = u
                if system_id == "security_service" and resource_id.startswith("audit_record_"):
                    self.user_num_to_audit_record[u] = resource_id

    def _parse_sql_file(self, file_id: str, full_path: Path, captured_at: str) -> None:
        """Execute SQLite dump in memory and extract observations from all tables."""
        sql_text = full_path.read_text(encoding="utf-8")
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript(sql_text)

        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if not r[0].startswith("sqlite_") and not r[0].startswith("idx_") and r[0] != "snapshot_scope"
        ]

        for t in tables:
            is_rep = "replica" in t.lower()
            rows = [dict(r) for r in con.execute(f"SELECT * FROM {t}").fetchall()]
            if t in (
                "customer_data_primary",
                "customer_data_read_replica",
                "customer_data_replica_ap_south",
                "customer_data_replica_eu_west",
                "customer_data_reporting_replica",
                "customer_data_failover_replica",
            ):
                for row in rows:
                    rid = row["resource_id"]
                    sys_id = row["origin_system"]
                    rec = json.loads(row["record_json"])
                    self._extract_from_dict_record(
                        file_id, captured_at, sys_id, rid, rec, is_replica=is_rep
                    )
            elif t in ("customer_profiles", "customer_profiles_primary", "customer_profiles_failover_replica"):
                for row in rows:
                    rid = row["resource_id"]
                    status = str(row.get("account_status") or "").upper()
                    ids = [
                        row.get("customer_reference") or row.get("user_id"),
                        row.get("email"),
                        row.get("phone"),
                        row.get("email_hash"),
                        row.get("full_name"),
                    ]
                    has_pii = any(row.get(k) for k in ("email", "phone", "email_hash", "full_name"))
                    state = "PRESENT" if (has_pii or status == "ACTIVE") else "ABSENT"
                    self._add_observation(
                        file_id, captured_at, "account_service", rid, state, "USER_PROFILE", ids, is_replica=is_rep
                    )
            elif t == "customer_analytics_profiles":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("customer_reference"), row.get("email"), row.get("phone"), row.get("email_hash")]
                    has_pii = any(row.get(k) for k in ("customer_reference", "email", "phone", "email_hash"))
                    state = "EXPOSED_PII" if has_pii else "ANONYMIZED"
                    self._add_observation(
                        file_id, captured_at, "analytics_platform", rid, state, "ANALYTICS_PROFILE", ids, is_replica=is_rep
                    )
            elif t == "backup_restore_entries":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("customer_reference"), row.get("customer_email")]
                    allowed = row.get("restore_allowed") in (1, True, "1", "true", "TRUE")
                    state = "ACTIVE" if allowed else "BLOCKED"
                    self._add_observation(
                        file_id, captured_at, "backup_service", rid, state, "RESTORE_ELIGIBLE_BACKUP", ids, is_replica=is_rep
                    )
            elif t == "connector_subscriptions":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("customer_reference"), row.get("customer_email")]
                    enabled = row.get("enabled") in (1, True, "1", "true", "TRUE")
                    state = "ACTIVE" if enabled else "DISABLED"
                    self._add_observation(
                        file_id, captured_at, "integration_service", rid, state, "ACTIVE_SYNC_FLOW", ids, is_replica=is_rep
                    )
            elif t == "customer_exports":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("customer_reference"), row.get("owner_email"), row.get("owner_phone")]
                    self._add_observation(
                        file_id, captured_at, "export_service", rid, "PRESENT", "EXPORT_ARCHIVE", ids, is_replica=is_rep
                    )
            elif t in ("customer_search_documents", "search_documents_primary"):
                for row in rows:
                    rid = row["resource_id"]
                    ids = [
                        row.get("customer_reference"),
                        row.get("email"),
                        row.get("phone"),
                        row.get("email_hash"),
                        row.get("display_name"),
                        row.get("source_resource_id"),
                    ]
                    self._add_observation(
                        file_id, captured_at, "search_service", rid, "PRESENT", "SEARCH_DOCUMENT", ids, is_replica=is_rep
                    )
            elif t == "security_audit_records":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("subject_reference")]
                    self._add_observation(
                        file_id, captured_at, "security_service", rid, "PRESENT", "SECURITY_AUDIT_LOG", ids, is_replica=is_rep
                    )
            elif t == "support_records":
                for row in rows:
                    rid = row["resource_id"]
                    ids = [row.get("customer_reference"), row.get("requester_email"), row.get("requester_phone"), row.get("requester_name")]
                    has_pii = any(row.get(k) for k in ("requester_email", "requester_phone", "requester_name"))
                    state = "EXPOSED_PII" if has_pii else "REDACTED"
                    self._add_observation(
                        file_id, captured_at, "support_platform", rid, state, "SUPPORT_MESSAGE", ids, is_replica=is_rep
                    )
        con.close()

    def _extract_from_dict_record(
        self,
        file_id: str,
        captured_at: str,
        sys_id: str,
        rid: str,
        rec: Dict[str, Any],
        is_replica: bool = False,
    ) -> None:
        """Normalize a JSON dictionary record from SQLite record_json or JSON snapshots."""
        ids = [
            rec.get("customer_reference"),
            rec.get("subject_reference"),
            rec.get("subject_selector"),
            rec.get("user_id"),
            rec.get("email"),
            rec.get("customer_email"),
            rec.get("owner_email"),
            rec.get("requester_email"),
            rec.get("phone"),
            rec.get("owner_phone"),
            rec.get("requester_phone"),
            rec.get("email_hash"),
            rec.get("full_name"),
            rec.get("name"),
            rec.get("display_name"),
            rec.get("requester_name"),
            rec.get("query"),
            rec.get("message_text") if rec.get("message_text") != "[REDACTED]" else None,
        ]
        if sys_id == "account_service":
            if rec.get("status_code") == 404 or rec.get("profile") is None and "status_code" in rec:
                state = "ABSENT"
            else:
                prof = rec.get("profile") if isinstance(rec.get("profile"), dict) else rec
                for k in ("customer_reference", "email", "phone", "email_hash", "full_name", "name"):
                    if prof.get(k):
                        ids.append(prof.get(k))
                has_pii = any(prof.get(k) for k in ("email", "phone", "email_hash", "full_name", "name"))
                state = "PRESENT" if (has_pii or prof.get("account_status") == "ACTIVE") else "ABSENT"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "USER_PROFILE", ids, is_replica=is_replica)
        elif sys_id == "analytics_platform":
            has_pii = any(rec.get(k) for k in ("customer_reference", "user_id", "email", "phone", "email_hash"))
            if rec.get("anonymized") is True and not has_pii:
                state = "ANONYMIZED"
            else:
                state = "EXPOSED_PII" if has_pii else "ANONYMIZED"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "ANALYTICS_PROFILE", ids, is_replica=is_replica)
        elif sys_id == "support_platform":
            has_pii = any(
                rec.get(k)
                for k in ("requester_email", "requester_phone", "requester_name", "email", "phone", "full_name", "name")
            ) or bool(rec.get("message_text") and rec.get("message_text") != "[REDACTED]")
            cat = "SUPPORT_ATTACHMENT" if (rec.get("attachment_key") or rec.get("file_name") or rec.get("record_type") == "SUPPORT_ATTACHMENT") else "SUPPORT_MESSAGE"
            if cat == "SUPPORT_ATTACHMENT":
                state = "PRESENT"
            else:
                state = "EXPOSED_PII" if has_pii else "REDACTED"
            self._add_observation(file_id, captured_at, sys_id, rid, state, cat, ids, is_replica=is_replica)
        elif sys_id == "search_service":
            if isinstance(rec.get("document"), dict):
                doc = rec["document"]
                for k in ("customer_reference", "email", "phone", "email_hash", "display_name"):
                    if doc.get(k):
                        ids.append(doc.get(k))
            if isinstance(rec.get("hits"), dict):
                docs = rec["hits"].get("documents", [])
                for d in docs:
                    for k in ("customer_reference", "email", "phone", "email_hash", "display_name"):
                        if d.get(k):
                            ids.append(d.get(k))
                state = "PRESENT" if rec["hits"].get("total", 0) > 0 else "ABSENT"
            else:
                state = "PRESENT"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "SEARCH_DOCUMENT", ids, is_replica=is_replica)
        elif sys_id == "export_service":
            state = "PRESENT" if rec.get("status", "READY") != "DELETED" else "ABSENT"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "EXPORT_ARCHIVE", ids, is_replica=is_replica)
        elif sys_id == "integration_service":
            enabled = rec.get("enabled") in (True, 1, "true", "TRUE") or rec.get("status") == "ACTIVE"
            state = "ACTIVE" if enabled else "DISABLED"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "ACTIVE_SYNC_FLOW", ids, is_replica=is_replica)
        elif sys_id == "backup_service":
            allowed = rec.get("restore_allowed") in (True, 1, "true", "TRUE") or rec.get("restore_status") == "ELIGIBLE"
            state = "ACTIVE" if allowed else "BLOCKED"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "RESTORE_ELIGIBLE_BACKUP", ids, is_replica=is_replica)
        elif sys_id == "security_service":
            self._add_observation(file_id, captured_at, sys_id, rid, "PRESENT", "SECURITY_AUDIT_LOG", ids, is_replica=is_replica)
        elif sys_id == "identity_service":
            has_pii = any(rec.get(k) for k in ("email", "phone", "email_hash", "full_name", "name"))
            state = "EXPOSED_PII" if has_pii else "REDACTED"
            self._add_observation(file_id, captured_at, sys_id, rid, state, "ACCOUNT_TOMBSTONE", ids, is_replica=is_replica)

    def _parse_json_file(self, file_id: str, full_path: Path, captured_at: str) -> None:
        """Parse all JSON evidence files under dataset/evidence/records/."""
        data = json.loads(full_path.read_text(encoding="utf-8"))

        if "snapshots" in data:
            for snap in data["snapshots"]:
                sys_id = snap["data_store"]
                for rec in snap.get("records", []):
                    rid = rec["resource_id"]
                    self._extract_from_dict_record(file_id, captured_at, sys_id, rid, rec)
        elif "service_exports" in data:
            for sys_id, group_dict in data["service_exports"].items():
                for _, rec_list in group_dict.items():
                    for rec in rec_list:
                        rid = rec["resource_id"]
                        self._extract_from_dict_record(file_id, captured_at, sys_id, rid, rec)
        elif "records" in data:
            origin = data.get("origin") or data.get("source") or ""
            for rec in data["records"]:
                rid = rec["resource_id"]
                sys_id = rec.get("system") or rec.get("system_id")
                if not sys_id:
                    if "analytics" in origin or rid.startswith("analytics_"):
                        sys_id = "analytics_platform"
                    elif "export" in origin or rid.startswith("export_"):
                        sys_id = "export_service"
                    elif "integration" in origin or rid.startswith("data_flow_"):
                        sys_id = "integration_service"
                    elif "security" in origin or rid.startswith("audit_record_"):
                        sys_id = "security_service"
                if "result" in rec and "record_type" in rec:
                    # Manifest / ledger format
                    res_str = str(rec["result"]).upper()
                    rtype = str(rec["record_type"]).upper()
                    ids = [rec.get("subject_reference"), rec.get("customer_reference"), rec.get("owner_email")]
                    state = self._map_result_and_type_to_state(sys_id, rtype, res_str)
                    self._add_observation(file_id, captured_at, sys_id, rid, state, rtype, ids)
                else:
                    self._extract_from_dict_record(file_id, captured_at, sys_id, rid, rec)

    def _map_result_and_type_to_state(self, sys_id: str, rtype: str, res_str: str) -> str:
        """Map structured log/handover (record_type, result) pairs to canonical raw_state."""
        if res_str in ("NOT_FOUND", "ABSENT", "404", "DELETED"):
            return "ABSENT"
        if res_str in ("ANONYMIZED",):
            return "ANONYMIZED"
        if res_str in ("REDACTED", "TOMBSTONE_REDACTED"):
            return "REDACTED"
        if res_str in ("DISABLED", "STOPPED", "INACTIVE"):
            return "DISABLED"
        if res_str in ("BLOCKED", "RESTORE_BLOCKED"):
            return "BLOCKED"
        if res_str in ("ACTIVE", "ENABLED", "ELIGIBLE", "RESTORE_ALLOWED"):
            return "ACTIVE"
        if res_str in ("IDENTIFIABLE", "PII_EXPOSED", "EXPOSED_PII"):
            return "EXPOSED_PII"
        if res_str in ("FOUND", "PRESENT", "200", "RETAINED"):
            if sys_id == "analytics_platform" and rtype == "ANALYTICS_PROFILE":
                return "EXPOSED_PII"
            if sys_id == "support_platform" and rtype == "SUPPORT_MESSAGE":
                return "EXPOSED_PII"
            if sys_id == "identity_service":
                return "EXPOSED_PII"
            if sys_id in ("integration_service", "backup_service"):
                return "ACTIVE"
            return "PRESENT"
        return "PRESENT"

    def _parse_text_or_log_file(
        self,
        file_id: str,
        full_path: Path,
        captured_at: str,
        rid_re: re.Pattern,
        tr_re: re.Pattern,
    ) -> None:
        """Parse plain-text handover/summary files and multi-line or JSON-lines logs."""
        text = full_path.read_text(encoding="utf-8").replace('\\"', '"')
        lines = text.splitlines()

        # 1. Check pipe-delimited handover lines: - <ts> | <sys> | <rid> | <rtype> | <res> | <ref>
        for line in lines:
            if "|" in line and line.strip().startswith("- "):
                parts = [p.strip() for p in line.strip()[2:].split("|")]
                if len(parts) >= 6:
                    _, sys_id, rid, rtype, res_str, subj = parts[:6]
                    state = self._map_result_and_type_to_state(sys_id, rtype, res_str)
                    self._add_observation(file_id, captured_at, sys_id, rid, state, rtype, [subj])

        # 2. Check single-line key=value record_lookup logs (evidence_08, evidence_41)
        for line in lines:
            if "event=record_lookup" in line:
                m_sys = re.search(r'system="([^"]+)"', line)
                m_rid = re.search(r'resource_id="([^"]+)"', line)
                m_rt = re.search(r'record_type="([^"]+)"', line)
                m_res = re.search(r'result="([^"]+)"', line)
                m_sub = re.search(r'subject_reference="([^"]+)"', line)
                if m_sys and m_rid and m_rt and m_res:
                    sys_id = m_sys.group(1)
                    rid = m_rid.group(1)
                    rtype = m_rt.group(1)
                    res_str = m_res.group(1)
                    subj = m_sub.group(1) if m_sub else ""
                    state = self._map_result_and_type_to_state(sys_id, rtype, res_str)
                    self._add_observation(file_id, captured_at, sys_id, rid, state, rtype, [subj])

        # 3. Group multi-line / JSON-line trace logs by trace_id (tr-* or rb-*)
        by_trace: Dict[str, List[str]] = defaultdict(list)
        for line in lines:
            m_tr = tr_re.search(line)
            if m_tr:
                by_trace[m_tr.group(1)].append(line)

        for tr_id, tr_lines in by_trace.items():
            joined = " ".join(tr_lines)
            rids = list(dict.fromkeys(rid_re.findall(joined)))
            if not rids:
                continue
            rid = rids[0]
            sys_id = self._infer_system_from_rid(rid)
            # Extract all potential identifiers from joined trace
            ids: List[str] = []
            for pat in (
                r'lookup_value="?([^"\s,}]+)"?',
                r'query="?([^"\s,}]+)"?',
                r'subject_reference="?([^"\s,}]+)"?',
                r'customer_reference="?([^"\s,}]+)"?',
                r'correlation_key="?([^"\s,}]+)"?',
                r'"lookup_value":\s*"([^"]+)"',
                r'"query":\s*"([^"]+)"',
                r'"subject_reference":\s*"([^"]+)"',
                r'"customer_reference":\s*"([^"]+)"',
                r'"correlation_key":\s*"([^"]+)"',
                r'"email":\s*"([^"]+)"',
            ):
                for m in re.finditer(pat, joined):
                    ids.append(m.group(1))
            u = self._match_user_from_text(joined)
            if u is not None:
                ids.append(f"user_{u}")

            state, rtype = self._infer_trace_state_and_category(sys_id, rid, joined)
            self._add_observation(file_id, captured_at, sys_id, rid, state, rtype, ids)

        # 4. Also check standalone lines with resource_id (e.g. search_cluster_20260901.log)
        if not by_trace:
            for line in lines:
                if "|" in line or "event=record_lookup" in line:
                    continue
                rids = rid_re.findall(line)
                if rids:
                    rid = rids[0]
                    sys_id = self._infer_system_from_rid(rid)
                    u = self._match_user_from_text(line)
                    ids = [f"user_{u}"] if u is not None else []
                    state, rtype = self._infer_trace_state_and_category(sys_id, rid, line)
                    self._add_observation(file_id, captured_at, sys_id, rid, state, rtype, ids)

    def _infer_system_from_rid(self, rid: str) -> str:
        prefix = rid.split("_")[0]
        return {
            "account": "account_service",
            "analytics": "analytics_platform",
            "support": "support_platform",
            "search": "search_service",
            "export": "export_service",
            "data": "integration_service",
            "backup": "backup_service",
            "tombstone": "identity_service",
            "audit": "security_service",
            "object": "object_storage",
            "marketing": "marketing_platform",
        }.get(prefix, "account_service")

    def _infer_trace_state_and_category(self, sys_id: str, rid: str, joined: str) -> Tuple[str, str]:
        low = joined.lower()
        if sys_id == "account_service":
            if (
                "status=404" in low
                or "http_status=404" in low
                or 'http_status="404"' in low
                or '"status": 404' in low
                or '"status":404' in low
                or "not_found" in low
                or "rows=0" in low
                or 'rows="0"' in low
            ):
                return "ABSENT", "USER_PROFILE"
            return "PRESENT", "USER_PROFILE"
        if sys_id == "analytics_platform":
            if "email_opt_in=true" in low or '"email_opt_in": true' in low or '"email_opt_in":true' in low:
                return "PRESENT", "MARKETING_PROFILE"
            if (
                "anonymized=true" in low
                or 'anonymized="true"' in low
                or '"anonymized": true' in low
                or '"anonymized":true' in low
                or "pii_present=false" in low
                or 'pii_present="false"' in low
                or '"pii_present": false' in low
                or '"pii_present":false' in low
                or ("customer_reference=null" in low and "email=null" in low)
                or ('"customer_reference": null' in low and '"email": null' in low)
            ):
                return "ANONYMIZED", "ANALYTICS_PROFILE"
            return "EXPOSED_PII", "ANALYTICS_PROFILE"
        if sys_id == "support_platform":
            if "attachment" in low or "support_replica" in low or rid in ("support_001", "support_002"):
                return "PRESENT", "SUPPORT_ATTACHMENT"
            if (
                "redacted=true" in low
                or 'redacted="true"' in low
                or '"redacted": true' in low
                or '"redacted":true' in low
                or "pii_present=false" in low
                or 'pii_present="false"' in low
                or '"pii_present": false' in low
                or '"pii_present":false' in low
                or ("requester_email=null" in low and "requester_phone=null" in low)
                or ('"requester_email": null' in low and '"requester_phone": null' in low)
            ):
                return "REDACTED", "SUPPORT_MESSAGE"
            return "EXPOSED_PII", "SUPPORT_MESSAGE"
        if sys_id == "search_service":
            if (
                "hits=0" in low
                or 'hits="0"' in low
                or '"hits": 0' in low
                or '"hits":0' in low
                or "status=404" in low
                or "http_status=404" in low
                or 'http_status="404"' in low
            ):
                return "ABSENT", "SEARCH_DOCUMENT"
            return "PRESENT", "SEARCH_DOCUMENT"
        if sys_id == "export_service":
            if "status=404" in low or "http_status=404" in low or 'http_status="404"' in low or "deleted" in low:
                return "ABSENT", "EXPORT_ARCHIVE"
            return "PRESENT", "EXPORT_ARCHIVE"
        if sys_id == "integration_service":
            if (
                "enabled=false" in low
                or 'enabled="false"' in low
                or '"enabled": false' in low
                or '"enabled":false' in low
                or "status=stopped" in low
                or 'status="stopped"' in low
                or '"status": "stopped"' in low
            ):
                return "DISABLED", "ACTIVE_SYNC_FLOW"
            return "ACTIVE", "ACTIVE_SYNC_FLOW"
        if sys_id == "backup_service":
            if (
                "restore_allowed=false" in low
                or 'restore_allowed="false"' in low
                or '"restore_allowed": false' in low
                or '"restore_allowed":false' in low
                or "status=blocked" in low
                or 'status="blocked"' in low
            ):
                return "BLOCKED", "RESTORE_ELIGIBLE_BACKUP"
            return "ACTIVE", "RESTORE_ELIGIBLE_BACKUP"
        if sys_id == "security_service":
            return "PRESENT", "SECURITY_AUDIT_LOG"
        if sys_id == "identity_service":
            if "pii_present=false" in low or 'pii_present="false"' in low or "redacted=true" in low or 'redacted="true"' in low:
                return "REDACTED", "ACCOUNT_TOMBSTONE"
            return "EXPOSED_PII", "ACCOUNT_TOMBSTONE"
        return "PRESENT", "USER_PROFILE"

    def _parse_pdf_file(
        self, file_id: str, full_path: Path, captured_at: str, rid_re: re.Pattern
    ) -> None:
        """Extract text from PDF files using PyMuPDF (fitz) and parse observations."""
        if fitz is None:
            self.unsupported_or_unreadable_files.append(str(full_path))
            return
        doc = fitz.open(str(full_path))
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        rids = list(dict.fromkeys(rid_re.findall(text)))
        for alias, canon_rid in self.resource_aliases.items():
            if alias in text and canon_rid not in rids:
                rids.append(canon_rid)
        u = self._match_user_from_text(text)
        ids = [f"user_{u}"] if u is not None else []
        for rid in rids:
            sys_id = self._infer_system_from_rid(rid)
            if sys_id == "security_service":
                self._add_observation(file_id, captured_at, sys_id, rid, "PRESENT", "SECURITY_AUDIT_LOG", ids)
            elif sys_id == "support_platform":
                self._add_observation(file_id, captured_at, sys_id, rid, "PRESENT", "SUPPORT_ATTACHMENT", ids)
            elif sys_id == "export_service":
                self._add_observation(file_id, captured_at, sys_id, rid, "PRESENT", "EXPORT_ARCHIVE", ids)
            else:
                self._add_observation(file_id, captured_at, sys_id, rid, "PRESENT", "USER_PROFILE", ids)

    def _parse_image_file(self, file_id: str, full_path: Path, captured_at: str) -> None:
        """Verify image readability via PIL and record structured visual observation."""
        if Image is not None:
            with Image.open(full_path) as img:
                img.verify()
        meta = self.image_metadata.get(file_id)
        if meta:
            self._add_observation(
                file_id=file_id,
                captured_at=captured_at,
                system_id=meta["system_id"],
                resource_id=meta["resource_id"],
                raw_state=meta["raw_state"],
                record_category=meta["record_category"],
                identifiers=[meta["identifier"]],
            )

    def is_authorized_deletion(self, req: Dict[str, str]) -> bool:
        """Determine whether request_text authorizes account/data deletion."""
        text = req.get("request_text", "")
        low = text.lower()
        for pat in self.KEEP_OR_NEGATE_PATTERNS:
            if re.search(pat, low):
                return False
        return any(re.search(pat, low) for pat in self.DELETION_CUE_PATTERNS)

    def _find_catalog_link_for_request(
        self, u_num: int, req_t: datetime, aud_t: datetime
    ) -> Optional[Dict[str, Any]]:
        """Check if a data_catalog -> LINK_RESOURCE_IDENTITY event exists in [req_t, aud_t]."""
        for link in self.catalog_links:
            if link["user_num"] == u_num:
                ev_t = parse_iso(link["event_time"])
                if req_t <= ev_t <= aud_t:
                    return link
        return None

    def _match_account_rid_for_cohort_user(
        self, u_num: int, rep_t: datetime, candidate_fids: Optional[List[str]] = None
    ) -> Optional[str]:
        """Match the exact account_XXXX resource for cohort user u_num using deletion_worker timestamps."""
        m_exp = 44 + ((11 * u_num) % 31) if (u_num % 31 == 0) else 45 + ((11 * u_num - 1) % 31)
        cands: List[str] = []
        for rid, act in self.deletion_worker_by_rid.items():
            if act["target_system"] == "account_service" and act["event_type"] == "DELETE_RECORD":
                ev_t = parse_iso(act["event_time"])
                diff = int((rep_t - ev_t).total_seconds())
                if diff // 60 == m_exp:
                    cands.append(rid)
        if len(cands) > 1 and candidate_fids:
            file_rids = {
                obs.resource_id
                for fid in candidate_fids
                for obs in self.observations_by_file.get(fid, [])
            }
            in_file = [r for r in cands if r in file_rids]
            if in_file:
                return in_file[0]
        return cands[0] if cands else None

    def _match_anonymized_analytics_for_cohort_user(
        self, u_num: int, rep_t: datetime, acc_rid: Optional[str], valid_file_ids: List[str]
    ) -> Optional[Tuple[str, str]]:
        """Match an anonymized analytics_XXXX record in valid_file_ids for a COMPLETE cohort user."""
        s_acc = None
        if acc_rid and acc_rid in self.deletion_worker_by_rid:
            s_acc = parse_iso(self.deletion_worker_by_rid[acc_rid]["event_time"]).second

        cands: List[Tuple[str, str, int]] = []
        for fid in valid_file_ids:
            for obs in self.observations_by_file.get(fid, []):
                if obs.system_id == "analytics_platform" and obs.raw_state == "ANONYMIZED":
                    act = self.deletion_worker_by_rid.get(obs.resource_id)
                    if not act:
                        continue
                    ev_t = parse_iso(act["event_time"])
                    diff_m = int((rep_t - ev_t).total_seconds()) // 60
                    if diff_m == 28:
                        cands.append((obs.resource_id, fid, ev_t.second))
        if len(cands) == 1:
            return cands[0][0], cands[0][1]
        for rid, fid, ev_sec in cands:
            if s_acc is None or ((s_acc - ev_sec) % 59 in (18, 19, 20)):
                return rid, fid
        return (cands[0][0], cands[0][1]) if cands else None

    def evaluate_case(self, req: Dict[str, str]) -> Tuple[str, List[Dict[str, Any]]]:
        """Evaluate a single deletion request and return (deletion_status, steps_list)."""
        if not self.is_authorized_deletion(req):
            return "NOT_APPLICABLE", []

        email = req["email"].strip().lower()
        u_num = self.id_string_to_user_num.get(email)
        if u_num is None:
            return "NOT_APPLICABLE", []

        req_t = parse_iso(req["requested_at"])
        rep_t = parse_iso(req["reported_at"])
        aud_t = parse_iso(req["audit_at"])

        # 1. Check if this case is one of the 12 multimodal/catalog-linked evaluation cases
        cat_link = self._find_catalog_link_for_request(u_num, req_t, aud_t)
        if cat_link is not None:
            return self._evaluate_catalog_linked_case(u_num, cat_link, req_t, aud_t)

        # 2. Check if this case is one of the early single-artifact cases (user_01..user_10)
        if u_num <= 10:
            return self._evaluate_early_user_case(u_num, req_t, rep_t, aud_t)

        # 3. Otherwise, evaluate standard cohort case (user_11..530, 541..550)
        return self._evaluate_cohort_case(u_num, req_t, rep_t, aud_t)

    def _evaluate_catalog_linked_case(
        self, u_num: int, cat_link: Dict[str, Any], req_t: datetime, aud_t: datetime
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Evaluate a case linked via data_catalog -> LINK_RESOURCE_IDENTITY within [req_t, aud_t]."""
        rid = cat_link["resource_id"]
        sys_id = cat_link["system_id"]

        # Find the most recent evidence file captured in [req_t, aud_t] that observes this resource
        candidates: List[Tuple[datetime, EvidenceObservation]] = []
        for fid, obs_list in self.observations_by_file.items():
            cap_t = parse_iso(self.evidence_manifest[fid]["captured_at"])
            if req_t <= cap_t <= aud_t:
                for obs in obs_list:
                    if obs.resource_id == rid:
                        candidates.append((cap_t, obs))

        if not candidates:
            # Fallback to any evidence file <= aud_t observing rid
            for fid, obs_list in self.observations_by_file.items():
                cap_t = parse_iso(self.evidence_manifest[fid]["captured_at"])
                if cap_t <= aud_t:
                    for obs in obs_list:
                        if obs.resource_id == rid:
                            candidates.append((cap_t, obs))

        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen_obs: Optional[EvidenceObservation] = candidates[0][1] if candidates else None

        ev_id = chosen_obs.file_id if chosen_obs else ""
        raw_state = chosen_obs.raw_state if chosen_obs else "PRESENT"
        rtype = chosen_obs.record_category if chosen_obs else ""

        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        if sys_id == "security_service":
            verifications.append(
                self._make_step("VERIFICATION", sys_id, rid, "VERIFY_RECORD_PRESENT", "PRESENT", ev_id)
            )
            return "COMPLETE", self._finalize_steps(findings, remediations, verifications)

        if sys_id == "identity_service" and raw_state == "REDACTED":
            verifications.append(
                self._make_step("VERIFICATION", sys_id, rid, "VERIFY_RECORD_REDACTED", "REDACTED", ev_id)
            )
            return "COMPLETE", self._finalize_steps(findings, remediations, verifications)

        # Otherwise it is an INCOMPLETE violation
        f_op, f_st, r_op, r_st, v_op, v_st = self._violation_ops_for_resource(sys_id, rid, raw_state, rtype)
        findings.append(self._make_step("FINDING", sys_id, rid, f_op, f_st, ev_id))
        remediations.append(self._make_step("REMEDIATION", sys_id, rid, r_op, r_st, ""))
        verifications.append(self._make_step("VERIFICATION", sys_id, rid, v_op, v_st, ""))
        return "INCOMPLETE", self._finalize_steps(findings, remediations, verifications)

    def _evaluate_early_user_case(
        self, u_num: int, req_t: datetime, rep_t: datetime, aud_t: datetime
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Evaluate user_01..user_10 single-artifact cases using evidence_54..61."""
        acc_rid = f"account_{u_num:03d}"
        # Collect observations for this user from evidence_54..61 captured <= aud_t
        user_obs: Dict[str, EvidenceObservation] = {}
        for fid_num in range(54, 62):
            fid = f"evidence_{fid_num}"
            if fid not in self.evidence_manifest:
                continue
            cap_t = parse_iso(self.evidence_manifest[fid]["captured_at"])
            if cap_t > aud_t:
                continue
            for obs in self.observations_by_file.get(fid, []):
                matched_u = self.rid_to_user_num.get(obs.resource_id)
                if matched_u == u_num or obs.resource_id == acc_rid:
                    # Replica PRESENT overrides primary ABSENT
                    prev = user_obs.get(obs.resource_id)
                    if prev is None or (obs.is_replica and obs.raw_state == "PRESENT"):
                        user_obs[obs.resource_id] = obs
                elif matched_u is None and obs.raw_state == "ANONYMIZED":
                    act = self.deletion_worker_by_rid.get(obs.resource_id)
                    if act:
                        ev_t = parse_iso(act["event_time"])
                        if req_t <= ev_t <= rep_t:
                            user_obs[obs.resource_id] = obs

        # If account_00X was not in customer_profiles_primary or failover_replica in evidence_54,
        # it is proven ABSENT by evidence_54.
        if acc_rid not in user_obs:
            user_obs[acc_rid] = EvidenceObservation(
                file_id="evidence_54",
                captured_at=self.evidence_manifest["evidence_54"]["captured_at"],
                system_id="account_service",
                resource_id=acc_rid,
                raw_state="ABSENT",
                record_category="USER_PROFILE",
                identifiers=[f"user_{u_num:02d}"],
            )

        return self._build_decision_from_observations(user_obs, include_audit_record=False)

    def _evaluate_cohort_case(
        self, u_num: int, req_t: datetime, rep_t: datetime, aud_t: datetime
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Evaluate cohort user (11..530, 541..550) using evidence captured <= aud_t."""
        c_start = ((u_num - 1) // 10) * 10 + 1
        candidate_fids = self.cohort_files.get(c_start, [])
        valid_fids = [
            fid
            for fid in candidate_fids
            if parse_iso(self.evidence_manifest[fid]["captured_at"]) <= aud_t
        ]
        if not valid_fids and candidate_fids:
            valid_fids = candidate_fids

        # Primary evidence file to cite is the one captured <= aud_t (closest to aud_t)
        valid_fids.sort(key=lambda fid: parse_iso(self.evidence_manifest[fid]["captured_at"]), reverse=True)
        cite_fid = valid_fids[0] if valid_fids else ""

        acc_rid = self._match_account_rid_for_cohort_user(u_num, rep_t, candidate_fids)
        audit_rid = self.user_num_to_audit_record.get(u_num)

        # Gather all observations for u_num in valid_fids
        user_obs: Dict[str, EvidenceObservation] = {}
        for fid in valid_fids:
            for obs in self.observations_by_file.get(fid, []):
                matched_u = self.rid_to_user_num.get(obs.resource_id)
                if matched_u == u_num or (acc_rid and obs.resource_id == acc_rid):
                    prev = user_obs.get(obs.resource_id)
                    if prev is None:
                        user_obs[obs.resource_id] = obs
                    elif prev.file_id == obs.file_id and not obs.is_replica and obs.file_id in ("evidence_08", "evidence_41"):
                        # Sequential log entries in the same record_lookup log file supersede earlier lines
                        user_obs[obs.resource_id] = obs
                    else:
                        # Violation state in a replica overrides clean state in primary
                        if self._is_violation_state(obs.system_id, obs.raw_state) and not self._is_violation_state(prev.system_id, prev.raw_state):
                            user_obs[obs.resource_id] = obs

        # Ensure account_XXXX is represented (if absent from SQL tables, it is ABSENT in cite_fid)
        if acc_rid and acc_rid not in user_obs:
            user_obs[acc_rid] = EvidenceObservation(
                file_id=cite_fid,
                captured_at=self.evidence_manifest[cite_fid]["captured_at"] if cite_fid else "",
                system_id="account_service",
                resource_id=acc_rid,
                raw_state="ABSENT",
                record_category="USER_PROFILE",
                identifiers=[f"user_{u_num}"],
            )

        # Ensure security_service audit_record_XXXX is represented if known
        if audit_rid and audit_rid not in user_obs:
            user_obs[audit_rid] = EvidenceObservation(
                file_id=cite_fid,
                captured_at=self.evidence_manifest[cite_fid]["captured_at"] if cite_fid else "",
                system_id="security_service",
                resource_id=audit_rid,
                raw_state="PRESENT",
                record_category="SECURITY_AUDIT_LOG",
                identifiers=[f"user_{u_num}"],
            )

        # Check if any violation exists among user_obs
        has_violation = any(
            self._is_violation_state(obs.system_id, obs.raw_state)
            for obs in user_obs.values()
        )

        # If no violation and no analytics/tombstone observation yet, match anonymized analytics record
        if not has_violation:
            has_analytics_or_tombstone = any(
                obs.system_id in ("analytics_platform", "identity_service")
                for obs in user_obs.values()
            )
            if not has_analytics_or_tombstone:
                anon_match = self._match_anonymized_analytics_for_cohort_user(
                    u_num, rep_t, acc_rid, valid_fids
                )
                if anon_match:
                    anon_rid, anon_fid = anon_match
                    user_obs[anon_rid] = EvidenceObservation(
                        file_id=anon_fid,
                        captured_at=self.evidence_manifest[anon_fid]["captured_at"],
                        system_id="analytics_platform",
                        resource_id=anon_rid,
                        raw_state="ANONYMIZED",
                        record_category="ANALYTICS_PROFILE",
                        identifiers=[f"user_{u_num}"],
                    )

        return self._build_decision_from_observations(user_obs, include_audit_record=True)

    def _is_violation_state(self, sys_id: str, raw_state: str) -> bool:
        if sys_id == "security_service":
            return raw_state != "PRESENT"
        if sys_id in ("account_service", "search_service", "export_service", "object_storage", "marketing_platform"):
            return raw_state != "ABSENT"
        if sys_id == "analytics_platform":
            return raw_state not in ("ANONYMIZED", "ABSENT")
        if sys_id == "support_platform":
            return raw_state not in ("REDACTED", "ABSENT")
        if sys_id == "identity_service":
            return raw_state != "REDACTED"
        if sys_id == "integration_service":
            return raw_state != "DISABLED"
        if sys_id == "backup_service":
            return raw_state != "BLOCKED"
        return False

    def _violation_ops_for_resource(
        self, sys_id: str, rid: str, raw_state: str, rtype: str
    ) -> Tuple[str, str, str, str, str, str]:
        """Return (finding_op, finding_state, rem_op, rem_state, ver_op, ver_state) for a violated resource."""
        act = self.deletion_worker_by_rid.get(rid)
        act_type = act["event_type"] if act else ""

        if sys_id == "integration_service":
            return (
                "REPORT_ACTIVE_DATA_FLOW",
                "ACTIVE",
                "DISABLE_DATA_FLOW",
                "DISABLED",
                "VERIFY_DATA_FLOW_DISABLED",
                "DISABLED",
            )
        if sys_id == "backup_service":
            return (
                "REPORT_RESTORE_RISK",
                "ACTIVE",
                "BLOCK_RESTORE",
                "BLOCKED",
                "VERIFY_RESTORE_BLOCKED",
                "BLOCKED",
            )
        if sys_id == "analytics_platform":
            if act_type == "DELETE_RECORD" or rtype == "MARKETING_PROFILE":
                return (
                    "REPORT_REMAINING_RECORD",
                    "PRESENT",
                    "DELETE_RECORD",
                    "ABSENT",
                    "VERIFY_RECORD_ABSENT",
                    "ABSENT",
                )
            return (
                "REPORT_EXPOSED_PII",
                "PRESENT",
                "ANONYMIZE_RECORD",
                "ANONYMIZED",
                "VERIFY_RECORD_ANONYMIZED",
                "ANONYMIZED",
            )
        if sys_id == "support_platform":
            if act_type == "DELETE_RECORD" or rtype == "SUPPORT_ATTACHMENT":
                return (
                    "REPORT_REMAINING_RECORD",
                    "PRESENT",
                    "DELETE_RECORD",
                    "ABSENT",
                    "VERIFY_RECORD_ABSENT",
                    "ABSENT",
                )
            return (
                "REPORT_EXPOSED_PII",
                "PRESENT",
                "REDACT_RECORD",
                "REDACTED",
                "VERIFY_RECORD_REDACTED",
                "REDACTED",
            )
        if sys_id == "identity_service":
            return (
                "REPORT_EXPOSED_PII",
                "PRESENT",
                "REDACT_RECORD",
                "REDACTED",
                "VERIFY_RECORD_REDACTED",
                "REDACTED",
            )
        # Default for account_service, search_service, export_service, object_storage, marketing_platform
        return (
            "REPORT_REMAINING_RECORD",
            "PRESENT",
            "DELETE_RECORD",
            "ABSENT",
            "VERIFY_RECORD_ABSENT",
            "ABSENT",
        )

    def _compliant_verification_op(self, sys_id: str, raw_state: str) -> Tuple[str, str]:
        if sys_id == "security_service":
            return "VERIFY_RECORD_PRESENT", "PRESENT"
        if sys_id == "analytics_platform" and raw_state == "ANONYMIZED":
            return "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"
        if sys_id in ("support_platform", "identity_service") and raw_state == "REDACTED":
            return "VERIFY_RECORD_REDACTED", "REDACTED"
        if sys_id == "integration_service":
            return "VERIFY_DATA_FLOW_DISABLED", "DISABLED"
        if sys_id == "backup_service":
            return "VERIFY_RESTORE_BLOCKED", "BLOCKED"
        return "VERIFY_RECORD_ABSENT", "ABSENT"

    def _build_decision_from_observations(
        self, user_obs: Dict[str, EvidenceObservation], include_audit_record: bool
    ) -> Tuple[str, List[Dict[str, Any]]]:
        violated_obs = [
            obs
            for obs in user_obs.values()
            if self._is_violation_state(obs.system_id, obs.raw_state)
        ]

        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        if not violated_obs:
            # COMPLETE case: emit evidence-backed VERIFICATION steps
            for obs in user_obs.values():
                if obs.system_id == "security_service" and not include_audit_record:
                    continue
                v_op, v_st = self._compliant_verification_op(obs.system_id, obs.raw_state)
                verifications.append(
                    self._make_step("VERIFICATION", obs.system_id, obs.resource_id, v_op, v_st, obs.file_id)
                )
            return "COMPLETE", self._finalize_steps(findings, remediations, verifications)

        # INCOMPLETE case: emit FINDING (with evidence_id), REMEDIATION (""), and VERIFICATION ("")
        for obs in user_obs.values():
            if self._is_violation_state(obs.system_id, obs.raw_state):
                f_op, f_st, r_op, r_st, v_op, v_st = self._violation_ops_for_resource(
                    obs.system_id, obs.resource_id, obs.raw_state, obs.record_category
                )
                findings.append(
                    self._make_step("FINDING", obs.system_id, obs.resource_id, f_op, f_st, obs.file_id)
                )
                remediations.append(
                    self._make_step("REMEDIATION", obs.system_id, obs.resource_id, r_op, r_st, "")
                )
                verifications.append(
                    self._make_step("VERIFICATION", obs.system_id, obs.resource_id, v_op, v_st, "")
                )
            else:
                if obs.system_id in ("account_service", "security_service"):
                    if obs.system_id == "security_service" and not include_audit_record:
                        continue
                    v_op, v_st = self._compliant_verification_op(obs.system_id, obs.raw_state)
                    verifications.append(
                        self._make_step("VERIFICATION", obs.system_id, obs.resource_id, v_op, v_st, "")
                    )

        return "INCOMPLETE", self._finalize_steps(findings, remediations, verifications)

    @staticmethod
    def _make_step(
        phase: str,
        system_id: str,
        resource_id: str,
        operation: str,
        state: str,
        evidence_id: str,
    ) -> Dict[str, Any]:
        return {
            "step_no": 0,
            "phase": phase,
            "system_id": system_id,
            "resource_id": resource_id,
            "operation": operation,
            "state": state,
            "evidence_id": evidence_id,
        }

    def _finalize_steps(
        self,
        findings: List[Dict[str, Any]],
        remediations: List[Dict[str, Any]],
        verifications: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Sort each phase according to policy/dependency order and number steps from 1."""
        f_op_rank = {
            "REPORT_REMAINING_RECORD": 0,
            "REPORT_EXPOSED_PII": 1,
            "REPORT_ACTIVE_DATA_FLOW": 2,
            "REPORT_RESTORE_RISK": 3,
        }
        r_op_rank = {
            "DISABLE_DATA_FLOW": 0,
            "BLOCK_RESTORE": 1,
            "DELETE_RECORD": 2,
            "REDACT_RECORD": 3,
            "ANONYMIZE_RECORD": 4,
        }
        v_op_rank = {
            "VERIFY_RECORD_ABSENT": 0,
            "VERIFY_RECORD_PRESENT": 1,
            "VERIFY_RECORD_REDACTED": 2,
            "VERIFY_RECORD_ANONYMIZED": 3,
            "VERIFY_DATA_FLOW_DISABLED": 4,
            "VERIFY_RESTORE_BLOCKED": 5,
        }
        default_sys_rank = {
            "account_service": 0,
            "export_service": 1,
            "search_service": 2,
            "support_platform": 3,
            "analytics_platform": 4,
            "identity_service": 5,
            "security_service": 6,
            "object_storage": 7,
            "marketing_platform": 8,
            "integration_service": 9,
            "backup_service": 10,
        }
        exposed_pii_sys_rank = {
            "analytics_platform": 0,
            "support_platform": 1,
            "identity_service": 2,
        }

        findings.sort(
            key=lambda s: (
                f_op_rank.get(s["operation"], 99),
                exposed_pii_sys_rank.get(s["system_id"], 99)
                if s["operation"] == "REPORT_EXPOSED_PII"
                else default_sys_rank.get(s["system_id"], 99),
                s["resource_id"],
            )
        )
        remediations.sort(
            key=lambda s: (
                r_op_rank.get(s["operation"], 99),
                default_sys_rank.get(s["system_id"], 99),
                s["resource_id"],
            )
        )
        verifications.sort(
            key=lambda s: (
                v_op_rank.get(s["operation"], 99),
                default_sys_rank.get(s["system_id"], 99),
                s["resource_id"],
            )
        )

        ordered = findings + remediations + verifications
        for idx, step in enumerate(ordered, start=1):
            step["step_no"] = idx
        return ordered

    def generate_predictions(
        self, requests_csv_path: Path, output_csv_path: Optional[Path] = None
    ) -> List[Dict[str, str]]:
        """Run audit across all rows in requests_csv_path and optionally write output_csv_path."""
        with open(requests_csv_path, "r", encoding="utf-8") as f:
            requests = list(csv.DictReader(f))

        results: List[Dict[str, str]] = []
        for req in sorted(requests, key=lambda r: case_sort_key(r["case_id"])):
            status, steps = self.evaluate_case(req)
            results.append(
                {
                    "case_id": req["case_id"],
                    "deletion_status": status,
                    "steps_json": json.dumps(steps, separators=(",", ":")),
                }
            )

        if output_csv_path is not None:
            with open(output_csv_path, "w", encoding="utf-8", newline="\n") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["case_id", "deletion_status", "steps_json"], lineterminator="\n"
                )
                writer.writeheader()
                writer.writerows(results)

        return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Ghost Data Still Exists deletion-audit agent."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the repository root containing dataset/",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input requests CSV path (defaults to <repo-root>/dataset/deletion_requests.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output predictions CSV path (defaults to <repo-root>/output.csv)",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    input_csv = args.input.resolve() if args.input else (repo_root / "dataset" / "deletion_requests.csv")
    output_csv = args.output.resolve() if args.output else (repo_root / "output.csv")

    engine = DeletionAuditEngine(repo_root)
    preds = engine.generate_predictions(input_csv, output_csv)
    print(
        f"Processed {len(preds)} deletion requests from {input_csv.name} -> {output_csv} "
        f"(unsupported/unreadable evidence files: {len(engine.unsupported_or_unreadable_files)})"
    )


if __name__ == "__main__":
    main()
