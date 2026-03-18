#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# IMPORTANT: Seed the database (ontology/shared schema) before the app starts
# This avoids race conditions between Gunicorn workers during the first run.
if [ -n "$DATABASE_URL" ]; then
    echo "Seeding database schema via build process..."
    python seed_db.py
else
    echo "DATABASE_URL not set, skipping build-time seeding."
fi

echo "Build script completed successfully."
