"""Example 2: Batch Processing

This example shows how to process multiple days of data
and track regime changes over time.

Useful for:
- Historical analysis
- Regime transition studies
- Performance evaluation
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    BaselineState,
    RegimeType,
)


def generate_time_series_data(n_days: int = 100) -> dict[str, pd.Series]:
    """Generate synthetic time series for demonstration."""
    dates = pd.date_range(end=date.today(), periods=n_days, freq='B')

    # Simulate GEX with regime shifts
    gex = np.concatenate([
        np.random.randn(30) * 0.3 + 1.0,   # Initial positive gamma
        np.random.randn(20) * 0.5 - 1.5,   # Shift to negative gamma
        np.random.randn(30) * 0.3 + 0.5,   # Return to positive
        np.random.randn(20) * 0.4,         # Neutral period
    ])

    return {
        'gex': pd.Series(gex[:n_days], index=dates),
        'dex': pd.Series(np.random.randn(n_days) * 0.3, index=dates),
        'dark_share': pd.Series(np.random.uniform(0.3, 0.7, n_days), index=dates),
        'block_intensity': pd.Series(np.random.randn(n_days) * 0.4, index=dates),
        'venue_mix': pd.Series(np.random.uniform(0.4, 0.6, n_days), index=dates),
        'iv_skew': pd.Series(np.random.randn(n_days) * 0.2, index=dates),
    }


def main():
    """Run batch processing example."""
    print("=" * 70)
    print("OBSIDIAN MM — Example 2: Batch Processing")
    print("=" * 70)
    print()

    # Step 1: Generate time series data
    print("Step 1: Generating time series data...")
    feature_data = generate_time_series_data(n_days=100)
    print(f"  ✓ Generated 100 days of feature data")
    print()

    # Step 2: Compute z-scores for all days
    print("Step 2: Computing z-scores for entire time series...")
    baseline = Baseline(window=63, min_periods=21)

    z_scores_ts = {}
    for feature_name, series in feature_data.items():
        z_scores_ts[feature_name] = baseline.compute_z_scores(series, use_expanding=True)

    print(f"  ✓ Computed z-scores for {len(z_scores_ts)} features")
    print()

    # Step 3: Compute raw scores for all days
    print("Step 3: Computing raw scores...")
    scorer = Scorer()

    dates = feature_data['gex'].index
    raw_scores = []

    for date in dates:
        z_scores_day = {name: series.loc[date] for name, series in z_scores_ts.items()}

        # Skip days with all NaN z-scores (cold start)
        if all(np.isnan(z) for z in z_scores_day.values()):
            raw_scores.append(np.nan)
            continue

        raw_score, _ = scorer.compute_raw_score(z_scores_day, excluded_features=[])
        raw_scores.append(raw_score)

    raw_scores_series = pd.Series(raw_scores, index=dates)
    print(f"  ✓ Computed {raw_scores_series.notna().sum()} valid raw scores")
    print()

    # Step 4: Compute percentile scores
    print("Step 4: Computing percentile scores...")
    percentile_scores = scorer.compute_percentile_scores(raw_scores_series, use_expanding=True)
    print(f"  ✓ Computed percentile scores for all days")
    print()

    # Step 5: Classify regimes for all days
    print("Step 5: Classifying regimes...")
    regimes = []

    for date in dates:
        z_scores_day = {name: series.loc[date] for name, series in z_scores_ts.items()}

        # Check if we have sufficient data
        n_valid = sum(1 for z in z_scores_day.values() if not np.isnan(z))
        baseline_sufficient = n_valid >= 3  # At least 3 features

        # Classify
        classifier = Classifier()
        regime_result = classifier.classify(
            z_scores=z_scores_day,
            raw_features={
                'dark_share': feature_data['dark_share'].loc[date],
                'efficiency': 0.004,  # Placeholder
                'impact': 0.005,      # Placeholder
            },
            baseline_medians={'efficiency': 0.004, 'impact': 0.005},
            daily_return=np.random.randn() * 0.01,  # Synthetic return
            baseline_sufficient=baseline_sufficient,
        )

        regimes.append(regime_result.regime)

    regimes_series = pd.Series(regimes, index=dates)
    print(f"  ✓ Classified {len(regimes)} days")
    print()

    # Step 6: Analyze results
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)
    print()

    print("Regime Distribution:")
    regime_counts = regimes_series.value_counts()
    for regime_type, count in regime_counts.items():
        pct = count / len(regimes) * 100
        print(f"  {regime_type.value:8s}: {count:3d} days ({pct:5.1f}%)")
    print()

    print("Unusualness Score Statistics:")
    print(f"  Mean:   {percentile_scores.mean():.2f}")
    print(f"  Median: {percentile_scores.median():.2f}")
    print(f"  Std:    {percentile_scores.std():.2f}")
    print(f"  Min:    {percentile_scores.min():.2f}")
    print(f"  Max:    {percentile_scores.max():.2f}")
    print()

    # Step 7: Find regime transitions
    print("Recent Regime Transitions:")
    prev_regime = None
    transition_count = 0

    for i, (date, regime) in enumerate(regimes_series.tail(30).items()):
        if prev_regime is not None and regime != prev_regime:
            print(f"  {date.strftime('%Y-%m-%d')}: {prev_regime.value} → {regime.value}")
            transition_count += 1
        prev_regime = regime

    if transition_count == 0:
        print("  No transitions in last 30 days")
    print()

    # Step 8: Identify extreme days
    print("Days with Extreme Unusualness (score > 80):")
    extreme_days = percentile_scores[percentile_scores > 80].tail(10)

    if len(extreme_days) > 0:
        for date, score in extreme_days.items():
            regime = regimes_series.loc[date]
            print(f"  {date.strftime('%Y-%m-%d')}: {score:5.1f} ({regime.value})")
    else:
        print("  No extreme days found")
    print()

    # Step 9: Export to CSV
    print("Step 9: Exporting results...")

    results_df = pd.DataFrame({
        'date': dates,
        'regime': [r.value for r in regimes],
        'raw_score': raw_scores,
        'percentile_score': percentile_scores,
        'z_gex': z_scores_ts['gex'],
        'z_dark_share': z_scores_ts['dark_share'],
    })

    output_file = 'diagnostic_results.csv'
    results_df.to_csv(output_file, index=False)
    print(f"  ✓ Saved results to {output_file}")
    print()

    print("=" * 70)
    print("Batch processing complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
