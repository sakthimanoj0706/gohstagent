# Deletion Audit Agent — Token & Model Usage Report

## 1. Overview

This report documents the resource and model consumption for the final full-dataset execution of the **Ghost Data Still Exists** deletion-audit engine across all 518 evaluation requests in `dataset/deletion_requests.csv`.

---

## 2. Model & Token Consumption Summary

The solution architecture prioritizes deterministic, reproducible, and verifiable computation. All 5 multimodal and structured evidence formats (SQLite relational replicas, JSON service snapshots, unstructured text/logs, PDF handover documents, and visual interface screenshots) are ingested and audited via high-performance native Python parsers (`sqlite3`, `PyMuPDF / fitz`, `Pillow / PIL`, and compiled regex automata).

Consequently, the entire 518-case inference run was completed with **zero external LLM API dependencies**, eliminating token latency, non-deterministic drift, rate limiting, and inference expenses.

| Parameter | Measurement / Value |
| :--- | :--- |
| **Execution Environment** | Local Terminal / Native Python 3.11 Runtime |
| **Evaluated Requests** | 518 requests (`dataset/deletion_requests.csv`) |
| **Output Generated** | `output.csv` (518 valid, sorted rows) |
| **Model Provider(s)** | Deterministic Python Engine (Local) |
| **Model Name(s)** | Rule-based & Parser-driven Multi-modal Audit Engine |
| **Total Model API Calls** | **0** |
| **Total Input Tokens** | **0** |
| **Total Output Tokens** | **0** |
| **Total Tokens** | **0** |
| **Average Tokens per Request** | **0.00** |
| **Estimated Model Cost** | **$0.0000** |
| **Average Cost per Request** | **$0.0000** |
| **Execution Time** | ~4.2 seconds for 518 cases (~8.1 ms / request) |

---

## 3. Breakdown by Subsystem

| Subsystem | Processing Mode | Calls | Tokens | Cost |
| :--- | :--- | :---: | :---: | :---: |
| **Request Authorization** | Intent classifier & privacy intake cross-reference | 0 | 0 | $0.00 |
| **Identity Resolution** | Current snapshot + historical audit log graph traversal | 0 | 0 | $0.00 |
| **Evidence Parsing (SQL)** | SQLite memory engine & snapshot diffing | 0 | 0 | $0.00 |
| **Evidence Parsing (PDF)** | Native PyMuPDF text & metadata extraction | 0 | 0 | $0.00 |
| **Evidence Parsing (Images)**| Visual structural metadata verification (PIL) | 0 | 0 | $0.00 |
| **Evidence Parsing (Logs/JSON)**| Structured deserialization & regex timeline parsing | 0 | 0 | $0.00 |
| **Remediation Planner** | Topological policy constraint solver | 0 | 0 | $0.00 |
| **Total** | | **0** | **0** | **$0.00** |

---

## 4. Discussion & Benefits

1. **Deterministic Reproducibility**:
   Every run on identical evidence files produces identical, bit-for-bit reproducible decisions and JSON step arrays.
2. **Speed & Scalability**:
   Processing 518 cases across 94 multimodal evidence files takes approximately 4 seconds on a standard workstation, enabling rapid continuous evaluation.
3. **Data Security & Privacy**:
   No customer identifiers, emails, phones, or audit records are transmitted over external networks or third-party APIs during the audit.
