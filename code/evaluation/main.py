#!/usr/bin/env python3
"""
Evaluation Harness for Ghost Data Still Exists (HackerRank Orchestrate October 2026)

Compares predictions from code/main.py against dataset/sample_output.csv, reporting:
- Case-level deletion_status accuracy
- Step-level and field-level accuracy
- Sequence-level exact match accuracy
- Detailed per-case mismatch diagnostics
- Results on 4 additional custom evaluation cases testing edge conditions
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

from main import DeletionAuditEngine  # noqa: E402


STEP_FIELDS = (
    "step_no",
    "phase",
    "system_id",
    "resource_id",
    "operation",
    "state",
    "evidence_id",
)


def evaluate_predictions(
    predictions: List[Dict[str, str]],
    gold_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Compare predicted rows against golden rows and compute comprehensive metrics."""
    pred_by_cid = {r["case_id"]: r for r in predictions}
    gold_by_cid = {r["case_id"]: r for r in gold_rows}

    total_cases = len(gold_by_cid)
    status_correct = 0
    sequence_exact = 0

    total_gold_steps = 0
    total_pred_steps = 0
    matched_steps_by_key = 0
    matched_steps_exact = 0

    field_matches = {f: 0 for f in STEP_FIELDS}
    field_totals = 0

    mismatches: List[Dict[str, Any]] = []

    for cid in sorted(gold_by_cid.keys()):
        g_row = gold_by_cid[cid]
        p_row = pred_by_cid.get(cid, {"deletion_status": "MISSING", "steps_json": "[]"})

        g_status = g_row["deletion_status"]
        p_status = p_row["deletion_status"]
        if g_status == p_status:
            status_correct += 1

        g_steps: List[Dict[str, Any]] = json.loads(g_row["steps_json"])
        p_steps: List[Dict[str, Any]] = json.loads(p_row["steps_json"])

        total_gold_steps += len(g_steps)
        total_pred_steps += len(p_steps)

        if g_status == p_status and g_steps == p_steps:
            sequence_exact += 1
        else:
            mismatches.append(
                {
                    "case_id": cid,
                    "gold_status": g_status,
                    "pred_status": p_status,
                    "gold_steps": g_steps,
                    "pred_steps": p_steps,
                }
            )

        # Align steps by (phase, system_id, resource_id) for step/field accuracy
        p_by_key = {(s["phase"], s["system_id"], s["resource_id"]): s for s in p_steps}
        for gs in g_steps:
            field_totals += 1
            key = (gs["phase"], gs["system_id"], gs["resource_id"])
            ps = p_by_key.get(key)
            if ps is not None:
                matched_steps_by_key += 1
                if all(gs.get(f) == ps.get(f) for f in STEP_FIELDS):
                    matched_steps_exact += 1
                for f in STEP_FIELDS:
                    if gs.get(f) == ps.get(f):
                        field_matches[f] += 1

    return {
        "total_cases": total_cases,
        "status_correct": status_correct,
        "status_accuracy": status_correct / total_cases if total_cases else 0.0,
        "sequence_exact": sequence_exact,
        "sequence_accuracy": sequence_exact / total_cases if total_cases else 0.0,
        "total_gold_steps": total_gold_steps,
        "total_pred_steps": total_pred_steps,
        "matched_steps_by_key": matched_steps_by_key,
        "matched_steps_exact": matched_steps_exact,
        "step_recall_by_key": matched_steps_by_key / total_gold_steps if total_gold_steps else 0.0,
        "step_exact_accuracy": matched_steps_exact / total_gold_steps if total_gold_steps else 0.0,
        " step_precision_by_key": matched_steps_by_key / total_pred_steps if total_pred_steps else 0.0,
        "field_accuracies": {
            f: (field_matches[f] / field_totals if field_totals else 0.0)
            for f in STEP_FIELDS
        },
        "field_matches": field_matches,
        "field_totals": field_totals,
        "mismatches": mismatches,
    }


def run_custom_evaluation_cases(engine: DeletionAuditEngine) -> List[Dict[str, Any]]:
    """Run 4 participant-created evaluation cases covering key policy and temporal edge conditions."""
    custom_cases: List[Tuple[Dict[str, str], str, List[Dict[str, Any]], str]] = [
        (
            {
                "case_id": "custom_case_01",
                "email": "haruka-kato@gmail.com",
                "requested_at": "2026-09-25T10:00:00Z",
                "reported_status": "COMPLETE",
                "reported_at": "2026-09-26T10:00:00Z",
                "audit_at": "2026-10-02T12:00:00Z",
                "request_text": "Please unsubscribe me from promotional marketing emails, but keep my account active and do not delete my profile.",
            },
            "NOT_APPLICABLE",
            [],
            "Non-deletion marketing opt-out request with misleading reported_status=COMPLETE",
        ),
        (
            {
                "case_id": "custom_case_02",
                "email": "leila.haddad@yahoo.com",
                "requested_at": "2026-08-26T09:10:00Z",
                "reported_status": "COMPLETE",
                "reported_at": "2026-08-28T09:03:00Z",
                "audit_at": "2026-09-02T23:30:00Z",
                "request_text": "Please delete my account and erase all personal data associated with my profile.",
            },
            "INCOMPLETE",
            [
                {
                    "step_no": 1,
                    "phase": "FINDING",
                    "system_id": "account_service",
                    "resource_id": "account_005",
                    "operation": "REPORT_REMAINING_RECORD",
                    "state": "PRESENT",
                    "evidence_id": "evidence_54",
                },
                {
                    "step_no": 2,
                    "phase": "REMEDIATION",
                    "system_id": "account_service",
                    "resource_id": "account_005",
                    "operation": "DELETE_RECORD",
                    "state": "ABSENT",
                    "evidence_id": "",
                },
                {
                    "step_no": 3,
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": "account_005",
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": "",
                },
            ],
            "Failover replica drift detection (user_05 absent from primary but ACTIVE in customer_profiles_failover_replica in evidence_54)",
        ),
        (
            {
                "case_id": "custom_case_03",
                "email": "areed1433@gmail.com",
                "requested_at": "2026-04-25T10:00:00Z",
                "reported_status": "COMPLETE",
                "reported_at": "2026-04-28T10:00:00Z",
                "audit_at": "2026-04-30T11:00:00Z",
                "request_text": "Por favor eliminen mi cuenta y todos mis datos personales.",
            },
            "INCOMPLETE",
            [
                {
                    "step_no": 1,
                    "phase": "FINDING",
                    "system_id": "backup_service",
                    "resource_id": "backup_9287",
                    "operation": "REPORT_RESTORE_RISK",
                    "state": "ACTIVE",
                    "evidence_id": "evidence_32",
                },
                {
                    "step_no": 2,
                    "phase": "REMEDIATION",
                    "system_id": "backup_service",
                    "resource_id": "backup_9287",
                    "operation": "BLOCK_RESTORE",
                    "state": "BLOCKED",
                    "evidence_id": "",
                },
                {
                    "step_no": 3,
                    "phase": "VERIFICATION",
                    "system_id": "backup_service",
                    "resource_id": "backup_9287",
                    "operation": "VERIFY_RESTORE_BLOCKED",
                    "state": "BLOCKED",
                    "evidence_id": "",
                },
            ],
            "Multilingual (Spanish) deletion request with visual PNG evidence (evidence_32) and strict temporal cutoff excluding later September logs",
        ),
        (
            {
                "case_id": "custom_case_04",
                "email": "a.eze08@gmail.com",
                "requested_at": "2026-09-03T12:00:00Z",
                "reported_status": "COMPLETE",
                "reported_at": "2026-09-06T12:00:00Z",
                "audit_at": "2026-09-16T12:00:00Z",
                "request_text": "Please close my account and delete my personal data under applicable privacy regulations.",
            },
            "COMPLETE",
            [
                {
                    "step_no": 1,
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": "account_4857",
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": "evidence_51",
                },
                {
                    "step_no": 2,
                    "phase": "VERIFICATION",
                    "system_id": "security_service",
                    "resource_id": "audit_record_6909",
                    "operation": "VERIFY_RECORD_PRESENT",
                    "state": "PRESENT",
                    "evidence_id": "evidence_51",
                },
                {
                    "step_no": 3,
                    "phase": "VERIFICATION",
                    "system_id": "identity_service",
                    "resource_id": "tombstone_440",
                    "operation": "VERIFY_RECORD_REDACTED",
                    "state": "REDACTED",
                    "evidence_id": "evidence_51",
                },
            ],
            "Compliant account tombstone (tombstone_440) + retained security audit log + temporal exclusion of post-audit failover replica (evidence_52 captured 2026-09-20)",
        ),
    ]

    results = []
    for req, exp_status, exp_steps, description in custom_cases:
        pred_status, pred_steps = engine.evaluate_case(req)
        passed = (pred_status == exp_status) and (pred_steps == exp_steps)
        results.append(
            {
                "case_id": req["case_id"],
                "description": description,
                "passed": passed,
                "expected_status": exp_status,
                "predicted_status": pred_status,
                "expected_steps": exp_steps,
                "predicted_steps": pred_steps,
            }
        )
    return results


def main() -> None:
    sample_req_path = REPO_ROOT / "dataset" / "sample_deletion_requests.csv"
    sample_out_path = REPO_ROOT / "dataset" / "sample_output.csv"

    engine = DeletionAuditEngine(REPO_ROOT)
    preds = engine.generate_predictions(sample_req_path)
    with open(sample_out_path, "r", encoding="utf-8") as f:
        gold = list(csv.DictReader(f))

    metrics = evaluate_predictions(preds, gold)

    print("=" * 72)
    print("GHOST DATA STILL EXISTS — SAMPLE EVALUATION REPORT")
    print("=" * 72)
    print(
        f"Case-Level Status Accuracy : {metrics['status_correct']}/{metrics['total_cases']} "
        f"({metrics['status_accuracy']*100:.2f}%)"
    )
    print(
        f"Sequence Exact Accuracy    : {metrics['sequence_exact']}/{metrics['total_cases']} "
        f"({metrics['sequence_accuracy']*100:.2f}%)"
    )
    print(
        f"Step Recall (by resource)  : {metrics['matched_steps_by_key']}/{metrics['total_gold_steps']} "
        f"({metrics['step_recall_by_key']*100:.2f}%)"
    )
    print(
        f"Step Exact Match Accuracy  : {metrics['matched_steps_exact']}/{metrics['total_gold_steps']} "
        f"({metrics['step_exact_accuracy']*100:.2f}%)"
    )
    print("\nField-Level Accuracies (across all 186 ground-truth steps):")
    for f_name, f_acc in metrics["field_accuracies"].items():
        print(
            f"  - {f_name:14s}: {metrics['field_matches'][f_name]}/{metrics['field_totals']} ({f_acc*100:.2f}%)"
        )

    print(f"\nIndividual Mismatches ({len(metrics['mismatches'])}):")
    for m in metrics["mismatches"]:
        print(
            f"  * {m['case_id']}: status gold={m['gold_status']} pred={m['pred_status']} | "
            f"steps gold={len(m['gold_steps'])} pred={len(m['pred_steps'])}"
        )
        g_set = {(s["phase"], s["system_id"], s["resource_id"], s["operation"], s["evidence_id"]) for s in m["gold_steps"]}
        p_set = {(s["phase"], s["system_id"], s["resource_id"], s["operation"], s["evidence_id"]) for s in m["pred_steps"]}
        if g_set - p_set:
            print(f"    Missing in pred : {sorted(g_set - p_set)}")
        if p_set - g_set:
            print(f"    Extra in pred   : {sorted(p_set - g_set)}")

    custom_results = run_custom_evaluation_cases(engine)
    passed_custom = sum(1 for r in custom_results if r["passed"])
    print("\n" + "=" * 72)
    print(f"CUSTOM EVALUATION CASES: {passed_custom}/{len(custom_results)} PASSED")
    print("=" * 72)
    for r in custom_results:
        status_label = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status_label}] {r['case_id']}: {r['description']}")
        if not r["passed"]:
            print(f"    Expected: {r['expected_status']} {r['expected_steps']}")
            print(f"    Actual  : {r['predicted_status']} {r['predicted_steps']}")


if __name__ == "__main__":
    main()
