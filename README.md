# uwindsor-findit — Documentation

This folder contains living project docs for onboarding and collaboration.

- **SETUP.md** — how to run the project (Docker/DevContainer or local)
- **PROJECT_STRUCTURE.md** — apps/modules responsibilities and routing
- **CODING_STYLE.md** — Django conventions and separation of concerns
- **BRANCHING_STYLE.md** — Git flow + PR rules

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

> Keep these docs short, practical, and updated. If a doc changes behavior, update the README and any scripts accordingly.
