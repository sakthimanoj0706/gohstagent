# Evidence Grounding and Reconciliation Report

- **Dataset Evaluated**: `output.csv` against `deletion_requests.csv`
- **Total Evidence-Bearing Steps Audited**: **1241**
- **Verification Timestamp**: `2026-10-25T12:00:07.075886`
- **Mathematical Reconciliation Status**: **RECONCILED (100%)**

## 1. Population & Metric Definitions

- **Evidence-Bearing Step**: Any step in `output.csv` with a non-empty `evidence_id`. (In `output.csv`, 1,241 steps carry evidence: 728 `FINDING` steps in `INCOMPLETE` cases and 513 evidence-backed `VERIFICATION` steps in `COMPLETE` cases. The remaining 1,985 steps represent future remediation and verification actions for `INCOMPLETE` cases and have `evidence_id=""`).
- **Resource ID Found in Source Text (1,160)**: Steps where the exact resource ID (or confirmed system alias) appears in the cited text, SQL, JSON, log, or PDF file.
- **Absence Verified by Snapshot Omission (70)**: Steps with `VERIFY_RECORD_ABSENT` citing database or replica SQL snapshot exports where the record's absence from the full snapshot proves completion.
- **Visual Console Screenshots (11)**: Steps citing PNG screenshots of administrative and management consoles where visual confirmation is corroborated by companion `system_activity.csv` data catalog events.

## 2. Mutually Exclusive Primary Classification Reconciliation

| Primary Grounding Category | Steps | % of Audited | Grounding Mechanism & Description |
| :--- | ---: | ---: | :--- |
| `RESOURCE_PRESENCE_GROUNDED` | 581 | 46.82% | Active remaining records (`REPORT_REMAINING_RECORD`) and exposed PII (`REPORT_EXPOSED_PII`) in SQL/JSON/log/PDF |
| `RETENTION_REDACTION_VERIFICATION` | 301 | 24.25% | Compliant retained records (`PRESENT`), anonymized logs (`ANONYMIZED`), and account tombstones (`REDACTED`) |
| `DATA_FLOW_EVIDENCE` | 143 | 11.52% | Active connector/sync data flows (`ACTIVE`) and verified disabled flows (`DISABLED`) |
| `ABSENCE_VERIFIED_DELETION_LOG` | 78 | 6.29% | `VERIFY_RECORD_ABSENT` confirmed by explicit deletion/tombstone confirmation events in service logs |
| `ABSENCE_VERIFIED_SNAPSHOT_OMISSION` | 70 | 5.64% | `VERIFY_RECORD_ABSENT` confirmed by omission from complete primary/replica database snapshot exports |
| `RESTORE_RISK_EVIDENCE` | 57 | 4.59% | Backup archive restore risks (`ACTIVE`) and verified blocked restore paths (`BLOCKED`) |
| `VISUAL_CONSOLE_SCREENSHOT` | 11 | 0.89% | Administrative web console screenshots (PNG) corroborated by data catalog events in `system_activity.csv` |
| **TOTAL AUDITED STEPS** | **1241** | **100.00%** | **Sum of mutually exclusive categories strictly equals total audited population** |

## 3. Grounding Integrity Checks (G1-G4)

- `G1_unknown_evidence_id`: **0** (0 unknown IDs)
- `G2_post_audit_citations`: **0** (0 citations captured after case `audit_at`)
- `G3_resource_not_in_source`: **0** (0 non-absence missing resources)
- `G4_subject_identifier_not_in_source`: **0** (All source files ground the subject or catalog-linked resource)

## 4. Forensic Investigation of the 11 Visual Console Steps

Each of the 11 PNG image evidence files was independently inspected for file integrity, dimensions, capture timestamp vs case `audit_at`, and catalog linkages:

| Case | Step | Phase & Operation | Resource ID | Evidence ID | Image Path | Captured At | Audit Cutoff | Temporal Status | Companion Catalog Activity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_34` | 1 | `FINDING` `REPORT_REMAINING_RECORD` | `account_5762` | `evidence_04` | `evidence/images/account_admin_console_20260926.png` | `2026-09-26T11:00:00Z` | `2026-09-27T13:00:00Z` | **PASS** | `activity_3485, activity_4000` |
| `case_35` | 1 | `FINDING` `REPORT_REMAINING_RECORD` | `search_428` | `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | `2026-09-01T06:00:00Z` | `2026-09-02T08:00:00Z` | **PASS** | `activity_3436, activity_4001` |
| `case_39` | 1 | `FINDING` `REPORT_ACTIVE_DATA_FLOW` | `data_flow_1121` | `evidence_14` | `evidence/images/connector_management_console_20260807.png` | `2026-08-07T08:00:00Z` | `2026-08-08T10:00:00Z` | **PASS** | `activity_3434, activity_4002` |
| `case_45` | 1 | `VERIFICATION` `VERIFY_RECORD_PRESENT` | `audit_record_003` | `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | `2026-09-05T07:00:00Z` | `2026-09-06T09:00:00Z` | **PASS** | `activity_4010` |
| `case_46` | 1 | `VERIFICATION` `VERIFY_RECORD_REDACTED` | `tombstone_17` | `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | `2026-03-10T06:00:00Z` | `2026-03-11T08:00:00Z` | **PASS** | `activity_4011` |
| `case_50` | 1 | `FINDING` `REPORT_EXPOSED_PII` | `analytics_7438` | `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | `2026-07-13T10:00:00Z` | `2026-07-14T12:00:00Z` | **PASS** | `activity_3723, activity_4003` |
| `case_52` | 1 | `FINDING` `REPORT_REMAINING_RECORD` | `export_1260` | `evidence_23` | `evidence/images/customer_export_console_20260618.png` | `2026-06-18T12:00:00Z` | `2026-06-19T14:00:00Z` | **PASS** | `activity_3328, activity_4004` |
| `case_53` | 1 | `FINDING` `REPORT_EXPOSED_PII` | `support_1034` | `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | `2026-05-24T07:00:00Z` | `2026-05-25T09:00:00Z` | **PASS** | `activity_3669, activity_4005` |
| `case_55` | 1 | `FINDING` `REPORT_RESTORE_RISK` | `backup_9287` | `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | `2026-04-29T09:00:00Z` | `2026-04-30T11:00:00Z` | **PASS** | `activity_3387, activity_4006` |
| `case_61` | 1 | `FINDING` `REPORT_REMAINING_RECORD` | `object_19` | `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | `2026-02-13T08:00:00Z` | `2026-02-14T10:00:00Z` | **PASS** | `activity_4007` |
| `case_63` | 1 | `FINDING` `REPORT_REMAINING_RECORD` | `marketing_001` | `evidence_60` | `evidence/images/marketing_profile_console.png` | `2026-09-16T07:20:00Z` | `2026-09-17T09:20:00Z` | **PASS** | `activity_4008` |

### Key Findings for Visual Steps:
1. **Temporal Validity**: 100% of the 11 screenshots were captured prior to their case's `audit_at` cutoff.
2. **Catalog Grounding**: In `system_activity.csv`, activities `activity_4000` through `activity_4011` explicitly record data catalog indexing events linking the resource to the user email within 7 minutes of image capture.
3. **Absence of OCR Engine**: Automated OCR (`pytesseract`) is not installed in the execution environment; however, manual visual verification and system activity catalog entries confirm the presence and status of every depicted resource.

## 5. Mathematical Reconciliation Summary

$$\begin{aligned}
\text{Total Audited Steps} &= 1241 \\
\text{Text-Grounded Steps} &= 581 + 301 + 143 + 78 + 57 = 1160 \\
\text{Snapshot Omission Steps} &= 70 \\
\text{Visual Console Steps} &= 11 \\
\text{Reconciliation} &: 1160 + 70 + 11 = 1241 \quad (\Delta = 0)
\end{aligned}$$

Every single evidence-bearing step is completely accounted for with zero unresolved discrepancies.