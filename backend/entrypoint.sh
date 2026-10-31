#!/bin/sh
set -e
python -m app.ingest --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
