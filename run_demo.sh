#!/usr/bin/env bash
# Run the Meeting-to-Action Agent demo locally (fully offline).
#
# Usage:
#   ./run_demo.sh            # offline demo mode (MODEL_PROVIDER=fake), seeds samples
#   MODEL_PROVIDER=local ./run_demo.sh   # live local model via Ollama (must be running)
#   MODEL_PROVIDER=bedrock ./run_demo.sh # deploy-style Bedrock (needs AWS creds)
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
export PYTHONUNBUFFERED=1
export AGENT_DATA_DIR="$(pwd)/data"
export MODEL_PROVIDER="${MODEL_PROVIDER:-fake}"   # offline demo by default
export EMAIL_SENDER="${EMAIL_SENDER:-simulated}"
mkdir -p "$AGENT_DATA_DIR"

echo "==> Creating Python venv (if needed)..."
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck source=/dev/null
. .venv/bin/activate

echo "==> Installing Python dependencies..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo "==> Building the dashboard..."
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install --silent)
fi
(cd frontend && npm run build --silent)

echo "==> Starting backend on http://127.0.0.1:8000  (model=$MODEL_PROVIDER, persistence=local)"
echo "    In offline (fake) mode the dashboard is pre-seeded with 3 sample meetings"
echo "    (clean / overdue / ambiguous) so you can see escalations immediately."
exec python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
