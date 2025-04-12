#!/bin/sh
set -e

echo "Collect static files"
python manage.py collectstatic --noinput

echo "Make database migrations and apply it"
python manage.py makemigrations
python manage.py migrate

echo "Starting server"
gunicorn main.wsgi -w 3 -b unix:/app/socket/wsgi.socket --capture-output