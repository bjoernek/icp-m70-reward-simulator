# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An ICP (Internet Computer) asset canister serving an interactive voting rewards simulator. The frontend is plain HTML/JavaScript (no framework). All computation runs client-side.

## Development Commands

```bash
# Convert neuron pickle data to aggregated JSON (only needed if data changes)
python3 scripts/convert_data.py

# Local development with dfx
dfx start --background
dfx deploy

# Quick local test without dfx (serves src/frontend/)
cd src/frontend && python3 -m http.server 8765

# Deploy to mainnet (requires cycles)
dfx deploy --network ic
```

## Architecture

```
data/nonzero_neurons_processed_*.pkl (source, ~20 MB)
    |  scripts/convert_data.py (pre-aggregates by dissolve_delay_seconds)
    v
src/frontend/data/neuron_groups.json (~0.8 MB, ~21K groups)
    |
    v
src/frontend/  (asset canister)
  index.html   - single page with sidebar controls + chart canvases
  app.js       - ported simulation logic + Chart.js rendering
  style.css    - layout (flexbox sidebar + main, responsive)
  lib/chart.umd.min.js - Chart.js v4 (bundled locally)
```

The original Streamlit app (`voting_rewards_app_v2.py`) is kept for reference but is not part of the canister.

### Data Pre-aggregation

The conversion script groups ~58K neurons by `dissolve_delay_seconds` into ~21K groups. Each group stores: `[dd_seconds, weighted_stake_sum, current_vp_sum, is_8y]` where `weighted_stake_sum = sum((stake_e8s + staked_maturity_e8s) * age_bonus)`. This is valid because the bonus function depends only on dissolve delay, so neurons with the same delay share the same bonus multiplier.

### Key Constants

- `SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60`
- `TS = 550_776_194` (total supply, ICP)
- `R = 0.0575` (reward rate, 5.75%)
- `SCALE = 1e8` (e8s to ICP conversion)

### Core Functions (in `app.js`, ported from `voting_rewards_app_v2.py`)

- `mapDissolveDelays()`: transforms delays using Proportional Scaling or Piecewise Linear mapping
- `dissolveDelayBonusConvex()`: convex bonus curve `f(x) = a * x^n + b`
- `computeMetrics()`: iterates groups, computes new voting power, alpha, and inflation reduction
- APY formula: `APY = bonus(x) * TS / vp_total * R * alpha * 100`

### Canister Config

`dfx.json` defines a single asset canister (`frontend`) with source `["src/frontend"]`. No backend canister, no build step.
