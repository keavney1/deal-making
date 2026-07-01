#!/usr/bin/env bash
set -euo pipefail

# Creates a local virtual environment in `.venv` and installs requirements.txt if present
PYTHON=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-.venv}

echo "Creating virtualenv at $VENV_DIR using $PYTHON"
$PYTHON -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
  echo "Installed requirements from requirements.txt"
else
  echo "No requirements.txt found; virtualenv created"
fi

echo "Activate it with: source $VENV_DIR/bin/activate"
