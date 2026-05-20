# Security Policy

## Sensitive data

Local profile folders, session files, tokens, cookies, launcher caches, saved account metadata, or personal account data must not be committed to the repository.

LoliSwap stores local saved profiles in:

```text
C:\Users\YOUR_USER\Documents\LoliSwap
```

That folder is intentionally outside the repository and should not be published.

If account credentials are saved in the app, the password is encrypted with Windows DPAPI for the current Windows user. It is still sensitive local data and should not be copied to another machine, published, or shared.

## Scope

This project does not implement authentication bypass. Optional autologin only starts the selected launcher and sends the saved login/password to the active launcher window using normal keyboard input for user-owned accounts.
