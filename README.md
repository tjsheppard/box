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
| [Dashy](https://github.com/Lissy93/dashy)                         | Dashboard                          |
| [Caddy + Tailscale](https://github.com/tailscale/caddy-tailscale) | HTTPS reverse proxy over Tailscale |
| [Gluetun](https://github.com/qdm12/gluetun)                       | VPN client (Mullvad WireGuard)     |

## Step 1 — Tailscale

1. [Create a Tailscale account](https://login.tailscale.com/start) (free tier works fine)
2. Go to [Settings → Keys](https://login.tailscale.com/admin/settings/keys) and generate a **reusable auth key**
3. Paste it into `.env` as `TS_AUTHKEY`

## Step 2 — Choose your access method

### Option A: Custom domain (Cloudflare)

Use this if you own a domain on Cloudflare. Services will be at `jellyfin.yourdomain.com`, etc.

1. Set `DOMAIN` in `.env` (e.g. `example.com`)
2. Create a [Cloudflare API token](https://dash.cloudflare.com/profile/api-tokens) with **Zone → DNS → Edit** permissions
3. Set `CF_API_TOKEN` in `.env`
4. The default `config/caddy/Caddyfile` is already configured for this mode
5. In Cloudflare DNS, add a **wildcard A record**:
   - **Name:** `*`
   - **Content:** your Tailscale IP (find it after first run in the [admin panel](https://login.tailscale.com/admin/machines))
   - **Proxy status:** DNS only (grey cloud — do NOT proxy)
6. Open `config/dashy/config.yml` and replace all `<DOMAIN>` with your domain

### Option B: Tailscale domain only

Use this if you don't have a custom domain. Services will be at `<service>.<tailnet>.ts.net`.

1. Copy the Tailscale Caddyfile:
   ```
   cp config/caddy/Caddyfile.tailscale config/caddy/Caddyfile
   ```
2. Find your **tailnet domain** at [DNS settings](https://login.tailscale.com/admin/dns) (e.g. `tail12345.ts.net`)
3. Set `TS_DOMAIN` in `.env`
4. Open `config/dashy/config.yml` and replace all `<DOMAIN>` with your tailnet domain

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

## Step 4 — Configure and run

1. Copy `.env.example` to `.env` and fill in your values:
   ```
   cp .env.example .env
   ```
2. Check your timezone, PUID/PGID, and media paths are correct
3. Build and start all containers:
   ```
   docker compose up -d --build
   ```

## Step 5 — Access your services

| Service      | Custom domain                      | Tailscale domain                     | Local            |
| ------------ | ---------------------------------- | ------------------------------------ | ---------------- |
| Jellyfin     | `https://jellyfin.yourdomain.com`  | `https://jellyfin.<tailnet>.ts.net`  | `localhost:8096` |
| Dashy        | `https://dashy.yourdomain.com`     | `https://dashy.<tailnet>.ts.net`     | `localhost:4000` |
| Portainer    | `https://portainer.yourdomain.com` | `https://portainer.<tailnet>.ts.net` | `localhost:9000` |
| File Browser | `https://files.yourdomain.com`     | `https://files.<tailnet>.ts.net`     | `localhost:8080` |
| Deluge       | `https://deluge.yourdomain.com`    | `https://deluge.<tailnet>.ts.net`    | `localhost:8112` |
| Prowlarr     | `https://prowlarr.yourdomain.com`  | `https://prowlarr.<tailnet>.ts.net`  | `localhost:9696` |
| Sonarr       | `https://sonarr.yourdomain.com`    | `https://sonarr.<tailnet>.ts.net`    | `localhost:8989` |
| Radarr       | `https://radarr.yourdomain.com`    | `https://radarr.<tailnet>.ts.net`    | `localhost:7878` |

## Jellyfin library cache

The Jellyfin config directory (`config/jellyfin/`) is **not** gitignored by default, so your library metadata cache is committable. This means you won't have to rebuild the library on a fresh clone. If you'd rather not commit it, uncomment the `config/jellyfin/*` line in `.gitignore`.

## Sharing with friends

1. In Tailscale, [share your device](https://tailscale.com/kb/1084/sharing) with friends
2. They install Tailscale, accept the share, then open the Jellyfin URL
3. Create Jellyfin accounts for them via the admin dashboard