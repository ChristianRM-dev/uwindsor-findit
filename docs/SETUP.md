# Setup

This project supports Docker-first development, local Python setup, and a Render demo deployment from `dev`.

## Requirements

- Python **3.12** if running locally
- Docker + Docker Compose if you want a Postgres workflow
- Git

## Option A — VS Code DevContainer

1. Install the VS Code extensions `Dev Containers`, `Python`, and `Docker`.
2. Open the repo folder in VS Code.
3. Run `Cmd/Ctrl + Shift + P` and choose **Dev Containers: Reopen in Container**.
4. Once the container is ready:

```bash
python manage.py check
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

- App: `http://localhost:8000`
- Postgres: `localhost:5432` from [docker-compose.yml](../docker-compose.yml)

## Option B — Docker Compose

From the repo root:

```bash
docker compose up --build
```

Then in a second terminal:

```bash
docker compose exec web bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Option C — Local Python

### 1) Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) Install dependencies

```bash
pip install -r requirements/dev.txt
```

### 3) Create your environment file

Copy [`.env.example`](../.env.example) to `.env` and update any values you need.

Minimum local values:

```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0,testserver
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1,http://localhost
DJANGO_SERVE_MEDIA_LOCALLY=true
```

If you do not set `DATABASE_URL`, Django will use the default local SQLite database at `db.sqlite3`.

To send real emails locally with the Brevo API, add these values to `.env`:

```env
EMAIL_PROVIDER=brevo
BREVO_API_KEY=your-brevo-api-key
BREVO_API_URL=https://api.brevo.com/v3/smtp/email
BREVO_REQUEST_TIMEOUT=10
EMAIL_DEBUG=true
DJANGO_DEFAULT_FROM_EMAIL=FindIt UWindsor <your-verified-sender@example.com>
```

Important notes:

- Use your Brevo API key for transactional email, not your SMTP credentials or Brevo account password.
- `DJANGO_DEFAULT_FROM_EMAIL` must match a sender or domain already verified in Brevo.
- Set `EMAIL_DEBUG=true` while testing to log the sender, recipients, subject, and Brevo response `messageId` in your `runserver` output.
- If `EMAIL_PROVIDER` is left empty, Django will keep using the console backend locally.

### 4) Load the initial fixture data

```bash
python manage.py migrate
mkdir -p storage/items/demo
cp apps/listings/sample_media/items/* storage/items/demo/
python manage.py loaddata apps/listings/fixtures/initial_data.json
```

Demo login created by the fixture:

```text
demo.reporter@uwindsor.ca / DemoPass123!
```

### 5) Run the app

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000`.

## Render demo deployment

This repo includes a Blueprint at [render.yaml](../render.yaml) and CI at [.github/workflows/ci.yml](../.github/workflows/ci.yml).

### What Render will create

- Web service: `uwindsor-findit-dev`
- Postgres database: `uwindsor-findit-dev-db`
- Region: `ohio`
- Branch: `dev`
- Deploy trigger: after GitHub checks pass

### How to create the Render environment

1. Push this branch to GitHub.
2. In Render, choose **New > Blueprint** and select this repository.
3. Accept the default service and database names unless you also update the host env vars in `render.yaml`.
4. Choose the free plans for the web service and Postgres.
5. After the first deploy, verify:

```text
https://uwindsor-findit-dev.onrender.com/health/
```

### Render commands and behavior

- Build:

```bash
pip install -r requirements/prod.txt && python manage.py collectstatic --noinput
```

- Pre-deploy:

- Start:

```bash
./scripts/render-start.sh
```

The start script runs migrations before starting Gunicorn because Render free tier does not support `preDeployCommand`.
Load demo data manually with `loaddata` if you want sample content in a fresh Render database.

The included Render blueprint does not configure a real email provider. Unless you add one yourself, deployed environments will use Django's console email backend.

### Demo limitations

- Uploaded files are served locally from the Render instance and can disappear after a restart or redeploy.
- The free Render Postgres plan is suitable for a school demo, not a long-lived environment.

## Useful commands

```bash
python manage.py check
python manage.py migrate
mkdir -p storage/items/demo
cp apps/listings/sample_media/items/* storage/items/demo/
python manage.py loaddata apps/listings/fixtures/initial_data.json
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py test apps.core.tests apps.chat.tests apps.listings.tests
```

## Troubleshooting

### "Dependency on app with no migrations"

```bash
python manage.py makemigrations <app_label>
python manage.py migrate
```

### Reset Docker Postgres

This deletes all local Postgres data:

```bash
docker compose down -v
docker compose up --build
```

### Reset local SQLite demo data

```bash
rm -f db.sqlite3
rm -rf storage
python manage.py migrate
mkdir -p storage/items/demo
cp apps/listings/sample_media/items/* storage/items/demo/
python manage.py loaddata apps/listings/fixtures/initial_data.json
python manage.py runserver
```
