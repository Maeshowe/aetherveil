# OBSIDIAN MM User Guide

**For retail quants, traders, and microstructure analysts**

This guide explains how to use OBSIDIAN MM to analyze market microstructure patterns and interpret diagnostic output.

---

## Table of Contents

1. [What is OBSIDIAN MM?](#what-is-obsidian-mm)
2. [Installation](#installation)
3. [Running Diagnostics](#running-diagnostics)
4. [Understanding Output](#understanding-output)
5. [Regime Types](#regime-types)
6. [Unusualness Scores](#unusualness-scores)
7. [Interpreting Results](#interpreting-results)
8. [Limitations](#limitations)
9. [FAQ](#faq)

---

## What is OBSIDIAN MM?

OBSIDIAN MM is a **diagnostic engine** that analyzes daily market microstructure to classify institutional and dealer behavior. It answers the question:

> **"What regime is the market maker operating in today?"**

It does **NOT** answer:
- "What will the price do tomorrow?"
- "Should I buy or sell?"
- "What's the probability of an up move?"

OBSIDIAN MM is **diagnostic**, not **predictive**. It helps you understand current microstructure conditions, not forecast future prices.

---

## Installation

### Prerequisites

- Python 3.12 or higher
- Basic command-line familiarity

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/aetherveil/obsidian-mm.git
cd obsidian-mm

# 2. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install package
pip install -e .

# 4. Verify installation
python -m obsidian.cli version
```

You should see:
```
OBSIDIAN MM v0.1.0
Market-Maker Regime Engine
```

---

## Running Diagnostics

### Basic Command

```bash
python -m obsidian.cli diagnose SPY
```

This analyzes SPY (S&P 500 ETF) for the latest available date.

### With Specific Date

```bash
python -m obsidian.cli diagnose SPY --date 2024-01-15
```

### JSON Output

```bash
python -m obsidian.cli diagnose SPY --format json
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--date` | Date in YYYY-MM-DD format | Latest available |
| `--format` | Output format (text or json) | text |
| `--cache-dir` | Directory for cached data | ./data |
| `--no-cache` | Skip cache, fetch fresh data | False |

---

## Understanding Output

### Example Diagnostic

```
=== OBSIDIAN MM Diagnostic: SPY @ 2024-01-15 ===

Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
Z_GEX = -2.3100 (threshold: -1.5000) ✓
Impact_vs_median = 0.0087 (threshold: 0.0052) ✓

Unusualness: 78 (Unusual)
Top drivers: GEX contrib=0.58; DARK_SHARE contrib=0.46

Excluded: charm (n = 9 < 21)
Baseline: PARTIAL
```

### Breaking It Down

#### 1. Header
```
=== OBSIDIAN MM Diagnostic: SPY @ 2024-01-15 ===
```
- **Ticker**: SPY
- **Date**: 2024-01-15

#### 2. Regime Classification
```
Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
```
- **Regime Type**: Γ⁻ (gamma-negative)
- **Description**: Dealers are short gamma, amplifying moves

#### 3. Triggering Conditions
```
Z_GEX = -2.3100 (threshold: -1.5000) ✓
Impact_vs_median = 0.0087 (threshold: 0.0052) ✓
```
- **Z_GEX = -2.31**: Gamma exposure is -2.31 standard deviations below normal
- **Threshold**: < -1.5 (rule requirement)
- **✓**: Condition met
- **Impact > median**: Price impact is above the 63-day median

#### 4. Unusualness Score
```
Unusualness: 78 (Unusual)
```
- **Score**: 78 out of 100
- **Interpretation**: "Unusual" band (60-80th percentile)
- Higher = more unusual microstructure

#### 5. Top Drivers
```
Top drivers: GEX contrib=0.58; DARK_SHARE contrib=0.46
```
- **GEX**: Contributes 0.58 to the raw score
- **DARK_SHARE**: Contributes 0.46 to the raw score
- These are the primary features driving the unusualness

#### 6. Excluded Features
```
Excluded: charm (n = 9 < 21)
```
- **Charm**: Excluded because only 9 observations available (need ≥ 21)
- Transparency: you always know what's missing

#### 7. Baseline State
```
Baseline: PARTIAL
```
- **PARTIAL**: Some features have valid baselines, some don't
- **COMPLETE**: All features have valid baselines (n ≥ 21)
- **EMPTY**: No features have valid baselines (cold start)

---

## Regime Types

OBSIDIAN MM classifies market microstructure into **7 regimes**, evaluated in **priority order** (first match wins).

### 1. Γ⁺ (Gamma-Positive Control)
**Symbol**: Γ⁺
**Triggering**: Z_GEX > +1.5 AND Efficiency < median

**Interpretation**: Dealers are significantly **long gamma**. Their hedging activity compresses the intraday range, resulting in below-normal price efficiency. This is a **volatility suppression** regime.

**What it means**:
- Low realized volatility expected
- Tight trading ranges
- Dealer hedging dampens price moves

---

### 2. Γ⁻ (Gamma-Negative Liquidity Vacuum)
**Symbol**: Γ⁻
**Triggering**: Z_GEX < −1.5 AND Impact > median

**Interpretation**: Dealers are significantly **short gamma**. Their hedging **amplifies** directional moves. Above-normal price impact per unit volume signals a **liquidity vacuum**.

**What it means**:
- High realized volatility expected
- Large intraday swings
- Dealer hedging accelerates moves

---

### 3. DD (Dark-Dominant Accumulation)
**Symbol**: DD
**Triggering**: DarkShare > 0.70 AND Z_block > +1.0

**Interpretation**: More than **70% of volume** is executing off-exchange, with block-print intensity elevated above +1σ. Consistent with **institutional positioning** via dark liquidity.

**What it means**:
- Large institutional players accumulating
- Minimal price impact (dark execution)
- Potentially building positions

---

### 4. ABS (Absorption-Like)
**Symbol**: ABS
**Triggering**: Z_DEX < −1.0 AND return ≥ −0.5% AND DarkShare > 0.50

**Interpretation**: Net delta exposure is significantly **negative** (sell pressure), but the daily move is no worse than −0.5%, and dark pool participation exceeds 50%. **Passive buying** is absorbing the sell flow.

**What it means**:
- Selling pressure being absorbed
- Price resilient despite selling
- Potential for reversal if absorption continues

---

### 5. DIST (Distribution-Like)
**Symbol**: DIST
**Triggering**: Z_DEX > +1.0 AND return ≤ +0.5%

**Interpretation**: Net delta exposure is significantly **positive** (buy pressure), but the daily move is no better than +0.5%. **Supply is being distributed** into strength without upside follow-through.

**What it means**:
- Buying pressure being distributed
- Price not responding to buying
- Potential for reversal if distribution continues

---

### 6. NEU (Neutral / Mixed)
**Symbol**: NEU
**Triggering**: No prior rule matched

**Interpretation**: No single microstructure pattern dominates. The instrument is in a **balanced or ambiguous** state.

**What it means**:
- No clear directional bias
- Mixed signals from different features
- Market in equilibrium

---

### 7. UND (Undetermined)
**Symbol**: UND
**Triggering**: Baseline insufficient OR all features excluded

**Interpretation**: System cannot classify. **Diagnosis withheld**.

**What it means**:
- Not enough historical data (cold start)
- All features missing or invalid
- Need more observations

---

## Unusualness Scores

The **unusualness score** (U_t) measures how unusual the current microstructure is compared to the past 63 trading days.

### Score Range: 0–100

| Score | Interpretation | Meaning |
|-------|---------------|---------|
| 0–30 | **Normal** | Microstructure within historical norms |
| 30–60 | **Elevated** | Measurable deviation; monitoring warranted |
| 60–80 | **Unusual** | Significant departure from baseline |
| 80–100 | **Extreme** | Rare microstructure configuration |

### What It Measures

The score is a **weighted sum of absolute z-scores** across 5 feature dimensions:

| Feature | Weight | What It Captures |
|---------|--------|------------------|
| Dark Pool Share | 0.25 | Institutional flow signal |
| GEX (Gamma Exposure) | 0.25 | Dealer positioning |
| Venue Mix | 0.20 | Execution structure deviation |
| Block Intensity | 0.15 | Large-print institutional activity |
| IV Skew | 0.15 | Options market stress |

**Important**: Weights are **conceptual allocations**, not optimized or tuned. They reflect microstructure relevance, not predictive power.

### How to Interpret

- **Low scores (0-30)**: Business as usual
- **Medium scores (30-60)**: Noteworthy but not alarming
- **High scores (60-80)**: Unusual conditions worth investigating
- **Extreme scores (80-100)**: Rare configurations; historical precedent analysis recommended

### What It Does NOT Mean

❌ **NOT a signal** — Score does not predict price direction
❌ **NOT a confidence** — High score ≠ high confidence of outcome
❌ **NOT a trade trigger** — Never use score alone for entry/exit

---

## Interpreting Results

### Case Study 1: Γ⁻ with High Unusualness

```
Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
Z_GEX = -2.31 (threshold: < -1.5) ✓
Impact_vs_median = 0.0087 (threshold: > 0.0052) ✓

Unusualness: 78 (Unusual)
Top drivers: GEX contrib=0.58; DARK_SHARE contrib=0.46
```

**What it tells you**:
1. Dealers are **short gamma** (-2.31σ below normal)
2. Price **impact is elevated** (above median)
3. Overall microstructure is **unusual** (78th percentile)
4. **GEX** and **dark share** are the main drivers

**Actionable insight**:
- Expect **volatile, directional moves**
- Dealer hedging will **amplify** any momentum
- Liquidity is **thin** (high price impact)
- Consider **position sizing** accordingly

**NOT actionable**:
- ❌ "Go long because it's unusual"
- ❌ "Sell because dealers are short gamma"
- ❌ "Buy volatility because score is 78"

---

### Case Study 2: DD with Low Unusualness

```
Regime: DD (Dark-Dominant Accumulation)
DarkShare = 0.75 (threshold: > 0.70) ✓
Z_block = 1.5 (threshold: > 1.0) ✓

Unusualness: 42 (Elevated)
Top drivers: DARK_SHARE contrib=0.40; BLOCK_INTENSITY contrib=0.30
```

**What it tells you**:
1. **75% of volume** executing off-exchange
2. **Block intensity** elevated (+1.5σ)
3. Microstructure is **elevated** but not extreme (42nd percentile)

**Actionable insight**:
- Large players are **accumulating quietly**
- **Low price impact** (dark execution)
- Potentially **early stage** of institutional positioning

**NOT actionable**:
- ❌ "Buy because institutions are accumulating"
- ❌ "Wait for score to hit 80 before acting"

---

### Case Study 3: NEU with Normal Score

```
Regime: NEU (Neutral / Mixed)

Unusualness: 25 (Normal)
Top drivers: VENUE_MIX contrib=0.12; GEX contrib=0.10

Excluded: none
Baseline: COMPLETE
```

**What it tells you**:
1. **No dominant pattern** — mixed signals
2. Microstructure is **normal** (25th percentile)
3. **All features valid** (complete baseline)

**Actionable insight**:
- Market is in **equilibrium**
- No extreme positioning or flow anomalies
- **Standard trading conditions**

**NOT actionable**:
- ❌ "Ignore because it's neutral"
- ❌ "Wait for a regime change"

---

## Limitations

### What OBSIDIAN MM Does NOT Do

1. **Does not predict prices**
   - O(t) ⇏ E[ΔP(t+1)]
   - Diagnostic only, never forecasts

2. **Does not generate signals**
   - No buy/sell recommendations
   - No entry/exit triggers

3. **Does not backtest**
   - No historical performance metrics
   - No Sharpe ratios or win rates

4. **Does not optimize**
   - Feature weights are **fixed conceptual allocations**
   - Never fitted to maximize profit

5. **Does not fill missing data**
   - NaN means NaN
   - Never imputed, interpolated, or approximated

### Data Requirements

- **Minimum observations**: 21 trading days per feature
- **Optimal window**: 63 trading days (1 quarter)
- **Cold start**: Expanding window for first 63 days
- **Missing data**: Features excluded if insufficient data

### Interpretation Cautions

⚠️ **Regime ≠ Signal**
A Γ⁻ regime does not mean "buy volatility" or "short the market"

⚠️ **Score ≠ Confidence**
An unusualness score of 80 does not mean "80% chance of..."

⚠️ **Past ≠ Future**
Historical regime transitions do not predict future transitions

⚠️ **Instrument Isolation**
SPY baseline ≠ AAPL baseline. Never compare scores across instruments.

---

## FAQ

### Q: Can I use OBSIDIAN MM for trading?

**A**: OBSIDIAN MM is a **diagnostic tool**, not a trading system. It provides **context** about current microstructure conditions but does not generate buy/sell signals. You can use it to:
- **Understand** current market conditions
- **Contextualize** price action
- **Inform** position sizing or risk management

You **cannot** use it to:
- Predict future price direction
- Generate entry/exit signals
- Calculate expected returns

---

### Q: Why is my unusualness score 0 (or very low)?

**A**: A low score means the current microstructure is **within historical norms**. This is **not a problem** — most days are normal. High scores are rare by design (only ~20% of days should score above 60).

---

### Q: What does "Excluded: charm (n = 9 < 21)" mean?

**A**: The "charm" feature was excluded from analysis because only 9 observations are available, but the system requires at least 21 to compute a valid z-score. This is **normal during cold start** (first few weeks) or if data is missing.

---

### Q: Can I change the feature weights?

**A**: No. The weights are **fixed conceptual allocations** reflecting microstructure relevance. They are **not tunable parameters**. Changing them would:
- Break reproducibility
- Enable overfitting
- Undermine the diagnostic philosophy

---

### Q: Why does the regime change every day?

**A**: Regime classification is **daily**. Microstructure conditions can change quickly. Frequent regime changes suggest:
- Market is **transitional**
- No stable pattern
- Conditions are **mixed**

This is **normal** — markets are not always in clear regimes.

---

### Q: What if I get "UND" (Undetermined)?

**A**: UND means the system cannot classify due to:
- **Insufficient baseline data** (cold start < 21 days)
- **All features excluded** (missing data)

**Solution**: Wait for more data to accumulate. After 21 trading days, the system should produce valid diagnostics.

---

### Q: Can I compare unusualness scores across different stocks?

**A**: **No.** Each instrument has its own baseline. SPY's 80 is **not comparable** to AAPL's 80. The score is **relative to the instrument's own history**, not absolute.

---

### Q: Is a Γ⁻ regime always bearish?

**A**: **No.** Γ⁻ means dealers are short gamma and hedging amplifies moves. This can create:
- **Large up moves** if the market rallies
- **Large down moves** if the market sells off

The regime describes **volatility characteristics**, not **directional bias**.

---

### Q: How often should I run diagnostics?

**A**: **Daily**, after market close. OBSIDIAN MM analyzes daily microstructure, so running it intraday is not meaningful. Use it to:
- Review the day's microstructure
- Plan for tomorrow's conditions
- Track regime transitions over time

---

### Q: What does "Baseline: PARTIAL" mean?

**A**: Some features have valid baselines (n ≥ 21), but others don't. This is **common** when:
- Different features have different data availability
- Some APIs are temporarily unavailable
- Cold start period for newer features

**Impact**: The diagnostic is still valid, but uses only the available features.

---

## Next Steps

1. **Experiment**: Run diagnostics on different instruments (SPY, QQQ, AAPL)
2. **Track**: Monitor regime changes over time (create a log)
3. **Contextualize**: Use diagnostics to understand price action
4. **Learn**: Compare diagnostics to actual market behavior

**Remember**: OBSIDIAN MM is a **tool for understanding**, not a **system for trading**.

---

## Support

For questions or issues:
- **Documentation**: [OBSIDIAN_MM_SPEC.md](../reference/OBSIDIAN_MM_SPEC.md)
- **GitHub Issues**: [Report a bug](https://github.com/aetherveil/obsidian-mm/issues)
- **Email**: [support@aetherveil.com]

---

*OBSIDIAN MM — Transparent microstructure diagnostics*
