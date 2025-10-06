#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip pre-commit
pre-commit install
echo "Repo initialized."