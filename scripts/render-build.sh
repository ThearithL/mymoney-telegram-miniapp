#!/usr/bin/env bash
set -u

if pip install -r requirements.txt; then
  exit 0
else
  status=$?
  DEPLOY_NOTIFY_STATUS=build_failed python scripts/render_notify.py || true
  exit "$status"
fi
