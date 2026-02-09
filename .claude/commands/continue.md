# /continue — Continue Previous Session

Run this at the start of every new session to load context from where we left off.

## Steps

### 1. Load Memory Context

```python
from memory.store import MemoryStore
store = MemoryStore()
print(store.get_session_context())
```

### 2. Start New Session

```python
session_id = store.start_session(
    goal="[describe today's goal]",
    modules=["expected/modules/to/touch.py"]
)
```

### 3. Check Current State
- Review the last session summary
- Run `pytest -v --tb=short` to verify everything passes
- Check what's done and what's next

### 4. Present Plan to User

```
## 🔄 Resuming Project

### Last time we:
[summary from memory]

### Today's plan:
[next steps]

### Current state:
- Tests passing: X/Y
- Next module: Z
```

Wait for user confirmation before starting work.

## Rules
- Always load memory first — never start from scratch
- Always run tests to confirm current state
- Always present the plan and wait for user confirmation
- If memory is empty (first session), say so and start from Phase 1: Discovery
