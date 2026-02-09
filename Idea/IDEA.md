# OBSIDIAN MM — Market-Maker Regime Engine

## Mi ez?

Egy **magyarázható market microstructure diagnosztikai rendszer**, ami naponta megmondja minden egyes részvényről: „milyen napot élünk?" — nem azt, hogy mit vegyünk, hanem azt, hogy milyen rezsimben működik a piac.

Kimenet részvényenként, naponta:
- **MM Unusualness Score** (U ∈ [0, 100]) — mennyire szokatlan ma a mikrostruktúra
- **Regime Label** — mi történik (Γ⁺, Γ⁻, DD, ABS, DIST, NEU, UND)
- **Explainability** — miért: top 3 driver + szöveges magyarázat

Példa: *„DarkShare 2.1σ above normal; block intensity elevated; impact per volume depressed → absorption-like accumulation detected."*

## Kinek szól?

Retail quantoknak és aktív kereskedőknek, akik a piaci mikrostruktúrát akarják érteni. Ez nem signal generátor — ez context engine.

Hasonló retail toolok (de nem ugyanaz):
- Unusual Whales: dark pool scanner, GEX/Periscope
- Traderslist: options flow
- Finviz: insider trading

**Ami NINCS a piacon:** kompozit MM regime + explainability dashboard retail szinten. Ez lenne az első.

## Milyen problémát old meg?

A retail kereskedők adatokhoz jutnak (dark pool %, GEX, flow), de nem kapnak **kontextust**: mit jelent ez együtt? Normális-e ez az adott részvénynél? A dealer long gamma, short gamma, vagy átmeneti? Absorpció van vagy disztribúció?

Az OBSIDIAN MM nem új adatot ad, hanem a meglévő adatokból **értelmezhető diagnózist** csinál.

## Hogyan képzelem el?

Megnyitom a dashboardot reggel. Látom, hogy az SPY Γ⁻ (gamma-negatív), az NVDA ABS (absorption-like), a TSLA NEU (semleges). Mindegyik mellett ott a score (0-100) és a magyarázat: miért. A SPY-nál nagy piros banner: „LIQUIDITY VACUUM — dealers short gamma, impact/volume elevated." Az NVDA-nál zöld: „Dark pool share 2σ above, blocks elevated, de az ár alig mozdul — valaki csendben vesz."

Nem mondja meg mit csináljak, de pontosan tudom, milyen környezetben kereskedek.

---

## Technikai specifikáció

> A teljes spec: `reference/OBSIDIAN_MM_SPEC.md` (503 sor)

### Rendszer típusa
- **Determinisztikus, rule-based** — nincs ML, nincs probabilisztikus classifier
- **Per-instrument, per-day** — minden részvényt a saját baseline-jához mér
- **Explainable by design** — minden output mellé kötelező a magyarázat

### Adatforrások (3 provider, mind tesztelve, mind működik)

| Provider | Tier | Endpoint-ek | Elérés |
|----------|------|-------------|--------|
| **Unusual Whales** | Paid | 22/22 ✅ | Dark pool, GEX, DEX, flow, IV, options |
| **Polygon.io** | Stock Dev + Options Starter | 17/23 ✅ | OHLCV, snapshots, indices, technicals |
| **FMP** | Ultimate | 11/11 ✅ | Profile, news, insider, fundamentals |

Polygon 6 hiányzó endpoint: ETF Global partner data (constituents, flows, analytics, profiles, taxonomies) + Universal Summaries → NOT_AUTHORIZED (magasabb tier kellene). **Ezek nem blokkolók** — az FMP-ből pótolható amit kell.

### Feature-ök (a spec Section 4-ből)

| Feature | Z-score | Forrás | Súly |
|---------|---------|--------|------|
| DarkShare (dark pool / total volume) | Z_dark | UW: darkpool/recent + Polygon: OHLCV | 0.25 |
| GEX (net dealer gamma exposure) | Z_GEX | UW: greek-exposure | 0.25 |
| Venue Mix (execution venue shift) | Z_venue | UW: darkpool + computed | 0.20 |
| Block Intensity (large print frequency) | Z_block | UW: darkpool/recent (size filter) | 0.15 |
| IV Skew (put-call skew deviation) | Z_IV | UW: iv-rank + option-contracts | 0.15 |
| DEX (net dealer delta exposure) | Z_DEX | UW: greek-exposure | classifier only |
| Price Efficiency (range / volume) | — | Polygon: OHLCV | classifier only |
| Price Impact (|ΔP| / volume) | — | Polygon: OHLCV | classifier only |
| Vanna & Charm | conditional | UW: greek-exposure | when available |

### Scoring (Section 5)

```
S_t = Σ w_k × |Z_k(t)|     # raw score (weighted absolute z-sum)
U_t = PercentileRank(S_t)   # [0, 100] bounded score
```

Rolling window: **W = 63 trading days** (~1 quarter)
Minimum observations: **N_min = 21 trading days** (~1 month)
Cold start: expanding window for first 63 days.

### Regime Classification (Section 6) — priority-ordered rules

| # | Regime | Condition | Meaning |
|---|--------|-----------|---------|
| 1 | **Γ⁺** | Z_GEX > +1.5 AND low efficiency | Dealers long gamma → volatility suppression |
| 2 | **Γ⁻** | Z_GEX < −1.5 AND high impact | Dealers short gamma → liquidity vacuum |
| 3 | **DD** | DarkShare > 0.70 AND Z_block > +1.0 | Dark-dominant institutional accumulation |
| 4 | **ABS** | Z_DEX < −1.0 AND price stable AND dark > 50% | Passive buying absorbing sell pressure |
| 5 | **DIST** | Z_DEX > +1.0 AND price stable | Distribution into strength |
| 6 | **NEU** | No rule matched | Neutral / mixed |
| 7 | **UND** | Insufficient data | Undetermined |

First match wins (short-circuit evaluation). Mutually exclusive.

### Dashboard (Section 9) — 4 page

| Page | Kérdés | Tartalom |
|------|--------|----------|
| **Daily State** | Mi az MM állapot ma? | U_t, R_t, top drivers, baseline |
| **Historical Regimes** | Hogyan változott? | {R_t}, {U_t} timeline |
| **Drivers & Contributors** | Mi hajtja a score-t? | w_k × |Z_k(t)| bar chart |
| **Baseline Status** | Mennyire megbízható? | n_f per feature, baseline badge |

Stack: **Streamlit + Plotly**

---

## Must Have (v1)

- [ ] Async data ingest 3 API-ból (UW, Polygon, FMP)
- [ ] Raw cache Parquet formátumban (immutable, append-only)
- [ ] Feature extraction: DarkShare, GEX, DEX, Block, IV, Efficiency, Impact
- [ ] Rolling 63-day baseline (μ, σ, Q) per instrument per feature
- [ ] Z-score normalization + percentile ranking
- [ ] Weighted composite score → U_t ∈ [0, 100]
- [ ] Priority-ordered regime classification → R_t
- [ ] Explainability output: top drivers + excluded features + baseline state
- [ ] Streamlit dashboard: Daily State page (core)
- [ ] SPY + QQQ + 5 egyedi ticker support
- [ ] CLI: `python -m obsidian run AAPL` → napi diagnózis terminálban
- [ ] NaN kezelés: no interpolation, no imputation, explicit exclusion
- [ ] Baseline state tracking: EMPTY / PARTIAL / COMPLETE
- [ ] Tests: minden core function tesztelve

## Nice to Have (v2+)

- [ ] Historical Regimes page (timeline chart)
- [ ] Drivers & Contributors page (bar chart decomposition)
- [ ] Baseline Status page (data quality dashboard)
- [ ] Regime Transition Matrix (Section 8 a spec-ből)
- [ ] Vanna & Charm conditional features
- [ ] Baseline drift detection (δ = 10%)
- [ ] SPY/QQQ global override banner
- [ ] Alerting (email/Discord ha score > 80)
- [ ] Multi-ticker watchlist (20+ tickers)
- [ ] Export: CSV/JSON daily report
- [ ] Mobile-friendly responsive layout

---

## Vizuális referenciák

A `reference/` mappában:
- `OBSIDIAN_MM_SPEC.md` — teljes technikai specifikáció (503 sor)
- `api_capabilities_report.csv` — 56 endpoint teszt eredménye
- `api_inspector.py` — az API tesztelő script
- `math_formulas.png` — mikrostruktúra normalizálási képletek
- `gex_spot_gamma.png` — Spot Gamma chart (Unusual Whales)
- `mm_exposures.png` — Market Maker Exposures (Unusual Whales Periscope)
- `contract_summary.png` — Options contract detail (UW dashboard)
- `insider_trading.png` — Finviz insider trading screen
- `block_trades_news.png` — Block trades + news feed
- `options_flow.png` — Live options flow (traderslist style)

---

## API Mapping — Melyik feature honnan jön?

### Unusual Whales (22 endpoint, mind működik)

**Core OBSIDIAN features:**
| Feature | UW Endpoint | Kulcs mezők |
|---------|-------------|-------------|
| GEX, DEX, Vanna, Charm | `/stock/{ticker}/greek-exposure` | call_gamma, put_gamma, call_delta, put_delta, call_vanna, put_vanna, call_charm, put_charm |
| Dark Pool prints | `/darkpool/recent` | ticker, volume, size, price, executed_at, market_center |
| IV Rank | `/stock/{ticker}/iv-rank` | iv_rank_1y, volatility, close |
| Options Flow | `/option-trades/flow-alerts` | total_premium, volume, strike, expiry, iv_start, has_sweep |
| Option Chain detail | `/stock/{ticker}/option-contracts` | implied_volatility, open_interest, volume, bid_volume, ask_volume, sweep_volume |
| Max Pain | `/stock/{ticker}/max-pain` | max_pain, close, open |
| Stock Screener | `/screener/stocks` | gex_net_change, put_call_ratio, iv30d, relative_volume, cum_dir_vega, implied_move_30 |
| SPIKE | `/market/spike` | volatility indicator |
| Market Tide | `/market/market-tide` | net_volume, net_call_premium, net_put_premium |
| ETF Flows | `/etfs/SPY/in-outflow` | volume, close, change, change_prem |

**Context / enrichment:**
| Endpoint | Használat |
|----------|-----------|
| `/market/sector-etfs` | Sector context overlay |
| `/market/oi-change` | Open interest shift detection |
| `/screener/option-contracts` | Hottest chains identification |
| `/short_screener` | Short interest context |
| `/congress/recent-trades` | Congressional activity flag |
| `/insider/transactions` | Insider signal overlay |

### Polygon.io (17 endpoint működik)

| Feature | Polygon Endpoint | Kulcs mezők |
|---------|------------------|-------------|
| Daily OHLCV | `/v2/aggs/ticker/{T}/range/1/day/...` | open, high, low, close, volume, vwap |
| Intraday snapshot | `/v2/snapshot/.../tickers/{T}` | day, prevDay, lastTrade |
| Index context (SPX, NDX, DJI) | `/v3/snapshot/indices` | value, change, change_percent |
| Daily Open/Close | `/v1/open-close/{T}/{date}` | open, close, high, low, volume, preMarket, afterHours |
| Technical indicators | `/v1/indicators/sma,ema,macd,rsi/...` | SMA50, EMA20, MACD, RSI14 |
| Options chain | `/v3/snapshot/options/{T}` | greeks, implied_volatility, volume |
| Market status | `/v1/marketstatus/now` | market open/closed |

**Nem elérhető** (NOT_AUTHORIZED a jelenlegi tier-en):
- ETF constituents, fund flows, analytics, profiles, taxonomies
- Universal Summaries
→ **Workaround:** FMP-ből pótolható (ETF flows, sector data)

### FMP (11 endpoint, mind működik)

| Feature | FMP Endpoint | Kulcs mezők |
|---------|--------------|-------------|
| Company profile | `/stable/profile` | marketCap, sector, industry |
| Real-time quote | `/stable/quote` | price, volume, change, marketCap |
| News | `/stable/news/stock` | title, publishedDate, text |
| Insider trading | `/stable/insider-trading/search` | transactionType, price, securitiesTransacted |
| Insider stats | `/stable/insider-trading/statistics` | totalPurchases, totalSales |
| Analyst consensus | `/stable/grades-consensus` | buy, hold, sell, strongBuy |
| Price targets | `/stable/price-target-consensus` | targetHigh, targetLow, targetConsensus |
| Dividends | `/stable/dividends` | dividend, yield |

---

## Build Order (Claude Code számára)

### Phase 1: Foundation (Sessions 1-3)
1. **Config & Secrets** — pydantic settings, .env kezelés, API key validation
2. **API Client Layer** — async httpx clients (UW, Polygon, FMP) with rate limiting
3. **Raw Cache** — Parquet writer/reader, immutable daily snapshots

### Phase 2: Core Engine (Sessions 4-7)
4. **Feature Extraction** — DarkShare, GEX, DEX, Block, IV, Efficiency, Impact
5. **Baseline System** — rolling 63d stats, expanding window cold start, state tracking
6. **Scoring** — weighted |Z| sum, percentile ranking → U_t
7. **Regime Classifier** — priority-ordered rules → R_t

### Phase 3: Explainability (Session 8)
8. **Explainability Engine** — top drivers, exclusions, baseline state, text generation

### Phase 4: Interface (Sessions 9-10)
9. **CLI** — `python -m obsidian run AAPL` → formatted terminal output
10. **Streamlit Dashboard** — Daily State page with Plotly charts

### Phase 5: Polish (Sessions 11-12)
11. **Multi-ticker** — SPY, QQQ + watchlist support
12. **Tests, docs, deployment** — pytest suite, README, Docker

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Python | 3.12+ | Modern syntax, type hints |
| httpx | async HTTP | Non-blocking API calls, connection pooling |
| pandas | DataFrames | Rolling stats, feature computation |
| pydantic | Config | Settings validation, type safety |
| pyarrow | Parquet I/O | Fast, columnar, immutable cache |
| Streamlit | Dashboard | Rapid prototyping, Python-native |
| Plotly | Charts | Interactive, professional visuals |
| pytest | Testing | Standard, simple, powerful |

---

## NaN Philosophy (nagyon fontos — a spec-ből)

> **"False negatives are acceptable. False confidence is not."**

- Ha adat hiányzik → NaN
- NaN-t nem interpolálunk, nem imputálunk, nem töltünk ki
- NaN feature kiesik a scoring-ból és a classifier-ből
- Ha minden feature NaN → Regime = UND, Score = N/A
- Az explainability mindig listázza a kizárt feature-öket és az okot

# IDEA.md Kiegészítés — Focus Universe

> Ez a rész az `Idea/IDEA.md` végéhez illesztendő, a "NaN Philosophy" szekció után.
> A teljes spec: `reference/FOCUS_UNIVERSE_SPEC.md`

---

## Focus Universe — Dinamikus Megfigyelési Kör

### Koncepció

Az OBSIDIAN nem statikus tickerlistát figyel, hanem **két szintű univerzumot**:

**CORE** (fix, mindig aktív):
- SPY, QQQ, IWM, DIA — a piaci mikrostruktúra csomópontjai
- Teljes pipeline fut rajtuk minden nap

**FOCUS** (dinamikus, magyarázó):
- Nem watchlist, nem trade idea — **diagnosztikai nagyítók**
- Megmondják: MIÉRT van QQQ Γ⁻-ban? → mert NVDA gamma stressz
- Objektív szabályok alapján lépnek be/ki

### Belépési szabályok (legalább egy igaz)

| Szabály | Feltétel | Példa |
|---------|----------|-------|
| Index súly | Top 15 (SPY), Top 10 (QQQ/DIA) | AAPL, MSFT, NVDA |
| Stressz | U_t ≥ 70 VAGY \|Z_GEX\| ≥ 2.0 VAGY DarkShare ≥ 0.65 | Bárki aki "szétcsúszik" |
| Event | Earnings ±1 nap, index rebalancing, macro nap | TSLA earnings előtt |

### Kilépés
- 3 egymást követő nap, ahol egyik belépési feltétel sem teljesül

### Napi pipeline
```
Pass 1: CORE (4) + Structural Focus (~15) + Event tickers
  → Teljes OBSIDIAN pipeline

Pass 2: Light Scan (~150 S&P 500 ticker)
  → Csak GEX + DarkShare + block check
  → Ha stressz → promóció FOCUS-ba → teljes pipeline
```

### Max méret: 30 focus ticker/nap

### KRITIKUS SZABÁLY
> **Focus ticker = lencse, nem célpont.**
> A dashboard SOHA nem mutat entry/exit-et focus tickerekre.
> Focus mindig CORE ETF kontextusában jelenik meg.

### Build Order kiegészítés

| Phase | Modul | Leírás |
|-------|-------|--------|
| 2 (Core Engine) | `src/obsidian/universe/` | Focus Universe Manager |
| 2 | `universe/structural.py` | Index weight lookup (FMP) |
| 2 | `universe/stress_scan.py` | Light scan + promóció |
| 2 | `universe/events.py` | Earnings/macro calendar |
| 4 (Interface) | Dashboard Focus Decomposition | CORE ETF → focus breakdown |

