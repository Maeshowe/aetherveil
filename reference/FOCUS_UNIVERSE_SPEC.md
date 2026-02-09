# OBSIDIAN Focus Universe Specification v1.0

**Scope:** Defines which instruments OBSIDIAN monitors, how they enter/exit, and how they relate to the diagnostic output.

---

## 1. Universe Structure

OBSIDIAN operates on a two-tier instrument universe:

```
OBSIDIAN UNIVERSE
├─ CORE (always on, fixed)
│   ├─ SPY   — broad market
│   ├─ QQQ   — growth / duration exposure
│   ├─ IWM   — small cap / liquidity stress proxy
│   └─ DIA   — value / old economy
│
└─ FOCUS (dynamic, explanatory)
    ├─ Index Heavyweights   — structural weight in index
    ├─ Stress Amplifiers    — gamma / liquidity anomaly
    └─ Event-Driven Names   — temporary, catalyst-based
```

### 1.1 CORE Tier

| Ticker | Role | Why |
|--------|------|-----|
| SPY | Broad market microstructure | First place gamma stress / liquidity vacuum appears |
| QQQ | Growth / duration exposure | Tech-heavy, sensitive to dealer positioning |
| IWM | Small cap / liquidity stress | Early warning for liquidity withdrawal |
| DIA | Value / old economy | Rotation signal, divergence from growth |

**Rules:**
- CORE tickers are **always monitored**. No entry/exit criteria.
- Full OBSIDIAN diagnostic pipeline runs on every CORE ticker every day.
- CORE tickers are the **primary diagnostic surface** — the system's backbone.

### 1.2 FOCUS Tier

Focus tickers are **dynamic, not static**. They enter and exit based on objective rules.

**Definition:**
> A Focus ticker is an instrument that, on a given day, has a disproportionately large structural impact on a CORE ETF's microstructure behavior.

Focus tickers serve three purposes:
1. **Explanation** — Why is QQQ in Γ⁻ today? → NVDA gamma stress.
2. **Localization** — Where is the stress concentrated?
3. **Stress source identification** — Which name is driving the regime?

**Focus tickers are NOT:**
- A watchlist
- Trade candidates
- Signal generators
- A static list of "favorites"

---

## 2. Focus Tier Entry Rules

A ticker enters the FOCUS tier if **at least one** of these conditions is true on a given day:

### 2.1 Index Weight Significance

```
Condition: ticker is in the Top N constituents by weight of any CORE ETF

SPY: Top 15 by weight
QQQ: Top 10 by weight
IWM: N/A (too fragmented — skip)
DIA: Top 10 by weight (30 components total)
```

**Source:** FMP `/stable/etf-holder` or equivalent index composition data.

These are **structural focus tickers** — they're always relevant because of their weight.

**Current structural focus (approximate, as of early 2025):**
AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, BRK.B, JPM, V, UNH, XOM, JNJ, MA, PG

This list shifts with market cap changes and index rebalancing.

### 2.2 Microstructure Stress Detection

```
Condition: ticker's OBSIDIAN Unusualness Score U_t ≥ 70
    OR  |Z_GEX| ≥ 2.0
    OR  DarkShare_t ≥ 0.65
    OR  |Z_block| ≥ 2.0
```

These are **stress amplifier** tickers — they may or may not be index heavyweights, but their microstructure is abnormal enough to potentially affect the broader market.

**Evaluation:** Requires OBSIDIAN pipeline to have already run on the ticker (chicken-and-egg handled by the Daily Pipeline — see Section 4).

### 2.3 Event-Driven Relevance

```
Condition: ticker has earnings within ±1 trading day
    OR  ticker is involved in index rebalancing (add/remove)
    OR  macro-sensitive day (CPI, FOMC, NFP) AND ticker is in Top 20 by options volume
```

These are **temporary focus tickers** — they enter for 1-3 days around the event.

**Source:**
- Earnings calendar: FMP `/stable/earning-calendar` or UW screener
- Index rebalancing: manual or news-based (v2: automated)
- Macro calendar: manual flag in config (v2: automated from economic calendar API)

---

## 3. Focus Tier Exit Rules

A ticker exits the FOCUS tier when:

```
NONE of the entry conditions (2.1, 2.2, 2.3) are true for 3 consecutive trading days.
```

The **3-day grace period** prevents oscillation at the boundary.

Exception: structural focus tickers (Rule 2.1) effectively never exit because index weights change slowly.

---

## 4. Daily Pipeline: Evaluation Order

The chicken-and-egg problem: stress detection (Rule 2.2) requires running OBSIDIAN on a ticker, but we don't know which tickers to run until we detect stress.

**Solution: two-pass daily pipeline.**

```
Pass 1: CORE + Structural Focus (always run)
  ├─ Run full OBSIDIAN on SPY, QQQ, IWM, DIA
  ├─ Run full OBSIDIAN on current structural focus tickers (Top N by weight)
  └─ Check event-driven rules (2.3) → add any event tickers

Pass 2: Stress Scan (conditional)
  ├─ For tickers NOT in Pass 1 universe:
  │   Light scan: fetch GEX, DarkShare, block data only
  │   If any stress threshold crossed → promote to FOCUS, run full pipeline
  └─ Output: final FOCUS tier for the day
```

### 4.1 Scan Universe for Pass 2

To keep Pass 2 manageable, the scan universe is bounded:

```
Scan candidates = S&P 500 components
                  MINUS tickers already in Pass 1
                  FILTERED to those with options volume > 1000 contracts/day (30d avg)
```

This typically yields 100-200 tickers for the light scan, which is fast because it only requires 2-3 API calls per ticker (GEX + dark pool).

### 4.2 Max Focus Tier Size

```
Max |FOCUS| = 30 tickers per day
```

If more than 30 tickers qualify, rank by a composite priority:
1. Structural focus tickers (always in)
2. Highest U_t score
3. Highest |Z_GEX|

This cap prevents pipeline overload and keeps the dashboard readable.

---

## 5. How Focus Tickers Appear in Output

### 5.1 In Explainability Text

When a CORE ETF gets a regime label, the explainability engine can reference focus tickers:

```
Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum) — QQQ
Unusualness: 82 (Extreme)
Top drivers: GEX |Z| = 2.47 × 0.25 = 0.62; Dark |Z| = 1.91 × 0.25 = 0.48

Focus context: Stress concentrated in NVDA (U=91, Γ⁻) and AAPL (U=74, ABS).
Combined QQQ weight: 18.2%. These names account for ~60% of QQQ GEX shift.
```

### 5.2 In Dashboard

The Daily State page for CORE ETFs includes an optional "Focus Decomposition" section:

```
┌─ QQQ: Γ⁻ (Gamma-Negative) — U=82 ────────────────────┐
│                                                         │
│  Top Drivers: GEX (0.62), DarkShare (0.48), IV (0.31)  │
│                                                         │
│  Focus Decomposition:                                   │
│  ┌──────┬────────┬───────┬──────────┬─────────────────┐ │
│  │ Name │ Weight │ U_t   │ Regime   │ Note            │ │
│  ├──────┼────────┼───────┼──────────┼─────────────────┤ │
│  │ NVDA │ 9.4%   │ 91    │ Γ⁻      │ Extreme GEX     │ │
│  │ AAPL │ 8.8%   │ 74    │ ABS     │ Elevated dark   │ │
│  │ MSFT │ 8.1%   │ 42    │ NEU     │ Normal          │ │
│  │ AMZN │ 5.3%   │ 38    │ NEU     │ Normal          │ │
│  └──────┴────────┴───────┴──────────┴─────────────────┘ │
│                                                         │
│  ⚠ 2/15 structural focus tickers in stress zone (>60)  │
└─────────────────────────────────────────────────────────┘
```

### 5.3 What Focus Tickers Do NOT Produce

- ❌ Trade signals
- ❌ Entry/exit points
- ❌ Directional predictions
- ❌ "Buy NVDA because it's in Γ⁻"

Focus tickers explain **why** a CORE ETF is in a given regime. That's all.

---

## 6. Critical Boundary — OBSIDIAN Integrity Rule

> **OBSIDIAN degrades when focus tickers become trade ideas.**

The moment you look at "NVDA U=91, Γ⁻" and think "short NVDA" instead of "QQQ is in a liquidity vacuum because of NVDA gamma stress" — the system has lost its purpose.

Focus tickers are **lenses**, not **targets**.

### 6.1 Implementation Guardrails

- Dashboard never shows entry/exit for focus tickers
- No P&L tracking on focus tickers
- No alerts framed as "NVDA is a short" — only "NVDA stress contributes to QQQ vacuum"
- Explainability text always frames focus context relative to CORE ETFs

---

## 7. Data Requirements per Tier

| Tier | Pipeline | API Calls/Ticker | Frequency |
|------|----------|------------------|-----------|
| CORE | Full OBSIDIAN (all features, scoring, regime, explainability) | ~8-10 | Daily, always |
| FOCUS (structural) | Full OBSIDIAN | ~8-10 | Daily, always |
| FOCUS (stress/event) | Full OBSIDIAN (after promotion) | ~8-10 | Daily, conditional |
| Scan candidates | Light scan (GEX + dark only) | 2-3 | Daily, Pass 2 |

### 7.1 API Budget Estimate (daily)

```
CORE:              4 × 10 =   40 calls
Structural Focus: 15 × 10 =  150 calls
Event Focus:       5 × 10 =   50 calls (peak)
Light Scan:      150 ×  3 =  450 calls

Total daily:     ~690 calls (well within API rate limits)
```

---

## 8. Parameter Registry (Focus Universe)

| Parameter | Value | Justification |
|-----------|-------|---------------|
| CORE tickers | SPY, QQQ, IWM, DIA | Fixed. Market structure nodes. |
| Structural top-N (SPY) | 15 | ~55% of index weight |
| Structural top-N (QQQ) | 10 | ~55% of index weight |
| Structural top-N (DIA) | 10 | 33% of components |
| Stress U_t threshold | ≥ 70 | "Unusual" band from main spec |
| Stress |Z_GEX| threshold | ≥ 2.0 | ~95th percentile |
| Stress DarkShare threshold | ≥ 0.65 | Near DD regime trigger |
| Stress |Z_block| threshold | ≥ 2.0 | ~95th percentile |
| Event window | ±1 trading day | Earnings, rebalancing |
| Exit grace period | 3 trading days | Anti-oscillation |
| Max FOCUS tier size | 30 | Dashboard readability + API budget |
| Scan universe | S&P 500, options vol > 1000 | Manageable, liquid names |

---

## 9. Build Order Integration

This spec adds the following to the OBSIDIAN build order:

| Phase | Step | Module | Depends On |
|-------|------|--------|------------|
| 2 | 4b | `src/obsidian/universe/` — Focus Universe Manager | Config, API Clients |
| 2 | 4c | `src/obsidian/universe/structural.py` — Index weight lookup | FMP client |
| 2 | 4d | `src/obsidian/universe/stress_scan.py` — Light scan + promotion | UW client, Features |
| 2 | 4e | `src/obsidian/universe/events.py` — Earnings/macro calendar | FMP client |
| 4 | 10b | Dashboard: Focus Decomposition section | Universe, Explainability |

---

## Appendix: Worked Example

**Date:** 2025-10-07 (hypothetical)

**Pass 1 results:**
- SPY: U=45, NEU
- QQQ: U=82, Γ⁻ ← unusual
- IWM: U=31, NEU
- DIA: U=28, NEU
- Structural focus: AAPL (U=74, ABS), NVDA (U=91, Γ⁻), MSFT (U=42, NEU), ...

**Pass 2 light scan:**
- CRWD: |Z_GEX| = 2.8 → promoted to FOCUS, full pipeline → U=88, Γ⁻
- TSLA: DarkShare = 0.71 → promoted to FOCUS, full pipeline → U=67, DD

**Final daily output:**

```
═══════════════════════════════════════════════════
OBSIDIAN MM — Daily Diagnostic — 2025-10-07
═══════════════════════════════════════════════════

CORE ETFs:
  SPY   U=45  NEU     Normal microstructure
  QQQ   U=82  Γ⁻      ⚠ LIQUIDITY VACUUM
  IWM   U=31  NEU     Normal microstructure
  DIA   U=28  NEU     Normal microstructure

QQQ Focus Decomposition:
  NVDA  (9.4%)  U=91  Γ⁻   Extreme GEX stress, dealers massively short gamma
  AAPL  (8.8%)  U=74  ABS   Elevated dark pool, passive buying absorbing flow
  CRWD  (0.3%)  U=88  Γ⁻   Promoted via stress scan — outsized GEX anomaly
  MSFT  (8.1%)  U=42  NEU   Normal

Explanation:
  QQQ liquidity vacuum driven primarily by NVDA dealer gamma
  stress (Z_GEX = -2.47). AAPL showing absorption pattern
  (DarkShare 2.1σ above baseline, price flat). CRWD flagged
  in stress scan — small index weight but extreme gamma
  dislocation may amplify QQQ hedging flows.

  Stress concentrated in 2/15 structural names + 1 scan promotion.
═══════════════════════════════════════════════════
```

This output answers: **"What kind of day is this?"** — not **"What should I trade?"**
