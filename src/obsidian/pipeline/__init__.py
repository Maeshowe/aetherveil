"""Data pipeline orchestration — API → Cache → Features → Engine → Results.

The pipeline coordinates the entire data flow:
1. Fetch raw data from API clients
2. Store in Parquet cache
3. Extract features from cached data
4. Run through diagnostic engine
5. Return results

Components:
- Orchestrator: Main coordinator
- Fetcher: API → Parquet Cache
- Processor: Cache → Features → Engine
"""

from obsidian.pipeline.orchestrator import Orchestrator

__all__ = ["Orchestrator"]
