# /stats — Project Memory Statistics

Show project memory overview: sessions, learnings, corrections, patterns.

## Usage

```python
from memory.store import MemoryStore
store = MemoryStore()
stats = store.get_session_stats()
counts = store.count_learnings()
```

## Display Format

```
## 📊 Project Stats

### Overview
- Sessions: X | Learnings: X | Corrections: X (Y→rules) | Tests: X

### Learnings by Category
- domain: X | api: X | quality: X | ...

### Recent Corrections
- ❌ wrong → ✅ correct
```
