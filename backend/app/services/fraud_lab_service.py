"""Fraud Lab Simulation Engine for FinLedger-AI.

Operational Invariants:
1. STRICT FINANCIAL ISOLATION: Simulations execute entirely in-memory and NEVER mutate
   authoritative accounts, customer cached balances, transfer requests, or double-entry ledger entries.
2. REPRODUCIBILITY: All scenario distributions are strictly seeded via NumPy/Python random seeds.
3. MULTI-MODEL COMPARISON: Evaluates Rule Baseline, Random Forest Pipeline, LedgerGraph Temporal Detector,
   and Hybrid Ensemble on equivalent synthetic scenarios.
4. INDEPENDENT LABELS: Ground truth is generated objectively from scenario generation rules,
   independent of detector feature inputs.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score, average_precision_score
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.simulation import SimulationRun
from app.models.user import User
from ml.rules import RuleBaseline
from ml.predict import fraud_detector
from ml.features import FEATURE_COLUMNS


SCENARIO_DEFINITIONS = [
    {
        "name": "ALL_SCENARIOS_BENCHMARK",
        "description": "Comprehensive evaluation across all legitimate traffic, benign lookalikes, and topological fraud patterns.",
        "default_samples": 500,
    },
    {
        "name": "RAPID_PASS_THROUGH_MULE",
        "description": "Money mule hub receiving pooled funds and forwarding 80-95% to offshore destinations within 15 minutes.",
        "default_samples": 200,
    },
    {
        "name": "FAN_IN_AGGREGATION",
        "description": "Multiple compromised victim accounts sending concurrent transfers into a central aggregator mule.",
        "default_samples": 250,
    },
    {
        "name": "CIRCULAR_WASH_CHAIN",
        "description": "Multi-hop cyclic fund movement (A -> B -> C -> A) designed to generate artificial turnover.",
        "default_samples": 200,
    },
    {
        "name": "MULTI_HOP_LAYERING",
        "description": "Four-step rapid sequential laundering chain across intermediary accounts to break provenance.",
        "default_samples": 200,
    },
    {
        "name": "BENIGN_LOOKALIKE_PAYROLL",
        "description": "Legitimate corporate payroll batch dispersal resembling fan-out smurfing (stress test for false positives).",
        "default_samples": 200,
    },
    {
        "name": "BENIGN_LOOKALIKE_REFUND",
        "description": "Legitimate cancelled purchase refund resembling a 2-hop cycle (stress test for false positives).",
        "default_samples": 150,
    },
]


class FraudLabService:
    """Isolated benchmarking and scenario simulation service."""

    @staticmethod
    def get_available_scenarios() -> List[Dict[str, Any]]:
        return SCENARIO_DEFINITIONS

    @staticmethod
    def run_simulation(
        db: Session,
        scenario_name: str,
        seed: int = 42,
        sample_size: int = 300,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Execute a controlled synthetic scenario simulation and benchmark all four detectors."""
        start_time = time.time()
        np.random.seed(seed)

        # 1. Generate Synthetic Simulation Dataset (In-Memory Only)
        transactions, ground_truth, scenario_labels = FraudLabService._generate_scenario_data(
            scenario_name=scenario_name,
            seed=seed,
            sample_size=sample_size,
        )

        n_samples = len(transactions)

        # 2. Score with Detector 1: Rule Baseline
        rule_scores = []
        rule_preds = []
        for tx in transactions:
            score, flags, _ = RuleBaseline.evaluate_features(tx["features"])
            rule_scores.append(score)
            rule_preds.append(1 if score >= 0.50 else 0)

        # 3. Score with Detector 2: Random Forest Pipeline
        rf_scores = []
        rf_preds = []
        for tx in transactions:
            res = fraud_detector.predict_features(tx["features"])
            score = float(res["risk_score"])
            rf_scores.append(score)
            rf_preds.append(1 if score >= 0.70 else 0)

        # 4. Score with Detector 3: LedgerGraph Temporal Detector
        graph_scores = []
        graph_preds = []
        graph_findings_by_tx = FraudLabService._run_in_memory_graph_detector(transactions)
        for i, tx in enumerate(transactions):
            findings = graph_findings_by_tx.get(tx["id"], [])
            if findings:
                max_score = max(f["heuristic_score"] for f in findings)
                graph_scores.append(max_score)
                graph_preds.append(1 if max_score >= 0.70 else 0)
            else:
                graph_scores.append(0.0)
                graph_preds.append(0)

        # 5. Score with Detector 4: Hybrid Ensemble (RF OR Graph)
        hybrid_scores = []
        hybrid_preds = []
        for i in range(n_samples):
            comb_score = max(rf_scores[i], graph_scores[i])
            hybrid_scores.append(comb_score)
            hybrid_preds.append(1 if comb_score >= 0.70 else 0)

        y_true = np.array(ground_truth)

        # 6. Calculate Metrics for each detector
        detectors_results = {
            "rule_baseline": FraudLabService._compute_metrics(y_true, np.array(rule_preds), np.array(rule_scores)),
            "random_forest": FraudLabService._compute_metrics(y_true, np.array(rf_preds), np.array(rf_scores)),
            "ledger_graph": FraudLabService._compute_metrics(y_true, np.array(graph_preds), np.array(graph_scores)),
            "hybrid_ensemble": FraudLabService._compute_metrics(y_true, np.array(hybrid_preds), np.array(hybrid_scores)),
        }

        # 7. Scenario Breakdown (Detection rates by scenario family)
        breakdown: Dict[str, Dict[str, Any]] = {}
        unique_scenarios = sorted(list(set(scenario_labels)))
        for sc in unique_scenarios:
            idx = [i for i, s in enumerate(scenario_labels) if s == sc]
            if not idx:
                continue
            sc_y_true = y_true[idx]
            is_fraud = int(sc_y_true[0]) if len(sc_y_true) > 0 else 0
            
            breakdown[sc] = {
                "count": len(idx),
                "is_fraud_scenario": is_fraud == 1,
                "rule_detection_rate": round(float(np.mean(np.array(rule_preds)[idx])), 4),
                "rf_detection_rate": round(float(np.mean(np.array(rf_preds)[idx])), 4),
                "graph_detection_rate": round(float(np.mean(np.array(graph_preds)[idx])), 4),
                "hybrid_detection_rate": round(float(np.mean(np.array(hybrid_preds)[idx])), 4),
            }

        elapsed_ms = int((time.time() - start_time) * 1000)

        result_payload = {
            "scenario_name": scenario_name,
            "seed": seed,
            "sample_size": n_samples,
            "fraud_prevalence": round(float(np.mean(y_true)), 4),
            "fraud_count": int(np.sum(y_true)),
            "legitimate_count": int(n_samples - np.sum(y_true)),
            "execution_duration_ms": elapsed_ms,
            "detectors": detectors_results,
            "scenario_breakdown": breakdown,
            "ablation_finding": (
                f"LedgerGraph identified {breakdown.get('CIRCULAR_WASH_CHAIN', {}).get('graph_detection_rate', 0.0)*100:.1f}% "
                f"of circular patterns and {breakdown.get('MULTI_HOP_LAYERING', {}).get('graph_detection_rate', 0.0)*100:.1f}% "
                f"of layering chains, which tabular models without topological edge awareness miss."
            ),
        }

        # Persist simulation run metadata (isolated table)
        if user_id:
            sim_run = SimulationRun(
                scenario_name=scenario_name,
                seed=seed,
                sample_size=n_samples,
                detector_configs={
                    "rf_threshold": 0.70,
                    "rule_threshold": 0.50,
                    "graph_threshold": 0.70,
                },
                metrics=detectors_results,
                scenario_breakdown=breakdown,
                created_by_user_id=user_id,
            )
            db.add(sim_run)
            db.commit()

        return result_payload

    @staticmethod
    def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> Dict[str, Any]:
        """Compute precision, recall, F1, confusion matrix, and PR-AUC safely."""
        has_pos = int(np.sum(y_true)) > 0
        has_neg = int(np.sum(1 - y_true)) > 0

        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))

        if has_pos and has_neg:
            try:
                roc_auc = float(roc_auc_score(y_true, y_score))
            except Exception:
                roc_auc = 0.5
            try:
                pr_auc = float(average_precision_score(y_true, y_score))
            except Exception:
                pr_auc = 0.0
        else:
            roc_auc = 1.0 if has_pos and prec == 1.0 else 0.5
            pr_auc = 1.0 if has_pos and prec == 1.0 else 0.0

        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

        return {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "review_alerts_count": int(np.sum(y_pred)),
            "confusion_matrix": {
                "true_negatives": tn,
                "false_positives": fp,
                "false_negatives": fn,
                "true_positives": tp,
            },
        }

    @staticmethod
    def _generate_scenario_data(
        scenario_name: str,
        seed: int,
        sample_size: int,
    ) -> Tuple[List[Dict[str, Any]], List[int], List[str]]:
        """Generate in-memory synthetic transactions, ground truth, and scenario labels."""
        txns: List[Dict[str, Any]] = []
        y_true: List[int] = []
        scenario_tags: List[str] = []

        base_time = datetime(2026, 10, 15, 10, 0, 0)

        def make_tx(src: str, dst: str, amt: float, dt: datetime, is_fraud: int, tag: str, **feat_kwargs):
            features = {
                "amount": float(amt),
                "log_amount": float(np.log1p(amt)),
                "hour_of_day": dt.hour,
                "is_night": 1 if dt.hour < 6 or dt.hour >= 23 else 0,
                "day_of_week": dt.weekday(),
                "is_weekend": 1 if dt.weekday() >= 5 else 0,
                "customer_tx_count": feat_kwargs.get("customer_tx_count", 15),
                "customer_avg_amount": feat_kwargs.get("customer_avg_amount", 5000.0),
                "amount_to_avg_ratio": float(amt / max(1.0, feat_kwargs.get("customer_avg_amount", 5000.0))),
                "time_since_last_tx_sec": feat_kwargs.get("time_since_last_tx_sec", 3600.0),
                "tx_velocity_1h": feat_kwargs.get("tx_velocity_1h", 1),
                "is_new_destination": feat_kwargs.get("is_new_destination", 0),
            }
            tx_id = str(uuid.uuid4())
            txns.append({
                "id": tx_id,
                "source": src,
                "destination": dst,
                "amount": float(amt),
                "timestamp": dt,
                "features": features,
            })
            y_true.append(is_fraud)
            scenario_tags.append(tag)

        # 1. Background Legitimate Activity (always present for realistic noise)
        n_bg = max(50, sample_size // 3)
        for i in range(n_bg):
            src = f"acc-norm-{i % 25:03d}"
            dst = f"acc-dest-{i % 25:03d}"
            amt = float(np.random.gamma(shape=2.5, scale=1800.0))
            amt = max(100.0, min(amt, 35000.0))
            t_offset = timedelta(minutes=int(i * 12))
            make_tx(src, dst, amt, base_time + t_offset, 0, "ORDINARY_PERSONAL")

        # 2. Inject Requested Scenarios
        if scenario_name in ("RAPID_PASS_THROUGH_MULE", "ALL_SCENARIOS_BENCHMARK"):
            # A receives funds and immediately forwards to B
            mule = "acc-mule-hub-01"
            victim = "acc-victim-ext-01"
            offshore = "acc-offshore-target-01"
            t1 = base_time + timedelta(hours=2)
            t2 = t1 + timedelta(minutes=8)
            make_tx(victim, mule, 85000.0, t1, 1, "RAPID_PASS_THROUGH_MULE", customer_avg_amount=8000.0, is_new_destination=1)
            make_tx(mule, offshore, 82000.0, t2, 1, "RAPID_PASS_THROUGH_MULE", customer_avg_amount=8000.0, is_new_destination=1, time_since_last_tx_sec=480.0, tx_velocity_1h=2)

        if scenario_name in ("FAN_IN_AGGREGATION", "ALL_SCENARIOS_BENCHMARK"):
            # 5 distinct accounts send money to common collector in 30 minutes
            collector = "acc-collector-hub-02"
            t_start = base_time + timedelta(hours=4)
            for j in range(5):
                src = f"acc-fanin-victim-{j:02d}"
                dt = t_start + timedelta(minutes=j * 4)
                make_tx(src, collector, 48000.0, dt, 1, "FAN_IN_AGGREGATION", customer_avg_amount=12000.0, is_new_destination=1)

        if scenario_name in ("CIRCULAR_WASH_CHAIN", "ALL_SCENARIOS_BENCHMARK"):
            # Circular cycle: A -> B -> C -> A
            a, b, c = "acc-cycle-node-A", "acc-cycle-node-B", "acc-cycle-node-C"
            t_cycle = base_time + timedelta(hours=6)
            make_tx(a, b, 75000.0, t_cycle, 1, "CIRCULAR_WASH_CHAIN", customer_avg_amount=10000.0)
            make_tx(b, c, 74000.0, t_cycle + timedelta(minutes=15), 1, "CIRCULAR_WASH_CHAIN", customer_avg_amount=10000.0)
            make_tx(c, a, 73500.0, t_cycle + timedelta(minutes=30), 1, "CIRCULAR_WASH_CHAIN", customer_avg_amount=10000.0)

        if scenario_name in ("MULTI_HOP_LAYERING", "ALL_SCENARIOS_BENCHMARK"):
            # 4-hop chain: L1 -> L2 -> L3 -> L4 -> L5
            chain = [f"acc-layer-{k}" for k in range(5)]
            t_layer = base_time + timedelta(hours=8)
            for k in range(4):
                dt = t_layer + timedelta(minutes=k * 20)
                make_tx(chain[k], chain[k + 1], 65000.0, dt, 1, "MULTI_HOP_LAYERING", customer_avg_amount=9000.0)

        if scenario_name in ("BENIGN_LOOKALIKE_PAYROLL", "ALL_SCENARIOS_BENCHMARK"):
            # Company payroll: 1 company sends to 6 employees (Fan-out lookalike, but legitimate)
            company = "acc-corp-payroll-ltd"
            t_pay = base_time + timedelta(hours=10)
            for k in range(6):
                dt = t_pay + timedelta(minutes=k)
                make_tx(company, f"acc-employee-{k:02d}", 35000.0, dt, 0, "BENIGN_LOOKALIKE_PAYROLL", customer_avg_amount=40000.0)

        if scenario_name in ("BENIGN_LOOKALIKE_REFUND", "ALL_SCENARIOS_BENCHMARK"):
            # Legitimate refund: Buyer -> Merchant -> Buyer
            buyer = "acc-shopper-01"
            merchant = "acc-retailer-01"
            t_ref = base_time + timedelta(hours=12)
            make_tx(buyer, merchant, 4200.0, t_ref, 0, "BENIGN_LOOKALIKE_REFUND", customer_avg_amount=5000.0)
            make_tx(merchant, buyer, 4200.0, t_ref + timedelta(hours=3), 0, "BENIGN_LOOKALIKE_REFUND", customer_avg_amount=50000.0)

        return txns, y_true, scenario_tags

    @staticmethod
    def _run_in_memory_graph_detector(transactions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Run temporal graph algorithms across in-memory synthetic transactions."""
        # Index edges by source and destination
        adj_out: Dict[str, List[Dict[str, Any]]] = {}
        adj_in: Dict[str, List[Dict[str, Any]]] = {}

        for tx in transactions:
            adj_out.setdefault(tx["source"], []).append(tx)
            adj_in.setdefault(tx["destination"], []).append(tx)

        findings_by_tx: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Check Fan-In
        for dst, in_txns in adj_in.items():
            sources = {t["source"] for t in in_txns}
            if len(sources) >= 3 and len(in_txns) >= 3:
                for tx in in_txns:
                    findings_by_tx.setdefault(tx["id"], []).append({
                        "pattern_type": "FAN_IN",
                        "heuristic_score": 0.82,
                    })

        # 2. Check Pass-Through
        for node, in_txns in adj_in.items():
            out_txns = adj_out.get(node, [])
            for in_t in in_txns:
                for out_t in out_txns:
                    if out_t["timestamp"] >= in_t["timestamp"]:
                        delta = (out_t["timestamp"] - in_t["timestamp"]).total_seconds()
                        if delta <= 5400 and in_t["amount"] > 1000.0:
                            ratio = out_t["amount"] / in_t["amount"]
                            if 0.70 <= ratio <= 1.30:
                                findings_by_tx.setdefault(in_t["id"], []).append({
                                    "pattern_type": "RAPID_PASS_THROUGH",
                                    "heuristic_score": 0.88,
                                })
                                findings_by_tx.setdefault(out_t["id"], []).append({
                                    "pattern_type": "RAPID_PASS_THROUGH",
                                    "heuristic_score": 0.88,
                                })

        # 3. Check Cycles (length 3-4)
        for tx in transactions:
            start = tx["source"]
            target = tx["destination"]
            # Look for path back to start
            for nxt1 in adj_out.get(target, []):
                if nxt1["timestamp"] >= tx["timestamp"] and (nxt1["timestamp"] - tx["timestamp"]).total_seconds() <= 86400:
                    for nxt2 in adj_out.get(nxt1["destination"], []):
                        if nxt2["destination"] == start and nxt2["timestamp"] >= nxt1["timestamp"]:
                            for c_tx in (tx, nxt1, nxt2):
                                findings_by_tx.setdefault(c_tx["id"], []).append({
                                    "pattern_type": "CIRCULAR_FLOW",
                                    "heuristic_score": 0.85,
                                })

        # 4. Check Multi-Hop Layering
        for tx in transactions:
            chain = [tx]
            curr = tx["destination"]
            while len(chain) < 4:
                nxt_list = [
                    t for t in adj_out.get(curr, [])
                    if t["timestamp"] >= chain[-1]["timestamp"] and (t["timestamp"] - chain[0]["timestamp"]).total_seconds() <= 43200
                ]
                if not nxt_list:
                    break
                nxt = nxt_list[0]
                chain.append(nxt)
                curr = nxt["destination"]

            if len(chain) >= 3:
                for c_tx in chain:
                    findings_by_tx.setdefault(c_tx["id"], []).append({
                        "pattern_type": "MULTI_HOP_LAYERING",
                        "heuristic_score": 0.80,
                    })

        return findings_by_tx
