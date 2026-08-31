#!/usr/bin/env bash
# Publish this project to a NEW public GitHub repo (one run; safe to re-run).
#
# It uses YOUR GitHub token (never echoed) to create the repo via the GitHub
# REST API, sets the remote on this local repo, and pushes `main`.
#
# Usage:
#   export GITHUB_TOKEN=ghp_...
#   export REPO_NAME=meeting-to-action-agent   # GitHub slug (optional)
#   ./publish.sh
#
# After this, the MIT LICENSE is visible in the repo's GitHub "About" section.
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: set GITHUB_TOKEN (a GitHub token with 'public_repo' / 'repo' scope)." >&2
  exit 1
fi
REPO_NAME="${REPO_NAME:-meeting-to-action-agent}"

# Resolve the repo owner from the token (without printing the token).
OWNER="$(curl -sSL -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["login"]}' 2>/dev/null || echo "")"
if [ -z "$OWNER" ]; then
  echo "ERROR: could not resolve GitHub user from token (token invalid?)." >&2
  exit 1
fi

echo "-> Creating public repo: github.com/$OWNER/$REPO_NAME"
curl -sSL -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$OWNER/$REPO_NAME" \
  -d "{\"name\":\"$REPO_NAME\",\"private\":false,\"description\":\"Meeting-to-Action Agent \xe2\x80\x94 Strands agent on Bedrock AgentCore\",\"auto_init\":false}" \
  >/dev/null || echo "   (repo may already exist \xe2\x9c\x93)"

# Point this local repo at the (new) public remote and push.
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
git branch -M main
git push -u origin main

echo
echo "Published: https://github.com/$OWNER/$REPO_NAME"
echo "LICENSE (MIT) is committed first \xe2\x90\x94 GitHub will show it in the repo 'About' section."
