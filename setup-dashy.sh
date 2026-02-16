#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# setup-dashy.sh — Generate config/dashy/config.yml from the template
#
# Reads DOMAIN from .env and substitutes it into the template along with
# any credential variables.
#
# Usage:
#   ./setup-dashy.sh              # reads from .env
#   ./setup-dashy.sh example.com  # override domain
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/config/dashy/config.yml.template"
OUTPUT="${SCRIPT_DIR}/config/dashy/config.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

# --- Load .env ---
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

# Allow passing domain as argument
if [[ $# -ge 1 ]]; then
  DOMAIN="$1"
fi

if [[ -z "${DOMAIN:-}" ]]; then
  echo "Usage: ./setup-dashy.sh <domain>"
  echo ""
  echo "Or set DOMAIN in .env"
  exit 1
fi

# --- Check template exists ---
if [[ ! -f "$TEMPLATE" ]]; then
  echo "Error: Template not found at ${TEMPLATE}"
  exit 1
fi

# --- Generate config ---
cp "$TEMPLATE" "$OUTPUT"

# Replace domain placeholder
sed -i '' "s/<DOMAIN>/${DOMAIN}/g" "$OUTPUT"

# Replace credential placeholders
for VAR in DELUGE_USER DELUGE_PASS PROWLARR_USER PROWLARR_PASS SONARR_USER SONARR_PASS \
           RADARR_USER RADARR_PASS JELLYFIN_USER JELLYFIN_PASS FILEBROWSER_USER FILEBROWSER_PASS \
           PORTAINER_USER PORTAINER_PASS; do
  VAL="${!VAR:-}"
  if [[ -n "$VAL" ]]; then
    sed -i '' "s/<${VAR}>/${VAL}/g" "$OUTPUT"
  fi
done

echo "Dashy config generated: ${OUTPUT}"
echo "  Domain: *.${DOMAIN}"
