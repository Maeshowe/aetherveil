# /wrap-up — Session Wrap-Up Ritual

Run this at the end of every work session to capture context before it's lost.

## Steps

### 1. Session Summary
What was accomplished? Which modules were built, modified, or fixed?

### 2. Capture Learnings

```python
from memory.store import MemoryStore
store = MemoryStore()
store.add_learning("description", category="category", source="session discovery")
```

Categories: `navigation`, `editing`, `testing`, `quality`, `architecture`, `performance`, `domain`, `api`, `debugging`, `general`.

### 3. Record Corrections
If the user corrected you, record each one:

```python
store.add_correction(
    what_i_did="...",
    what_was_wrong="...",
    correct_approach="..."
)
```

Ask: **"Should this become a permanent rule?"** If yes: `store.promote_correction_to_rule(id)`

### 4. End the Session

```python
store.end_session(
    session_id=current_session_id,
    summary="What was accomplished",
    modules=["files/touched.py"],
    tests_added=N
)
```

### 5. Next Session Prep
Tell the user what's next, any blockers, any open questions.

## Output Format

```
## 🏁 Session Wrap-Up

### Accomplished
- Built X, modified Y, fixed Z

### Learnings Captured (N new)
- [category] Description

### Corrections Recorded (N)
- ❌ Wrong → ✅ Correct

### Stats
- Tests added: N
- Modules touched: list

### Next Session
- Next up: [task]
- Blockers: [if any]
```
