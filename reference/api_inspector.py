import os
import yaml
import requests
import pandas as pd
import json
from datetime import datetime

# --- KONFIGURÁCIÓ (Írd be a kulcsaidat vagy használd a környezeti változókat) ---
API_KEYS = {
    "UW": os.getenv("UW_API_KEY", "YOUR_KEY_HERE"),
    "FMP": os.getenv("FMP_API_KEY", "YOUR_KEY_HERE"),
    "POLYGON": os.getenv("POLYGON_API_KEY", "YOUR_KEY_HERE")
}

# Fájl elérési útja (amit feltöltöttél)
UW_YAML_PATH = "UW_Bundled_References_export.yaml"

# Teszt ticker
SYMBOL = "AAPL"
DATE = datetime.now().strftime("%Y-%m-%d")

# --- SEGÉDFÜGGVÉNYEK ---

def analyze_json_structure(data, parent_key=''):
    """Rekurzívan kigyűjti a JSON kulcsokat, hogy lássuk milyen adatmezők vannak."""
    keys = set()
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{parent_key}.{k}" if parent_key else k
            keys.add(full_key)
            keys.update(analyze_json_structure(v, full_key))
    elif isinstance(data, list) and len(data) > 0:
        # Csak az első elemet vizsgáljuk listánál a struktúra miatt
        keys.update(analyze_json_structure(data[0], parent_key))
    return keys

def test_endpoint(provider, url, headers=None, params=None):
    """Meghív egy végpontot és elemzi a választ."""
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        status = response.status_code
        
        available_fields = "N/A"
        error_msg = ""

        if status == 200:
            try:
                data = response.json()
                # Mezők kinyerése (max 50-et mutatunk, hogy olvasható legyen)
                fields = list(analyze_json_structure(data))
                available_fields = ", ".join(fields[:20]) + ("..." if len(fields) > 20 else "")
            except:
                available_fields = "Non-JSON Response"
        else:
            error_msg = response.text[:100] # Csak az elejét

        return {
            "Provider": provider,
            "URL": url,
            "Status": status,
            "Success": status == 200,
            "Data Fields Sample": available_fields,
            "Error": error_msg
        }
    except Exception as e:
        return {
            "Provider": provider,
            "URL": url,
            "Status": "Ex",
            "Success": False,
            "Data Fields Sample": "",
            "Error": str(e)
        }

# --- 1. UNUSUAL WHALES YAML PARSER ---
def parse_uw_yaml():
    endpoints = []
    if not os.path.exists(UW_YAML_PATH):
        print(f"[WARN] UW YAML fájl nem található: {UW_YAML_PATH}")
        return []
    
    print(f"[INFO] UW YAML feldolgozása...")
    with open(UW_YAML_PATH, 'r') as file:
        try:
            spec = yaml.safe_load(file)
            for path, methods in spec.get('paths', {}).items():
                for method, details in methods.items():
                    if method == 'get': # Csak a GET kérések érdekelnek most
                        summary = details.get('summary', 'No summary')
                        # Helyettesítsük be a tickert a path-ba teszteléshez
                        test_path = path.replace('{ticker}', SYMBOL).replace('{symbol}', SYMBOL)
                        
                        endpoints.append({
                            "Provider": "Unusual Whales",
                            "Category": details.get('tags', ['General'])[0],
                            "Endpoint": test_path,
                            "Description": summary
                        })
        except Exception as e:
            print(f"[ERROR] YAML hiba: {e}")
    return endpoints

# --- 2. TESZT LISTA ÖSSZEÁLLÍTÁSA ---
def run_tests():
    results = []

    # --- UNUSUAL WHALES (Kulcs végpontok) ---
    print(f"[INFO] Unusual Whales tesztelése...")
    uw_headers = {"Authorization": f"Bearer {API_KEYS['UW']}", "User-Agent": "PythonClient"}
    uw_base = "https://api.unusualwhales.com"

    uw_targets = [
        # Market Overview
        (f"{uw_base}/api/market/market-tide", "Market Tide"),
        (f"{uw_base}/api/market/total-options-volume", "Total Options Volume"),
        (f"{uw_base}/api/market/top-net-impact", "Top Net Impact"),
        (f"{uw_base}/api/market/sector-etfs", "Sector ETFs"),
        (f"{uw_base}/api/market/spike", "SPIKE (Volatility)"),
        (f"{uw_base}/api/market/oi-change", "OI Change"),
        # Options Flow
        (f"{uw_base}/api/option-trades/flow-alerts", "Flow Alerts"),
        (f"{uw_base}/api/screener/option-contracts", "Hottest Chains"),
        (f"{uw_base}/api/stock/{SYMBOL}/option-contracts", "Option Contracts"),
        (f"{uw_base}/api/net-flow/expiry", "Net Flow by Expiry"),
        # Dark Pool
        (f"{uw_base}/api/darkpool/recent", "Dark Pool (Recent)"),
        # Congress & Insider
        (f"{uw_base}/api/congress/recent-trades", "Congress Trades"),
        (f"{uw_base}/api/insider/transactions", "Insider Transactions"),
        (f"{uw_base}/api/market/insider-buy-sells", "Insider Buy/Sells Total"),
        # Screeners & Analysts
        (f"{uw_base}/api/screener/analysts", "Analyst Ratings"),
        (f"{uw_base}/api/screener/stocks", "Stock Screener"),
        (f"{uw_base}/api/short_screener", "Short Screener"),
        # Per-Ticker
        (f"{uw_base}/api/stock/{SYMBOL}/greek-exposure", "Greek Exposure (GEX)"),
        (f"{uw_base}/api/stock/{SYMBOL}/iv-rank", "IV Rank"),
        (f"{uw_base}/api/stock/{SYMBOL}/max-pain", "Max Pain"),
        # ETF
        (f"{uw_base}/api/etfs/SPY/in-outflow", "ETF Inflow/Outflow (SPY)"),
        # Seasonality
        (f"{uw_base}/api/seasonality/market", "Market Seasonality"),
    ]

    for url, desc in uw_targets:
        res = test_endpoint("UW", url, headers=uw_headers)
        res['Description'] = desc
        results.append(res)

    # --- FINANCIAL MODELING PREP (Ultimate Tier) ---
    print(f"[INFO] FMP tesztelése...")
    fmp_base = "https://financialmodelingprep.com/stable"
    fmp_params = {"apikey": API_KEYS['FMP']}
    
    fmp_targets = [
        # Alap profil & árak
        (f"{fmp_base}/profile", {"symbol": "AAPL"}, "Company Profile"),
        (f"{fmp_base}/quote", {"symbol": "AAPL"}, "Real-time Quote"),
        # Pénzügyi kimutatások
        (f"{fmp_base}/income-statement", {"symbol": "AAPL", "limit": "1"}, "Income Statement"),
        (f"{fmp_base}/earning-call-transcript", {"symbol": "AAPL", "quarter": "3", "year": "2023"}, "Earnings Transcript (Ultimate)"),
        # Elemzői adatok
        (f"{fmp_base}/grades-consensus", {"symbol": "AAPL"}, "Analyst Grade Consensus"),
        (f"{fmp_base}/price-target-consensus", {"symbol": "AAPL"}, "Price Target Consensus"),
        (f"{fmp_base}/analyst-estimates", {"symbol": "AAPL", "period": "annual"}, "Analyst Estimates"),
        # Insider trading
        (f"{fmp_base}/insider-trading/search", {"symbol": "AAPL"}, "Insider Trading"),
        (f"{fmp_base}/insider-trading/statistics", {"symbol": "AAPL"}, "Insider Trade Statistics"),
        # Hírek & osztalék
        (f"{fmp_base}/news/stock", {"symbols": "AAPL", "limit": "1"}, "Stock News"),
        (f"{fmp_base}/dividends", {"symbol": "AAPL"}, "Dividends"),
    ]

    for url, extra_params, desc in fmp_targets:
        params = {**fmp_params, **extra_params}
        res = test_endpoint("FMP", url, params=params)
        res['Description'] = desc
        results.append(res)

    # --- POLYGON.IO (Stock Dev + Options Starter) ---
    print(f"[INFO] Polygon.io tesztelése...")
    poly_headers = {"Authorization": f"Bearer {API_KEYS['POLYGON']}"}
    
    poly_base = "https://api.polygon.io"
    poly_targets = [
        # Stocks (Dev Tier)
        (f"{poly_base}/v2/aggs/ticker/{SYMBOL}/range/1/day/2023-01-09/{DATE}", "Stock History"),
        (f"{poly_base}/v2/snapshot/locale/us/markets/stocks/tickers/{SYMBOL}", "Stock Snapshot"),
        (f"{poly_base}/v2/last/trade/{SYMBOL}", "Last Trade"),
        (f"{poly_base}/v2/snapshot/locale/us/markets/stocks/gainers", "Top Gainers"),
        (f"{poly_base}/v2/snapshot/locale/us/markets/stocks/losers", "Top Losers"),
        # Options (Starter)
        (f"{poly_base}/v3/reference/options/contracts?underlying_ticker={SYMBOL}&limit=1", "Options Reference"),
        (f"{poly_base}/v3/snapshot/options/{SYMBOL}?limit=1", "Options Chain Snapshot"),
        # Indices (Starter)
        (f"{poly_base}/v3/snapshot/indices?ticker.any_of=I:SPX,I:DJI,I:NDX", "Indices Snapshot"),
        # --- v1 végpontok ---
        # Daily Open/Close
        (f"{poly_base}/v1/open-close/{SYMBOL}/2025-12-31", "Daily Open/Close (Stock)"),
        (f"{poly_base}/v1/open-close/I:SPX/2025-12-31", "Daily Open/Close (Index)"),
        # Technikai indikátorok
        (f"{poly_base}/v1/indicators/sma/{SYMBOL}?timespan=day&window=50&limit=1", "SMA (50-day)"),
        (f"{poly_base}/v1/indicators/ema/{SYMBOL}?timespan=day&window=20&limit=1", "EMA (20-day)"),
        (f"{poly_base}/v1/indicators/macd/{SYMBOL}?timespan=day&limit=1", "MACD"),
        (f"{poly_base}/v1/indicators/rsi/{SYMBOL}?timespan=day&window=14&limit=1", "RSI (14-day)"),
        # Market status
        (f"{poly_base}/v1/marketstatus/now", "Market Status"),
        (f"{poly_base}/v1/marketstatus/upcoming", "Upcoming Holidays"),
        # SEC filings
        (f"{poly_base}/v1/reference/sec/filings?ticker={SYMBOL}&limit=1", "SEC Filings"),
        # Summaries
        (f"{poly_base}/v1/summaries?ticker.any_of={SYMBOL},MSFT,GOOGL", "Universal Summaries"),
        # --- ETF Global partner data ---
        (f"{poly_base}/etf-global/v1/constituents?composite_ticker=SPY&limit=1", "ETF Constituents (SPY)"),
        (f"{poly_base}/etf-global/v1/fund-flows?composite_ticker=SPY&limit=1", "ETF Fund Flows (SPY)"),
        (f"{poly_base}/etf-global/v1/analytics?composite_ticker=SPY&limit=1", "ETF Analytics (SPY)"),
        (f"{poly_base}/etf-global/v1/profiles?composite_ticker=SPY&limit=1", "ETF Profiles (SPY)"),
        (f"{poly_base}/etf-global/v1/taxonomies?composite_ticker=SPY&limit=1", "ETF Taxonomies (SPY)"),
    ]

    for url, desc in poly_targets:
        res = test_endpoint("Polygon", url, headers=poly_headers)
        res['Description'] = desc
        results.append(res)

    return results

# --- MAIN ---
if __name__ == "__main__":
    # 1. UW YAML betöltése
    uw_definitions = parse_uw_yaml()
    print(f"Betöltve {len(uw_definitions)} UW végpont definíció a YAML-ből.")

    # 2. Tesztek futtatása
    if any(k == "YOUR_KEY_HERE" for k in API_KEYS.values()) and not os.getenv("CI"):
         print("FIGYELEM: Az API kulcsok nincsenek beállítva a script elején!")
    
    test_data = run_tests()

    # 3. Riport generálása
    df = pd.DataFrame(test_data)
    
    # Kiírás CSV-be
    output_file = "api_capabilities_report.csv"
    df.to_csv(output_file, index=False)
    
    print("\n--- EREDMÉNYEK ---")
    # Megjelenítjük a sikeres hívásokat és hogy milyen adatmezőket találtunk
    pd.set_option('display.max_colwidth', 50)
    print(df[['Provider', 'Description', 'Success', 'Data Fields Sample']])
    print(f"\nRészletes riport mentve: {output_file}")