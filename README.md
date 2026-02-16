# Box 🦜 📦 🍿

Get movies and series. That's it. Using open-source technologies.

| Service                                                           | Description                        |
| ----------------------------------------------------------------- | ---------------------------------- |
| [Jellyfin](https://github.com/jellyfin/jellyfin)                  | Media server                       |
| [Deluge](https://github.com/deluge-torrent/deluge)                | Torrent client                     |
| [Prowlarr](https://github.com/Prowlarr/Prowlarr)                  | Indexer manager                    |
| [Sonarr](https://github.com/Sonarr/Sonarr)                        | Show manager                       |
| [Radarr](https://github.com/Radarr/Radarr)                        | Film manager                       |
| [File Browser](https://github.com/filebrowser/filebrowser)        | File management                    |
| [Portainer](https://github.com/portainer/portainer)               | Container management               |
| [Homepage](https://github.com/gethomepage/homepage)               | Dashboard                          |
| [Caddy + Tailscale](https://github.com/tailscale/caddy-tailscale) | HTTPS reverse proxy over Tailscale |
| [Gluetun](https://github.com/qdm12/gluetun)                       | VPN client (Mullvad WireGuard)     |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)
- [GitHub Desktop](https://desktop.github.com/) is recommended for cloning and managing the repository

## Step 1 — Basic setup

1. Copy `.env.example` to `.env`:
   ```
   cp .env.example .env
   ```
2. Check your timezone (`TZ`), `DOWNLOADS` and `MEDIA` paths are correct
3. Check `PUID` and `PGID` match your user (find with `id $USER`)

## Step 2 — Choose your access method

### Option A: Local only

Keep it simple. Services are available at `localhost` ports on the machine running Box. No Tailscale or Cloudflare needed.

No additional configuration needed — just build and start:

```
docker compose up -d --build
```

### Option B: Remote access (Tailscale + Cloudflare)

Access all services remotely via your own domain (e.g. `jellyfin.example.com`) over Tailscale. Requires a Tailscale account and a domain managed by Cloudflare.

1. [Create a Tailscale account](https://login.tailscale.com/start) (free tier works fine)
2. Go to [Settings → Keys](https://login.tailscale.com/admin/settings/keys) and generate a **reusable auth key**
3. Set `TS_AUTHKEY` in `.env`
4. Generate a Tailscale **API access token** at [Settings → Keys](https://login.tailscale.com/admin/settings/keys) and set `TS_API_KEY` in `.env`
5. Set `DOMAIN` in `.env` (e.g. `example.com`)
6. Create a [Cloudflare API token](https://dash.cloudflare.com/profile/api-tokens) with **Zone → DNS → Edit** permissions
7. Set `CF_API_TOKEN` in `.env`
8. Set `CF_ZONE_ID` in `.env` — found on your domain's overview page in the [Cloudflare dashboard](https://dash.cloudflare.com) (right sidebar, under **API**)
9. Copy the Caddyfile:
   ```
   cp apps/caddy/config/Caddyfile.cloudflare apps/caddy/data/Caddyfile
   ```
10. Generate the Homepage dashboard config:
    ```
    ./scripts/setup-homepage.sh
    ```
11. Build and start:
    ```
    docker compose up -d --build
    ```

> **Note:** DNS records are created automatically when the Caddy container starts. It registers itself as a Tailscale node called "box", then uses the Tailscale API to discover its own IP and upserts Cloudflare A records for `DOMAIN` and `*.DOMAIN`. Check progress with `docker compose logs caddy`. If you need to manually update DNS records after the container is running, you can still use `./scripts/setup-dns.sh`.

## Step 3 — Optional: Mullvad WireGuard VPN

Routes download traffic through Mullvad. Skip this step if you don't need a VPN.

1. Go to [Mullvad WireGuard config generator](https://mullvad.net/en/account/wireguard-config)
2. Generate and download a WireGuard configuration
3. Copy from the config file:
   - `PrivateKey` → `.env` as `WIREGUARD_PRIVATE_KEY`
   - `Address` (IPv4, e.g. `10.x.x.x/32`) → `.env` as `WIREGUARD_ADDRESSES`
4. Optionally set `VPN_CITY` in `.env` (e.g. `Zurich`, `London`)
5. Add to `.env`:
   ```
   COMPOSE_FILE=docker-compose.yml:docker-compose.vpn.yml
   ```

## Accessing your services

| Service      | Local            | Remote (Option B)                  |
| ------------ | ---------------- | ---------------------------------- |
| Jellyfin     | `localhost:8096` | `https://jellyfin.yourdomain.com`  |
| Homepage     | `localhost:3000` | `https://yourdomain.com`           |
| Portainer    | `localhost:9000` | `https://portainer.yourdomain.com` |
| File Browser | `localhost:8080` | `https://files.yourdomain.com`     |
| Deluge       | `localhost:8112` | `https://deluge.yourdomain.com`    |
| Prowlarr     | `localhost:9696` | `https://prowlarr.yourdomain.com`  |
| Sonarr       | `localhost:8989` | `https://sonarr.yourdomain.com`    |
| Radarr       | `localhost:7878` | `https://radarr.yourdomain.com`    |

## Jellyfin library cache

The Jellyfin data directory (`apps/jellyfin/data/`) is gitignored by default, so your library metadata is not committed. If you'd like to commit it for portability, remove the `apps/*/data/` rule from `.gitignore` and add back specific ignores for the other apps.

## Sharing with friends

1. In Tailscale, [share your device](https://tailscale.com/kb/1084/sharing) with friends
2. They install Tailscale, accept the share, then open the Jellyfin URL
3. Create Jellyfin accounts for them via the admin dashboard