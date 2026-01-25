# Project structure

## High-level layout

Typical repo tree:

```
uwindsor-findit/
  apps/
    core/
    users/
    chat/
    listings/
  config/
  templates/
  requirements/
  docker-compose.yml
  Dockerfile
  manage.py
```

## Apps and responsibilities

### `apps/core/`
Shared cross-cutting concerns and generic pages.

**Typical contents**
- shared utilities/helpers (small, generic)
- health check endpoint
- base mixins, generic view helpers
- public pages (home) and generic authenticated pages (dashboard)

**Routing**
- mounted at `/` (root)
- examples:
  - `/` → home
  - `/dashboard/` → authenticated page

### `apps/users/`
Authentication and user-related domain logic.

**Responsibilities**
- registration & login flow (UWindsor-only)
- user profile (future)
- permissions/roles (future)

**Routing**
- mounted at `/auth/`
- examples:
  - `/auth/register/`
  - `/auth/login/`
  - `/auth/logout/`

### `apps/chat/` (future)
Real-time or async messaging domain.

**Responsibilities**
- chat rooms / messages
- websocket routing (if using Channels)
- message persistence and rules

**Routing**
- suggested mount: `/chat/`

### `apps/listings/` (future)
The core domain area for “FindIt” listings/objects.

**Responsibilities**
- create/list/update/delete listings
- search/filter (later can become a separate `search` module or service)
- permissions around listing ownership and moderation

**Routing**
- suggested mount: `/listings/`

## Routing pattern (recommended)

`config/urls.py` should stay small and only **mount apps**:

```python
urlpatterns = [
  path("admin/", admin.site.urls),
  path("auth/", include("apps.users.urls")),
  path("", include("apps.core.urls")),
  path("chat/", include("apps.chat.urls")),
  path("listings/", include("apps.listings.urls")),
]
```

Each app owns its own URLs in `apps/<app>/urls.py` and should declare `app_name`.

## Templates

- `templates/` (repo root) is for **shared** templates:
  - `base.html`
  - partials (navbar, messages)
- each app can also ship templates inside:
  - `apps/<app>/templates/<app>/...`

Use:
- global layout extends `base.html`
- keep app templates namespaced (`core/home.html`, `users/login.html`, etc.)
