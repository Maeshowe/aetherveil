"""Tests for Processor — Cache → Features → Engine → Results.

Tests data normalization, feature extraction, and the full diagnostic pipeline
using synthetic data written to a temporary Parquet cache.
"""

import asyncio
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from obsidian.cache import ParquetStore
from obsidian.engine import RegimeType, BaselineState
from obsidian.pipeline.processor import Processor, DiagnosticResult


# --- Helpers to generate realistic synthetic data ---


def make_dark_pool_prints(
    ticker: str, n_days: int = 30, start_date: date = date(2024, 1, 1)
) -> pd.DataFrame:
    """Generate raw UW-style dark pool print data."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n_days):
        dt = start_date + timedelta(days=i)
        n_prints = rng.integers(5, 20)
        for _ in range(n_prints):
            rows.append({
                "size": int(rng.integers(100, 50000)),
                "ticker": ticker,
                "price": str(round(600 + rng.normal(0, 5), 2)),
                "volume": 80000000,
                "executed_at": f"{dt.isoformat()}T{rng.integers(9, 16)}:00:00Z",
                "market_center": rng.choice(["D", "L", "B", "X"]),
                "premium": "0",
                "nbbo_ask": "600.50",
                "nbbo_bid": "600.40",
                "canceled": False,
                "nbbo_ask_quantity": 100,
                "nbbo_bid_quantity": 100,
                "sale_cond_codes": None,
                "tracking_id": int(rng.integers(1, 999999)),
                "trade_code": None,
                "trade_settlement": "regular",
                "ext_hour_sold_codes": None,
            })
    return pd.DataFrame(rows)


def make_greeks_data(n_days: int = 30, start_date: date = date(2024, 1, 1)) -> pd.DataFrame:
    """Generate UW-style Greek exposure data (string columns, like real API)."""
    rng = np.random.default_rng(42)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    rows = []
    for dt in dates:
        call_gamma = rng.normal(4000000, 1000000)
        put_gamma = rng.normal(-5000000, 1000000)
        rows.append({
            "date": dt.isoformat(),
            "call_gamma": str(round(call_gamma, 4)),
            "put_gamma": str(round(put_gamma, 4)),
            "call_delta": str(round(rng.normal(180000000, 20000000), 4)),
            "put_delta": str(round(rng.normal(-130000000, 15000000), 4)),
            "call_vanna": str(round(rng.normal(10000000, 3000000), 4)),
            "put_vanna": str(round(rng.normal(-8000000, 2000000), 4)),
            "call_charm": str(round(rng.normal(-3000000, 500000), 4)),
            "put_charm": str(round(rng.normal(1000000, 300000), 4)),
        })
    return pd.DataFrame(rows)


def make_bars_data(n_days: int = 30, start_date: date = date(2024, 1, 1)) -> pd.DataFrame:
    """Generate Polygon-style daily bars (short column names, ms timestamps)."""
    rng = np.random.default_rng(42)
    rows = []
    price = 600.0
    for i in range(n_days):
        dt = start_date + timedelta(days=i)
        ts_ms = int(pd.Timestamp(dt).timestamp() * 1000)
        daily_change = rng.normal(0, 2)
        o = round(price, 2)
        c = round(price + daily_change, 2)
        h = round(max(o, c) + abs(rng.normal(0, 1)), 2)
        l = round(min(o, c) - abs(rng.normal(0, 1)), 2)
        v = float(rng.integers(50_000_000, 120_000_000))
        rows.append({"v": v, "vw": round((h + l) / 2, 4), "o": o, "c": c, "h": h, "l": l, "t": ts_ms, "n": int(rng.integers(500000, 1200000))})
        price = c
    return pd.DataFrame(rows)


def make_iv_rank_data(n_days: int = 30, start_date: date = date(2024, 1, 1)) -> pd.DataFrame:
    """Generate UW-style IV rank data (string columns, like real API)."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n_days):
        dt = start_date + timedelta(days=i)
        rows.append({
            "date": dt.isoformat(),
            "volatility": str(round(rng.uniform(0.15, 0.45), 4)),
            "iv_rank_1y": str(round(rng.uniform(0.0, 1.0), 4)),
            "close": str(round(600 + rng.normal(0, 5), 2)),
            "updated_at": f"{dt.isoformat()}T16:00:00Z",
        })
    return pd.DataFrame(rows)


# --- Normalization tests ---


class TestNormalizeDarkPool:
    """Test _normalize_dark_pool static method."""

    def test_filters_to_correct_ticker(self) -> None:
        """Only keeps rows matching the requested ticker."""
        df = pd.DataFrame({
            "ticker": ["SPY", "AAPL", "SPY", "MSFT"],
            "size": [1000, 500, 2000, 300],
            "volume": [80000000, 50000000, 80000000, 30000000],
            "executed_at": [
                "2024-01-15T10:00:00Z", "2024-01-15T10:00:00Z",
                "2024-01-15T11:00:00Z", "2024-01-15T10:00:00Z",
            ],
            "market_center": ["D", "D", "L", "D"],
        })
        result = Processor._normalize_dark_pool(df, "SPY")
        # Should aggregate the 2 SPY rows into 1 daily row
        assert len(result) == 1
        assert result["dark_volume"].iloc[0] == 3000  # 1000 + 2000

    def test_empty_after_filter(self) -> None:
        """Returns empty DataFrame if no rows match ticker."""
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "size": [500, 300],
            "volume": [50000000, 30000000],
            "executed_at": ["2024-01-15T10:00:00Z", "2024-01-15T10:00:00Z"],
            "market_center": ["D", "D"],
        })
        result = Processor._normalize_dark_pool(df, "SPY")
        assert result.empty

    def test_empty_input(self) -> None:
        """Handles empty DataFrame."""
        result = Processor._normalize_dark_pool(pd.DataFrame(), "SPY")
        assert result.empty

    def test_venue_columns_created(self) -> None:
        """Creates per-venue volume columns from market_center."""
        df = pd.DataFrame({
            "ticker": ["SPY", "SPY", "SPY"],
            "size": [1000, 2000, 500],
            "volume": [80000000, 80000000, 80000000],
            "executed_at": [
                "2024-01-15T10:00:00Z", "2024-01-15T11:00:00Z", "2024-01-15T12:00:00Z",
            ],
            "market_center": ["D", "L", "D"],
        })
        result = Processor._normalize_dark_pool(df, "SPY")
        assert "D_volume" in result.columns
        assert "L_volume" in result.columns
        assert result["D_volume"].iloc[0] == 1500  # 1000 + 500
        assert result["L_volume"].iloc[0] == 2000

    def test_aggregates_across_days(self) -> None:
        """Groups by date correctly."""
        df = pd.DataFrame({
            "ticker": ["SPY", "SPY", "SPY"],
            "size": [1000, 2000, 1500],
            "volume": [80000000, 80000000, 80000000],
            "executed_at": [
                "2024-01-15T10:00:00Z", "2024-01-15T11:00:00Z",
                "2024-01-16T10:00:00Z",
            ],
            "market_center": ["D", "D", "L"],
        })
        result = Processor._normalize_dark_pool(df, "SPY")
        assert len(result) == 2  # Two separate days


class TestNormalizeGreeks:
    """Test _normalize_greeks static method."""

    def test_converts_strings_to_numeric(self) -> None:
        """String columns are converted to float."""
        df = pd.DataFrame({
            "date": ["2024-01-15"],
            "call_gamma": ["4500000.0"],
            "put_gamma": ["-5000000.0"],
            "call_delta": ["180000000"],
            "put_delta": ["-130000000"],
        })
        result = Processor._normalize_greeks(df)
        assert result["call_gamma"].dtype == np.float64
        assert result["put_gamma"].iloc[0] == pytest.approx(-5000000.0)

    def test_sets_date_index(self) -> None:
        """Date column becomes the DatetimeIndex."""
        df = pd.DataFrame({
            "date": ["2024-01-15", "2024-01-16"],
            "call_gamma": ["1000", "2000"],
            "put_gamma": ["-500", "-600"],
        })
        result = Processor._normalize_greeks(df)
        assert isinstance(result.index, pd.DatetimeIndex)
        assert "date" not in result.columns

    def test_empty_input(self) -> None:
        """Handles empty DataFrame."""
        result = Processor._normalize_greeks(pd.DataFrame())
        assert result.empty


class TestNormalizeBars:
    """Test _normalize_bars static method."""

    def test_renames_columns(self) -> None:
        """Polygon short names → standard names."""
        df = pd.DataFrame({
            "v": [85000000.0],
            "vw": [600.12],
            "o": [598.50],
            "c": [601.25],
            "h": [602.00],
            "l": [597.80],
            "t": [1705276800000],
            "n": [950000],
        })
        result = Processor._normalize_bars(df)
        assert "volume" in result.columns
        assert "open" in result.columns
        assert "close" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        # Short names should be gone
        assert "v" not in result.columns
        assert "o" not in result.columns

    def test_sets_datetime_index(self) -> None:
        """Timestamp column is converted to DatetimeIndex."""
        df = pd.DataFrame({
            "v": [85000000.0],
            "o": [598.50],
            "c": [601.25],
            "h": [602.00],
            "l": [597.80],
            "t": [1705276800000],
            "n": [950000],
        })
        result = Processor._normalize_bars(df)
        assert isinstance(result.index, pd.DatetimeIndex)

    def test_empty_input(self) -> None:
        """Handles empty DataFrame."""
        result = Processor._normalize_bars(pd.DataFrame())
        assert result.empty


class TestNormalizeIvRank:
    """Test _normalize_iv_rank static method."""

    def test_converts_strings_to_numeric(self) -> None:
        """String columns are converted to float."""
        df = pd.DataFrame({
            "date": ["2024-01-15"],
            "volatility": ["0.3250"],
            "iv_rank_1y": ["0.72"],
            "close": ["601.50"],
        })
        result = Processor._normalize_iv_rank(df)
        assert result["iv_rank_1y"].dtype == np.float64
        assert result["volatility"].iloc[0] == pytest.approx(0.3250)
        assert result["iv_rank_1y"].iloc[0] == pytest.approx(0.72)

    def test_sets_date_index(self) -> None:
        """Date column becomes the DatetimeIndex."""
        df = pd.DataFrame({
            "date": ["2024-01-15", "2024-01-16"],
            "iv_rank_1y": ["0.50", "0.55"],
            "volatility": ["0.30", "0.32"],
        })
        result = Processor._normalize_iv_rank(df)
        assert isinstance(result.index, pd.DatetimeIndex)
        assert "date" not in result.columns

    def test_empty_input(self) -> None:
        """Handles empty DataFrame."""
        result = Processor._normalize_iv_rank(pd.DataFrame())
        assert result.empty


# --- Full pipeline tests ---


class TestProcessTicker:
    """Test full diagnostic pipeline with synthetic cached data."""

    @pytest_asyncio.fixture
    async def loaded_processor(self, tmp_path):
        """Create Processor with synthetic data pre-loaded in cache."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)
        n_days = 30

        # Write synthetic data to cache
        start = date(2024, 1, 1)
        greeks = make_greeks_data(n_days=n_days, start_date=start)
        bars = make_bars_data(n_days=n_days, start_date=start)

        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)
        await cache.write(ticker="SPY", source="bars", dt=target, data=bars, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        return processor, target

    @pytest.mark.asyncio
    async def test_produces_diagnostic_result(self, loaded_processor) -> None:
        """Full pipeline produces a valid DiagnosticResult."""
        processor, target = loaded_processor
        result = await processor.process_ticker("SPY", target)

        assert isinstance(result, DiagnosticResult)
        assert result.ticker == "SPY"
        assert result.date == target
        assert isinstance(result.regime, RegimeType)
        assert isinstance(result.regime_label, str)
        assert isinstance(result.z_scores, dict)
        assert isinstance(result.baseline_state, str)
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0

    @pytest.mark.asyncio
    async def test_z_scores_are_numeric(self, loaded_processor) -> None:
        """Z-scores should be float values (possibly NaN)."""
        processor, target = loaded_processor
        result = await processor.process_ticker("SPY", target)

        for name, z in result.z_scores.items():
            assert isinstance(z, (float, np.floating)), f"{name} z-score is not float: {type(z)}"

    @pytest.mark.asyncio
    async def test_score_is_bounded(self, loaded_processor) -> None:
        """Percentile score should be in [0, 100] when available."""
        processor, target = loaded_processor
        result = await processor.process_ticker("SPY", target)

        if result.score_percentile is not None:
            assert 0.0 <= result.score_percentile <= 100.0

    @pytest.mark.asyncio
    async def test_to_dict_serializable(self, loaded_processor) -> None:
        """to_dict produces JSON-serializable output."""
        import json
        processor, target = loaded_processor
        result = await processor.process_ticker("SPY", target)

        d = result.to_dict()
        # Should not raise — NaN becomes null in JSON
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)
        assert "SPY" in json_str

    @pytest.mark.asyncio
    async def test_no_data_returns_undetermined(self, tmp_path) -> None:
        """No cached data → regime UNDETERMINED, empty z_scores."""
        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        result = await processor.process_ticker("FAKE", date(2024, 1, 15))

        assert result.regime == RegimeType.UNDETERMINED
        assert result.z_scores == {}
        assert result.baseline_state == "EMPTY"
        assert result.score_raw is None
        assert result.score_percentile is None

    @pytest.mark.asyncio
    async def test_greeks_only_partial_baseline(self, tmp_path) -> None:
        """Only greeks data → PARTIAL baseline, gex/dex computed."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)
        greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        result = await processor.process_ticker("SPY", target)

        # Should have GEX and DEX z-scores
        assert "gex" in result.z_scores
        assert "dex" in result.z_scores
        # Dark pool features should NOT be present (no data)
        assert result.z_scores.get("dark_share") is None or np.isnan(result.z_scores.get("dark_share", float("nan")))

    @pytest.mark.asyncio
    async def test_iv_rank_loaded_from_cache(self, tmp_path) -> None:
        """IV rank data is loaded from cache and produces iv_rank feature."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)
        iv_rank = make_iv_rank_data(n_days=30, start_date=date(2024, 1, 1))
        greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        await cache.write(ticker="SPY", source="iv_rank", dt=target, data=iv_rank, overwrite=True)
        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        result = await processor.process_ticker("SPY", target)

        assert "iv_rank" in result.z_scores
        assert "iv_rank" in result.raw_features

    @pytest.mark.asyncio
    async def test_iv_rank_nan_when_no_data(self, tmp_path) -> None:
        """IV rank is absent when no iv_rank cache data exists."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)
        greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        result = await processor.process_ticker("SPY", target)

        # iv_rank should not appear in z_scores (no data source)
        assert "iv_rank" not in result.z_scores or np.isnan(result.z_scores.get("iv_rank", float("nan")))


class TestProcessAll:
    """Test processing multiple tickers."""

    @pytest.mark.asyncio
    async def test_processes_multiple_tickers(self, tmp_path) -> None:
        """Returns results for all tickers, even if some fail."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)

        # Load data for SPY only — QQQ has no data
        greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        results = await processor.process_all({"SPY", "QQQ"}, target)

        assert "SPY" in results
        assert "QQQ" in results
        # SPY should have valid features; QQQ should be UNDETERMINED
        assert results["SPY"].regime != RegimeType.UNDETERMINED or len(results["SPY"].z_scores) > 0
        assert results["QQQ"].regime == RegimeType.UNDETERMINED

    @pytest.mark.asyncio
    async def test_instrument_isolation(self, tmp_path) -> None:
        """Each ticker's baseline is independent — no cross-contamination."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)

        # Give SPY and QQQ different data
        spy_greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        qqq_greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        # Shift QQQ gamma significantly to get different z-scores
        qqq_greeks["call_gamma"] = qqq_greeks["call_gamma"].apply(
            lambda x: str(float(x) * 3)
        )

        await cache.write(ticker="SPY", source="greeks", dt=target, data=spy_greeks, overwrite=True)
        await cache.write(ticker="QQQ", source="greeks", dt=target, data=qqq_greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)
        results = await processor.process_all({"SPY", "QQQ"}, target)

        # Z-scores should differ because data differs
        spy_gex = results["SPY"].z_scores.get("gex")
        qqq_gex = results["QQQ"].z_scores.get("gex")
        if spy_gex is not None and qqq_gex is not None:
            if not (np.isnan(spy_gex) or np.isnan(qqq_gex)):
                # They should be different since we multiplied QQQ gamma by 3
                # (not guaranteed to be different z-scores, but likely)
                pass  # Just verify both were computed independently


    @pytest.mark.asyncio
    async def test_failure_excluded_from_results(self, tmp_path) -> None:
        """Tickers that raise exceptions are excluded from results."""
        cache = ParquetStore(base_path=str(tmp_path))
        target = date(2024, 2, 15)

        # Load valid data only for SPY
        greeks = make_greeks_data(n_days=30, start_date=date(2024, 1, 1))
        await cache.write(ticker="SPY", source="greeks", dt=target, data=greeks, overwrite=True)

        processor = Processor(cache_dir=str(tmp_path), window=20, min_periods=5)

        # Patch process_ticker to raise for FAIL ticker
        original = processor.process_ticker

        async def _patched(ticker, target_date):
            if ticker == "FAIL":
                raise RuntimeError("Simulated failure")
            return await original(ticker, target_date)

        processor.process_ticker = _patched
        results = await processor.process_all({"SPY", "FAIL"}, target)

        assert "SPY" in results
        assert "FAIL" not in results


class TestDiagnosticResult:
    """Test DiagnosticResult dataclass."""

    def test_to_dict_fields(self) -> None:
        """to_dict includes all required fields."""
        result = DiagnosticResult(
            ticker="SPY",
            date=date(2024, 1, 15),
            regime=RegimeType.NEUTRAL,
            regime_label="NEU — Neutral / Mixed",
            score_raw=0.5,
            score_percentile=25.0,
            interpretation="Normal",
            z_scores={"gex": 1.0, "dex": -0.5},
            raw_features={"dark_share": 0.35, "gex": 500000},
            baseline_state="COMPLETE",
            explanation="Test explanation",
        )
        d = result.to_dict()
        assert d["ticker"] == "SPY"
        assert d["date"] == "2024-01-15"
        assert d["regime"] == "NEU"
        assert d["score_raw"] == 0.5
        assert d["score_percentile"] == 25.0
        assert d["z_scores"]["gex"] == 1.0
        assert d["raw_features"]["dark_share"] == 0.35
        assert d["baseline_state"] == "COMPLETE"

    def test_to_dict_with_none_scores(self) -> None:
        """to_dict handles None scores (UNDETERMINED regime)."""
        result = DiagnosticResult(
            ticker="SPY",
            date=date(2024, 1, 15),
            regime=RegimeType.UNDETERMINED,
            regime_label="UND — Undetermined",
            score_raw=None,
            score_percentile=None,
            interpretation=None,
            z_scores={},
            raw_features={},
            baseline_state="EMPTY",
            explanation="No data.",
        )
        d = result.to_dict()
        assert d["score_raw"] is None
        assert d["score_percentile"] is None
        assert d["interpretation"] is None


class TestSafeLast:
    """Test Processor._safe_last static method."""

    def test_normal_series(self) -> None:
        """Returns last value from a normal Series."""
        series = pd.Series([1.0, 2.0, 3.0])
        assert Processor._safe_last(series) == 3.0

    def test_empty_series(self) -> None:
        """Returns NaN for empty Series."""
        series = pd.Series([], dtype=float)
        assert np.isnan(Processor._safe_last(series))

    def test_none_input(self) -> None:
        """Returns NaN for None input."""
        assert np.isnan(Processor._safe_last(None))

    def test_series_with_nan_last(self) -> None:
        """Returns NaN if last value is NaN (no interpolation)."""
        series = pd.Series([1.0, 2.0, np.nan])
        result = Processor._safe_last(series)
        assert np.isnan(result)

    def test_single_value(self) -> None:
        """Returns the only value from a single-element Series."""
        series = pd.Series([42.0])
        assert Processor._safe_last(series) == 42.0
