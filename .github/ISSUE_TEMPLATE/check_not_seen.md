---
name: Check not recognized
about: A protection exists but agent-canary doesn't see it
labels: check-not-seen
---

## Function flagged as "no checks" or "partial checks"

**Function name**:
**File**:
**Line**:

## The check that exists

(describe where the protection is: in the same function, in a decorator, in function parameters, in a middleware, in an API gateway, etc.)

## Code snippet

```python
(paste the function code AND the check code, even if in different files)
```

## Notes

If the check is in a different file (middleware, gateway), the correct resolution is `# checked:ok — protected by [where]` in your source code. This issue template is for checks that ARE in the same function scope but agent-canary doesn't detect them.
