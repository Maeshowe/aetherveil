# /search — Search Project Memory

Search stored learnings using full-text search with BM25 ranking.

## Usage

```python
from memory.store import MemoryStore
store = MemoryStore()

results = store.search("query terms")        # Full-text search
results = store.list_learnings(category="api") # Browse by category
counts = store.count_learnings()               # Counts per category
```

## FTS5 Syntax
- `dark pool` — both terms
- `"dark pool"` — exact phrase
- `dark OR pool` — either term
- `dark NOT pool` — exclude term
- `dark*` — prefix match

## Display Format
```
## 🔍 Search: "query" — N results
1. [category] Content — 📅 date
2. [category] Content — 📅 date
```
