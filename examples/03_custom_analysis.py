"""Example 3: Custom Analysis

This example shows advanced usage patterns:
- Custom regime rule evaluation
- Detailed explainability analysis
- Feature importance tracking
- Baseline drift detection
"""

import pandas as pd
import numpy as np
from datetime import date

from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    Explainer,
    RegimeType,
    FEATURE_WEIGHTS,
)


def analyze_regime_triggers(classifier: Classifier, z_scores: dict, raw_features: dict,
                            baseline_medians: dict, daily_return: float) -> dict:
    """Analyze which regime rules would match given the inputs.

    This helps understand why a specific regime was assigned and which
    alternative regimes were close to matching.
    """
    results = {}

    # Extract key values
    z_gex = z_scores.get('gex', np.nan)
    z_dex = z_scores.get('dex', np.nan)
    z_block = z_scores.get('block_intensity', np.nan)
    dark_share = raw_features.get('dark_share', np.nan)
    efficiency = raw_features.get('efficiency', np.nan)
    impact = raw_features.get('impact', np.nan)
    efficiency_median = baseline_medians.get('efficiency', np.nan)
    impact_median = baseline_medians.get('impact', np.nan)

    # Check each rule
    results['Γ⁺'] = {
        'Z_GEX > 1.5': z_gex > 1.5 if not np.isnan(z_gex) else None,
        'Efficiency < median': efficiency < efficiency_median if not np.isnan(efficiency) and not np.isnan(efficiency_median) else None,
        'match': (z_gex > 1.5 and efficiency < efficiency_median) if not np.isnan(z_gex) and not np.isnan(efficiency) and not np.isnan(efficiency_median) else False,
    }

    results['Γ⁻'] = {
        'Z_GEX < -1.5': z_gex < -1.5 if not np.isnan(z_gex) else None,
        'Impact > median': impact > impact_median if not np.isnan(impact) and not np.isnan(impact_median) else None,
        'match': (z_gex < -1.5 and impact > impact_median) if not np.isnan(z_gex) and not np.isnan(impact) and not np.isnan(impact_median) else False,
    }

    results['DD'] = {
        'DarkShare > 0.70': dark_share > 0.70 if not np.isnan(dark_share) else None,
        'Z_block > 1.0': z_block > 1.0 if not np.isnan(z_block) else None,
        'match': (dark_share > 0.70 and z_block > 1.0) if not np.isnan(dark_share) and not np.isnan(z_block) else False,
    }

    results['ABS'] = {
        'Z_DEX < -1.0': z_dex < -1.0 if not np.isnan(z_dex) else None,
        'Return >= -0.5%': daily_return >= -0.005,
        'DarkShare > 0.50': dark_share > 0.50 if not np.isnan(dark_share) else None,
        'match': (z_dex < -1.0 and daily_return >= -0.005 and dark_share > 0.50) if not np.isnan(z_dex) and not np.isnan(dark_share) else False,
    }

    results['DIST'] = {
        'Z_DEX > 1.0': z_dex > 1.0 if not np.isnan(z_dex) else None,
        'Return <= 0.5%': daily_return <= 0.005,
        'match': (z_dex > 1.0 and daily_return <= 0.005) if not np.isnan(z_dex) else False,
    }

    return results


def analyze_feature_importance(contributions: dict) -> pd.DataFrame:
    """Analyze feature importance relative to their configured weights."""
    data = []

    for feature, contrib in contributions.items():
        weight = FEATURE_WEIGHTS.get(feature, 0.0)

        # Implied |Z| = contrib / weight
        implied_z = contrib / weight if weight > 0 else np.nan

        data.append({
            'feature': feature,
            'contribution': contrib,
            'weight': weight,
            'implied_|Z|': implied_z,
        })

    df = pd.DataFrame(data)
    df = df.sort_values('contribution', ascending=False)

    return df


def main():
    """Run custom analysis example."""
    print("=" * 70)
    print("OBSIDIAN MM — Example 3: Custom Analysis")
    print("=" * 70)
    print()

    # Generate example data
    np.random.seed(42)
    dates = pd.date_range(end=date.today(), periods=100, freq='B')

    feature_data = {
        'gex': pd.Series(np.random.randn(100) * 0.5 - 1.0, index=dates),  # Negative bias
        'dex': pd.Series(np.random.randn(100) * 0.3, index=dates),
        'dark_share': pd.Series(np.random.uniform(0.4, 0.8, 100), index=dates),
        'block_intensity': pd.Series(np.random.randn(100) * 0.4 + 0.5, index=dates),
        'venue_mix': pd.Series(np.random.uniform(0.4, 0.6, 100), index=dates),
        'iv_skew': pd.Series(np.random.randn(100) * 0.2, index=dates),
    }

    # === ANALYSIS 1: Detailed Regime Rule Evaluation ===
    print("=" * 70)
    print("ANALYSIS 1: Detailed Regime Rule Evaluation")
    print("=" * 70)
    print()

    baseline = Baseline()
    scorer = Scorer()
    classifier = Classifier()

    # Compute z-scores
    z_scores = {name: baseline.compute_z_scores(series).iloc[-1]
                for name, series in feature_data.items()}

    raw_features = {
        'dark_share': feature_data['dark_share'].iloc[-1],
        'efficiency': 0.0035,
        'impact': 0.0065,
    }

    baseline_medians = {
        'efficiency': 0.0040,
        'impact': 0.0055,
    }

    daily_return = -0.012

    # Analyze all regime rules
    rule_analysis = analyze_regime_triggers(
        classifier, z_scores, raw_features, baseline_medians, daily_return
    )

    print("Regime Rule Evaluation:")
    print()

    for regime, conditions in rule_analysis.items():
        match = conditions.pop('match')
        match_str = "✓ MATCH" if match else "  no match"

        print(f"{regime:8s} {match_str}")
        for condition, result in conditions.items():
            if result is None:
                status = "⚠ N/A"
            elif result:
                status = "✓ True"
            else:
                status = "✗ False"
            print(f"  {condition:25s}: {status}")
        print()

    # === ANALYSIS 2: Feature Importance Breakdown ===
    print("=" * 70)
    print("ANALYSIS 2: Feature Importance Breakdown")
    print("=" * 70)
    print()

    raw_score, contributions = scorer.compute_raw_score(z_scores)
    importance_df = analyze_feature_importance(contributions)

    print("Feature Contributions:")
    print()
    print(importance_df.to_string(index=False))
    print()
    print(f"Total Raw Score: {raw_score:.4f}")
    print()

    # === ANALYSIS 3: Baseline Drift Detection ===
    print("=" * 70)
    print("ANALYSIS 3: Baseline Drift Detection")
    print("=" * 70)
    print()

    print("Checking for baseline drift in recent window...")
    print()

    for feature_name, series in feature_data.items():
        stats_series = baseline.compute_statistics(series)

        # Compare current mean to 10 days ago
        if len(stats_series) > 10:
            current_stats = stats_series.iloc[-1]
            prev_stats = stats_series.iloc[-10]

            if current_stats.is_valid and prev_stats.is_valid:
                drift_detected = baseline.detect_drift(current_stats.mean, prev_stats.mean)

                pct_change = ((current_stats.mean - prev_stats.mean) / prev_stats.mean) * 100

                status = "⚠ DRIFT" if drift_detected else "✓ Stable"

                print(f"{feature_name:18s}: {status:12s} ({pct_change:+6.2f}%)")

    print()

    # === ANALYSIS 4: Historical Regime Persistence ===
    print("=" * 70)
    print("ANALYSIS 4: Historical Regime Persistence")
    print("=" * 70)
    print()

    print("Computing historical regime sequence...")
    print()

    regimes = []
    for i in range(len(dates)):
        z_scores_day = {name: baseline.compute_z_scores(series).iloc[i]
                       for name, series in feature_data.items()}

        result = classifier.classify(
            z_scores=z_scores_day,
            raw_features=raw_features,
            baseline_medians=baseline_medians,
            daily_return=np.random.randn() * 0.01,
            baseline_sufficient=True,
        )
        regimes.append(result.regime)

    regimes_series = pd.Series(regimes, index=dates)

    # Calculate persistence (self-transition probability)
    print("Regime Persistence Analysis:")
    print()

    for regime_type in [r for r in RegimeType if r != RegimeType.UNDETERMINED]:
        regime_days = (regimes_series == regime_type)

        if regime_days.sum() == 0:
            continue

        # Count self-transitions
        transitions = 0
        persists = 0

        prev = None
        for current in regimes_series[regime_days]:
            if prev == regime_type:
                transitions += 1
                if current == regime_type:
                    persists += 1
            prev = current

        if transitions > 0:
            persistence = persists / transitions * 100
            print(f"{regime_type.value:8s}: {persistence:5.1f}% persistence ({persists}/{transitions} transitions)")

    print()

    print("=" * 70)
    print("Custom analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
