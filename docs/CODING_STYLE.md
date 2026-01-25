# Coding style

This document defines practical conventions for a clean Django codebase.

## General principles

- **Readability > cleverness**
- Keep **views thin**, move business logic into services/modules
- Avoid leaking domain rules into templates
- Prefer explicit names: `listings/services.py`, `users/forms.py`, etc.

## Python & Django conventions

- Follow **PEP 8**
- Use **Black** formatting and **Ruff** linting (optional but recommended)
- Type hints are encouraged in services and utilities

### Imports
Prefer grouped imports:

```python
# stdlib
from datetime import datetime

# third-party
from django.db import models

# local
from apps.users.models import User
```

## Separation of concerns

### Views
**Views should:**
- validate input (or delegate to forms/serializers)
- orchestrate calls to services
- choose template / response
- handle redirects and messages

**Views should NOT:**
- contain heavy business logic
- contain complex queries that should be shared

### Forms
Use forms for:
- validation (including UWindsor email rule)
- mapping request data to domain actions

### Services
Place domain actions in `services.py` (or `services/` package) inside the app.

Examples:
- `apps/listings/services.py` → create listing, update listing, permission checks
- `apps/chat/services.py` → send message, join room

### Selectors / Queries (optional pattern)
For complex read paths, use `selectors.py`:

- `apps/listings/selectors.py` → listing search queries, filters, prefetching

### Models
- Keep model methods small and domain-focused
- Prefer service layer for multi-model workflows

## Templates & UI

- Shared layout: `templates/base.html`
- Use Bootstrap utility classes for consistent spacing
- Keep templates simple:
  - no heavy query logic
  - no permission logic beyond simple conditionals

## Naming

- Apps: singular domain (`users`, `chat`, `listings`)
- URLs: nouns for resources, verbs for actions only when necessary
- Templates: namespaced by app (`users/login.html`)

## Configuration

- `config/settings.py` should stay organized:
  - group Django apps, third-party apps, local apps
- Never commit secrets:
  - `.env` is local only
  - keep `.env.example` updated

## Testing (recommended)

- Put tests inside each app: `apps/<app>/tests.py` or `tests/` package
- Minimum for auth:
  - reject non-`@uwindsor.ca`
  - allow `@uwindsor.ca`
  - dashboard requires auth
