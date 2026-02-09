# /learn — Capture a Learning

Quick command to save a learning to persistent memory during work.

## Usage

```python
from memory.store import MemoryStore
store = MemoryStore()
store.add_learning(
    content="[clear, actionable statement]",
    category="[category]",
    source="[how we discovered this]"
)
```

## Categories

| Category | When to use |
|----------|-------------|
| `navigation` | File paths, where to find things |
| `editing` | Code patterns that work well |
| `testing` | Test strategies, fixture patterns |
| `quality` | Style, lint, type hint patterns |
| `architecture` | Design decisions, module boundaries |
| `performance` | Speed optimizations |
| `domain` | Business/domain specifics |
| `api` | External API quirks, rate limits |
| `debugging` | Bug patterns, common failures |
| `general` | Everything else |

Confirm with: `✅ Learned: [brief summary] (category: [category])`
