"""Example 1: Basic Diagnostic

This example shows the most basic usage of OBSIDIAN MM:
computing a diagnostic for a single instrument on a single day.

For demonstration purposes, this uses synthetic data.
In production, you would fetch real data from APIs.
"""

import pandas as pd
import numpy as np
from datetime import date

from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    Explainer,
    BaselineState,
)


def generate_synthetic_feature_data(n_days: int = 100) -> dict[str, pd.Series]:
    """Generate synthetic feature data for demonstration.

    In production, this would come from API clients and feature extraction.
    """
    dates = pd.date_range(end=date.today(), periods=n_days, freq='B')

    return {
        'gex': pd.Series(np.random.randn(n_days) * 0.5 + 0.1, index=dates),
        'dex': pd.Series(np.random.randn(n_days) * 0.3, index=dates),
        'dark_share': pd.Series(np.random.uniform(0.3, 0.7, n_days), index=dates),
        'block_intensity': pd.Series(np.random.randn(n_days) * 0.4, index=dates),
        'venue_mix': pd.Series(np.random.uniform(0.4, 0.6, n_days), index=dates),
        'iv_skew': pd.Series(np.random.randn(n_days) * 0.2 - 0.1, index=dates),
    }


def main():
    """Run basic diagnostic example."""
    print("=" * 60)
    print("OBSIDIAN MM — Example 1: Basic Diagnostic")
    print("=" * 60)
    print()

    # Step 1: Generate synthetic feature data
    print("Step 1: Generating synthetic feature data...")
    feature_data = generate_synthetic_feature_data(n_days=100)
    print(f"  ✓ Generated {len(feature_data)} features with 100 days of data")
    print()

    # Step 2: Compute z-scores using Baseline
    print("Step 2: Computing z-scores...")
    baseline = Baseline(window=63, min_periods=21)

    z_scores_latest = {}
    feature_counts = {}

    for feature_name, series in feature_data.items():
        # Compute z-scores for entire series
        z_series = baseline.compute_z_scores(series, use_expanding=True)

        # Get latest z-score (last day)
        z_scores_latest[feature_name] = z_series.iloc[-1]

        # Count valid observations
        feature_counts[feature_name] = series.notna().sum()

        print(f"  ✓ {feature_name}: Z = {z_scores_latest[feature_name]:.4f}, n = {feature_counts[feature_name]}")

    print()

    # Step 3: Determine baseline state
    print("Step 3: Determining baseline state...")
    baseline_state = baseline.get_state(feature_counts)
    print(f"  ✓ Baseline state: {baseline_state.value}")
    print()

    # Step 4: Compute unusualness score
    print("Step 4: Computing unusualness score...")
    scorer = Scorer()

    raw_score, contributions = scorer.compute_raw_score(
        z_scores=z_scores_latest,
        excluded_features=[],
    )

    print(f"  ✓ Raw score: {raw_score:.4f}")
    print(f"  ✓ Top contributors:")
    for feature, contrib in sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]:
        print(f"      {feature}: {contrib:.4f}")

    # For single-day demo, use raw score as percentile (normally computed from history)
    percentile_score = min(raw_score * 50, 100)  # Simple mapping for demo
    interpretation = scorer.get_interpretation(percentile_score)

    print(f"  ✓ Percentile score: {percentile_score:.1f} ({interpretation.value})")
    print()

    # Step 5: Classify regime
    print("Step 5: Classifying regime...")
    classifier = Classifier()

    # Extract raw features (normally from feature extraction, here we use latest values)
    raw_features = {
        'dark_share': feature_data['dark_share'].iloc[-1],
        'efficiency': 0.0035,  # Example values
        'impact': 0.0055,
    }

    baseline_medians = {
        'efficiency': feature_data['gex'].rolling(63).median().iloc[-1] * 0.001 + 0.004,  # Synthetic
        'impact': 0.0052,
    }

    daily_return = 0.005  # +0.5% example

    regime_result = classifier.classify(
        z_scores=z_scores_latest,
        raw_features=raw_features,
        baseline_medians=baseline_medians,
        daily_return=daily_return,
        baseline_sufficient=(baseline_state != BaselineState.EMPTY),
    )

    print(f"  ✓ Regime: {regime_result.regime.value} ({regime_result.regime.get_description()})")
    print()

    # Step 6: Generate explanation
    print("Step 6: Generating explanation...")
    explainer = Explainer()

    from obsidian.engine import ScoringResult, InterpretationBand

    scoring_result = ScoringResult(
        raw_score=raw_score,
        percentile_score=percentile_score,
        interpretation=interpretation,
        feature_contributions=contributions,
        excluded_features=[],
    )

    output = explainer.explain(
        regime_result=regime_result,
        scoring_result=scoring_result,
        excluded_features=[],
        baseline_state=baseline_state,
        ticker='SPY',
        date=str(date.today()),
    )

    print()
    print("=" * 60)
    print("DIAGNOSTIC OUTPUT")
    print("=" * 60)
    print()
    print(output.format_full())
    print()

    # Step 7: Structured output (JSON)
    print("=" * 60)
    print("STRUCTURED OUTPUT (for programmatic use)")
    print("=" * 60)
    print()

    import json
    print(json.dumps(output.to_dict(), indent=2))


if __name__ == '__main__':
    main()
