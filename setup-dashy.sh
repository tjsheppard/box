#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# setup-dashy.sh — Generate config/dashy/config.yml from the template
#
# Reads DOMAIN and TS_DOMAIN from .env. If both are set (Option C), the
# Cloudflare domain is used for primary links and Tailscale links are kept
# as a collapsed fallback section. If only one is set, the fallback section
# is removed.
#
# Usage:
#   ./setup-dashy.sh              # reads from .env
#   ./setup-dashy.sh example.com  # override primary domain
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

# Allow passing primary domain as argument
if [[ $# -ge 1 ]]; then
  DOMAIN="$1"
fi

# Resolve primary domain (DOMAIN takes precedence, then TS_DOMAIN)
PRIMARY="${DOMAIN:-${TS_DOMAIN:-}}"
TS_FALLBACK="${TS_DOMAIN:-}"

if [[ -z "$PRIMARY" ]]; then
  echo "Usage: ./setup-dashy.sh <domain>"
  echo ""
  echo "Or set DOMAIN or TS_DOMAIN in .env"
  exit 1
fi

# --- Check template exists ---
if [[ ! -f "$TEMPLATE" ]]; then
  echo "Error: Template not found at ${TEMPLATE}"
  exit 1
fi

# --- Generate config ---
cp "$TEMPLATE" "$OUTPUT"

# Replace primary domain placeholders
sed -i '' "s/<DOMAIN>/${PRIMARY}/g" "$OUTPUT"

# Handle Tailscale fallback section
if [[ -n "$TS_FALLBACK" && "$TS_FALLBACK" != "$PRIMARY" ]]; then
  # Option C: both domains — fill in fallback links
  sed -i '' "s/<TS_DOMAIN>/${TS_FALLBACK}/g" "$OUTPUT"
  echo "Dashy config generated: ${OUTPUT}"
  echo "  Primary:  *.${PRIMARY}"
  echo "  Fallback: *.${TS_FALLBACK}"
else
  # Option B or no fallback — remove the entire Tailscale Fallback section
  sed -i '' '/^  - name: Tailscale Fallback$/,$ d' "$OUTPUT"
  echo "Dashy config generated: ${OUTPUT}"
  echo "  Domain: *.${PRIMARY}"
fi
