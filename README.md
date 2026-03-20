# uwindsor-findit — Documentation

This folder contains living project docs for onboarding and collaboration.

- **SETUP.md** — how to run the project (Docker/DevContainer or local)
- **PROJECT_STRUCTURE.md** — apps/modules responsibilities and routing
- **CODING_STYLE.md** — Django conventions and separation of concerns
- **BRANCHING_STYLE.md** — Git flow + PR rules
- **render.yaml** — Render Blueprint for the `dev` demo environment
- **.github/workflows/ci.yml** — CI checks that gate auto-deploys from `dev`

## Database bootstrap

After pulling new model changes:

```bash
python3 manage.py migrate
python3 manage.py seed_minimal_catalogs
```

`seed_minimal_catalogs` is idempotent and creates baseline records for:
- categories
- campus locations
- sample items

## Deploying to Render

This repo is prepared for a Render demo deployment from the `dev` branch.

- Create a new Blueprint in Render and point it at this repository.
- Keep the default resource names from [render.yaml](render.yaml) unless you also update the host-related env vars there.
- Render will provision:
  - the web service `uwindsor-findit-dev`
  - the Postgres database `uwindsor-findit-dev-db`
- GitHub Actions runs CI on pushes and PRs targeting `dev`.
- Render is configured to auto-deploy only after those checks pass.
- On the free web service plan, bootstrap happens at app start because `preDeployCommand` is not supported.

After the first deploy:

- set the Brevo values that Render prompts for
- set `DJANGO_DEFAULT_FROM_EMAIL` to the sender address you already verified in Brevo
- if you intentionally switch back to Resend later, update `EMAIL_PROVIDER` and the matching provider env vars
- open `/health/` to verify the service is up
- optionally create a superuser from the Render Shell

Demo notes:

- uploads are intentionally ephemeral in this iteration
- the free Render Postgres plan is suitable for a short-lived demo, not a long-running environment
- Render Free cannot use SMTP, so this repo is configured to send email through Brevo's HTTP API by default
- the deploy flow assumes your `DJANGO_DEFAULT_FROM_EMAIL` sender is already verified in Brevo
- Resend remains supported as a secondary provider through `EMAIL_PROVIDER=resend`

> Keep these docs short, practical, and updated. If a doc changes behavior, update the README and any scripts accordingly.
