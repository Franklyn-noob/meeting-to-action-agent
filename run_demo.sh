#!/usr/bin/env bash
# Run the Meeting-to-Action Agent demo locally (fully offline).
#
# Usage:
#   ./run_demo.sh                                   # offline demo mode (MODEL_PROVIDER=fake), seeds samples
#   MODEL_PROVIDER=local ./run_demo.sh              # live local model via Ollama (must be running)
#   MODEL_PROVIDER=groq ./run_demo.sh               # live Groq model (reads groq_api/GROQ_API_KEY from groq.env; set GROQ_MODEL_ID if needed)
#   MODEL_PROVIDER=bedrock ./run_demo.sh            # deploy-style Bedrock (needs AWS creds)
#   EMAIL_PROVIDER=smtp ./run_demo.sh               # real email via Gmail SMTP (needs smtp_email/smtp_password in groq.env)
#   MODEL_PROVIDER=groq EMAIL_PROVIDER=smtp ./run_demo.sh   # live Groq model + real SMTP email
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
export PYTHONUNBUFFERED=1
export AGENT_DATA_DIR="$(pwd)/data"
export MODEL_PROVIDER="${MODEL_PROVIDER:-fake}"   # offline demo by default
export EMAIL_SENDER="${EMAIL_SENDER:-simulated}"
# Safely load KEY=VALUE secrets from ./groq.env. We do NOT `source` it: a naive
# source would execute bare-token lines as shell commands (and can leak secret
# values verbatim in error messages). Instead each line is parsed with a guarded
# regex: the variable name is restricted to a valid identifier, so a KEY=VALUE
# line (spaces around '=' allowed) is only ever *assigned*, never executed. A
# lone bare-token line is assigned to GROQ_API_KEY for backward compatibility
# with the legacy single-token file. Loaded only for providers that need local
# secrets; production injects these via the AgentCore runtime environment.
if [ -f groq.env ] && { [ "${MODEL_PROVIDER:-}" = "groq" ] || [ "${EMAIL_PROVIDER:-}" = "smtp" ]; }; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [ -z "$line" ] && continue
    case "$line" in '#'*) continue;; esac
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
    elif [ -z "${GROQ_API_KEY:-}" ]; then
      export GROQ_API_KEY="$line"
    fi
  done < groq.env
fi
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
