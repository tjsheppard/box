#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# setup-homepage.sh — Generate Homepage config files from templates
#
# Reads DOMAIN from .env and substitutes it into the templates along with
# any API key / credential variables.
#
# Usage:
#   ./setup-homepage.sh              # reads from .env
#   ./setup-homepage.sh example.com  # override domain
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/apps/homepage/config"
OUTPUT_DIR="${SCRIPT_DIR}/apps/homepage/data"
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
  echo "Usage: ./setup-homepage.sh <domain>"
  echo ""
  echo "Or set DOMAIN in .env"
  exit 1
fi

# --- Check templates exist ---
for tmpl in services.yaml.template settings.yaml.template bookmarks.yaml.template; do
  if [[ ! -f "${TEMPLATE_DIR}/${tmpl}" ]]; then
    echo "Error: Template not found at ${TEMPLATE_DIR}/${tmpl}"
    exit 1
  fi
done

# --- Ensure output directory exists ---
mkdir -p "${OUTPUT_DIR}"

# --- Generate config files from templates ---
for tmpl in services.yaml.template settings.yaml.template bookmarks.yaml.template; do
  output="${OUTPUT_DIR}/${tmpl%.template}"
  cp "${TEMPLATE_DIR}/${tmpl}" "$output"

  # Replace domain placeholder
  sed -i '' "s/<DOMAIN>/${DOMAIN}/g" "$output"

  # Replace API key and credential placeholders
  for VAR in JELLYFIN_API_KEY DELUGE_PASS PROWLARR_API_KEY SONARR_API_KEY RADARR_API_KEY PORTAINER_API_KEY; do
    VAL="${!VAR:-}"
    if [[ -n "$VAL" ]]; then
      sed -i '' "s/<${VAR}>/${VAL}/g" "$output"
    fi
  done
done

# --- Copy static config files to data directory ---
for static in docker.yaml widgets.yaml; do
  if [[ -f "${TEMPLATE_DIR}/${static}" ]]; then
    cp "${TEMPLATE_DIR}/${static}" "${OUTPUT_DIR}/${static}"
  fi
done

echo "Homepage config generated in: ${OUTPUT_DIR}/"
echo "  Domain: *.${DOMAIN}"
echo ""
echo "Files created:"
echo "  - services.yaml"
echo "  - settings.yaml"
echo "  - bookmarks.yaml"
echo ""
echo "Note: widgets.yaml and docker.yaml are static and don't need templating."
echo ""
echo "If you haven't set API keys yet, update these in .env and re-run:"
echo "  JELLYFIN_API_KEY, DELUGE_PASS, PROWLARR_API_KEY,"
echo "  SONARR_API_KEY, RADARR_API_KEY, PORTAINER_API_KEY"
