#!/bin/bash
set -e
echo "Waiting for database..."
while ! python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('db', 5432)); s.close()" 2>/dev/null; do
  sleep 1
done
echo "Running migrations..."
python manage.py migrate --noinput
echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8000
