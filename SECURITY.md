# Security Policy

## Sensitive data

Local profile folders, session files, tokens, cookies, launcher caches, or personal account data must not be committed to the repository.

LoliSwap stores local saved profiles in:

```text
C:\Users\YOUR_USER\Documents\LoliSwap
```

That folder is intentionally outside the repository and should not be published.

## Scope

This project does not implement authentication bypass, password storage, or automated login. It only saves and restores local files for user-owned profiles.
