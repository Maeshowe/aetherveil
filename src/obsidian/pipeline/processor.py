"""Processor — Cache -> Features -> Engine -> Results.

Extracts features from cached data and runs through diagnostic engine.
"""

import asyncio
import logging
from datetime import date, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np

from obsidian.cache import ParquetStore
from obsidian.features import (
    compute_dark_share,
    compute_block_intensity,
    compute_gex,
    compute_dex,
    compute_efficiency,
    compute_impact,
    compute_venue_mix
)
from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    Explainer,
    BaselineState,
    ScoringResult,
    RegimeType,
    ExcludedFeature,
)

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Complete diagnostic output for one ticker on one date."""

    ticker: str
    date: date
    regime: RegimeType
    regime_label: str
    score_raw: float | None
    score_percentile: float | None
    interpretation: str | None
    z_scores: dict[str, float]
    raw_features: dict[str, float]
    baseline_state: str
    explanation: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "ticker": self.ticker,
            "date": self.date.isoformat(),
            "regime": self.regime.value,
            "regime_label": self.regime_label,
            "score_raw": self.score_raw,
            "score_percentile": self.score_percentile,
            "interpretation": self.interpretation,
            "z_scores": self.z_scores,
            "raw_features": self.raw_features,
            "baseline_state": self.baseline_state,
            "explanation": self.explanation
        }


class Processor:
    """Processes cached data through feature extraction and engine.

    Responsibilities:
    - Load data from Parquet cache
    - Extract features using feature computation functions
    - Run through baseline, scoring, classification, explainability
    - Return structured diagnostic results

    Usage:
        processor = Processor(cache_dir="data/")

        # Process single ticker
        result = await processor.process_ticker(
            ticker="SPY",
            target_date=date(2024, 1, 15)
        )
    """

    def __init__(
        self,
        cache_dir: str = "data/",
        window: int = 63,
        min_periods: int = 21
    ) -> None:
        """Initialize processor with cache and engine components.

        Args:
            cache_dir: Directory for Parquet cache
            window: Rolling baseline window size (default: 63 days)
            min_periods: Minimum non-NaN observations for valid baseline (default: 21)
        """
        self.cache = ParquetStore(base_path=cache_dir)

        # Engine components
        self.baseline = Baseline(window=window, min_periods=min_periods)
        self.scorer = Scorer(window=window)
        self.classifier = Classifier()
        self.explainer = Explainer()

    @staticmethod
    def _safe_last(series: pd.Series | None) -> float:
        """Get the last value from a Series, or NaN if empty/None.

        Per spec: Missing data -> NaN. Never interpolate.
        """
        if series is None or len(series) == 0:
            return float("nan")
        return series.iloc[-1]

    @staticmethod
    def _normalize_dark_pool(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Aggregate raw UW dark pool prints into daily summaries.

        UW returns individual trade-level prints. Feature functions expect
        daily aggregates with columns like dark_volume, total_volume, etc.
        """
        if df.empty:
            return df
        # Filter to requested ticker (UW may return mixed tickers)
        if "ticker" in df.columns:
            df = df[df["ticker"].str.upper() == ticker.upper()].copy()
        if df.empty:
            return df
        # Convert types
        for col in ["size", "volume", "price"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Parse dates
        if "executed_at" in df.columns:
            df["date"] = pd.to_datetime(df["executed_at"]).dt.normalize()
        else:
            return pd.DataFrame()
        # Aggregate by date
        daily = df.groupby("date").agg(
            dark_volume=("size", "sum"),
            total_volume=("volume", "first"),
            block_count=("size", "count"),
        ).reset_index()
        daily = daily.sort_values("date").set_index("date")
        # Add venue distribution columns (market_center -> per-venue volumes)
        if "market_center" in df.columns:
            venue_counts = df.groupby(["date", "market_center"])["size"].sum().unstack(fill_value=0)
            venue_counts.columns = [f"{c}_volume" for c in venue_counts.columns]
            daily = daily.join(venue_counts)
        return daily

    @staticmethod
    def _normalize_greeks(df: pd.DataFrame) -> pd.DataFrame:
        """Convert UW Greek exposure columns from strings to numeric."""
        if df.empty:
            return df
        numeric_cols = [
            "call_gamma", "put_gamma", "call_delta", "put_delta",
            "call_vanna", "put_vanna", "call_charm", "put_charm",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Parse date column to datetime index for time-series features
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").set_index("date")
        return df

    @staticmethod
    def _normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
        """Rename Polygon short column names to standard names."""
        if df.empty:
            return df
        rename_map = {
            "v": "volume", "o": "open", "c": "close",
            "h": "high", "l": "low", "vw": "vwap",
            "t": "timestamp", "n": "transactions",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        # Convert timestamp (ms epoch) to datetime index
        if "timestamp" in df.columns:
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.sort_values("date").set_index("date")
        return df

    @staticmethod
    def _normalize_iv_rank(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize UW IV rank data to a time-series DataFrame.

        UW iv-rank endpoint returns: date, volatility, iv_rank_1y, close.
        We use iv_rank_1y directly (pre-computed 1-year percentile by UW).
        """
        if df.empty:
            return df
        for col in ["volatility", "iv_rank_1y", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").set_index("date")
        return df

    async def load_historical_features(
        self,
        ticker: str,
        end_date: date,
        lookback_days: int = 100
    ) -> dict[str, pd.Series]:
        """Load and compute features for historical window.

        Args:
            ticker: Symbol to process
            end_date: Most recent date to include
            lookback_days: How many days back to load (default: 100)

        Returns:
            Dictionary mapping feature_name -> Series of values

        Notes:
            - Returns NaN for features where data is missing
            - Always instrument-isolated (no cross-ticker pooling)
            - Date index is sorted ascending
        """
        ticker = ticker.upper()
        start_date = end_date - timedelta(days=lookback_days)

        # Load all data sources for this ticker (async I/O)
        dark_data = await self.cache.read_range(ticker, "dark_pool", start_date, end_date)
        greeks_data = await self.cache.read_range(ticker, "greeks", start_date, end_date)
        bars_data = await self.cache.read_range(ticker, "bars", start_date, end_date)
        iv_rank_data = await self.cache.read_range(ticker, "iv_rank", start_date, end_date)

        # Normalize data types and column names from raw API responses
        dark_data = self._normalize_dark_pool(dark_data, ticker)
        greeks_data = self._normalize_greeks(greeks_data)
        bars_data = self._normalize_bars(bars_data)
        iv_rank_data = self._normalize_iv_rank(iv_rank_data)

        # Extract features (returns Series or None)
        features = {}

        # Dark pool features
        if not dark_data.empty:
            try:
                dark_share = compute_dark_share(dark_data)
                if dark_share is not None:
                    features['dark_share'] = dark_share
            except Exception as e:
                logger.warning("DarkShare computation failed: %s", e)

            try:
                block_intensity = compute_block_intensity(dark_data)
                if block_intensity is not None:
                    features['block_intensity'] = block_intensity
            except Exception as e:
                logger.warning("BlockIntensity computation failed: %s", e)

            try:
                venue_mix = compute_venue_mix(dark_data)
                if venue_mix is not None:
                    features['venue_mix'] = venue_mix
            except Exception as e:
                logger.warning("VenueMix computation failed: %s", e)

        # Greeks features
        if not greeks_data.empty:
            try:
                gex = compute_gex(greeks_data)
                if gex is not None:
                    features['gex'] = gex
            except Exception as e:
                logger.warning("GEX computation failed: %s", e)

            try:
                dex = compute_dex(greeks_data)
                if dex is not None:
                    features['dex'] = dex
            except Exception as e:
                logger.warning("DEX computation failed: %s", e)

        # IV Rank feature (from UW iv-rank endpoint, NOT greek-exposure)
        # NOTE: iv_skew is not available from UW API (greek-exposure has no
        # put/call IV columns). We use UW's pre-computed iv_rank_1y instead.
        if not iv_rank_data.empty and "iv_rank_1y" in iv_rank_data.columns:
            try:
                iv_rank_series = iv_rank_data["iv_rank_1y"].dropna()
                if len(iv_rank_series) > 0:
                    features['iv_rank'] = iv_rank_series
            except Exception as e:
                logger.warning("IV_Rank extraction failed: %s", e)

        # Price features (need high/low/open/close/volume from bars)
        if not bars_data.empty:
            try:
                efficiency = compute_efficiency(bars_data)
                if efficiency is not None:
                    features['efficiency'] = efficiency
            except Exception as e:
                logger.warning("Efficiency computation failed: %s", e)

            try:
                impact = compute_impact(bars_data)
                if impact is not None:
                    features['impact'] = impact
            except Exception as e:
                logger.warning("Impact computation failed: %s", e)

        return features

    async def process_ticker(
        self,
        ticker: str,
        target_date: date
    ) -> DiagnosticResult:
        """Run full diagnostic pipeline for one ticker on one date.

        Args:
            ticker: Symbol to process
            target_date: Date to diagnose

        Returns:
            DiagnosticResult with regime, score, explanation

        Notes:
            - Loads 100-day lookback for baseline window
            - Returns UND regime if insufficient data
            - Never interpolates or imputes missing features
        """
        ticker = ticker.upper()

        # Step 1: Load historical features
        feature_data = await self.load_historical_features(ticker, target_date, lookback_days=100)

        if not feature_data:
            # No features available
            return DiagnosticResult(
                ticker=ticker,
                date=target_date,
                regime=RegimeType.UNDETERMINED,
                regime_label="UND — Undetermined",
                score_raw=None,
                score_percentile=None,
                interpretation=None,
                z_scores={},
                raw_features={},
                baseline_state="EMPTY",
                explanation="No feature data available for this ticker/date."
            )

        # Step 2: Compute z-scores for latest day
        z_scores_latest = {}
        feature_counts = {}

        for feature_name, series in feature_data.items():
            # Compute z-scores for entire series
            z_series = self.baseline.compute_z_scores(series, use_expanding=True)

            # Get latest z-score: try exact target_date first, fall back to last value
            # (target_date may be a weekend/holiday with no trading data)
            if len(z_series) == 0:
                z_scores_latest[feature_name] = np.nan
            elif target_date in z_series.index:
                z_scores_latest[feature_name] = z_series.loc[target_date]
            else:
                # Use most recent available z-score
                z_scores_latest[feature_name] = z_series.iloc[-1]

            # Count valid observations
            feature_counts[feature_name] = series.notna().sum()

        # Step 3: Determine baseline state
        baseline_state = self.baseline.get_state(feature_counts)

        # Step 4: Compute unusualness score
        excluded_names = [k for k, v in z_scores_latest.items() if pd.isna(v)]
        excluded_feature_objs = [
            ExcludedFeature(feature_name=name, reason="NaN value")
            for name in excluded_names
        ]

        if baseline_state != BaselineState.EMPTY:
            raw_score, contributions = self.scorer.compute_raw_score(
                z_scores=z_scores_latest,
                excluded_features=excluded_names
            )

            # Compute percentile (simplified for now - would use historical scores)
            percentile_score = min(raw_score * 50, 100)
            interpretation = self.scorer.get_interpretation(percentile_score)
            interpretation_str = interpretation.value
        else:
            raw_score = None
            percentile_score = None
            interpretation_str = None
            contributions = {}

        # Step 5: Classify regime
        # Use NaN (not None) for missing values — classifier uses np.isnan()
        _nan = float("nan")

        # Collect all raw feature values for the latest day
        all_raw_features = {
            name: self._safe_last(series)
            for name, series in feature_data.items()
        }

        # Subset needed by classifier
        raw_features = {
            'dark_share': all_raw_features.get('dark_share', _nan),
            'efficiency': all_raw_features.get('efficiency', _nan),
            'impact': all_raw_features.get('impact', _nan),
        }

        baseline_medians = {
            'efficiency': self._safe_last(feature_data['efficiency'].rolling(63).median()) if 'efficiency' in feature_data and len(feature_data['efficiency']) > 0 else _nan,
            'impact': self._safe_last(feature_data['impact'].rolling(63).median()) if 'impact' in feature_data and len(feature_data['impact']) > 0 else _nan,
        }

        daily_return = 0.0  # Would compute from bars_data if available

        regime_result = self.classifier.classify(
            z_scores=z_scores_latest,
            raw_features=raw_features,
            baseline_medians=baseline_medians,
            daily_return=daily_return,
            baseline_sufficient=(baseline_state != BaselineState.EMPTY)
        )

        # Step 6: Generate explanation
        if raw_score is not None:
            scoring_result = ScoringResult(
                raw_score=raw_score,
                percentile_score=percentile_score,
                interpretation=self.scorer.get_interpretation(percentile_score),
                feature_contributions=contributions,
                excluded_features=excluded_names
            )
        else:
            scoring_result = None

        explanation_output = self.explainer.explain(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded_feature_objs,
            baseline_state=baseline_state,
            ticker=ticker,
            date=target_date.isoformat()
        )

        return DiagnosticResult(
            ticker=ticker,
            date=target_date,
            regime=regime_result.regime,
            regime_label=f"{regime_result.regime.value} — {regime_result.regime.get_description()}",
            score_raw=raw_score,
            score_percentile=percentile_score,
            interpretation=interpretation_str,
            z_scores=z_scores_latest,
            raw_features=all_raw_features,
            baseline_state=baseline_state.value,
            explanation=explanation_output.format_full()
        )

    async def process_all(
        self,
        tickers: set[str],
        target_date: date
    ) -> dict[str, DiagnosticResult]:
        """Process multiple tickers concurrently on the same date.

        Baseline, Scorer, Classifier, and Explainer are stateless (pure
        functions), and ParquetStore reads are concurrent-safe, so parallel
        execution is safe.

        Args:
            tickers: Set of ticker symbols
            target_date: Date to diagnose

        Returns:
            Dictionary mapping ticker -> DiagnosticResult
        """
        async def _process_one(ticker: str) -> tuple[str, DiagnosticResult | None]:
            try:
                return ticker, await self.process_ticker(ticker, target_date)
            except Exception as e:
                logger.error("Failed to process %s: %s", ticker, e, exc_info=True)
                return ticker, None

        tasks = [_process_one(t) for t in sorted(tickers)]
        completed = await asyncio.gather(*tasks)
        return {t: r for t, r in completed if r is not None}
