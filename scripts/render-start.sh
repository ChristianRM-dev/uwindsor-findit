#!/usr/bin/env sh

set -eu

python manage.py migrate

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}"
