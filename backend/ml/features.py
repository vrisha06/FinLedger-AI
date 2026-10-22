"""Feature Engineering Pipeline for FinLedger-AI Fraud Detection.

Constructs leakage-free temporal and behavioral features.
Guarantees that all historical rolling metrics exclusively use records
strictly prior to the transaction being scored (t < t_curr).
"""

from datetime import datetime, timezone
import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "amount",
    "log_amount",
    "hour_of_day",
    "is_night",
    "day_of_week",
    "is_weekend",
    "customer_tx_count",
    "customer_avg_amount",
    "amount_to_avg_ratio",
    "time_since_last_tx_sec",
    "tx_velocity_1h",
    "is_new_destination",
]


def _parse_timestamp(val) -> datetime:
    """Parse various timestamp representations into a timezone-aware UTC datetime."""
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
    # Parse string
    dt = pd.to_datetime(val)
    if dt.tzinfo is None:
        return dt.tz_localize("UTC").to_pydatetime()
    return dt.tz_convert("UTC").to_pydatetime()


def extract_features_df(df: pd.DataFrame) -> pd.DataFrame:
    """Extract tabular features from a chronological transaction DataFrame without future leakage.

    Args:
        df: DataFrame containing at least:
            ['transaction_id', 'timestamp', 'source_user_id',
             'source_account_id', 'destination_account_id', 'amount']

    Returns:
        pd.DataFrame: DataFrame containing exactly the columns in FEATURE_COLUMNS.
    """
    if df.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    # Work on a copy sorted chronologically
    work_df = df.copy()
    work_df["parsed_time"] = pd.to_datetime(work_df["timestamp"], utc=True)
    work_df.sort_values(by="parsed_time", inplace=True)

    # 1. Direct temporal transformations
    amounts = work_df["amount"].astype(float).values
    log_amounts = np.log1p(amounts)
    hours = work_df["parsed_time"].dt.hour.values
    is_nights = np.where((hours >= 1) & (hours <= 5), 1, 0)
    days_of_week = work_df["parsed_time"].dt.dayofweek.values
    is_weekends = np.where(days_of_week >= 5, 1, 0)

    # 2. Sequential state tracking per customer (strictly prior to each transaction)
    n_rows = len(work_df)
    customer_tx_counts = np.zeros(n_rows, dtype=int)
    customer_avg_amounts = np.zeros(n_rows, dtype=float)
    amount_to_avg_ratios = np.zeros(n_rows, dtype=float)
    time_since_lasts = np.zeros(n_rows, dtype=float)
    tx_velocity_1hs = np.zeros(n_rows, dtype=int)
    is_new_destinations = np.zeros(n_rows, dtype=int)

    # Per-customer history caches: user_id -> list of (timestamp_epoch, amount, dest_id)
    cust_history: dict[str, list[tuple[float, float, str]]] = {}
    cust_destinations: dict[str, set[str]] = {}

    timestamps_epoch = work_df["parsed_time"].astype("int64").values // 10**9
    user_ids = work_df["source_user_id"].astype(str).values
    dest_ids = work_df["destination_account_id"].astype(str).values

    for idx in range(n_rows):
        uid = user_ids[idx]
        amt = amounts[idx]
        ts_sec = timestamps_epoch[idx]
        did = dest_ids[idx]

        history = cust_history.get(uid, [])
        known_dests = cust_destinations.get(uid, set())

        # Extract features strictly from past transactions (prior to current idx)
        if not history:
            customer_tx_counts[idx] = 0
            customer_avg_amounts[idx] = amt  # Baseline is current amount if first
            amount_to_avg_ratios[idx] = 1.0
            time_since_lasts[idx] = 86400.0  # Default 1 day if first
            tx_velocity_1hs[idx] = 1
            is_new_destinations[idx] = 1
        else:
            n_prior = len(history)
            customer_tx_counts[idx] = n_prior

            # Historical average amount
            sum_prior = sum(h[1] for h in history)
            avg_prior = sum_prior / n_prior
            customer_avg_amounts[idx] = avg_prior
            amount_to_avg_ratios[idx] = amt / (avg_prior + 1e-4)

            # Elapsed seconds since last transaction
            last_ts = history[-1][0]
            elapsed = max(0.0, ts_sec - last_ts)
            time_since_lasts[idx] = elapsed

            # Velocity in trailing 1 hour (3600 seconds)
            one_hr_ago = ts_sec - 3600.0
            recent_count = sum(1 for h in history if h[0] >= one_hr_ago)
            tx_velocity_1hs[idx] = recent_count + 1  # Including current

            # Novel destination check
            is_new_destinations[idx] = 1 if did not in known_dests else 0

        # Update customer state AFTER computing features (strictly preventing leakage)
        if uid not in cust_history:
            cust_history[uid] = [(ts_sec, amt, did)]
            cust_destinations[uid] = {did}
        else:
            cust_history[uid].append((ts_sec, amt, did))
            cust_destinations[uid].add(did)

    features_df = pd.DataFrame(
        {
            "amount": amounts,
            "log_amount": log_amounts,
            "hour_of_day": hours,
            "is_night": is_nights,
            "day_of_week": days_of_week,
            "is_weekend": is_weekends,
            "customer_tx_count": customer_tx_counts,
            "customer_avg_amount": customer_avg_amounts,
            "amount_to_avg_ratio": amount_to_avg_ratios,
            "time_since_last_tx_sec": time_since_lasts,
            "tx_velocity_1h": tx_velocity_1hs,
            "is_new_destination": is_new_destinations,
        },
        index=work_df.index,
    )

    return features_df[FEATURE_COLUMNS]


def extract_single_features(
    amount: float,
    timestamp: datetime,
    destination_account_id: str,
    prior_transactions: list[dict],
) -> dict:
    """Extract features for a single real-time inference request using strictly prior customer history.

    Args:
        amount: Transaction amount (float).
        timestamp: Time of transfer (datetime).
        destination_account_id: Destination account UUID string.
        prior_transactions: List of historical dicts strictly prior to this transaction,
            each containing at least: 'amount', 'timestamp', 'destination_account_id'.

    Returns:
        dict: Mapped dictionary with all columns in FEATURE_COLUMNS.
    """
    ts = _parse_timestamp(timestamp)
    hour = ts.hour
    is_night = 1 if (hour >= 1 and hour <= 5) else 0
    dow = ts.weekday()
    is_weekend = 1 if dow >= 5 else 0

    amt_val = float(amount)
    log_amt = float(np.log1p(amt_val))

    if not prior_transactions:
        return {
            "amount": amt_val,
            "log_amount": log_amt,
            "hour_of_day": hour,
            "is_night": is_night,
            "day_of_week": dow,
            "is_weekend": is_weekend,
            "customer_tx_count": 0,
            "customer_avg_amount": amt_val,
            "amount_to_avg_ratio": 1.0,
            "time_since_last_tx_sec": 86400.0,
            "tx_velocity_1h": 1,
            "is_new_destination": 1,
        }

    # Sort prior transactions chronologically
    sorted_prior = []
    for p in prior_transactions:
        p_ts = _parse_timestamp(p["timestamp"])
        sorted_prior.append((p_ts, float(p["amount"]), str(p["destination_account_id"])))
    sorted_prior.sort(key=lambda x: x[0])

    n_prior = len(sorted_prior)
    avg_prior = sum(p[1] for p in sorted_prior) / n_prior
    ratio = amt_val / (avg_prior + 1e-4)

    last_tx_time = sorted_prior[-1][0]
    elapsed = max(0.0, (ts - last_tx_time).total_seconds())

    one_hr_ago = ts - pd.Timedelta(hours=1)
    velocity_1h = sum(1 for p in sorted_prior if p[0] >= one_hr_ago) + 1

    known_dests = {p[2] for p in sorted_prior}
    is_new = 1 if str(destination_account_id) not in known_dests else 0

    return {
        "amount": amt_val,
        "log_amount": log_amt,
        "hour_of_day": hour,
        "is_night": is_night,
        "day_of_week": dow,
        "is_weekend": is_weekend,
        "customer_tx_count": n_prior,
        "customer_avg_amount": round(avg_prior, 2),
        "amount_to_avg_ratio": round(ratio, 4),
        "time_since_last_tx_sec": round(elapsed, 1),
        "tx_velocity_1h": velocity_1h,
        "is_new_destination": is_new,
    }
