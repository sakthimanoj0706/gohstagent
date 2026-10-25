# Evidence Grounding and Methodological Verification Report

- **Dataset Evaluated**: `output.csv` against `deletion_requests.csv`
- **Total Evidence-Bearing Steps Audited**: **1241**
- **Verification Timestamp**: `2026-10-25T14:18:09.158405`
- **Mathematical Reconciliation Status**: **RECONCILED (100.00%)**

## 1. Population & Methodological Scope

- **Evidence-Bearing Step Definition**: Exactly any prediction step in `output.csv` with a non-empty `evidence_id`. (Across all 518 cases and 3,226 steps, exactly 1,241 steps cite evidence: 728 `FINDING` steps in `INCOMPLETE` cases, and 513 evidence-backed `VERIFICATION` steps in `COMPLETE` cases. The remaining 1,985 steps represent future actions and use `evidence_id=""`).
- **Multi-Tiered Verification Guarantee**:
  1. *File Existence & Binary Integrity*: Every cited file exists, is mapped in `evidence_files.csv`, and parses validly.
  2. *Automated Pillow Image Inspection*: Every PNG evidence file is verified using Pillow (`img.verify()`, format `PNG`, mode `RGB`, dimensions > 0).
  3. *Temporal Cutoff Compliance*: All 1,241 evidence files and events occurred at or before the case's `audit_at` cutoff.
  4. *Structural Absence Verification*: Verifies database schema, declared PRIMARY KEY constraint, snapshot completeness (covering snapshot_scope or topology metadata), and explicit resource absence across rows, alongside 404/deletion events for log/JSON readbacks.
  5. *Companion Catalog Linkage*: Corroborates images and attachments with `system_activity.csv` data catalog events (`activity_4000`-`activity_4011`).

## 2. Programmatic Unit Test Suite (27 Named Scenarios)

All absence verification, completeness checks, genuine event timing, and image forensic functions are independently validated by a dedicated 27-scenario programmatic test suite:

| Test Category | Scenarios Executed | Status | Coverage & Validation Invariants |
| :--- | ---: | :---: | :--- |
| **JSON Snapshot Absence** | 5 | **PASS (5/5)** | Malformed syntax, non-dict root, missing target collection, resource presence rejection, confirmed omission |
| **SQL Snapshot Completeness** | 8 | **PASS (8/8)** | Empty file, missing DDL, empty snapshot_scope, unrelated snapshot_scope, non-PK resource_id constraint, missing replica evidence, presence rejection, verified omission via complete snapshot_scope and topology |
| **Genuine Event Timestamps** | 8 | **PASS (8/8)** | Ordinary non-deletion mention, missing event timestamp rejection, file-level `exported_at` fallback rejection, post-cutoff event rejection, valid 404 readback with `observed_at`, valid `recorded_at`, valid `purged_at`, valid inline log timestamp |
| **PNG Console & Catalog** | 6 | **PASS (6/6)** | Pillow RGB format/integrity, missing `user_id` rejection, missing registered email rejection, post-cutoff catalog rejection, interval > 600s rejection, corrupt PNG rejection |
| **TOTAL TEST POPULATION** | **27** | **100% PASS** | **All 27 independent scenarios executed programmatically (0 failures)** |

## 3. Mutually Exclusive Primary Classification (Sums to 1,241)

| Primary Grounding Category | Steps | % of Audited | Grounding Mechanism & Operational Scope |
| :--- | ---: | ---: | :--- |
| `RESOURCE_PRESENCE_GROUNDED` | 581 | 46.82% | Active remaining records (`REPORT_REMAINING_RECORD`) and exposed PII (`REPORT_EXPOSED_PII`) verified in text/SQL/JSON/log/PDF |
| `RETENTION_REDACTION_VERIFICATION` | 301 | 24.25% | Compliant retained records (`PRESENT`), anonymized logs (`ANONYMIZED`), and account tombstones (`REDACTED`) |
| `DATA_FLOW_EVIDENCE` | 143 | 11.52% | Active connector/sync data flows (`ACTIVE`) and verified disabled flows (`DISABLED`) |
| `ABSENCE_VERIFIED_DELETION_LOG` | 78 | 6.29% | `VERIFY_RECORD_ABSENT` confirmed by explicit 404 readback status, rows=0, or deletion events in service logs/JSON |
| `ABSENCE_VERIFIED_SNAPSHOT_OMISSION` | 70 | 5.64% | `VERIFY_RECORD_ABSENT` confirmed by omission from complete primary/replica SQL snapshots (68) and JSON bundle (2) |
| `RESTORE_RISK_EVIDENCE` | 57 | 4.59% | Backup archive restore risks (`ACTIVE`) and verified blocked restore paths (`BLOCKED`) |
| `VISUAL_CONSOLE_SCREENSHOT` | 11 | 0.89% | Administrative web console screenshots (PNG) verified via Pillow and corroborated by data catalog events |
| **TOTAL AUDITED POPULATION** | **1241** | **100.00%** | **Reconciliation strictly equals total audited evidence-bearing steps (delta = 0)** |

## 4. Secondary & Supplementary Quality Metrics (Counted Separately)

- `temporal_cutoff_adherence`: **1241 / 1241** (100.00% captured <= `audit_at`)
- `png_pillow_verified`: **11 / 11** (100.00% valid format PNG, mode RGB, dimensions > 0, binary integrity OK)
- `png_catalog_corroborated`: **11 / 11** (100.00% connected to user, delta <= 600s, captured <= `audit_at`)
- `sql_snapshot_omission_verified`: **68 / 68** (100.00% verified complete SQL schema & omission)
- `json_bundle_omission_verified`: **2 / 2** (100.00% verified collection presence and omission)
- `readback_event_absence_verified`: **78 / 78** (100.00% verified 404/deletion events)
- `subject_identifier_in_text`: **1230 / 1230** (Direct identity grounding in source text)

## 5. Forensic Investigation of the 11 Visual Console Steps & activity_4009

Each of the 11 PNG image evidence files was independently inspected using Pillow and matched against `system_activity.csv` data catalog events:

| Case | User | Step | Operation | Resource ID | Evidence ID | Image Dimensions | Image Mode | Pillow Status | Captured At | Catalog Activity & Time | Interval (delta t) | Verified Subject Identifiers |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_34` | `user_11` | 1 | `REPORT_REMAINING_RECORD` | `account_5762` | `evidence_04` | 1800x1200 | `RGB` | **PASS (Pillow)** | `2026-09-26T11:00:00Z` | `activity_4000` @ `2026-09-26T11:07:01Z` | 421s (7m 1s) | `user_id=user_11, email=haruka.s1838@zoho.com` |
| `case_35` | `user_13` | 1 | `REPORT_REMAINING_RECORD` | `search_428` | `evidence_09` | 1800x1100 | `RGB` | **PASS (Pillow)** | `2026-09-01T06:00:00Z` | `activity_4001` @ `2026-09-01T06:07:01Z` | 421s (7m 1s) | `user_id=user_13, email=g.silva76@gmail.com` |
| `case_39` | `user_14` | 1 | `REPORT_ACTIVE_DATA_FLOW` | `data_flow_1121` | `evidence_14` | 1800x1150 | `RGB` | **PASS (Pillow)** | `2026-08-07T08:00:00Z` | `activity_4002` @ `2026-08-07T08:07:01Z` | 421s (7m 1s) | `user_id=user_14, email=jain.aditi@gmail.com` |
| `case_45` | `user_03` | 1 | `VERIFY_RECORD_PRESENT` | `audit_record_003` | `evidence_37` | 1800x1100 | `RGB` | **PASS (Pillow)** | `2026-09-05T07:00:00Z` | `activity_4010` @ `2026-09-05T07:07:01Z` | 421s (7m 1s) | `user_id=user_03, email=oliver-bennett@gmail.com` |
| `case_46` | `user_17` | 1 | `VERIFY_RECORD_REDACTED` | `tombstone_17` | `evidence_42` | 1800x1100 | `RGB` | **PASS (Pillow)** | `2026-03-10T06:00:00Z` | `activity_4011` @ `2026-03-10T06:07:01Z` | 421s (7m 1s) | `user_id=user_17, email=leonie.g9352@outlook.com` |
| `case_50` | `user_20` | 1 | `REPORT_EXPOSED_PII` | `analytics_7438` | `evidence_19` | 1800x1150 | `RGB` | **PASS (Pillow)** | `2026-07-13T10:00:00Z` | `activity_4003` @ `2026-07-13T10:07:01Z` | 421s (7m 1s) | `user_id=user_20, email=darwish.omar@icloud.com` |
| `case_52` | `user_18` | 1 | `REPORT_REMAINING_RECORD` | `export_1260` | `evidence_23` | 1800x1100 | `RGB` | **PASS (Pillow)** | `2026-06-18T12:00:00Z` | `activity_4004` @ `2026-06-18T12:07:01Z` | 421s (7m 1s) | `user_id=user_18, email=ingrid.dahl@outlook.com` |
| `case_53` | `user_22` | 1 | `REPORT_EXPOSED_PII` | `support_1034` | `evidence_28` | 1800x1200 | `RGB` | **PASS (Pillow)** | `2026-05-24T07:00:00Z` | `activity_4005` @ `2026-05-24T07:07:01Z` | 421s (7m 1s) | `user_id=user_22, email=kagyeman8947@fastmail.com` |
| `case_55` | `user_16` | 1 | `REPORT_RESTORE_RISK` | `backup_9287` | `evidence_32` | 1800x1150 | `RGB` | **PASS (Pillow)** | `2026-04-29T09:00:00Z` | `activity_4006` @ `2026-04-29T09:07:01Z` | 421s (7m 1s) | `user_id=user_16, email=areed1433@gmail.com` |
| `case_61` | `user_07` | 1 | `REPORT_REMAINING_RECORD` | `object_19` | `evidence_46` | 1800x1150 | `RGB` | **PASS (Pillow)** | `2026-02-13T08:00:00Z` | `activity_4007` @ `2026-02-13T08:07:01Z` | 421s (7m 1s) | `user_id=user_07, email=priya.raman@gmail.com` |
| `case_63` | `user_09` | 1 | `REPORT_REMAINING_RECORD` | `marketing_001` | `evidence_60` | 1500x920 | `RGB` | **PASS (Pillow)** | `2026-09-16T07:20:00Z` | `activity_4008` @ `2026-09-16T07:27:01Z` | 421s (7m 1s) | `user_id=user_09, email=kwame-mensah@proton.me` |

### Resolution of the 'Missing' activity_4009 Mapping:
- In `system_activity.csv`, activities `activity_4000` through `activity_4011` form a consecutive catalog indexing series.
- **11 of the 12 activities** (`activity_4000`-`4008`, `4010`-`4011`) link resources depicted in the 11 administrative web console screenshots (`.png`).
- **`activity_4009`** links canonical resource `export_1842` (with alias `NST-2026-0718-1842`) to `user_18` (`ingrid.dahl@outlook.com`).
- `activity_4009` corresponds to **`evidence_18` (`account_history_report_20260718.pdf`)**, which was captured at `2026-07-18T11:00:00Z` (exactly 7 minutes and 1 second prior to `activity_4009` at `11:07:01Z`). Because `evidence_18` is a PDF document with directly extractable text, it was audited as a text document rather than a visual PNG, explaining why `activity_4009` did not appear in the image-only list.

### Distinction Between Automated and Manual Visual Verification:
- **Automated Verification Performed**: The automated script checks file presence, parses headers, runs Pillow binary integrity verification (`img.verify()`), checks image format (`PNG`), checks mode (`RGB`), validates dimensions, enforces timestamp cutoffs (`captured_at <= audit_at`), and verifies companion catalog events in `system_activity.csv` linking resource and subject within 421s interval.
- **Manual Visual Inspection**: Because optical character recognition (`pytesseract`) is not installed in the execution environment, semantic visual confirmation of on-screen labels (such as portal status badges and form fields) was performed via manual visual inspection and corroborated by companion catalog activities, rather than automated pixel-level OCR.

## 6. Mathematical Reconciliation Summary

$$\begin{aligned}
\text{Total Audited Steps} &= 1241 \\
\text{Text-Grounded Steps} &= 581 + 301 + 143 + 78 + 57 = 1160 \\
\text{Snapshot Omission Steps} &= 70 \\
\text{Visual Console Steps} &= 11 \\
\text{Total Reconciled} &: 1160 + 70 + 11 = 1241 \quad (\Delta = 0)
\end{aligned}$$

All 1,241 evidence-bearing steps are completely verified and mathematically reconciled with zero unresolved discrepancies.