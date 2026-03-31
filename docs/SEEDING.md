# Seeding

This project uses a Django JSON fixture for its official initial data.

## What gets loaded

The fixture at [../apps/listings/fixtures/initial_data.json](../apps/listings/fixtures/initial_data.json) loads:

- 8 default categories
- 29 official UWindsor campus buildings
- 1 active demo reporter user
- 3 sample items total
- 1 image per sample item

Tracked sample images are stored in [../apps/listings/sample_media/items](../apps/listings/sample_media/items) and must be copied into `storage/items/demo/` before running `loaddata`.

## Local SQLite Reset and Rebuild

Use these commands from the repo root:

```bash
rm -f db.sqlite3
rm -rf storage
./.venv/bin/python manage.py migrate
mkdir -p storage/items/demo
cp apps/listings/sample_media/items/* storage/items/demo/
./.venv/bin/python manage.py loaddata apps/listings/fixtures/initial_data.json
./.venv/bin/python manage.py runserver
```

## Demo Login

```text
demo.reporter@uwindsor.ca / DemoPass123!
```

## Optional Chat Demo Seed

The default initial dataset intentionally loads exactly 3 items and does not auto-seed chat demo content.

If you want the extra chat demo data later, run:

```bash
./.venv/bin/python manage.py seed_message_demo
```

## Notes

- The fixture is the official replacement for the old Python seed command.
- The application still uses a normal Django database such as SQLite or PostgreSQL.
- If you replace the sample images later, keep the same filenames unless you also update the fixture paths.
