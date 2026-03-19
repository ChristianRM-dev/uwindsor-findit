#!/usr/bin/env sh

set -eu

python manage.py migrate
python manage.py seed_minimal_catalogs
python manage.py seed_message_demo

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}"
