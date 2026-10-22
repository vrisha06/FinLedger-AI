# FinLedger-AI — AI Fraud Detection Subsystem Guide & Compliance Audit

**Project:** FinLedger-AI: An Auditable Financial Transaction System with AI-Assisted Fraud Detection  
**Module:** Advisory AI Fraud Detection Pipeline & Forensic Investigation Subsystem  
**Status:** Verified & Remediated  
**Model Version:** `rf-v1.0.0` (Scikit-Learn RandomForestClassifier)  

---

## 1. Executive Summary & Core Architectural Invariants

The FinLedger-AI fraud detection module provides **transparent, advisory-only machine learning classification and heuristic rule scoring** to assist compliance officers and banking staff in triaging suspicious financial transfers.

### Core Architectural Invariants
1. **Advisory-Only Separation (Mandatory Financial Invariant)**:
   - The AI/ML subsystem possesses **zero autonomous authority**.
   - The model and rule engine **never** independently debit or credit accounts, manufacture ledger entries, reverse committed transfers, or freeze accounts.
   - Alert triage actions are strictly reserved for authorized banking staff members.
2. **Post-Commit Isolation**:
   - Fraud scoring is invoked **strictly after** the double-entry financial transfer transaction has committed and all row-level locks on `accounts` have been released.
   - Fraud inference operates in an independent database session. If the ML pipeline throws an exception, the committed financial transfer remains completely unaffected, and an auditable `FRAUD_SCORING_FAILED` record is logged.
3. **Idempotency Safeguard**:
   - Replaying a financial transfer with an existing `Idempotency-Key` returns the cached financial response and **never duplicates** `FraudPrediction` records.
4. **Append-Only Auditing**:
   - Every staff review action updates the alert record and appends an immutable, sanitized `FRAUD_ALERT_REVIEW` audit log entry.

---

## 2. Synthetic Banking Transaction Dataset

Because financial institutions cannot share proprietary, regulated customer financial histories due to privacy laws, FinLedger-AI includes a reproducible, deterministic synthetic banking transaction generator (`backend/ml/generator.py`).

### Generation Characteristics
- **Random Seed Reproducibility**: Uses deterministic NumPy/Python random seeds (default `seed=42`).
- **Diurnal Human Activity Simulation**: Models realistic hourly banking traffic via 24 normalized weights reflecting human wakefulness and commercial activity in India (IST peaks between 09:00 and 21:00; low activity between 01:00 and 05:00).
- **Log-Normal Amount Distributions**: Simulates standard retail payment amounts where small transactions dominate and large transfers taper log-normally.
- **Strict Financial Invariants**: All generated records feature positive `amount` (`NUMERIC(15, 2)` equivalent), distinct source and destination account identifiers, and currency strictly denominated in `INR`.

### Five Ground-Truth Fraud Scenarios
The generator injects five canonical fraud patterns into approximately 2.5% of generated traffic:

| Scenario Identifier | Pattern Description | Injected Features & Logic |
| :--- | :--- | :--- |
| `VELOCITY_BURST` | Rapid successive transfers within short intervals. | 4–6 transactions per hour; short inter-transaction intervals (<180 seconds). |
| `ZSCORE_OUTLIER` | Severe spending spikes relative to historical customer baseline. | Transfer amount is $\ge 5\times$ historical customer average and $\ge \text{INR } 10,000$. |
| `RAPID_DRAIN` | High-value successive draining transfers. | Rapid transfer within 10 minutes of prior activity with amount $\ge \text{INR } 15,000$ and ratio $\ge 3\times$. |
| `OFF_HOURS_HIGH_VALUE` | High-value transfers during late-night off-hours. | Initiated between 01:00 and 05:00 IST with amount $\ge \text{INR } 25,000$. |
| `STRUCTURING` | Regulatory reporting evasion ("smurfing"). | Transfer amounts in $[\text{INR } 48,000.00, 49,999.00]$ just below the regulatory $\text{INR } 50,000$ PAN verification threshold. |

### Exploratory Benford's Law Analysis
The generator incorporates first-digit distribution analysis using Benford's Law:
$$P(d) = \log_{10}\left(1 + \frac{1}{d}\right), \quad d \in \{1, \dots, 9\}$$
- **Academic Purpose**: Evaluates whether multi-scale legitimate transaction amounts naturally conform to logarithmic first-digit frequencies.
- **Evaluation Metric**: Mean Absolute Deviation ($\text{MAD} = \frac{1}{9}\sum_{d=1}^9 |O_d - E_d|$).
- **Scope Restriction**: Benford's Law is used strictly as an exploratory data validation tool on aggregate distributions; it is **not** utilized as a standalone deterministic classifier for single transaction decisions.

---

## 3. Leakage-Free Feature Engineering Pipeline

The feature engineering pipeline (`backend/ml/features.py`) constructs 12 temporal and customer-behavioral features without future or target leakage:

```python
FEATURE_COLUMNS = [
    "amount",                  # Continuous transaction amount (INR)
    "log_amount",              # Natural log transformation: log(1 + amount)
    "hour_of_day",             # Hour of transaction in UTC [0-23]
    "is_night",                # Binary indicator: 1 if hour in [1, 5], else 0
    "day_of_week",             # Day of week [0=Monday, 6=Sunday]
    "is_weekend",              # Binary indicator: 1 if Saturday or Sunday
    "customer_tx_count",       # Trailing transaction count for source customer strictly prior to t
    "customer_avg_amount",     # Trailing average transaction amount strictly prior to t
    "amount_to_avg_ratio",     # Ratio: current amount / (trailing average + 1e-4)
    "time_since_last_tx_sec",  # Elapsed seconds since customer's immediate prior transaction
    "tx_velocity_1h",          # Trailing 1-hour transaction frequency (including current)
    "is_new_destination",      # Binary indicator: 1 if destination never previously seen for user
]
```

### Leakage Prevention Guarantees
1. **Zero Future Leakage**: For any transaction $T_i$ occurring at timestamp $t_i$, rolling metrics ($\text{customer\_avg\_amount}$, $\text{time\_since\_last\_tx\_sec}$, $\text{tx\_velocity\_1h}$) are computed exclusively using records where $t < t_i$. Customer state dictionaries are updated **after** feature extraction for the row.
2. **Zero Target Leakage**: The ground-truth columns `is_fraud` and `fraud_scenario` are completely excluded from `FEATURE_COLUMNS`.
3. **Real-Time Parity**: The real-time inference function `extract_single_features()` applies identical mathematical transformations using past records queried from the PostgreSQL database (`created_at <= transfer.created_at` and `id != transfer.id`).

---

## 4. Rule-Based Fraud Detection Baseline

A transparent, deterministic heuristic baseline (`backend/ml/rules.py`) serves as an explainable benchmark against which machine learning models are evaluated.

### Heuristic Scoring Matrix
- `RULE_VELOCITY_BURST`: Weight = 0.40 ($\ge 4$ txns in 1 hour or elapsed time $< 180\text{s}$)
- `RULE_ZSCORE_OUTLIER`: Weight = 0.40 ($\text{ratio} \ge 5.0$ and $\text{amount} \ge 10,000.00$)
- `RULE_RAPID_DRAIN`: Weight = 0.35 ($\text{ratio} \ge 3.0$, time $< 600\text{s}$, and $\text{amount} \ge 15,000.00$)
- `RULE_OFF_HOURS_HIGH_VALUE`: Weight = 0.35 ($\text{is\_night} == 1$ and $\text{amount} \ge 25,000.00$)
- `RULE_STRUCTURING`: Weight = 0.40 ($48,000.00 \le \text{amount} \le 49,999.00$ and customer average $< 25,000.00$)
- **Baseline Classification Threshold**: $0.50$ (Composite score capped at $1.00$).

---

## 5. Machine Learning Classification Pipeline

The machine learning pipeline (`backend/ml/train.py`, `backend/ml/evaluate.py`, `backend/ml/predict.py`) implements a class-imbalanced Scikit-Learn classification workflow.

### Architecture
- **Classifier**: `RandomForestClassifier` (100 estimators, max depth 10, min samples leaf 2, balanced class weighting).
- **Preprocessing**: `StandardScaler` fitted **strictly on training split data** to normalize multi-scale features without validation or test leakage.
- **Temporal Splitting**: Chronological holdout split preserving time sequence:
  - **Train Set**: 70% (7,000 transactions, 188 fraud cases, 2.69% prevalence).
  - **Validation Set**: 15% (1,500 transactions, 35 fraud cases).
  - **Test Set**: 15% (1,500 transactions, 27 fraud cases, 1.80% prevalence).
- **Calibrated Decision Threshold**: $0.70$ (tuned to prioritize high precision and minimize alert fatigue for compliance staff).
- **Fail-Safe Fallback**: If model artifacts are missing or corrupted, `FraudDetector` gracefully falls back to the deterministic `RuleBaseline`.

---

## 6. Empirical Benchmark Results (Test Split)

The following metrics were produced by executing the evaluation benchmark (`backend/ml/evaluate.py`) on the identical held-out 1,500 test transactions (`seed=42`):

| Evaluation Metric | Rule-Based Baseline | ML Model (`RandomForestClassifier`) | Relative Improvement |
| :--- | :--- | :--- | :--- |
| **Precision** | **0.8889** (88.89%) | **0.9600** (96.00%) | **+7.11%** |
| **Recall** | **0.5926** (59.26%) | **0.8889** (88.89%) | **+29.63%** |
| **F1-Score** | **0.7111** (71.11%) | **0.9231** (92.31%) | **+21.20%** |
| **ROC-AUC** | **0.6960** | **0.9976** | **+0.3016** |
| **PR-AUC (Avg Precision)** | **0.5995** | **0.9551** | **+0.3556** |

### Confusion Matrix Breakdown (Test Set: 1,500 Samples, 27 Fraud)
- **ML Model (`RandomForestClassifier`)**:
  - True Positives (TP): **24**
  - False Positives (FP): **1**
  - True Negatives (TN): **1,472**
  - False Negatives (FN): **3**
- **Rule Baseline**:
  - True Positives (TP): **16**
  - False Positives (FP): **2**
  - True Negatives (TN): **1,471**
  - False Negatives (FN): **11**

**Key Finding**: The Random Forest classifier significantly out-performs the rule baseline in recall (capturing 24 of 27 fraud events vs. 16 for rules) while maintaining near-zero false positives ($\text{FP}=1$), directly combating operational alert fatigue.

---

## 7. Prediction Persistence, Data Privacy & Redaction

### Database Model (`fraud_predictions` Table)
Advisory predictions are persisted with full auditability and schema check constraints:
- `id` (`UUID`, Primary Key)
- `transfer_request_id` (`UUID`, Foreign Key to `transfer_requests`, Unique)
- `model_version` (`VARCHAR(30)`, e.g., `rf-v1.0.0`)
- `risk_score` (`NUMERIC(5, 4)`, Range: $[0.0000, 1.0000]$)
- `decision` (`VARCHAR(20)`, Enum: `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`)
- `rule_flags` (`JSONB`, Array of triggered rule flags)
- `feature_snapshot` (`JSONB`, Tabular features captured at inference time)
- `explanation` (`TEXT`, Forensic evidence narrative)
- `review_status` (`VARCHAR(20)`, Enum: `PENDING`, `CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`)
- `reviewed_by_user_id` (`UUID`, Foreign Key to `users`, Nullable)
- `review_notes` (`TEXT`, Forensic notes entered by staff, Nullable)
- `reviewed_at` (`TIMESTAMPTZ`, Nullable)
- `created_at` (`TIMESTAMPTZ`, Indexed with `risk_score` for queue ordering)

### Data Privacy & Sensitive Field Scrubbing
- **Zero Sensitive Data in Feature Snapshots**: Feature snapshots contain strictly mathematical ratios and temporal metrics; customer passwords, API tokens, session credentials, and PAN numbers are **never stored** in `feature_snapshot`.
- **Automated PII/PAN Scrubbing in Audit Logs**: `AuditService.sanitize_audit_metadata` automatically redacts:
  - Passwords and password hashes (bcrypt, Argon2).
  - JWT tokens (`Bearer eyJ...`).
  - Indian PAN numbers (`[A-Z]{5}[0-9]{4}[A-Z]`).
  - Tax identifiers and SSNs (`tax_id`, `ssn`, `pan_number`).

---

## 8. Human-in-the-Loop Staff Review & Audit Trail

### Staff Triage API Endpoints
- `GET /api/v1/fraud/alerts`: Lists advisory alerts filtered by `review_status`, `decision`, and `min_risk_score`. Guarded by `require_staff` RBAC dependency.
- `GET /api/v1/fraud/alerts/{alert_id}`: Fetches complete forensic snapshot, rule flags, and model explanations.
- `PATCH /api/v1/fraud/alerts/{alert_id}/review`: Updates triage status (`CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`). Enforces mandatory forensic review notes (`min_length=3, max_length=1000`) and logs an immutable `FRAUD_ALERT_REVIEW` audit trail.

### Frontend Advisory Presentation
The frontend (`frontend/src/pages/staff/FraudTriagePage.tsx` and `AlertTriageDrawer.tsx`):
- Clearly displays the advisory notice: *"Machine learning risk scores and rule flags serve strictly as advisory decision-support signals for staff triage. The AI subsystem possesses zero autonomous authority to alter balances, debit funds, or reject transactions."*
- Requires compliance officers to input investigation rationale before submitting review determinations.
- Displays risk scores as advisory percent indicators alongside transparent rule flags and model explanations.

---

## 9. Academic Disclaimers, Limitations & Ethical Considerations

> [!WARNING]
> **ACADEMIC DISCLAIMER**: This evaluation was conducted strictly on synthetic banking transaction data generated from simulated mathematical distributions and injected heuristic scenarios. The measured metrics (e.g., 96.00% precision, 92.31% F1) **DO NOT** represent validated real-world fraud detection efficacy, generalization to production banking traffic, or guaranteed financial-loss reduction.

### Production Limitations
1. **Synthetic vs. Real-World Dynamics**: Synthetic data does not exhibit the long-tail edge cases, network topology, or subtle behavioral shifts present in live financial systems.
2. **Concept Drift & Adversarial Adaptation**: Real-world fraudsters dynamically alter tactics once detection rules are identified. Production deployment requires automated monitoring of data drift and continuous retraining.
3. **Class Imbalance**: Actual fraud prevalence in production card networks and RTGS transfers is typically $\le 0.1\%$, significantly rarer than our synthetic 2.5% rate.

---

## 10. CLI Reproducibility Commands

To regenerate synthetic datasets, retrain the classification pipeline, evaluate benchmarks, and run test suites, execute the following native commands:

### 1. Generate Synthetic Transactions & Benford Analysis
```powershell
cd backend
..\.venv\Scripts\python.exe ml/generator.py --count 10000 --seed 42 --benford
```

### 2. Train Machine Learning Pipeline
```powershell
cd backend
..\.venv\Scripts\python.exe ml/train.py --count 10000 --seed 42
```

### 3. Run Evaluation Benchmark
```powershell
cd backend
..\.venv\Scripts\python.exe ml/evaluate.py
```

### 4. Execute ML & Fraud Test Suites
```powershell
cd backend
..\.venv\Scripts\pytest.exe tests/test_ml_generator.py tests/test_ml_rules_and_features.py tests/test_ml_pipeline.py tests/test_fraud_integration.py -v
```

### 5. Execute Full System Backend Test Suite
```powershell
cd backend
..\.venv\Scripts\pytest.exe -v
```

### 6. Verify System Ledger Reconciliation
```powershell
cd backend
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py --test
```
