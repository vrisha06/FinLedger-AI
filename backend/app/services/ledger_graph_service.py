"""LedgerGraph: Temporal Money-Flow Graph Analysis & Pattern Detector.

Operational Invariants:
1. Operates over PostgreSQL relational transfer records as the authoritative ground truth.
2. Point-in-time correctness: Evaluates only events where timestamp <= as_of_time (no future leakage).
3. Strictly advisory: Generates forensic findings for staff triage; never blocks, rejects, or mutates transfers.
4. Explanations link directly to transfer IDs, account IDs, and timestamped amounts.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, deque
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, desc

from app.models.transfer import TransferRequest
from app.models.account import Account
from app.models.graph import GraphFinding
from app.models.audit import AuditLog

DETECTOR_VERSION = "ledgergraph-v1.0"


def _to_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone for consistent comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class LedgerGraphService:
    """Forensic graph analysis engine detecting multi-account money movement topologies."""

    @staticmethod
    def analyze_transaction(
        db: Session,
        transfer_request_id: uuid.UUID,
        as_of_time: Optional[datetime] = None,
        persist: bool = True,
    ) -> List[GraphFinding]:
        """Run deterministic temporal graph pattern detection for a specific transfer.

        Strictly respects point-in-time cutoff: transfers occurring after as_of_time
        are excluded from graph construction.
        """
        transfer = db.get(TransferRequest, transfer_request_id)
        if not transfer:
            return []

        raw_cutoff = as_of_time or transfer.posted_at or transfer.created_at
        cutoff_time = _to_utc(raw_cutoff)
        # Bounded temporal analysis window: 48 hours preceding the target event
        window_start = cutoff_time - timedelta(hours=48)

        # 1. Fetch all authoritative transfers within the bounded time window up to cutoff_time
        stmt = (
            select(TransferRequest)
            .where(
                and_(
                    TransferRequest.status == "POSTED",
                    TransferRequest.created_at >= window_start,
                    TransferRequest.created_at <= cutoff_time,
                )
            )
            .order_by(TransferRequest.created_at.asc())
        )
        window_transfers = list(db.scalars(stmt).all())

        # Filter strictly up to cutoff_time (defense-in-depth against timezone misinterpretation)
        window_transfers = [t for t in window_transfers if _to_utc(t.created_at) <= cutoff_time]

        # If the target transfer is POSTED and within window, ensure it's in the list
        if transfer not in window_transfers and transfer.status == "POSTED" and _to_utc(transfer.created_at) <= cutoff_time:
            window_transfers.append(transfer)

        if not window_transfers:
            return []

        # 2. Build in-memory temporal directed graph
        # Node -> list of outgoing edges: (edge_transfer, dest_account_id, amount, timestamp)
        adj_out: Dict[uuid.UUID, List[TransferRequest]] = defaultdict(list)
        adj_in: Dict[uuid.UUID, List[TransferRequest]] = defaultdict(list)

        for txn in window_transfers:
            adj_out[txn.source_account_id].append(txn)
            adj_in[txn.destination_account_id].append(txn)

        src_id = transfer.source_account_id
        dst_id = transfer.destination_account_id
        findings: List[GraphFinding] = []

        # Pattern A: Fan-In (Pooling / Aggregation to Destination)
        fan_in_finding = LedgerGraphService._detect_fan_in(
            dst_id, adj_in[dst_id], cutoff_time, window_start
        )
        if fan_in_finding:
            findings.append(fan_in_finding)

        # Pattern B: Fan-Out (Dispersal from Source)
        fan_out_finding = LedgerGraphService._detect_fan_out(
            src_id, adj_out[src_id], cutoff_time, window_start
        )
        if fan_out_finding:
            findings.append(fan_out_finding)

        # Pattern C: Rapid Pass-Through (Mule Pipe at Source or Destination)
        pass_through_dst = LedgerGraphService._detect_rapid_pass_through(
            dst_id, adj_in[dst_id], adj_out[dst_id], cutoff_time
        )
        if pass_through_dst:
            findings.append(pass_through_dst)

        pass_through_src = LedgerGraphService._detect_rapid_pass_through(
            src_id, adj_in[src_id], adj_out[src_id], cutoff_time
        )
        if pass_through_src and (not pass_through_dst or pass_through_src.primary_account_id != pass_through_dst.primary_account_id):
            findings.append(pass_through_src)

        # Pattern D: Multi-Hop Layering Chain
        layering_finding = LedgerGraphService._detect_layering(
            transfer, adj_out, adj_in, cutoff_time
        )
        if layering_finding:
            findings.append(layering_finding)

        # Pattern E: Circular Transaction Flow (Cycles)
        circular_finding = LedgerGraphService._detect_cycles(
            transfer, adj_out, cutoff_time
        )
        if circular_finding:
            findings.append(circular_finding)

        # Pattern F: Burst Velocity
        burst_finding = LedgerGraphService._detect_burst_velocity(
            src_id, adj_out[src_id], cutoff_time
        )
        if burst_finding:
            findings.append(burst_finding)

        if persist and findings:
            for f in findings:
                db.add(f)
            db.commit()

        return findings

    @staticmethod
    def _detect_fan_in(
        target_account_id: uuid.UUID,
        incoming_txns: List[TransferRequest],
        cutoff_time: datetime,
        window_start: datetime,
    ) -> Optional[GraphFinding]:
        """Detect multiple distinct sources aggregating funds into a common account."""
        # Consider transfers in the last 24 hours
        recent_txns = [t for t in incoming_txns if _to_utc(t.created_at) >= cutoff_time - timedelta(hours=24)]
        distinct_sources = {t.source_account_id for t in recent_txns if t.source_account_id != target_account_id}

        if len(distinct_sources) >= 3 and len(recent_txns) >= 3:
            total_inflow = sum((Decimal(str(t.amount)) for t in recent_txns), Decimal("0.00"))
            severity = "HIGH" if len(distinct_sources) >= 5 or total_inflow >= Decimal("100000.00") else "MEDIUM"
            score = Decimal("0.8200") if severity == "HIGH" else Decimal("0.6500")

            earliest_time = min(_to_utc(t.created_at) for t in recent_txns)
            time_span_min = max(1, int((cutoff_time - earliest_time).total_seconds() / 60))

            explanation = (
                f"LedgerGraph Fan-In Pattern Detected: Account received {len(recent_txns)} incoming transfers "
                f"totaling ₹{total_inflow:,.2f} from {len(distinct_sources)} distinct source accounts within {time_span_min} minutes. "
                f"Heuristic indicator of fund funneling/aggregation. Benign lookalike: Merchant payment gateway, crowdfunding, or family pooling."
            )

            return GraphFinding(
                pattern_type="FAN_IN",
                detector_version=DETECTOR_VERSION,
                severity=severity,
                heuristic_score=score,
                primary_account_id=target_account_id,
                window_start=earliest_time,
                window_end=cutoff_time,
                involved_transfer_ids=[str(t.id) for t in recent_txns],
                involved_account_ids=[str(target_account_id)] + [str(s) for s in distinct_sources],
                evidence={
                    "in_degree": len(distinct_sources),
                    "transfer_count": len(recent_txns),
                    "total_inflow_inr": str(total_inflow),
                    "time_span_minutes": time_span_min,
                    "threshold_sources": 3,
                },
                explanation=explanation,
                review_status="PENDING",
            )
        return None

    @staticmethod
    def _detect_fan_out(
        source_account_id: uuid.UUID,
        outgoing_txns: List[TransferRequest],
        cutoff_time: datetime,
        window_start: datetime,
    ) -> Optional[GraphFinding]:
        """Detect an account dispersing funds to numerous distinct recipients rapidly."""
        recent_txns = [t for t in outgoing_txns if _to_utc(t.created_at) >= cutoff_time - timedelta(hours=24)]
        distinct_destinations = {t.destination_account_id for t in recent_txns if t.destination_account_id != source_account_id}

        if len(distinct_destinations) >= 3 and len(recent_txns) >= 3:
            total_outflow = sum((Decimal(str(t.amount)) for t in recent_txns), Decimal("0.00"))
            severity = "HIGH" if len(distinct_destinations) >= 5 or total_outflow >= Decimal("100000.00") else "MEDIUM"
            score = Decimal("0.8000") if severity == "HIGH" else Decimal("0.6200")

            earliest_time = min(_to_utc(t.created_at) for t in recent_txns)
            time_span_min = max(1, int((cutoff_time - earliest_time).total_seconds() / 60))

            explanation = (
                f"LedgerGraph Fan-Out Pattern Detected: Account dispersed {len(recent_txns)} transfers "
                f"totaling ₹{total_outflow:,.2f} to {len(distinct_destinations)} distinct recipients within {time_span_min} minutes. "
                f"Heuristic indicator of structured dispersal or smurfing. Benign lookalike: Corporate payroll or batch vendor settlements."
            )

            return GraphFinding(
                pattern_type="FAN_OUT",
                detector_version=DETECTOR_VERSION,
                severity=severity,
                heuristic_score=score,
                primary_account_id=source_account_id,
                window_start=earliest_time,
                window_end=cutoff_time,
                involved_transfer_ids=[str(t.id) for t in recent_txns],
                involved_account_ids=[str(source_account_id)] + [str(d) for d in distinct_destinations],
                evidence={
                    "out_degree": len(distinct_destinations),
                    "transfer_count": len(recent_txns),
                    "total_outflow_inr": str(total_outflow),
                    "time_span_minutes": time_span_min,
                    "threshold_destinations": 3,
                },
                explanation=explanation,
                review_status="PENDING",
            )
        return None

    @staticmethod
    def _detect_rapid_pass_through(
        account_id: uuid.UUID,
        incoming_txns: List[TransferRequest],
        outgoing_txns: List[TransferRequest],
        cutoff_time: datetime,
    ) -> Optional[GraphFinding]:
        """Detect an account receiving funds and quickly forwarding >= 70% onward."""
        # Find pairs of in -> out within 90 minutes
        for in_txn in reversed(incoming_txns):
            in_amt = Decimal(str(in_txn.amount))
            if in_amt <= Decimal("500.00"):
                continue

            for out_txn in outgoing_txns:
                t_in = _to_utc(in_txn.created_at)
                t_out = _to_utc(out_txn.created_at)
                if t_out >= t_in:
                    delta_sec = (t_out - t_in).total_seconds()
                    if 0 <= delta_sec <= 5400:  # <= 90 minutes
                        out_amt = Decimal(str(out_txn.amount))
                        ratio = out_amt / in_amt if in_amt > 0 else Decimal("0")
                        if Decimal("0.70") <= ratio <= Decimal("1.30"):
                            delta_min = max(1, int(delta_sec / 60))
                            severity = "CRITICAL" if in_amt >= Decimal("50000.00") else "HIGH"
                            score = Decimal("0.8900") if severity == "CRITICAL" else Decimal("0.7800")

                            explanation = (
                                f"LedgerGraph Rapid Pass-Through Detected: Account received ₹{in_amt:,.2f} "
                                f"(transfer {in_txn.id}) and forwarded ₹{out_amt:,.2f} (transfer {out_txn.id}) "
                                f"within {delta_min} minutes (pass-through ratio: {float(ratio)*100:.1f}%). "
                                f"Strong heuristic indicator of money-mule transit. Benign lookalike: Immediate debt repayment or instant bill settlement."
                            )

                            return GraphFinding(
                                pattern_type="RAPID_PASS_THROUGH",
                                detector_version=DETECTOR_VERSION,
                                severity=severity,
                                heuristic_score=score,
                                primary_account_id=account_id,
                                window_start=t_in,
                                window_end=t_out,
                                involved_transfer_ids=[str(in_txn.id), str(out_txn.id)],
                                involved_account_ids=[
                                    str(account_id),
                                    str(in_txn.source_account_id),
                                    str(out_txn.destination_account_id),
                                ],
                                evidence={
                                    "inflow_amount_inr": str(in_amt),
                                    "outflow_amount_inr": str(out_amt),
                                    "pass_through_ratio": f"{float(ratio):.4f}",
                                    "delta_minutes": delta_min,
                                    "threshold_ratio_min": "0.70",
                                },
                                explanation=explanation,
                                review_status="PENDING",
                            )
        return None

    @staticmethod
    def _detect_layering(
        current_txn: TransferRequest,
        adj_out: Dict[uuid.UUID, List[TransferRequest]],
        adj_in: Dict[uuid.UUID, List[TransferRequest]],
        cutoff_time: datetime,
    ) -> Optional[GraphFinding]:
        """Detect multi-hop directed chain of transfers (>= 3 hops) moving within a short period."""
        chains: List[List[TransferRequest]] = []

        def dfs_forward(path: List[TransferRequest], curr_node: uuid.UUID, depth: int):
            if depth >= 4:
                return
            for nxt_txn in adj_out[curr_node]:
                t_nxt = _to_utc(nxt_txn.created_at)
                t_prev = _to_utc(path[-1].created_at)
                if t_nxt >= t_prev:
                    delta_hours = (t_nxt - _to_utc(path[0].created_at)).total_seconds() / 3600
                    if delta_hours <= 12 and nxt_txn.destination_account_id not in [p.source_account_id for p in path]:
                        new_path = path + [nxt_txn]
                        if len(new_path) >= 3:
                            chains.append(new_path)
                        dfs_forward(new_path, nxt_txn.destination_account_id, depth + 1)

        # Backward search
        t_curr = _to_utc(current_txn.created_at)
        for prev_txn in adj_in[current_txn.source_account_id]:
            t_prev = _to_utc(prev_txn.created_at)
            if t_prev <= t_curr:
                delta_prev_hours = (t_curr - t_prev).total_seconds() / 3600
                if delta_prev_hours <= 12:
                    initial_path = [prev_txn, current_txn]
                    dfs_forward(initial_path, current_txn.destination_account_id, depth=2)

        if chains:
            longest_chain = max(chains, key=lambda c: len(c))
            hop_count = len(longest_chain)
            total_vol = sum((Decimal(str(t.amount)) for t in longest_chain), Decimal("0.00"))
            time_span_min = int((_to_utc(longest_chain[-1].created_at) - _to_utc(longest_chain[0].created_at)).total_seconds() / 60)

            node_ids = []
            for t in longest_chain:
                if str(t.source_account_id) not in node_ids:
                    node_ids.append(str(t.source_account_id))
                if str(t.destination_account_id) not in node_ids:
                    node_ids.append(str(t.destination_account_id))

            explanation = (
                f"LedgerGraph Multi-Hop Layering Detected: Funds moved across {hop_count} sequential account hops "
                f"in {time_span_min} minutes through accounts: {' -> '.join(node_ids)}. "
                f"Heuristic indicator of intermediate laundering layers designed to break audit trails. "
                f"Benign lookalike: Multi-party supply chain fulfillment or escrow disbursement."
            )

            return GraphFinding(
                pattern_type="MULTI_HOP_LAYERING",
                detector_version=DETECTOR_VERSION,
                severity="HIGH" if hop_count >= 4 else "MEDIUM",
                heuristic_score=Decimal("0.8400") if hop_count >= 4 else Decimal("0.7200"),
                primary_account_id=current_txn.source_account_id,
                window_start=_to_utc(longest_chain[0].created_at),
                window_end=_to_utc(longest_chain[-1].created_at),
                involved_transfer_ids=[str(t.id) for t in longest_chain],
                involved_account_ids=node_ids,
                evidence={
                    "hop_count": hop_count,
                    "chain_transfer_ids": [str(t.id) for t in longest_chain],
                    "time_span_minutes": time_span_min,
                    "cumulative_volume_inr": str(total_vol),
                },
                explanation=explanation,
                review_status="PENDING",
            )
        return None

    @staticmethod
    def _detect_cycles(
        current_txn: TransferRequest,
        adj_out: Dict[uuid.UUID, List[TransferRequest]],
        cutoff_time: datetime,
    ) -> Optional[GraphFinding]:
        """Detect circular transaction topology returning funds to an ancestor account."""
        start_node = current_txn.source_account_id
        target_node = current_txn.destination_account_id

        queue = deque([([current_txn], target_node)])
        found_cycles: List[List[TransferRequest]] = []

        while queue:
            path, curr = queue.popleft()
            if len(path) > 4:
                continue

            for nxt_txn in adj_out.get(curr, []):
                t_nxt = _to_utc(nxt_txn.created_at)
                t_prev = _to_utc(path[-1].created_at)
                if t_nxt >= t_prev:
                    delta_hours = (t_nxt - _to_utc(path[0].created_at)).total_seconds() / 3600
                    if delta_hours <= 24:
                        if nxt_txn.destination_account_id == start_node:
                            found_cycles.append(path + [nxt_txn])
                            break
                        elif nxt_txn.destination_account_id not in [p.source_account_id for p in path]:
                            queue.append((path + [nxt_txn], nxt_txn.destination_account_id))

        if found_cycles:
            cycle = min(found_cycles, key=lambda c: len(c))
            cycle_len = len(cycle)
            earliest = _to_utc(cycle[0].created_at)
            latest = _to_utc(cycle[-1].created_at)
            duration_min = max(1, int((latest - earliest).total_seconds() / 60))

            account_cycle = [str(cycle[0].source_account_id)]
            for t in cycle:
                account_cycle.append(str(t.destination_account_id))

            explanation = (
                f"LedgerGraph Circular Transaction Flow Detected: Directed flow completed a {cycle_len}-hop cycle "
                f"returning funds to initial account: {' -> '.join(account_cycle)} within {duration_min} minutes. "
                f"Heuristic indicator of wash transactions or artificial turnover inflation. Benign lookalike: Cancelled transaction refund or liquidity balancing."
            )

            return GraphFinding(
                pattern_type="CIRCULAR_FLOW",
                detector_version=DETECTOR_VERSION,
                severity="HIGH",
                heuristic_score=Decimal("0.8800"),
                primary_account_id=start_node,
                window_start=earliest,
                window_end=latest,
                involved_transfer_ids=[str(t.id) for t in cycle],
                involved_account_ids=account_cycle,
                evidence={
                    "cycle_length": cycle_len,
                    "cycle_path": account_cycle,
                    "duration_minutes": duration_min,
                },
                explanation=explanation,
                review_status="PENDING",
            )
        return None

    @staticmethod
    def _detect_burst_velocity(
        account_id: uuid.UUID,
        outgoing_txns: List[TransferRequest],
        cutoff_time: datetime,
    ) -> Optional[GraphFinding]:
        """Detect sudden high-frequency bursts of outgoing transfers within a short window."""
        ten_min_window = cutoff_time - timedelta(minutes=15)
        burst_txns = [t for t in outgoing_txns if _to_utc(t.created_at) >= ten_min_window and _to_utc(t.created_at) <= cutoff_time]

        if len(burst_txns) >= 4:
            total_amt = sum((Decimal(str(t.amount)) for t in burst_txns), Decimal("0.00"))
            time_span_sec = int((cutoff_time - _to_utc(burst_txns[0].created_at)).total_seconds())

            explanation = (
                f"LedgerGraph Burst Velocity Detected: Account initiated {len(burst_txns)} transfers "
                f"totaling ₹{total_amt:,.2f} in {time_span_sec} seconds ({len(burst_txns)*4}/hour rate). "
                f"Heuristic indicator of automated credential stuffing, bot withdrawal, or emergency account draining."
            )

            return GraphFinding(
                pattern_type="BURST_VELOCITY",
                detector_version=DETECTOR_VERSION,
                severity="HIGH",
                heuristic_score=Decimal("0.8500"),
                primary_account_id=account_id,
                window_start=_to_utc(burst_txns[0].created_at),
                window_end=cutoff_time,
                involved_transfer_ids=[str(t.id) for t in burst_txns],
                involved_account_ids=[str(account_id)] + [str(t.destination_account_id) for t in burst_txns],
                evidence={
                    "burst_count": len(burst_txns),
                    "time_span_seconds": time_span_sec,
                    "total_amount_inr": str(total_amt),
                    "threshold_count": 4,
                },
                explanation=explanation,
                review_status="PENDING",
            )
        return None

    @staticmethod
    def get_subgraph(
        db: Session,
        account_id: Optional[uuid.UUID] = None,
        transfer_id: Optional[uuid.UUID] = None,
        hops: int = 2,
        limit: int = 60,
    ) -> Dict[str, Any]:
        """Extract a bounded subgraph around an account or transfer for interactive visualization."""
        target_account_id = account_id

        if transfer_id and not target_account_id:
            transfer = db.get(TransferRequest, transfer_id)
            if transfer:
                target_account_id = transfer.source_account_id

        if not target_account_id:
            # Return the top active accounts across recent posted transfers
            stmt = (
                select(TransferRequest)
                .where(TransferRequest.status == "POSTED")
                .order_by(TransferRequest.created_at.desc())
                .limit(limit)
            )
            transfers = list(db.scalars(stmt).all())
        else:
            # Bounded BFS neighborhood expansion up to requested hops
            visited_accounts: Set[uuid.UUID] = {target_account_id}
            frontier: Set[uuid.UUID] = {target_account_id}
            transfers: List[TransferRequest] = []

            for _ in range(min(hops, 3)):
                if not frontier:
                    break
                stmt = (
                    select(TransferRequest)
                    .where(
                        and_(
                            TransferRequest.status == "POSTED",
                            or_(
                                TransferRequest.source_account_id.in_(frontier),
                                TransferRequest.destination_account_id.in_(frontier),
                            ),
                        )
                    )
                    .order_by(TransferRequest.created_at.desc())
                    .limit(limit)
                )
                hop_txns = list(db.scalars(stmt).all())
                new_frontier: Set[uuid.UUID] = set()
                for t in hop_txns:
                    if t not in transfers:
                        transfers.append(t)
                    for acc in (t.source_account_id, t.destination_account_id):
                        if acc not in visited_accounts:
                            visited_accounts.add(acc)
                            new_frontier.add(acc)
                frontier = new_frontier

        # Gather node details
        node_ids = set()
        for t in transfers:
            node_ids.add(t.source_account_id)
            node_ids.add(t.destination_account_id)

        accounts_map = {}
        if node_ids:
            acc_stmt = select(Account).where(Account.id.in_(node_ids))
            for acc in db.scalars(acc_stmt).all():
                cust_name = acc.customer.full_name if acc.customer else "System / Clearing"
                accounts_map[acc.id] = {
                    "id": str(acc.id),
                    "account_number": acc.account_number,
                    "account_type": acc.account_type,
                    "cached_balance": str(acc.cached_balance),
                    "customer_name": cust_name,
                    "status": acc.status,
                }

        nodes = [accounts_map[nid] for nid in node_ids if nid in accounts_map]
        edges = [
            {
                "id": str(t.id),
                "source": str(t.source_account_id),
                "target": str(t.destination_account_id),
                "amount": str(t.amount),
                "currency": t.currency,
                "created_at": t.created_at.isoformat(),
                "status": t.status,
            }
            for t in transfers
        ]

        # Fetch recent graph findings relating to these accounts
        findings_stmt = (
            select(GraphFinding)
            .where(GraphFinding.primary_account_id.in_(node_ids))
            .order_by(GraphFinding.created_at.desc())
            .limit(20)
        )
        findings = list(db.scalars(findings_stmt).all())

        return {
            "target_account_id": str(target_account_id) if target_account_id else None,
            "nodes": nodes,
            "edges": edges,
            "findings": [
                {
                    "id": str(f.id),
                    "pattern_type": f.pattern_type,
                    "severity": f.severity,
                    "heuristic_score": str(f.heuristic_score),
                    "primary_account_id": str(f.primary_account_id),
                    "explanation": f.explanation,
                    "evidence": f.evidence,
                    "created_at": f.created_at.isoformat(),
                    "review_status": f.review_status,
                }
                for f in findings
            ],
        }
