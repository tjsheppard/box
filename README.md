# Box 🦜 📦 🍿

Get movie and series. That's it. Using open-source technologies. You don't need to make any accounts.

https://github.com/filebrowser/filebrowser
https://github.com/deluge-torrent/deluge
https://github.com/Prowlarr/Prowlarr
https://github.com/jellyfin/jellyfin
https://github.com/Sonarr/Sonarr
https://github.com/Radarr/Radarr


## Step 1

Go to Mullvad VPN, download OpenVPN files and add content to:

1. `vpn.crt` - certificate
2. `vpn.txt` - username and password

## Step 2 

Check everything in `.env` is correct.
Make sure to add your Plex claim token and that your paths are correct (are they pointing to your external hard drive?).

### Run Docker
```
    docker compose up -d
```

## Step 3
Setup your applications:
- File Browser - `[hostname].local:8080/files`
- Deluge - `[hostname].local:8112`
- Prowlarr - `[hostname].local:9696`
- Sonarr - `[hostname].local:8989`
- Radarr - `[hostname].local:7878`
- Plex - `[hostname].local:32400/web`