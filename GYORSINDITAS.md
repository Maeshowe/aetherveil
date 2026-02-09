# 🚀 OBSIDIAN MM — Gyorsindítási Útmutató

## Mit kapsz ebben a csomagban?

Egy **komplett Claude Code projekt kit**, ami mindent tartalmaz ahhoz, hogy a Claude Code "automatikusan" megépítse az OBSIDIAN MM rendszert. A csomag két rétegből áll:

### 1. réteg: Keretrendszer (bármely projekthez újrahasznosítható)
- `CLAUDE.md` — Claude Code instrukciók, szerepek, szabályok
- `.claude/agents/` — 7 specializált agent (architect, code-review, test, stb.)
- `.claude/commands/` — 5 slash parancs (/continue, /wrap-up, /learn, /search, /stats)
- `memory/` — Persistent memória rendszer (SQLite + FTS5 keresés)

### 2. réteg: OBSIDIAN MM specifikus tartalom
- `Idea/IDEA.md` — A teljes termékspecifikáció, build order, API mapping
- `reference/` — Quant spec (503 sor), API teszt eredmények, vizuális referenciák
- CLAUDE.md domain szabályok (NaN kezelés, GEX sign convention, stb.)

---

## Telepítés (5 perc)

### 1. Másold a fájlokat egy üres mappába

```bash
mkdir obsidian-mm
cd obsidian-mm

# Másold ide a csomag teljes tartalmát
# (CLAUDE.md, Idea/, reference/, memory/, .claude/, tests/, .gitignore, .env.example)
```

### 2. Állítsd be az API kulcsokat

```bash
cp .env.example .env
# Szerkeszd a .env fájlt — írd be a valódi kulcsaidat
```

Szükséges előfizetések:
| Provider | Tier | Ár (~) | Hol |
|----------|------|--------|-----|
| Unusual Whales | Paid API | $30-50/hó | unusualwhales.com |
| Polygon.io | Stocks Developer | $29/hó | polygon.io |
| FMP | Ultimate | $79/hó | financialmodelingprep.com |

### 3. Indítsd el a Claude Code-ot

```bash
cd obsidian-mm
claude
```

Claude Code automatikusan beolvassa a `CLAUDE.md`-t. Ezek után:

```
Te: /continue
```

Ez az egyetlen parancs, amivel elindulsz. Claude betölti a memóriát (ha van), elolvassa az IDEA.md-t és a spec-et, és javaslatot tesz a következő lépésre.

---

## Első Session — Lépésről Lépésre

### 1. Indítás
```
Te: /continue

Claude: Ez az első session. Memória üres.
Elolvastam az Idea/IDEA.md-t és a reference/OBSIDIAN_MM_SPEC.md-t.

A Build Order szerint az első lépés:
**Phase 1, Step 1: Config & Secrets**
- Pydantic Settings class a 3 API kulcshoz
- .env olvasás, validálás
- Tesztek

Indulhatunk?

Te: Igen, kezdjük!
```

### 2. Tervezés (opcionális, de ajánlott)
```
Te: /agents/architect
    Tervezd meg a config modult.

Claude: [Megtervezi a pydantic settings struktúrát, a fájlokat, a teszteket]
```

### 3. Építés
```
Claude: [Megírja a src/obsidian/config.py-t, teszteket, mindent]
```

### 4. Ellenőrzés
```
Te: /agents/code-review
    Nézd át amit írtál.

Claude: [Átnézi, javítja ha kell]
```

### 5. Tanulás mentése
```
Te: /learn
    A pydantic settings v2-ben a model_config = SettingsConfigDict(...) kell,
    nem a belső Config class.

Claude: ✅ Learned: Pydantic v2 uses SettingsConfigDict, not inner Config class
         (category: quality)
```

### 6. Session lezárás
```
Te: /wrap-up

Claude: ## 🏁 Session Wrap-Up
### Accomplished
- Built src/obsidian/config.py with pydantic settings
- 3 API keys validated from .env
- 5 tests passing

### Next Session
- Phase 1, Step 2: API Client Layer
```

---

## Következő Session-ök

Minden session ugyanígy:

```
/continue → dolgozz → /learn közben → /wrap-up végén
```

A Build Order (Idea/IDEA.md-ből):

| Phase | Session | Modul |
|-------|---------|-------|
| 1: Foundation | 1 | Config & Secrets |
| 1: Foundation | 2 | API Client Layer (async httpx) |
| 1: Foundation | 3 | Raw Cache (Parquet) |
| 2: Core Engine | 4 | Feature Extraction |
| 2: Core Engine | 5 | Baseline System (rolling 63d) |
| 2: Core Engine | 6 | Scoring (weighted |Z| → U_t) |
| 2: Core Engine | 7 | Regime Classifier (rules → R_t) |
| 3: Explain | 8 | Explainability Engine |
| 4: Interface | 9 | CLI |
| 4: Interface | 10 | Streamlit Dashboard |
| 5: Polish | 11 | Multi-ticker + watchlist |
| 5: Polish | 12 | Tests, docs, deploy |

Minden session végén a `/wrap-up` rögzíti, hol tartasz. Következő session `/continue`-val tudja, mi a következő lépés.

---

## Agentek — Mikor mit hívj

| Szituáció | Agent |
|-----------|-------|
| Új modul építése előtt | `/agents/architect` |
| Modul megírása után | `/agents/code-review` |
| Tesztek kellenek | `/agents/test` |
| Kód zavaros lett | `/agents/refactor` |
| Végső dokumentáció | `/agents/docs` |
| API kulcsok biztonsága | `/agents/security` |
| Kiadás előtt | `/agents/deploy` |

---

## Tipikus Kérdések

**K: Mi van ha elfelejtlek leállítani /wrap-up nélkül?**
A: Nem vész el minden, de a következő `/continue` nem tudja pontosan, hol tartottál. Érdemes ilyenkor röviden összefoglalni mi történt.

**K: A reference/ mappát módosíthatom?**
A: Igen, ez a te tudásbázisod. Bővítheted új scriptek, leírások, API dokumentáció hozzáadásával. Claude Code hozzáfér és használja.

**K: Mi van ha hibát vét Claude?**
A: Szólj neki. A Self-Correction Loop automatikusan rögzíti, szabályt javasol, és soha többé nem ismétli meg.

**K: Mennyire kész a rendszer?**
A: A csomag tartalmazza: a teljes spec-et, az API mapping-et, a build ordert, a keretrendszert. A kód 0% — azt a Claude Code építi session-ről session-re. Kb. 10-12 session alatt áll össze a v1.

**K: Kell valami plusz a Claude Max-on kívül?**
A: Igen — a 3 API előfizetés (UW, Polygon, FMP), összesen kb. $140/hó. Plusz egy terminal (VS Code, iTerm, stb.) ahol Claude Code fut.

---

## Fájlstruktúra összefoglaló

```
obsidian-mm/
├── CLAUDE.md                      # Claude Code instrukciók (auto-load)
├── Idea/
│   └── IDEA.md                    # Termékleírás + build order
├── reference/                     # Tudásbázis (bővíthető)
│   ├── OBSIDIAN_MM_SPEC.md        # Quant spec (503 sor)
│   ├── api_capabilities_report.csv # API teszt (56 endpoint)
│   ├── api_inspector.py           # API tesztelő script
│   ├── math_formulas.png          # Normalizálási képletek
│   ├── gex_spot_gamma.png         # Spot Gamma chart
│   ├── mm_exposures.png           # Market Maker Exposures
│   ├── contract_summary.png       # Options contract detail
│   ├── insider_trading.png        # Insider trading screen
│   ├── block_trades_news.png      # Block trades + news
│   └── options_flow.png           # Live options flow
├── memory/                        # Memória rendszer
│   ├── __init__.py
│   └── store.py                   # SQLite + FTS5
├── .claude/
│   ├── agents/                    # 7 agent
│   │   ├── architect.md
│   │   ├── code-review.md
│   │   ├── test.md
│   │   ├── refactor.md
│   │   ├── docs.md
│   │   ├── security.md
│   │   └── deploy.md
│   └── commands/                  # 5 parancs
│       ├── continue.md
│       ├── wrap-up.md
│       ├── learn.md
│       ├── search.md
│       └── stats.md
├── tests/
│   └── test_memory_store.py       # 16 teszt
├── .env.example                   # API key template
├── .gitignore
└── GYORSINDITAS.md                # Ez a fájl
```
