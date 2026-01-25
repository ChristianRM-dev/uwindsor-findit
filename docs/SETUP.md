# Setup

This project is **Docker-first** (recommended), but supports **local setup** as well.

## Requirements

- Python **3.12+** (if running locally)
- Docker + Docker Compose (if using containers)
- Git

## Option A — VS Code DevContainer (recommended)

1. Install VS Code extensions:
   - Dev Containers
   - Python
   - Docker

2. Open the repo folder in VS Code.

3. `Cmd/Ctrl + Shift + P` → **Dev Containers: Reopen in Container**

4. Once inside the container:

```bash
python manage.py check
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

- App: `http://localhost:8000`
- Postgres (Docker): exposed on `localhost:5432` (see `docker-compose.yml`)

## Option B — Docker Compose (no DevContainer)

From the repo root:

```bash
docker compose up --build
```

Then open a second terminal:

```bash
docker compose exec web bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Option C — Local Python (venv)

### 1) Create and activate venv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) Install deps

```bash
pip install -r requirements/dev.txt
```

### 3) Environment variables

Create a `.env` file at the repo root (do **not** commit it). Use `.env.example` as a starting point.

Minimum recommended:

```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://findit:findit@localhost:5432/findit
```

### 4) Database options (local)

**Recommended:** use Docker **only for Postgres** even if you run Django locally.

```bash
docker compose up -d db
```

Now your local Django can connect to `localhost:5432`.

### 5) Run migrations + server

```bash
python manage.py migrate
python manage.py runserver
```

Open: `http://127.0.0.1:8000`

## Useful commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py test
```

## Troubleshooting

### "Dependency on app with no migrations"
Create migrations for that app:

```bash
python manage.py makemigrations <app_label>
python manage.py migrate
```

### Reset DB (Docker)
⚠️ This deletes all Postgres data:

```bash
docker compose down -v
docker compose up --build
```
