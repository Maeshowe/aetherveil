# NOFA — Normalized Order Flow Anomaly

**Relation to OBSIDIAN:** Intraday order flow interpretation layer.
**Source:** OrderFlowAnomaly Pine Script v1–v4 (TradingView) + microstructure math formulas.

---

## 1. What This Is and Why It Matters

OBSIDIAN operates on **daily aggregated** data — it sees the day's end result.
NOFA operates on **intraday bar-level** data — it sees what happened during the day.

Together:

```
OBSIDIAN (daily):  "QQQ is in Γ⁻ (liquidity vacuum) today"
     ↓ why? drill down ↓
NOFA (intraday):   "Strong sell flow at 10:15, absorbed at 590 strike.
                    Flow efficiency dropped to 0.12 — price barely moved
                    despite 2.8σ selling pressure → ABSORPTION detected"
```

**NOFA is the microscope. OBSIDIAN is the map.**

NOFA does NOT generate signals. Like OBSIDIAN, it classifies what is happening, not what to do.

---

## 2. Mathematical Foundation

### 2.1 Signed Volume & Imbalance

Source: microstructure formulas image (math_formulas.png)

**Trade volume decomposition:**
```
V_t = trade volume in interval t
V⁺_t, V⁻_t = buy/sell volume
I_t = V⁺_t - V⁻_t  (signed imbalance)
```

**Bounded imbalance** (unitless, ∈ [-1, 1]):
```
ι_t = (V⁺_t - V⁻_t) / (V⁺_t + V⁻_t + ε),  ε > 0
```

In Pine Script (without tick data, approximated via candle direction):
```
signed_volume = volume × candle_direction
imbalance = Σ(signed_volume, N) / (Σ(volume, N) + ε)
```

**Limitation:** TradingView has no tick-level aggressor data. Candle direction is a proxy. Real order flow requires Level 2 / trade-and-quote data.

### 2.2 Intraday Seasonality Normalization

Volume varies systematically by time-of-day (high at open/close, low at lunch).

**Time-of-day bucket τ(t):**
```
Ṽ_t = V_t / E[V | τ(t)]
Ĩ_t = I_t / E[|I| | τ(t)]
```

This removes session bias. A volume spike at 12:30 means more than the same spike at 9:30.

### 2.3 Z-Score Normalization

**Standard:**
```
Z_V(t) = (V_t - μ̂_V(τ(t))) / σ̂_V(τ(t))
Z_I(t) = (I_t - μ̂_I(τ(t))) / σ̂_I(τ(t))
```

**Robust (MAD-based, heavy-tail tolerant):**
```
σ̂_MAD(τ) = 1.4826 × median(|X - median(X)| | τ)
```

### 2.4 Depth-Normalized Imbalance

When order book data is available (not on TradingView, but available via API):
```
ι_t^depth = (D_t^b - D_t^a) / (D_t^b + D_t^a + ε)
```
Where D^b, D^a = top-of-book bid/ask depths.

### 2.5 Feature Vector

The full normalized microstructure state:
```
φ_t = (Z_V(t), Z_I(t), ι_t, ι_t^depth)
```

---

## 3. Pine Script Evolution (v1 → v4)

### v1: Foundation
- Signed volume proxy (candle direction)
- Bounded imbalance [-1, 1]
- Seasonality normalization
- Z-score composite (additive: w_v × Z_vol + w_i × Z_imb)
- Fixed thresholds (±2σ, ±3σ)

### v2: Anomaly Gating
- **Key innovation:** Activity and direction as separate anomalies
- **Multiplicative mode:** Both must be unusual for signal
  - `score = sign(direction) × √(|activity_anom| × |direction_anom|)`
- **Anomaly gate:** minimum σ threshold before component contributes
- Adaptive thresholds (percentile-based instead of fixed)
- State change detection

### v3: Validity Score + State Machine
- **Validity score (0-100):** "Is this anomaly interpretable?"
  - Components: activity threshold, direction threshold, persistence, context
- **State machine:** QUIET → BUILDING → ACTIVE → PEAK → FADING
  - Tracks regime lifecycle, not just point-in-time level
- Score weighting by validity

### v4: Interpretation Layer (current)
- **Flow Efficiency:** price_change / cumulative_flow — the key absorption metric
- **Absorption detection:** persistent flow + price doesn't respond
- **Distribution detection:** flow decaying + price stable
- **MM Control / Chop:** zero-crosses + low persistence + range compression
- **NO-TRADE zone:** explicit marking of untradeable conditions
  - Extreme flow without price response (trap)
  - Conflicting states
  - Very low flow efficiency
  - Chop zone
- **Priority order:** NO-TRADE > ABSORPTION > DISTRIBUTION > MM CONTROL > NORMAL
- **Interpretation labels** on chart with state-change detection

---

## 4. OBSIDIAN Integration Points

### 4.1 Where NOFA Features Map to OBSIDIAN

| NOFA Concept | OBSIDIAN Equivalent | Integration |
|-------------|---------------------|-------------|
| Flow Efficiency | Price Efficiency (Section 4.7) | Same concept: range/volume ratio |
| Absorption detection | ABS regime | NOFA provides intraday granularity |
| Distribution detection | DIST regime | NOFA shows the process, OBSIDIAN the daily result |
| MM Control / Chop | Γ⁺ (gamma-positive control) | Overlapping but different perspective |
| NO-TRADE zone | No direct equivalent | Dashboard warning overlay |
| Activity anomaly | Z_dark, Z_block (unusual activity) | Different data source, same concept |
| Direction anomaly | Z_DEX (directional pressure) | NOFA = price-based, OBSIDIAN = delta-based |
| Bounded imbalance | Unitless imbalance ι_t | Identical mathematical construction |

### 4.2 Integration Architecture

```
OBSIDIAN Daily Pipeline
├─ Feature Extraction (dark pool, GEX, DEX, IV...)
├─ Scoring → U_t
├─ Classification → R_t
├─ Explainability → text
│
└─ [v2+] NOFA Intraday Drill-Down
    ├─ Run on CORE ETFs (SPY, QQQ, IWM, DIA)
    ├─ Run on stressed FOCUS tickers (U_t > 70)
    ├─ Detect: absorption, distribution, MM control, no-trade
    └─ Enrich explainability:
        "QQQ Γ⁻ — NOFA shows absorption at 590 strike level,
         flow efficiency 0.12 (normal: 0.45), sell flow persistent
         but price flat → dealer absorption confirmed"
```

### 4.3 Data Source Difference

| Aspect | Pine Script (TradingView) | OBSIDIAN Python (API) |
|--------|--------------------------|----------------------|
| Volume direction | Candle proxy (open vs close) | UW: bid_volume, ask_volume, sweep_volume |
| Depth data | Not available | UW: option OI as proxy |
| Granularity | Any bar (1m, 5m, 15m...) | Daily aggregated (v1), intraday expansion (v2+) |
| Greeks | Not available | UW: GEX, DEX, Vanna, Charm |
| Dark pool | Not available | UW: dark pool prints with size |

**Key advantage of OBSIDIAN over Pine Script:**
- Access to actual signed order flow (bid/ask volume from UW), not candle proxy
- Access to options Greeks (GEX, DEX) for regime classification
- Access to dark pool data for institutional activity
- Cross-instrument analysis (CORE + FOCUS)

---

## 5. Implementation Plan for OBSIDIAN

### Phase 1 (v1): Daily-Only — Already in Build Order
OBSIDIAN runs on daily data. The Price Efficiency and Price Impact features (Spec Section 4.7-4.8) already capture the same concept as NOFA's flow efficiency at daily granularity.

**No extra work needed** — the OBSIDIAN spec already covers this.

### Phase 2 (v2+): Intraday NOFA Module
When OBSIDIAN expands to intraday analysis:

```
src/obsidian/
├─ nofa/                           # NEW: NOFA intraday module
│   ├─ __init__.py
│   ├─ signed_volume.py            # Buy/sell volume from UW data
│   ├─ imbalance.py                # Bounded imbalance calculation
│   ├─ seasonality.py              # Time-of-day normalization
│   ├─ flow_efficiency.py          # Price response vs flow intensity
│   ├─ interpretation.py           # Absorption, distribution, MM control, no-trade
│   └─ models.py                   # NOFAResult dataclass
```

**Data requirement:** Intraday bar data from Polygon (1m/5m/15m aggregates) + intraday options flow from UW.

### Phase 3 (v3+): Real-Time Dashboard
- NOFA as a live panel within the Streamlit dashboard
- Intraday chart with NOFA overlay
- Real-time flow efficiency + interpretation state

---

## 6. What to Keep from Pine Scripts

### Keep (translate to Python):
- Bounded imbalance formula: `ι = Σ(signed_vol) / (Σ(vol) + ε)`
- Seasonality normalization: volume / E[volume | time_of_day]
- Flow efficiency: `price_change_norm / cumulative_flow`
- Absorption logic: persistent flow + price doesn't respond
- Distribution logic: flow decaying + price stable
- MM Control: zero-crosses + low persistence + range compression
- NO-TRADE conditions: mismatch, conflicting states, low efficiency
- Interpretation priority: NO-TRADE > ABSORPTION > DISTRIBUTION > MM CONTROL > NORMAL
- Adaptive thresholds (percentile-based)
- Multiplicative anomaly gating: both activity AND direction must be unusual

### Discard (Pine-specific, not needed):
- Candle direction proxy (we have real bid/ask volume from UW API)
- All visualization code (hline, plot, label, table — Streamlit handles this)
- Alert conditions (Pine alert system)
- Input group organization (Pine UI)

### Upgrade (better data available via API):
- Signed volume: use UW `bid_volume` / `ask_volume` instead of candle proxy
- Imbalance: real trade-level imbalance from UW dark pool + options flow
- Depth: option OI at strike as depth proxy (UW option-contracts)
- Greeks: GEX/DEX for absorption/distribution context (unavailable in Pine)

---

## 7. Pine Scripts as Reference

The 4 Pine Script versions are archived in `reference/pine/` for reference:

| File | Version | Key Feature | Lines |
|------|---------|-------------|-------|
| `OrderFlowAnomaly.pine` | v1 | Foundation: seasonality, z-score, composite | 340 |
| `OrderFlowAnomaly_v2.pine` | v2 | Multiplicative gating, adaptive thresholds | 388 |
| `OrderFlowAnomaly_v3.pine` | v3 | Validity score, state machine | 425 |
| `OrderFlowAnomaly_v4.pine` | v4 | Interpretation layer, absorption, no-trade | 557 |

These are **read-only reference**, not code to execute. The Python implementation will use better data sources and different architecture.

---

## 8. Summary: How the Pieces Fit

```
┌─────────────────────────────────────────────────┐
│              OBSIDIAN MM System                  │
│                                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ DAILY LAYER (v1 — current build)            │ │
│  │                                              │ │
│  │  API Data → Features → Z-scores → U_t, R_t  │ │
│  │  (dark pool, GEX, DEX, IV, OHLCV)          │ │
│  │  Output: "QQQ is Γ⁻ today, U=82"           │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │                            │
│                     │ drill down (v2+)           │
│                     ▼                            │
│  ┌─────────────────────────────────────────────┐ │
│  │ INTRADAY LAYER — NOFA Module (future)       │ │
│  │                                              │ │
│  │  Intraday bars → Imbalance → Seasonality    │ │
│  │  → Flow Efficiency → Interpretation          │ │
│  │  Output: "Absorption at 590, flow eff 0.12" │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │                            │
│                     │ context                    │
│                     ▼                            │
│  ┌─────────────────────────────────────────────┐ │
│  │ FOCUS UNIVERSE (dynamic)                     │ │
│  │                                              │ │
│  │  Which names are driving the stress?         │ │
│  │  Output: "NVDA (Γ⁻, U=91) + AAPL (ABS)"   │ │
│  └─────────────────────────────────────────────┘ │
│                                                  │
│  Math: formulas image (math_formulas.png)        │
│  Pine ref: reference/pine/*.pine                 │
└─────────────────────────────────────────────────┘
```
