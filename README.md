# ICP M70 Reward Simulator

An interactive simulator for exploring voting reward parameter changes under the [Mission 70](https://internetcomputer.org/whitepapers/mission70.pdf) proposal for the Internet Computer Protocol.

**Live app:** https://fe5jc-aaaaa-aaaam-aivbq-cai.icp0.io/

## What it does

The simulator lets you adjust proposed governance parameters and immediately see:

- **Inflation reduction (%):** how much the total voting reward amount shrinks compared to the current scheme, holding the neuron population constant
- **Max neuron APY:** the annualized yield for a neuron locked at maximum dissolve delay (no age bonus)
- **Max neuron APY with 8-year bonus:** same, for neurons with exactly 8 years dissolve delay

### Parameters

| Parameter | Description |
|---|---|
| Max dissolve delay | The new maximum dissolve delay (1-8 years) |
| Min dissolve delay | Minimum delay required to earn rewards (0.5-6 months) |
| Max bonus | Dissolve delay bonus multiplier at maximum delay (2x, 3x, or 4x) |
| Convexity n | Exponent of the bonus curve: 1=linear, 2=quadratic, 3=cubic |
| 8-year commitment bonus | Extra multiplier for neurons locked at exactly 8 years |

The bonus curve is `f(x) = a * x^n + min_bonus`, capped at max dissolve delay.

For further information see the [Mission 70 whitepaper](https://internetcomputer.org/whitepapers/mission70.pdf).

Inflation reduction is computed relative to the current scheme, normalized so that neurons at max delay earn the same base reward rate.

## Architecture

A frontend-only [ICP asset canister](https://internetcomputer.org/docs/building-apps/frontends/using-an-asset-canister) serving plain HTML/JS. All computation runs client-side. No backend canister.

Neuron data: snapshot of non-zero-stake neurons as of 2026-04-08, pre-aggregated to ~21K groups by dissolve delay (~800KB JSON). Total supply: 550,776,194 ICP. Reward rate: 5.75%.

## Local development

```bash
dfx start --background
dfx deploy
# Open the printed local URL
```

