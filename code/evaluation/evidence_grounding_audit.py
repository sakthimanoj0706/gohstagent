"""Independent evidence-grounding audit for output.csv (and sample predictions).

For every step that carries an evidence_id, this script opens the cited source
(not just the manifest) and checks:
  G1  the evidence_id exists (evidence_files.csv file_id or system_activity.csv activity_id)
  G2  the evidence was captured / occurred at or before the case's audit_at
  G3  the cited source text actually mentions the step's resource_id
  G4  (files) the source mentions at least one current/historical identifier of the subject
      or the resource is linked to the subject elsewhere in the same file
PNG files cannot be checked for G3/G4 because no OCR engine is available; they are
reported as NOT_VERIFIABLE rather than passed.

Usage:
  python code/evaluation/evidence_grounding_audit.py [--requests CSV] [--predictions CSV]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET = REPO_ROOT / "dataset"

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".png":
        return None
    if ext == ".pdf":
        if fitz is None:
            return None
        with fitz.open(str(path)) as doc:
            return "\n".join(p.get_text("text") for p in doc)
    return path.read_text(encoding="utf-8", errors="replace").replace('\\"', '"')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", default=str(DATASET / "deletion_requests.csv"))
    ap.add_argument("--predictions", default=str(REPO_ROOT / "output.csv"))
    ap.add_argument("--report", default=str(REPO_ROOT / "code" / "evaluation" / "evidence_grounding_report.md"))
    args = ap.parse_args()

    manifest = {r["file_id"]: r for r in csv.DictReader(open(DATASET / "evidence_files.csv", encoding="utf-8"))}
    activities = {r["activity_id"]: r for r in csv.DictReader(open(DATASET / "system_activity.csv", encoding="utf-8"))}
    requests = {r["case_id"]: r for r in csv.DictReader(open(args.requests, encoding="utf-8"))}
    preds = list(csv.DictReader(open(args.predictions, encoding="utf-8")))

    # identity sets per user (current + historical)
    ident_to_user = {}
    user_idents = defaultdict(set)
    for r in csv.DictReader(open(DATASET / "user_identities.csv", encoding="utf-8")):
        u = r["user_id"]
        for c in ("user_id", "email", "phone", "email_hash", "name"):
            v = (r.get(c) or "").strip().lower()
            if v:
                ident_to_user[v] = u
                user_idents[u].add(v)
    for r in csv.DictReader(open(DATASET / "user_audit_log.csv", encoding="utf-8")):
        u = r["user_id"]
        for c in ("old_value", "new_value"):
            v = (r.get(c) or "").strip().lower()
            if v:
                ident_to_user[v] = u
                user_idents[u].add(v)

    # resource aliases from system_activity.csv
    resource_aliases = {}
    for act in activities.values():
        m_al = re.search(r"linked\s+([^\s(]+)\s*\(([^)]+)\)", act.get("details", ""))
        if m_al:
            canon = m_al.group(1).strip()
            al = m_al.group(2).strip()
            if al and al != canon:
                resource_aliases[al] = canon

    text_cache: dict[str, str | None] = {}

    def text_of(fid: str):
        if fid not in text_cache:
            p = DATASET / manifest[fid]["file_path"]
            text_cache[fid] = load_text(p) if p.exists() else None
        return text_cache[fid]

    counts = Counter()
    issues = defaultdict(list)  # category -> [(case, step summary)]
    for row in preds:
        cid, status = row["case_id"], row["deletion_status"]
        steps = json.loads(row["steps_json"])
        req = requests.get(cid)
        if req is None:
            continue
        aud = parse_iso(req["audit_at"])
        subj_user = ident_to_user.get(req["email"].strip().lower())
        idents = {i for i in user_idents.get(subj_user, set())}
        for s in steps:
            ev = s["evidence_id"]
            if not ev:
                continue
            counts["evidence_steps"] += 1
            tag = f"{cid} step {s['step_no']} {s['phase']} {s['operation']} {s['resource_id']} <- {ev}"
            if ev in manifest:
                counts["file_refs"] += 1
                cap = parse_iso(manifest[ev]["captured_at"])
                if cap > aud:
                    issues["G2_post_audit"].append(tag)
                t = text_of(ev)
                if t is None:
                    counts["not_verifiable_png"] += 1
                    issues["NOT_VERIFIABLE_image_no_ocr"].append(tag)
                    continue
                low = t.lower()
                aliases = [s["resource_id"].lower()] + [al.lower() for al, c in resource_aliases.items() if c == s["resource_id"]]
                rid_present = any(re.search(r"(?<![a-z0-9_])" + re.escape(al) + r"(?![0-9])", low) is not None for al in aliases)
                if not rid_present:
                    if s["operation"] == "VERIFY_RECORD_ABSENT" or s["state"] == "ABSENT":
                        # absence claims: resource legitimately missing from snapshot
                        issues["G3_absence_inferred_from_omission"].append(tag)
                        counts["absence_by_omission"] += 1
                    else:
                        issues["G3_resource_not_in_source"].append(tag)
                        counts["rid_missing"] += 1
                else:
                    counts["rid_found"] += 1
                subj_present = any(i in low for i in idents if len(i) >= 5) or (subj_user and re.search(r"\b" + re.escape(subj_user) + r"\b", low))
                if not subj_present:
                    issues["G4_subject_identifier_not_in_source"].append(tag)
            elif ev in activities:
                counts["activity_refs"] += 1
                a = activities[ev]
                if parse_iso(a["event_time"]) > aud:
                    issues["G2_post_audit"].append(tag)
                if a["resource_id"] != s["resource_id"]:
                    issues["G3_resource_not_in_source"].append(tag)
            else:
                issues["G1_unknown_evidence_id"].append(tag)

    lines = ["# Evidence Grounding Audit", "",
             f"- Predictions: `{Path(args.predictions).name}`  Requests: `{Path(args.requests).name}`",
             f"- Evidence-bearing steps checked: **{counts['evidence_steps']}** "
             f"(file refs {counts['file_refs']}, activity refs {counts['activity_refs']})",
             f"- Resource ID found in cited source text: **{counts['rid_found']}**",
             f"- ABSENT claims supported only by omission from the cited snapshot: **{counts['absence_by_omission']}**",
             f"- Non-absence claims whose resource ID is NOT in the cited source: **{counts['rid_missing']}**",
             f"- Image citations not machine-verifiable (no OCR available): **{counts['not_verifiable_png']}**", "",
             "| Category | Count |", "| :--- | ---: |"]
    for k in sorted(issues):
        lines.append(f"| `{k}` | {len(issues[k])} |")
    lines.append("")
    for k in sorted(issues):
        lines.append(f"## {k} ({len(issues[k])})")
        for t in issues[k][:40]:
            lines.append(f"- {t}")
        if len(issues[k]) > 40:
            lines.append(f"- ... {len(issues[k]) - 40} more")
        lines.append("")
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:14 + len(issues)]))
    print(f"Report written to {args.report}")
    hard_fail = len(issues["G1_unknown_evidence_id"]) + len(issues["G2_post_audit"]) + len(issues["G3_resource_not_in_source"])
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
