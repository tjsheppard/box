#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# setup-dns.sh — Create or update a wildcard A record in Cloudflare DNS
#
# Reads DOMAIN, CF_API_TOKEN, and CF_ZONE_ID from .env, auto-detects the
# Tailscale IPv4 address, then ensures *.DOMAIN points to it.
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# --- Load .env ---
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: .env file not found at ${ENV_FILE}"
  echo "Copy .env.example to .env and fill in your values first."
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# --- Validate required variables ---
missing=()
[[ -z "${DOMAIN:-}" ]] && missing+=("DOMAIN")
[[ -z "${CF_API_TOKEN:-}" ]] && missing+=("CF_API_TOKEN")
[[ -z "${CF_ZONE_ID:-}" ]] && missing+=("CF_ZONE_ID")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Error: The following variables are missing from .env:"
  printf '  - %s\n' "${missing[@]}"
  echo ""
  echo "Set them in ${ENV_FILE} and try again."
  echo "CF_ZONE_ID can be found on your domain's overview page in the Cloudflare dashboard (right sidebar)."
  exit 1
fi

# --- Check dependencies ---
for cmd in curl jq tailscale; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: '$cmd' is required but not installed."
    exit 1
  fi
done

# --- Get Tailscale IP ---
echo "Detecting Tailscale IPv4 address..."
TAILSCALE_IP="$(tailscale ip -4 2>/dev/null)" || {
  echo "Error: Could not get Tailscale IP. Is Tailscale running?"
  echo "You can check with: tailscale status"
  exit 1
}
echo "  Tailscale IP: ${TAILSCALE_IP}"

# --- Cloudflare API ---
CF_API="https://api.cloudflare.com/client/v4"
RECORD_NAME="*.${DOMAIN}"

auth_header="Authorization: Bearer ${CF_API_TOKEN}"
content_type="Content-Type: application/json"

echo "Using Zone ID: ${CF_ZONE_ID}"

# Check for existing wildcard A record
echo "Checking for existing DNS record: ${RECORD_NAME}..."
response="$(curl -s -X GET \
  "${CF_API}/zones/${CF_ZONE_ID}/dns_records?type=A&name=${RECORD_NAME}" \
  -H "$auth_header" \
  -H "$content_type")"

success="$(echo "$response" | jq -r '.success')"
if [[ "$success" != "true" ]]; then
  echo "Error: Cloudflare API request failed."
  echo "$response" | jq '.errors' 2>/dev/null || echo "$response"
  exit 1
fi

record_count="$(echo "$response" | jq '.result | length')"

if [[ "$record_count" -gt 0 ]]; then
  # Record exists — check if update is needed
  record_id="$(echo "$response" | jq -r '.result[0].id')"
  current_ip="$(echo "$response" | jq -r '.result[0].content')"

  if [[ "$current_ip" == "$TAILSCALE_IP" ]]; then
    echo "DNS record already exists and is up to date."
    echo "  ${RECORD_NAME} → ${TAILSCALE_IP}"
    exit 0
  fi

  # Update existing record
  echo "Updating existing record (${current_ip} → ${TAILSCALE_IP})..."
  update_response="$(curl -s -X PUT \
    "${CF_API}/zones/${CF_ZONE_ID}/dns_records/${record_id}" \
    -H "$auth_header" \
    -H "$content_type" \
    -d "{\"type\":\"A\",\"name\":\"*\",\"content\":\"${TAILSCALE_IP}\",\"ttl\":1,\"proxied\":false}")"

  if [[ "$(echo "$update_response" | jq -r '.success')" == "true" ]]; then
    echo "DNS record updated successfully."
    echo "  ${RECORD_NAME} → ${TAILSCALE_IP}"
  else
    echo "Error: Failed to update DNS record."
    echo "$update_response" | jq '.errors' 2>/dev/null || echo "$update_response"
    exit 1
  fi
else
  # Create new record
  echo "Creating wildcard A record..."
  create_response="$(curl -s -X POST \
    "${CF_API}/zones/${CF_ZONE_ID}/dns_records" \
    -H "$auth_header" \
    -H "$content_type" \
    -d "{\"type\":\"A\",\"name\":\"*\",\"content\":\"${TAILSCALE_IP}\",\"ttl\":1,\"proxied\":false}")"

  if [[ "$(echo "$create_response" | jq -r '.success')" == "true" ]]; then
    echo "DNS record created successfully."
    echo "  ${RECORD_NAME} → ${TAILSCALE_IP}"
  else
    echo "Error: Failed to create DNS record."
    echo "$create_response" | jq '.errors' 2>/dev/null || echo "$create_response"
    exit 1
  fi
fi
