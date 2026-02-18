# Box 🦜 📦 🍿

Stream films and shows from Real Debrid via Jellyfin. That's it.

Uses [Debrid Media Manager](https://debridmediamanager.com) to add content to your Real Debrid library, [Zurg](https://github.com/debridmediamanager/zurg-testing) to expose it as WebDAV, and a custom organiser to create clean Jellyfin-compatible symlinks.

```
Debrid Media Manager → Real Debrid → Zurg (WebDAV) → rclone (FUSE) → Organiser (symlinks) → Jellyfin
```

Each container that needs the Zurg filesystem (organiser, Jellyfin) runs its own embedded [rclone](https://rclone.org/) FUSE mount. This avoids FUSE mount propagation issues on macOS Docker Desktop.

| Service                                                           | Description                               |
| ----------------------------------------------------------------- | ----------------------------------------- |
| [Jellyfin](https://github.com/jellyfin/jellyfin)                  | Media server (+ embedded rclone mount)    |
| [Zurg](https://github.com/debridmediamanager/zurg-testing)        | Real Debrid WebDAV server                 |
| Media Organiser                                                   | Symlink creator (+ embedded rclone mount) |
| [File Browser](https://github.com/filebrowser/filebrowser)        | File management                           |
| [Portainer](https://github.com/portainer/portainer)               | Container management                      |
| [Homepage](https://github.com/gethomepage/homepage)               | Dashboard                                 |
| [Caddy + Tailscale](https://github.com/tailscale/caddy-tailscale) | HTTPS reverse proxy over Tailscale        |

## How it works

1. **Add content** — use [Debrid Media Manager](https://debridmediamanager.com) to add films and shows to your Real Debrid library
2. **Zurg** exposes your Real Debrid library as a WebDAV server, automatically categorising torrents into `films/` and `shows/` directories
3. **Media Organiser** mounts Zurg via its own embedded rclone instance, scans every 5 minutes, parses torrent names using `guessit`, verifies against TMDb, and creates clean symlinks:
   - `media/films/The Dark Knight (2008)/The Dark Knight (2008).mkv`
   - `media/shows/Breaking Bad (2008)/Season 01/Breaking Bad (2008) S01E01.mkv`
4. **Jellyfin** runs its own embedded rclone mount and reads the organised `media/` directory — symlinks resolve because both containers mount at `/zurg`

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)
- A [Real Debrid](https://real-debrid.com/) account
- [GitHub Desktop](https://desktop.github.com/) is recommended for cloning and managing the repository

## Step 1 — Basic setup

1. Copy `.env.example` to `.env`:
   ```
   cp .env.example .env
   ```
2. Set your **Real Debrid API token** (`REAL_DEBRID_API_KEY`) — get it from https://real-debrid.com/apitoken
3. Set your **TMDb API key** (`TMDB_API_KEY`) — free key from https://www.themoviedb.org/settings/api (recommended for accurate naming)
4. Check your timezone (`TZ`) and `MEDIA` path are correct
5. Check `PUID` and `PGID` match your user (find with `id $USER`)

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

## Adding content

1. Go to [Debrid Media Manager](https://debridmediamanager.com) and sign in with your Real Debrid account
2. Search for a film or show and add it to your library
3. Within ~5 minutes, the organiser will detect the new content, create properly named symlinks, and Jellyfin will pick it up on its next library scan

> **Tip:** You can trigger a Jellyfin library scan manually from the Jellyfin admin dashboard, or wait for the scheduled scan.

## Accessing your services

| Service      | Local            | Remote (Option B)                  |
| ------------ | ---------------- | ---------------------------------- |
| Jellyfin     | `localhost:8096` | `https://jellyfin.yourdomain.com`  |
| Homepage     | `localhost:3000` | `https://yourdomain.com`           |
| Portainer    | `localhost:9000` | `https://portainer.yourdomain.com` |
| File Browser | `localhost:8080` | `https://files.yourdomain.com`     |
| Zurg         | `localhost:9999` | `https://zurg.yourdomain.com`      |

## Transcoding

Jellyfin supports transcoding for clients that can't direct-play the source format. On macOS with Apple Silicon, hardware transcoding (VideoToolbox) is not available inside Docker containers — software transcoding is used instead, which is fast enough on Apple Silicon for most use cases.

If you migrate to a Linux host with an Intel iGPU or NVIDIA GPU, uncomment the device passthrough lines in `docker-compose.yml` to enable hardware transcoding.

## Jellyfin library cache

The Jellyfin data directory (`apps/jellyfin/data/`) is gitignored by default, so your library metadata is not committed. If you'd like to commit it for portability, remove the `apps/*/data/` rule from `.gitignore` and add back specific ignores for the other apps.

## Sharing with friends

1. In Tailscale, [share your device](https://tailscale.com/kb/1084/sharing) with friends
2. They install Tailscale, accept the share, then open the Jellyfin URL
3. Create Jellyfin accounts for them via the admin dashboard