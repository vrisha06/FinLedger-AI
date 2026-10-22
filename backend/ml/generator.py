"""Synthetic Transaction Data Generator for FinLedger-AI.

Generates reproducible banking transaction datasets with realistic customer behavior,
diurnal activity cycles, log-normal transaction amount distributions, and five
deliberately injected ground-truth fraud scenarios.

Includes exploratory Benford's Law analysis evaluating first-digit divergence
on multi-scale financial amounts.
"""

from datetime import datetime, timedelta, timezone
import math
import uuid
from pathlib import Path
import numpy as np
import pandas as pd


# Ground-truth fraud scenario identifiers
SCENARIO_NONE = "NONE"
SCENARIO_VELOCITY_BURST = "VELOCITY_BURST"
SCENARIO_ZSCORE_OUTLIER = "ZSCORE_OUTLIER"
SCENARIO_RAPID_DRAIN = "RAPID_DRAIN"
SCENARIO_OFF_HOURS_HIGH_VALUE = "OFF_HOURS_HIGH_VALUE"
SCENARIO_STRUCTURING = "STRUCTURING"

ALL_FRAUD_SCENARIOS = [
    SCENARIO_VELOCITY_BURST,
    SCENARIO_ZSCORE_OUTLIER,
    SCENARIO_RAPID_DRAIN,
    SCENARIO_OFF_HOURS_HIGH_VALUE,
    SCENARIO_STRUCTURING,
]


def _get_diurnal_hour_weights() -> np.ndarray:
    """Return 24 normalized hourly weights reflecting human diurnal banking activity.

    Peaks during business and evening retail hours (09:00 - 21:00 IST).
    Low probability during night and early morning hours (01:00 - 05:00 IST).
    """
    # 24 hours: 00:00 to 23:00
    hourly_curve = np.array([
        0.010,  # 00:00
        0.005,  # 01:00 (Night lull)
        0.003,  # 02:00
        0.002,  # 03:00
        0.003,  # 04:00
        0.008,  # 05:00
        0.020,  # 06:00
        0.035,  # 07:00
        0.055,  # 08:00
        0.075,  # 09:00 (Morning business start)
        0.085,  # 10:00
        0.080,  # 11:00
        0.085,  # 12:00 (Lunch peak)
        0.075,  # 13:00
        0.070,  # 14:00
        0.070,  # 15:00
        0.065,  # 16:00
        0.070,  # 17:00
        0.080,  # 18:00 (Evening retail peak)
        0.075,  # 19:00
        0.065,  # 20:00
        0.050,  # 21:00
        0.030,  # 22:00
        0.017,  # 23:00
    ])
    return hourly_curve / hourly_curve.sum()


def evaluate_benford_law(amounts: pd.Series | np.ndarray) -> dict:
    """Evaluate mathematical conformance to Benford's Law on leading digits.

    Benford's Law states that in naturally occurring multi-scale datasets,
    the probability of the first digit d in {1..9} is:
        P(d) = log10(1 + 1/d)

    Application & Limitations:
    - Benford's Law is mathematically valid ONLY for continuous, multi-order-of-magnitude
      financial distributions spanning multiple powers of 10.
    - Fixed-amount retail payments, psychological pricing (e.g. 99, 999), or structured
      transfers naturally deviate from pure Benford distributions.
    - We treat Benford conformance as an exploratory statistical check, not as a standalone
      proof of real-world fraud detection efficacy.

    Returns:
        dict: Empirical frequencies, theoretical frequencies, and Mean Absolute Deviation (MAD).
    """
    # Clean amounts and extract first non-zero digit
    clean_series = pd.Series(amounts).dropna()
    first_digits = []
    for val in clean_series:
        val_str = f"{abs(float(val)):.2f}".replace(".", "").lstrip("0")
        if val_str and val_str[0].isdigit() and val_str[0] != "0":
            first_digits.append(int(val_str[0]))

    if not first_digits:
        return {"error": "No valid non-zero amounts found"}

    counts = pd.Series(first_digits).value_counts()
    n_total = len(first_digits)

    empirical = {}
    theoretical = {}
    mad_sum = 0.0

    for d in range(1, 10):
        emp_prob = counts.get(d, 0) / n_total
        theo_prob = math.log10(1.0 + 1.0 / d)
        empirical[str(d)] = round(float(emp_prob), 4)
        theoretical[str(d)] = round(float(theo_prob), 4)
        mad_sum += abs(emp_prob - theo_prob)

    mad = round(mad_sum / 9.0, 4)

    # Nigrini MAD conformance thresholds:
    # < 0.006: Close conformity
    # 0.006 - 0.012: Acceptable conformity
    # 0.012 - 0.015: Marginally acceptable
    # > 0.015: Non-conformity
    conformity = (
        "CLOSE_CONFORMITY" if mad < 0.006
        else "ACCEPTABLE_CONFORMITY" if mad < 0.012
        else "MARGINAL_CONFORMITY" if mad < 0.015
        else "NON_CONFORMITY"
    )

    return {
        "sample_size": n_total,
        "mean_absolute_deviation": mad,
        "conformity_evaluation": conformity,
        "empirical_frequencies": empirical,
        "theoretical_benford_frequencies": theoretical,
    }


def generate_synthetic_transactions(
    num_transactions: int = 10000,
    num_customers: int = 200,
    fraud_rate: float = 0.025,
    random_seed: int = 42,
    start_date: datetime | None = None,
    simulation_days: int = 30,
) -> pd.DataFrame:
    """Generate reproducible synthetic banking transactions with documented ground-truth labels.

    Args:
        num_transactions: Total records to generate (e.g. 5,000 - 50,000).
        num_customers: Size of simulated customer pool.
        fraud_rate: Target proportion of suspicious transactions (default ~2.5%).
        random_seed: Seed for NumPy random generator to ensure exact reproducibility.
        start_date: Starting timestamp for the simulation window (UTC).
        simulation_days: Window length in days.

    Returns:
        pd.DataFrame: Chronologically ordered transactions with ground-truth labels.
    """
    rng = np.random.default_rng(random_seed)

    if start_date is None:
        start_date = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Initialize customer profiles and baseline parameters
    customers = []
    for _ in range(num_customers):
        user_id = str(uuid.uuid4())
        account_id = str(uuid.uuid4())
        # Customer spending baseline: log-normal median amount between ₹1,000 and ₹6,000
        base_amount = float(rng.lognormal(mean=7.7, sigma=0.6))
        customers.append({
            "user_id": user_id,
            "account_id": account_id,
            "base_amount": round(base_amount, 2),
        })

    # Destination accounts pool (mix of existing customers and external destinations)
    external_destinations = [str(uuid.uuid4()) for _ in range(num_customers // 2)]
    all_destinations = [c["account_id"] for c in customers] + external_destinations

    # 2. Determine fraud transaction count
    target_fraud_count = int(num_transactions * fraud_rate)
    target_legit_count = num_transactions - target_fraud_count

    diurnal_weights = _get_diurnal_hour_weights()
    seconds_in_window = simulation_days * 86400

    # 3. Generate legitimate transactions
    records = []

    # Assign transaction counts to customers proportionally
    customer_probs = rng.dirichlet(np.ones(num_customers) * 1.5)
    selected_customers = rng.choice(customers, size=target_legit_count, p=customer_probs)

    # Distribute timestamps across simulation days weighted by diurnal curve
    day_offsets = rng.uniform(0, simulation_days, size=target_legit_count)
    hours = rng.choice(24, size=target_legit_count, p=diurnal_weights)
    minutes = rng.integers(0, 60, size=target_legit_count)
    seconds = rng.integers(0, 60, size=target_legit_count)

    for i in range(target_legit_count):
        cust = selected_customers[i]
        day = int(day_offsets[i])
        hr = int(hours[i])
        mn = int(minutes[i])
        sec = int(seconds[i])

        tx_time = start_date + timedelta(days=day, hours=hr, minutes=mn, seconds=sec)

        # Pick destination different from source
        dest_id = rng.choice(all_destinations)
        while dest_id == cust["account_id"]:
            dest_id = rng.choice(all_destinations)

        # Legitimate log-normal amount centered near customer's baseline
        amount = float(rng.lognormal(mean=math.log(cust["base_amount"]), sigma=0.55))
        amount = max(10.0, min(amount, 85000.0))
        amount = round(amount, 2)

        records.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": tx_time,
            "source_user_id": cust["user_id"],
            "source_account_id": cust["account_id"],
            "destination_account_id": dest_id,
            "amount": amount,
            "currency": "INR",
            "is_fraud": 0,
            "fraud_scenario": SCENARIO_NONE,
        })

    # 4. Inject distinct ground-truth fraud scenarios
    # Divide fraud scenarios roughly equally among the 5 categories
    scenario_counts = {sc: target_fraud_count // len(ALL_FRAUD_SCENARIOS) for sc in ALL_FRAUD_SCENARIOS}
    # Distribute remainder
    remainder = target_fraud_count - sum(scenario_counts.values())
    for sc in ALL_FRAUD_SCENARIOS[:remainder]:
        scenario_counts[sc] += 1

    # Scenario 1: VELOCITY_BURST (rapid multiple transactions within minutes)
    for _ in range(scenario_counts[SCENARIO_VELOCITY_BURST] // 4 + 1):
        cust = rng.choice(customers)
        burst_base_time = start_date + timedelta(
            days=int(rng.integers(2, simulation_days - 2)),
            hours=int(rng.integers(8, 20)),
            minutes=int(rng.integers(0, 50)),
        )
        burst_len = min(4, scenario_counts[SCENARIO_VELOCITY_BURST])
        for b in range(burst_len):
            dest_id = rng.choice(external_destinations)
            offset_sec = int(rng.integers(30, 180) * (b + 1))
            tx_time = burst_base_time + timedelta(seconds=offset_sec)
            amount = round(float(rng.uniform(3000.0, 12000.0)), 2)

            records.append({
                "transaction_id": str(uuid.uuid4()),
                "timestamp": tx_time,
                "source_user_id": cust["user_id"],
                "source_account_id": cust["account_id"],
                "destination_account_id": dest_id,
                "amount": amount,
                "currency": "INR",
                "is_fraud": 1,
                "fraud_scenario": SCENARIO_VELOCITY_BURST,
            })
            scenario_counts[SCENARIO_VELOCITY_BURST] -= 1
            if scenario_counts[SCENARIO_VELOCITY_BURST] <= 0:
                break

    # Scenario 2: ZSCORE_OUTLIER (sudden spike 6x to 15x customer historical baseline)
    while scenario_counts[SCENARIO_ZSCORE_OUTLIER] > 0:
        cust = rng.choice(customers)
        tx_time = start_date + timedelta(
            days=int(rng.integers(5, simulation_days - 1)),
            hours=int(rng.integers(9, 21)),
            minutes=int(rng.integers(0, 59)),
        )
        dest_id = rng.choice(external_destinations)
        # Spike far above baseline
        multiplier = float(rng.uniform(6.0, 15.0))
        amount = round(max(cust["base_amount"] * multiplier, 35000.0), 2)
        amount = min(amount, 99000.0)

        records.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": tx_time,
            "source_user_id": cust["user_id"],
            "source_account_id": cust["account_id"],
            "destination_account_id": dest_id,
            "amount": amount,
            "currency": "INR",
            "is_fraud": 1,
            "fraud_scenario": SCENARIO_ZSCORE_OUTLIER,
        })
        scenario_counts[SCENARIO_ZSCORE_OUTLIER] -= 1

    # Scenario 3: RAPID_DRAIN (rapid high-value draining transfers)
    while scenario_counts[SCENARIO_RAPID_DRAIN] > 0:
        cust = rng.choice(customers)
        drain_base_time = start_date + timedelta(
            days=int(rng.integers(3, simulation_days - 2)),
            hours=int(rng.integers(10, 18)),
            minutes=int(rng.integers(0, 45)),
        )
        dest_id = rng.choice(external_destinations)
        # Successive draining transfer
        amount = round(float(rng.uniform(25000.0, 60000.0)), 2)
        records.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": drain_base_time,
            "source_user_id": cust["user_id"],
            "source_account_id": cust["account_id"],
            "destination_account_id": dest_id,
            "amount": amount,
            "currency": "INR",
            "is_fraud": 1,
            "fraud_scenario": SCENARIO_RAPID_DRAIN,
        })
        scenario_counts[SCENARIO_RAPID_DRAIN] -= 1

    # Scenario 4: OFF_HOURS_HIGH_VALUE (high amount during 01:00 AM - 04:30 AM night lull)
    while scenario_counts[SCENARIO_OFF_HOURS_HIGH_VALUE] > 0:
        cust = rng.choice(customers)
        tx_time = start_date + timedelta(
            days=int(rng.integers(1, simulation_days)),
            hours=int(rng.integers(1, 4)),  # Strict night lull
            minutes=int(rng.integers(0, 59)),
            seconds=int(rng.integers(0, 59)),
        )
        dest_id = rng.choice(external_destinations)
        amount = round(float(rng.uniform(28000.0, 75000.0)), 2)

        records.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": tx_time,
            "source_user_id": cust["user_id"],
            "source_account_id": cust["account_id"],
            "destination_account_id": dest_id,
            "amount": amount,
            "currency": "INR",
            "is_fraud": 1,
            "fraud_scenario": SCENARIO_OFF_HOURS_HIGH_VALUE,
        })
        scenario_counts[SCENARIO_OFF_HOURS_HIGH_VALUE] -= 1

    # Scenario 5: STRUCTURING (amounts just below ₹50,000 regulatory reporting threshold)
    # Synthetic Demonstration Assumption: Simulates avoidance of ₹50k PAN requirement
    while scenario_counts[SCENARIO_STRUCTURING] > 0:
        cust = rng.choice(customers)
        tx_time = start_date + timedelta(
            days=int(rng.integers(1, simulation_days)),
            hours=int(rng.integers(9, 21)),
            minutes=int(rng.integers(0, 59)),
        )
        dest_id = rng.choice(external_destinations)
        # Amounts strictly in [48500.00, 49950.00]
        amount = round(float(rng.uniform(48500.0, 49950.0)), 2)

        records.append({
            "transaction_id": str(uuid.uuid4()),
            "timestamp": tx_time,
            "source_user_id": cust["user_id"],
            "source_account_id": cust["account_id"],
            "destination_account_id": dest_id,
            "amount": amount,
            "currency": "INR",
            "is_fraud": 1,
            "fraud_scenario": SCENARIO_STRUCTURING,
        })
        scenario_counts[SCENARIO_STRUCTURING] -= 1

    df = pd.DataFrame(records)

    # 5. Sort chronologically by timestamp
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Convert timestamp to ISO format string
    df["timestamp"] = df["timestamp"].apply(lambda t: t.isoformat())

    return df


def save_synthetic_dataset(
    df: pd.DataFrame,
    output_path: Path | str | None = None,
) -> Path:
    """Save generated transactions to the designated development data path."""
    if output_path is None:
        output_dir = Path(__file__).resolve().parent / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "synthetic_transactions.csv"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic banking transactions for FinLedger-AI.")
    parser.add_argument("--count", type=int, default=10000, help="Number of transactions to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random generator seed")
    parser.add_argument("--fraud-rate", type=float, default=0.025, help="Target fraud proportion")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--benford", action="store_true", help="Run Benford's Law analysis on generated amounts")
    args = parser.parse_args()

    print(f"Generating {args.count} synthetic transactions (seed={args.seed}, fraud_rate={args.fraud_rate:.1%})...")
    data = generate_synthetic_transactions(
        num_transactions=args.count,
        random_seed=args.seed,
        fraud_rate=args.fraud_rate,
    )
    saved_file = save_synthetic_dataset(data, args.output)
    print(f"Dataset successfully saved to: {saved_file}")
    print(f"Total rows: {len(data)}, Fraud count: {data['is_fraud'].sum()} ({data['is_fraud'].mean():.2%})")

    if args.benford:
        print("\n--- Benford's Law First-Digit Analysis (Legitimate Transactions) ---")
        legit_amounts = data[data["is_fraud"] == 0]["amount"]
        report = evaluate_benford_law(legit_amounts)
        print(f"Sample Size: {report['sample_size']}")
        print(f"Mean Absolute Deviation (MAD): {report['mean_absolute_deviation']} -> {report['conformity_evaluation']}")
        for digit, freq in report["empirical_frequencies"].items():
            theo = report["theoretical_benford_frequencies"][digit]
            print(f"  Digit {digit}: Empirical = {freq:.4f}, Theoretical = {theo:.4f}")
