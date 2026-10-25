# Evidence Grounding Audit

- Predictions: `output.csv`  Requests: `deletion_requests.csv`
- Evidence-bearing steps checked: **1241** (file refs 1241, activity refs 0)
- Resource ID found in cited source text: **1160**
- ABSENT claims supported only by omission from the cited snapshot: **70**
- Non-absence claims whose resource ID is NOT in the cited source: **0**
- Image citations not machine-verifiable (no OCR available): **11**

| Category | Count |
| :--- | ---: |
| `G3_absence_inferred_from_omission` | 70 |
| `NOT_VERIFIABLE_image_no_ocr` | 11 |

## G3_absence_inferred_from_omission (70)
- case_103 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4070 <- evidence_10
- case_107 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_7510 <- evidence_10
- case_108 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6750 <- evidence_10
- case_111 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_9314 <- evidence_10
- case_112 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_2259 <- evidence_10
- case_126 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_8819 <- evidence_87
- case_127 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6805 <- evidence_87
- case_155 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1992 <- evidence_15
- case_157 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_2154 <- evidence_15
- case_162 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_5983 <- evidence_15
- case_175 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_246 <- evidence_84
- case_178 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1090 <- evidence_84
- case_204 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_9268 <- evidence_20
- case_206 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4522 <- evidence_20
- case_213 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6674 <- evidence_81
- case_215 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1956 <- evidence_81
- case_218 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4066 <- evidence_81
- case_219 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4678 <- evidence_81
- case_221 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4512 <- evidence_81
- case_243 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4264 <- evidence_78
- case_244 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_7650 <- evidence_78
- case_253 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6073 <- evidence_24
- case_257 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_3601 <- evidence_24
- case_260 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_7811 <- evidence_24
- case_294 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6996 <- evidence_75
- case_295 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_9091 <- evidence_75
- case_297 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6023 <- evidence_75
- case_299 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1618 <- evidence_75
- case_304 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4771 <- evidence_29
- case_308 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_8647 <- evidence_29
- case_309 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_4319 <- evidence_29
- case_335 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_8892 <- evidence_72
- case_336 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_2282 <- evidence_72
- case_339 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1340 <- evidence_72
- case_354 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_3918 <- evidence_33
- case_362 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_507 <- evidence_33
- case_393 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1093 <- evidence_69
- case_395 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_6443 <- evidence_69
- case_398 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1140 <- evidence_69
- case_403 step 1 VERIFICATION VERIFY_RECORD_ABSENT account_1246 <- evidence_38
- ... 30 more

## NOT_VERIFIABLE_image_no_ocr (11)
- case_34 step 1 FINDING REPORT_REMAINING_RECORD account_5762 <- evidence_04
- case_35 step 1 FINDING REPORT_REMAINING_RECORD search_428 <- evidence_09
- case_39 step 1 FINDING REPORT_ACTIVE_DATA_FLOW data_flow_1121 <- evidence_14
- case_45 step 1 VERIFICATION VERIFY_RECORD_PRESENT audit_record_003 <- evidence_37
- case_46 step 1 VERIFICATION VERIFY_RECORD_REDACTED tombstone_17 <- evidence_42
- case_50 step 1 FINDING REPORT_EXPOSED_PII analytics_7438 <- evidence_19
- case_52 step 1 FINDING REPORT_REMAINING_RECORD export_1260 <- evidence_23
- case_53 step 1 FINDING REPORT_EXPOSED_PII support_1034 <- evidence_28
- case_55 step 1 FINDING REPORT_RESTORE_RISK backup_9287 <- evidence_32
- case_61 step 1 FINDING REPORT_REMAINING_RECORD object_19 <- evidence_46
- case_63 step 1 FINDING REPORT_REMAINING_RECORD marketing_001 <- evidence_60
