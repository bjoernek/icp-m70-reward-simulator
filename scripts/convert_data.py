"""
Convert the preprocessed neuron pickle to a compact JSON file
for the frontend canister.

Groups neurons by dissolve_delay_seconds and pre-computes:
  - weighted_stake_sum = sum((stake_e8s + staked_maturity_e8s) * age_bonus)
  - current_vp_sum = sum(current_potential_voting_power)
  - is_8y = 1 if dissolve_delay_seconds == 8 * SECONDS_PER_YEAR else 0

Usage:
    python scripts/convert_data.py
"""

from pathlib import Path

import json
import pandas as pd

SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60
EIGHT_YEAR_SECONDS = int(8.0 * SECONDS_PER_YEAR)

def main():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    pkl_files = sorted(data_dir.glob("nonzero_neurons_processed_*.pkl"))
    if not pkl_files:
        raise FileNotFoundError(f"No processed pickle files found in {data_dir}")

    pkl_path = pkl_files[-1]
    print(f"Reading {pkl_path}")
    df = pd.read_pickle(pkl_path)
    print(f"Loaded {len(df)} neurons")

    # Compute weighted stake per neuron
    df["weighted_stake"] = (df["stake_e8s"] + df["staked_maturity_e8s"]) * df["age_bonus"]

    # Group by dissolve_delay_seconds
    grouped = df.groupby("dissolve_delay_seconds").agg(
        weighted_stake_sum=("weighted_stake", "sum"),
        current_vp_sum=("current_potential_voting_power", "sum"),
    ).reset_index()

    # Flag 8-year groups
    grouped["is_8y"] = (grouped["dissolve_delay_seconds"] == EIGHT_YEAR_SECONDS).astype(int)

    print(f"Collapsed to {len(grouped)} groups")

    # Build compact list-of-lists
    groups = []
    for _, row in grouped.iterrows():
        groups.append([
            int(row["dissolve_delay_seconds"]),
            row["weighted_stake_sum"],
            int(row["current_vp_sum"]),
            int(row["is_8y"]),
        ])

    output = {
        "neuron_count": len(df),
        "group_count": len(grouped),
        "source_file": pkl_path.name,
        "groups": groups,
    }

    out_path = Path(__file__).resolve().parent.parent / "src" / "frontend" / "data" / "neuron_groups.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {out_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
