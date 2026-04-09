"""
Local Streamlit app to explore convex dissolve-delay parameters and inflation reduction.
Run with:
    streamlit run voting_rewards_app.py
"""

from __future__ import annotations

from typing import Union

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

#from load_nonzero_neurons import load_nonzero_neurons
from pathlib import Path


SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60
MONTHS_TO_YEARS = 1.0 / 12.0


# Load the latest processed neuron data from the data directory
def load_data() -> pd.DataFrame:
    data_dir = Path(__file__).resolve().parent / "data"
    pkl_files = sorted(data_dir.glob("nonzero_neurons_processed_*.pkl"))
    if not pkl_files:
        raise FileNotFoundError(f"No processed pickle files found in {data_dir}")
    return pd.read_pickle(pkl_files[-1])  # Use the latest by name (date-sorted)


def map_dissolve_delays(
    x_years: Union[float, pd.Series, np.ndarray],
    *,
    scheme: str,
    new_min_delay_years: float,
    new_max_delay_years: float,
) -> Union[float, pd.Series, np.ndarray]:
    """
    Map dissolve delays according to the selected scheme.
    
    Parameters
    ----------
    x_years : dissolve delays in years
    scheme : "simple_cap", "proportional_scaling", or "piecewise_linear"
    new_min_delay_years : target minimum dissolve delay
    new_max_delay_years : target maximum dissolve delay
    
    Returns
    -------
    Mapped dissolve delays in years
    """
    as_series = isinstance(x_years, pd.Series)
    x_arr = x_years.to_numpy(dtype=float) if as_series else np.asarray(x_years, dtype=float)
    
    if scheme == "simple_cap":
        # Simple cap: just limit to new_max_delay_years
        mapped = np.minimum(x_arr, new_max_delay_years)
    
    elif scheme == "proportional_scaling":
        # Proportional scaling: multiply all delays by (new_max / old_max)
        old_max = 8.0  # 8 years (current maximum delay)
        scaling_factor = new_max_delay_years / old_max
        mapped = x_arr * scaling_factor
    
    elif scheme == "piecewise_linear":
        # Piecewise linear mapping from [6 months, 8 years] to [new_min_delay_years, new_max_delay_years]
        old_min = 6.0 / 12.0  # 6 months in years (current minimum eligible delay)
        old_max = 8.0  # 8 years (current maximum delay)
        new_min = new_min_delay_years
        new_max = new_max_delay_years
        
        # Initialize mapped array as copy of original
        mapped = x_arr.copy()
        
        # For neurons with dissolve delay between old_min and old_max: linear interpolation
        mask = (x_arr >= old_min) & (x_arr <= old_max)
        mapped[mask] = new_min + (x_arr[mask] - old_min) / (old_max - old_min) * (new_max - new_min)
        
        # For neurons above old_max: cap at new_max
        mapped[x_arr > old_max] = new_max
        
        # For neurons between new_min and old_min: cap at new_min
        mask_mid = (x_arr >= new_min) & (x_arr < old_min)
        mapped[mask_mid] = new_min
        
        # For neurons below new_min: keep as is (no adjustment)
        # This is already handled since we copied x_arr
    
    else:
        raise ValueError(f"Unknown scheme: {scheme}")
    
    if as_series:
        return pd.Series(mapped, index=x_years.index, name="dissolve_delay_mapped")
    return mapped


def dissolve_delay_bonus_convex(
    x_years: Union[float, pd.Series, np.ndarray],
    *,
    min_delay_years: float,
    max_delay_years: float,
    min_bonus: float,
    max_bonus: float,
    n: float,
):
    """Convex dissolve-delay bonus function f(x) = a * x^n + b with caps."""
    as_series = isinstance(x_years, pd.Series)
    x_arr = x_years.to_numpy(dtype=float) if as_series else np.asarray(x_years, dtype=float)

    a = (max_bonus - min_bonus) / (max_delay_years ** n)
    x_capped = np.minimum(x_arr, max_delay_years)
    bonus = a * (x_capped ** n) + min_bonus
    #bonus = np.where(x_arr < min_delay_years, min_bonus, bonus)

    if as_series:
        return pd.Series(bonus, index=x_years.index, name="dissolve_delay_bonus_convex")
    return bonus


def compute_metrics(
    max_delay_years: float,
    max_bonus: float,
    convexity_n: float,
    min_delay_years: float,
    mapping_scheme: str,
    eight_year_bonus: float,
    min_bonus: float = 1.0,
) -> dict:
    df = load_data().copy()

    # Apply dissolve delay mapping according to selected scheme
    df["dissolve_delay_mapped"] = map_dissolve_delays(
        df["dissolve_delay_seconds"] / SECONDS_PER_YEAR,
        scheme=mapping_scheme,
        new_min_delay_years=min_delay_years,
        new_max_delay_years=max_delay_years,
    )

    # Compute bonus based on mapped dissolve delays
    df["dissolve_delay_bonus_convex"] = dissolve_delay_bonus_convex(
        df["dissolve_delay_mapped"],
        max_delay_years=max_delay_years,
        max_bonus=max_bonus,
        min_bonus=min_bonus,
        min_delay_years=min_delay_years,
        n=convexity_n,
    )

    mask = (df["dissolve_delay_mapped"]  >= min_delay_years)
    df["new_potential_voting_power"] = 0.0
    
    # Base calculation
    df.loc[mask, "new_potential_voting_power"] = (
        (df.loc[mask, "stake_e8s"] + df.loc[mask, "staked_maturity_e8s"])
        * df.loc[mask, "age_bonus"]
        * df.loc[mask, "dissolve_delay_bonus_convex"]
    )
    
    # Apply additional bonus for neurons with exactly 8 years dissolve delay
    eight_year_seconds = 8.0 * SECONDS_PER_YEAR
    mask_8y = df["dissolve_delay_seconds"] == eight_year_seconds
    df.loc[mask_8y, "new_potential_voting_power"] *= eight_year_bonus

    scale = 1e8
    current_vp_sum = df["current_potential_voting_power"].sum() / scale
    new_vp_sum = df["new_potential_voting_power"].sum() / scale

    dd_bonus_old = 1 + max_delay_years / 8.0
    dd_bonus_new = max_bonus
    alpha = dd_bonus_old / dd_bonus_new * (new_vp_sum / current_vp_sum) / eight_year_bonus
    inflation_reduction = np.round((1 - alpha) * 100, 2)

    return {
        "inflation_reduction_pct": inflation_reduction,
        "new_vp_sum": new_vp_sum,
        "current_vp_sum": current_vp_sum,
        "dd_bonus_old": dd_bonus_old,
        "dd_bonus_new": dd_bonus_new,
        "alpha": alpha,
    }


def main() -> None:
    st.title("Voting Rewards Scenario Explorer")
    #st.write("Adjust convex dissolve-delay parameters to see inflation reduction.")

    with st.sidebar:
        st.subheader("Parameters")
        max_delay_years = st.slider("Max dissolve delay (years)", min_value=1, max_value=8, value=2, step=1)
        min_delay_months = st.slider(
            "Min dissolve delay (months)", min_value=0.5, max_value=6.0, value=0.5, step=0.5
        )
        min_delay_years = min_delay_months * MONTHS_TO_YEARS
        
        max_bonus = st.selectbox("Max bonus", options=[2, 3, 4], index=1)
        convexity_n = st.selectbox("Convexity n", options=[1, 2, 3], index=1)
        
        st.markdown("---")
        st.subheader("Additional Bonuses")
        eight_year_bonus = st.selectbox(
            "8-year commitment bonus",
            options=[1.0, 1.1, 1.2, 1.3],
            index=1,
        )
        
        st.markdown("---")
        st.subheader("Dissolve Delay Mapping")
        mapping_scheme = st.selectbox(
            "Mapping scheme",
            options=["simple_cap", "proportional_scaling", "piecewise_linear"],
            format_func=lambda x: {
                "simple_cap": "Simple Cap",
                "proportional_scaling": "Proportional Scaling",
                "piecewise_linear": "Piecewise Linear"
            }[x],
            index=0,
            help="Simple Cap: neurons with dissolve delay > max are capped. "
                 "Proportional Scaling: all delays are multiplied by (new_max / 8y). "
                 "Piecewise Linear: neurons with 6mo-8y are linearly mapped to [min, max]."
        )

    metrics = compute_metrics(
        max_delay_years=float(max_delay_years),
        max_bonus=float(max_bonus),
        convexity_n=float(convexity_n),
        min_delay_years=float(min_delay_years),
        mapping_scheme=mapping_scheme,
        eight_year_bonus=float(eight_year_bonus),
    )


    raw_infl = metrics["inflation_reduction_pct"]
    raw_infl_pct = 0.0 if abs(raw_infl) < 0.01 else raw_infl
    st.metric("Inflation reduction (%)", f"{raw_infl_pct:.2f}")
    # compute inflation reduction scalar = 1 - inflation_reduction_pct / 100
    alpha = 1 - raw_infl / 100

    # Pie chart for inflation reduction vs remaining.
    reduced = float(np.clip(raw_infl, 0, 100))
    remaining = max(0.0, 100.0 - reduced)
    pie_df = pd.DataFrame(
        {"category": ["Reduced", "Remaining"], "value": [reduced, remaining]}
    )
    pie = (
        alt.Chart(pie_df)
        .mark_arc()
        .encode(theta="value", color="category")
        #.properties(title="Inflation Breakdown")
    )
    st.altair_chart(pie, use_container_width=True)

    # Plot bonus curve from 0 to selected max_delay_years.
    x = np.linspace(0, max_delay_years, 200)
    bonus_y = dissolve_delay_bonus_convex(
        x,
        max_delay_years=float(max_delay_years),
        max_bonus=float(max_bonus),
        min_bonus=1.0,
        min_delay_years=float(min_delay_years),
        n=float(convexity_n),
    )

    # APY curve: APY(x) = bonus(x) * TS / voting_power_convex * R(t)
    TS = 540_000_000  # total supply
    R = 0.0588       
    vp_convex = metrics["new_vp_sum"]
    if vp_convex > 0:
        apy_y = bonus_y * TS / vp_convex * R * 100 * alpha  # convert to percent
        # Zero out APY for delays below the minimum.
        apy_y[x < min_delay_years] = 0.0
    else:
        apy_y = np.full_like(bonus_y, 0.0)

    chart_df = pd.DataFrame({"years": x, "bonus": bonus_y, "apy_pct": apy_y})

    bonus_chart = (
        alt.Chart(chart_df)
        .mark_line()
        .encode(x=alt.X("years:Q", title="Dissolve delay (years)"),
                y=alt.Y("bonus:Q", title="Bonus"))
        .properties(title="Dissolve Delay Bonus")
    )
    st.altair_chart(bonus_chart, use_container_width=True)

    apy_chart = (
        alt.Chart(chart_df)
        .mark_line()
        .encode(x=alt.X("years:Q", title="Dissolve delay (years)"),
                y=alt.Y("apy_pct:Q", title="Neuron APY (%)"))
        .properties(title="Neuron APY (%)")
    )
    st.altair_chart(apy_chart, use_container_width=True)

    # Dissolve Delay Mapping visualization (always shown at bottom)
    st.subheader("Dissolve Delay Mapping")
    x_old = np.linspace(0, 8, 200)
    x_new = map_dissolve_delays(
        x_old, 
        scheme=mapping_scheme, 
        new_min_delay_years=float(min_delay_years),
        new_max_delay_years=float(max_delay_years)
    )
    
    mapping_df = pd.DataFrame({"old_delay": x_old, "new_delay": x_new})
    mapping_chart = (
        alt.Chart(mapping_df)
        .mark_line(color="steelblue", strokeWidth=2)
        .encode(
            x=alt.X("old_delay:Q", title="Original dissolve delay (years)", scale=alt.Scale(domain=[0, 8])),
            y=alt.Y("new_delay:Q", title="Mapped dissolve delay (years)", scale=alt.Scale(domain=[0, max_delay_years])),
        )
        .properties(title=f"Dissolve Delay Mapping: Old → New ({mapping_scheme.replace('_', ' ').title()})")
    )
    st.altair_chart(mapping_chart, use_container_width=True)


if __name__ == "__main__":
    main()

