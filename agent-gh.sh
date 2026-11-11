#!/usr/bin/env bash
# agent-gh.sh — run a command as the anilhelvaci-agent[bot] GitHub App.
#
#   agent-gh.sh gh pr create --title "..." --body "..."
#   agent-gh.sh git commit -m "..."
#   agent-gh.sh git push origin agent/feature-x
#   agent-gh.sh bash            # a whole shell for an agent
#
# Only the wrapped process (and its children) act as the bot.
# Your normal shell, your `gh auth login`, and your git identity/signing stay untouched.
#
# Requires: openssl, curl, jq, gh

set -euo pipefail

APP_ID="${GH_APP_ID:-5718417}"
INSTALLATION_ID="${GH_APP_INSTALLATION_ID:-181019261}"
KEY="${GH_APP_PRIVATE_KEY_PATH:?Set GH_APP_PRIVATE_KEY_PATH to the GitHub App private key (.pem)}"
BOT_LOGIN="anilhelvaci-agent[bot]"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/agent-gh"
CACHE_FILE="$CACHE_DIR/token-$APP_ID-$INSTALLATION_ID"

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

mint_token() {
  local now header payload unsigned sig jwt
  now=$(date +%s)
  header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
  payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 540)) "$APP_ID" | b64url)
  unsigned="$header.$payload"
  sig=$(printf '%s' "$unsigned" | openssl dgst -sha256 -sign "$KEY" | b64url)
  jwt="$unsigned.$sig"

  curl -fsS -X POST \
    -H "Authorization: Bearer $jwt" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/app/installations/$INSTALLATION_ID/access_tokens" \
    | jq -r '.token'
}

get_token() {
  # Tokens live ~60 min; reuse one for up to 50 min.
  local now; now=$(date +%s)
  if [[ -f "$CACHE_FILE" ]]; then
    local cached_exp cached_tok
    read -r cached_exp cached_tok < "$CACHE_FILE" || true
    if [[ -n "${cached_tok:-}" && "$cached_exp" -gt "$now" ]]; then
      printf '%s' "$cached_tok"; return
    fi
  fi
  local tok; tok=$(mint_token)
  [[ -n "$tok" && "$tok" != "null" ]] || { echo "agent-gh: failed to mint token" >&2; exit 1; }
  mkdir -p "$CACHE_DIR"; chmod 700 "$CACHE_DIR"
  # Write to a private temp file, then rename, so parallel agents never read a partial file.
  local tmp; tmp=$(mktemp "$CACHE_DIR/token.XXXXXX")
  printf '%s %s\n' $((now + 3000)) "$tok" > "$tmp"
  mv -f "$tmp" "$CACHE_FILE"
  printf '%s' "$tok"
}

get_bot_id() {
  local f="$CACHE_DIR/bot_id"
  if [[ ! -s "$f" ]]; then
    mkdir -p "$CACHE_DIR"
    GH_TOKEN="$1" gh api "/users/anilhelvaci-agent%5Bbot%5D" --jq .id > "$f"
  fi
  cat "$f"
}

[[ $# -gt 0 ]] || { sed -n '2,12p' "$0"; exit 1; }

TOKEN=$(get_token)
BOT_ID=$(get_bot_id "$TOKEN")
BOT_EMAIL="${BOT_ID}+${BOT_LOGIN}@users.noreply.github.com"

# gh: GH_TOKEN overrides your stored login for this process only.
export GH_TOKEN="$TOKEN"

# git identity: env vars beat any user.name/user.email in git config.
export GIT_AUTHOR_NAME="$BOT_LOGIN"    GIT_AUTHOR_EMAIL="$BOT_EMAIL"
export GIT_COMMITTER_NAME="$BOT_LOGIN" GIT_COMMITTER_EMAIL="$BOT_EMAIL"

# git config overrides for this process only:
#  - never sign bot commits/tags with YOUR key
#  - push over HTTPS using gh as credential helper (which picks up GH_TOKEN)
#  - rewrite SSH GitHub URLs to HTTPS, so pushes never fall back to YOUR SSH key
export GIT_CONFIG_COUNT=6
export GIT_CONFIG_KEY_0=commit.gpgsign                   GIT_CONFIG_VALUE_0=false
export GIT_CONFIG_KEY_1=tag.gpgsign                      GIT_CONFIG_VALUE_1=false
export GIT_CONFIG_KEY_2=credential.https://github.com.helper GIT_CONFIG_VALUE_2=""
export GIT_CONFIG_KEY_3=credential.https://github.com.helper GIT_CONFIG_VALUE_3="!gh auth git-credential"
export GIT_CONFIG_KEY_4=url.https://github.com/.insteadOf     GIT_CONFIG_VALUE_4=git@github.com:
export GIT_CONFIG_KEY_5=url.https://github.com/.pushInsteadOf GIT_CONFIG_VALUE_5=git@github.com:

exec "$@"
