# FinLedger-AI: Research Foundations, Problem Definition & Technical Novelty

**Author:** Saksham Raj  
**Academic Context:** Database Systems B.Tech Capstone Project  
**Status:** Approved Research Specification  

---

## 1. Problem Statement

Modern retail banking and real-time payment rails (such as India's Unified Payments Interface — UPI) process billions of high-velocity financial transactions monthly. However, this convenience introduces severe operational challenges:
1. **Multi-Account Coordinated Laundering & Money-Mule Rings**: Fraudulent actors do not operate single isolated accounts. They use mule networks, rapid fan-in (accumulating small stolen funds into a hub), rapid fan-out (dispersing funds across dozens of secondary mules), multi-hop layering, and circular routing to evade single-transaction heuristic thresholds.
2. **Social Engineering & Destination Impersonation**: Account identifiers (such as account numbers or virtual payment addresses) are opaque strings. Victims are frequently manipulated into authorizing irreversible payments to fraudsters posing as legitimate entities because the interface fails to authoritatively display the verified recipient before commitment.
3. **Black-Box AI Decisions Lacking Evidentiary Audit Trails**: Conventional machine learning models produce uncalibrated risk probabilities without causal attribution or ledger linkage. When an investigator must defend a freeze or dispute, a score without linked debit/credit records, point-in-time features, and deterministic rule explanations fails regulatory scrutiny.
4. **Disconnection Between Advisory AI and Database Relational Invariants**: Naive architectures frequently allow AI models to mutate balances or introduce eventual-consistency discrepancies, violating fundamental double-entry balance and ACID transaction invariants.

---

## 2. Research Context & Prior Art

This implementation synthesizes key regulatory reports, industry guidelines, and academic research:

1. **Reserve Bank of India (RBI) — FREE-AI Committee Report (August 2025)**:
   - Emphasizes the *FREE* framework: **F**airness, **R**esilience, **E**xplainability, and **E**valuation in banking AI.
   - Mandates that algorithmic systems operating in Indian financial institutions must have human-in-the-loop oversight, strict governance against automated prejudicial actions, and verifiable explainability trails.
2. **National Payments Corporation of India (NPCI) — Addendum on Beneficiary-Name Verification (April 2025)**:
   - *UPI Operating Circular No. 101/A*: Mandates pre-transaction display of the destination account-holder's verified legal name prior to user confirmation to eliminate impersonation fraud and misdirected transfers.
   - FinLedger-AI translates this principle into **PayeeGuard**, providing an authenticated, server-verified preview of destination legal names and first-time recipient status without leaking sensitive KYC metadata.
3. **RBI Money-Mule Identification Initiatives & MuleHunter.AI**:
   - Focuses on identifying dormant accounts suddenly exhibiting high-velocity pass-through activity, multi-source pooling (fan-in), and rapid layering.
   - FinLedger-AI incorporates these patterns into **LedgerGraph**, a deterministic, temporal graph detector operating over relational transfer records.
4. **Financial Stability Board (FSB) — Sound Practices for Responsible Adoption of AI (October 2026)**:
   - Highlights operational risks: model drift, lack of explainability, third-party dependency, and the risk of automated decision-making without auditability.
   - FinLedger-AI implements **AI Health & Governance**, providing artifact fingerprinting, explicit fallback states, and distribution monitoring (Population Stability Index).
5. **Academic Literature on Graph Learning & Fraud Detection**:
   - *Review of Graph Learning for Financial Fraud Detection (ScienceDirect, 2025)*: Demonstrates that while tabular models (Random Forests, Gradient Boosting) capture per-transaction statistical distributions, money-laundering topologies (cycles, layering, bipartite pooling) require graph-relational structures.
   - Crucially, offline evaluation must enforce **point-in-time correctness** ($t \le t_{event}$) to prevent future leakage across temporal edges.
6. **W3C Web Content Accessibility Guidelines (WCAG 2.2 AA)**:
   - Mandates non-color-reliant indicators, minimum 4.5:1 text contrast, tabular numeric alignment, focus states, and keyboard navigability across financial dashboards.

---

## 3. FinLedger-AI's Engineering Contributions

| Domain | Prior Art / Common Practice | FinLedger-AI Academic Contribution |
| :--- | :--- | :--- |
| **Accounting Invariants** | Application-level balance updates or loose eventual consistency. | Strictly enforced PostgreSQL double-entry ledger with `CONSTRAINT TRIGGER` deferrable validation ($\sum \text{Debits} == \sum \text{Credits}$), append-only triggers, and canonical ascending row-locking. |
| **Recipient Verification** | Client-side input display or unverified user memos. | **PayeeGuard**: Authoritative backend pre-transfer verification displaying destination legal name, masked account ID, and first-time recipient alert with strict ownership validation. |
| **Money-Flow Graph Detection** | Separate heavy graph DBs or future-leaking static graph analytics. | **LedgerGraph**: In-database bounded temporal graph analytics over authoritative relational transfers; deterministic detection of Fan-in, Fan-out, Rapid Pass-through, Multi-hop Layering, and Cycles with point-in-time safety. |
| **Forensic Investigation** | Opaque fraud score badges without source linkage. | **Forensic Dossier**: Unified timeline linking transfer records, balanced ledger postings, rule flags, ML feature vectors, and human investigator decisions. |
| **Customer Recourse** | Manual offline customer service tickets. | **Customer Recourse Workflow**: Authenticated dispute initiation with state-machine progression (`OPEN` $\to$ `UNDER_REVIEW` $\to$ `RESOLVED`), append-only case events, and strict isolation from financial balance mutation. |
| **Evaluation & Benchmarking** | Fabricated metrics or static dashboards. | **Fraud Lab**: Seeded synthetic scenario generator producing reproducible topological fraud patterns and benign lookalikes; empirical comparison of Rules, Random Forest, LedgerGraph, and Hybrid ensembles. |
| **AI Governance** | Silent fallback or unmonitored model endpoints. | **AI Health Workspace**: Runtime readiness inspection, model fingerprinting, explicit fallback disclosure, and feature distribution drift monitoring. |

---

## 4. Scope & Limitations of the Academic Prototype

1. **Internal Account Verification**: PayeeGuard verifies recipients against the internal FinLedger-AI database. It does not integrate with external NPCI IMPS/UPI directory APIs or CBS core banking switches.
2. **Relational Graph Scaling**: LedgerGraph operates efficiently over bounded time-windows and depth limits within PostgreSQL. For millions of nodes across multi-decade histories, an external graph execution engine (e.g. Apache AGE or Neo4j) would be utilized.
3. **Advisory ML**: Random Forest probabilities and heuristic graph scores are advisory risk indicators; they are not calibrated real-world probabilities of prosecution and do not automate fund freezing.
4. **Dispute Resolution**: Customer recourse cases document disputes and staff determinations; financial reversals require independent, authorized double-entry accounting transactions.
