#!/usr/bin/env python3
"""
Media Organiser — creates Jellyfin-compatible symlinks from a Zurg/rclone mount.

Reads the raw torrent-named files from /zurg/films/ and /zurg/shows/, parses
them with guessit, optionally verifies against TMDb, and creates a clean symlink
tree at /media/films/ and /media/shows/ following Jellyfin naming conventions.

Jellyfin naming conventions:
  Films: /media/films/Film Name (Year)/Film Name (Year).ext
  Shows: /media/shows/Show Name (Year)/Season XX/Show Name (Year) SXXEXX.ext

Environment variables:
  TMDB_API_KEY        — TMDb API key for name verification (optional but recommended)
  SCAN_INTERVAL_SECS  — seconds between scans (default: 300)
  PUID / PGID         — not used directly (symlinks don't have ownership issues)
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import requests
from guessit import guessit

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ZURG_MOUNT = Path("/zurg")
MEDIA_DIR = Path("/media")
STATE_FILE = Path("/app/data/state.json")

# The path where the Zurg mount appears inside Jellyfin's container.
# Both the organiser and Jellyfin run their own rclone mount at /zurg.
JELLYFIN_ZURG_PATH = Path(os.environ.get("JELLYFIN_ZURG_PATH", "/zurg"))

FILMS_DIR = MEDIA_DIR / "films"
SHOWS_DIR = MEDIA_DIR / "shows"

ZURG_FILMS = ZURG_MOUNT / "films"
ZURG_SHOWS = ZURG_MOUNT / "shows"

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECS", "300"))

TMDB_BASE = "https://api.themoviedb.org/3"

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".ts", ".vob", ".iso", ".m2ts",
}

# Characters that are not allowed in filenames (Jellyfin restriction)
UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

# ---------------------------------------------------------------------------
# Quality scoring — when duplicates exist, the highest score wins
# ---------------------------------------------------------------------------

RESOLUTION_SCORES = {
    "4320p": 100,  # 8K
    "2160p": 90,   # 4K
    "1080p": 70,
    "1080i": 65,
    "720p":  50,
    "576p":  30,
    "480p":  20,
    "360p":  10,
}

SOURCE_SCORES = {
    "Blu-ray":    60,
    "Ultra HD Blu-ray": 65,
    "HD-DVD":     55,
    "Web":        40,
    "HDTV":       35,
    "PDTV":       25,
    "SDTV":       20,
    "DVD":        30,
    "VHS":        5,
    "Telecine":   10,
    "Telesync":   8,
    "Workprint":  3,
    "Camera":     1,
}

CODEC_SCORES = {
    "H.265": 30,
    "HEVC":  30,
    "H.264": 20,
    "AVC":   20,
    "VP9":   18,
    "AV1":   35,
    "MPEG-2": 5,
    "XviD":   3,
    "DivX":   3,
}

# Bonus points for various quality markers
REMUX_BONUS = 25       # Remux = untouched disc stream
HDR_BONUS = 15         # Any HDR (HDR10, HDR10+, Dolby Vision, HLG)
ATMOS_BONUS = 10       # Dolby Atmos / DTS:X
LOSSLESS_AUDIO_BONUS = 8  # DTS-HD MA, TrueHD, FLAC, PCM


def score_quality(name: str) -> int:
    """Score a torrent/file name by quality. Higher = better."""
    guess = guessit(name)
    score = 0

    # Resolution
    res = guess.get("screen_size", "")
    score += RESOLUTION_SCORES.get(res, 0)

    # Source
    source = guess.get("source", "")
    if isinstance(source, list):
        score += max(SOURCE_SCORES.get(s, 0) for s in source)
    else:
        score += SOURCE_SCORES.get(source, 0)

    # Video codec
    codec = guess.get("video_codec", "")
    score += CODEC_SCORES.get(codec, 0)

    # Remux bonus
    name_upper = name.upper()
    if "REMUX" in name_upper:
        score += REMUX_BONUS

    # HDR bonus
    other = guess.get("other", [])
    if not isinstance(other, list):
        other = [other]
    hdr_terms = {"HDR10", "HDR10+", "HDR", "Dolby Vision", "DV", "HLG", "HDR10Plus"}
    if any(o in hdr_terms for o in other) or any(t in name_upper for t in ("HDR", "DV", "DOLBY.VISION")):
        score += HDR_BONUS

    # Lossless audio bonus
    audio = guess.get("audio_codec", "")
    if isinstance(audio, list):
        audio = " ".join(audio)
    audio_str = f"{audio} {name_upper}"
    if any(t in audio_str for t in ("DTS-HD", "DTS-HD MA", "TRUEHD", "TRUE HD", "FLAC", "PCM", "LPCM")):
        score += LOSSLESS_AUDIO_BONUS

    # Atmos / DTS:X bonus
    if "ATMOS" in name_upper or "DTS:X" in name_upper or "DTS-X" in name_upper:
        score += ATMOS_BONUS

    return score


def format_score(score: int) -> str:
    """Human-readable quality score label."""
    if score >= 200:
        return f"★★★★★ ({score})"
    if score >= 150:
        return f"★★★★ ({score})"
    if score >= 100:
        return f"★★★ ({score})"
    if score >= 50:
        return f"★★ ({score})"
    return f"★ ({score})"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("organiser")


# ---------------------------------------------------------------------------
# State persistence — track what we've already processed
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load the processing state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt state file, starting fresh")
    return {"films": {}, "shows": {}}


def save_state(state: dict):
    """Persist the processing state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# TMDb lookup
# ---------------------------------------------------------------------------

def tmdb_search_film(title: str, year: int | None = None) -> dict | None:
    """Search TMDb for a film, return {title, year} or None."""
    if not TMDB_API_KEY:
        return None
    params = {"api_key": TMDB_API_KEY, "query": title}
    if year:
        params["year"] = year
    try:
        resp = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            r = results[0]
            release = r.get("release_date", "")
            return {
                "title": r["title"],
                "year": int(release[:4]) if release and len(release) >= 4 else year,
            }
    except Exception as e:
        log.debug(f"TMDb film search failed for '{title}': {e}")
    return None


def tmdb_search_tv(title: str, year: int | None = None) -> dict | None:
    """Search TMDb for a TV show, return {title, year} or None."""
    if not TMDB_API_KEY:
        return None
    params = {"api_key": TMDB_API_KEY, "query": title}
    if year:
        params["first_air_date_year"] = year
    try:
        resp = requests.get(f"{TMDB_BASE}/search/tv", params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            r = results[0]
            air_date = r.get("first_air_date", "")
            return {
                "title": r["name"],
                "year": int(air_date[:4]) if air_date and len(air_date) >= 4 else year,
            }
    except Exception as e:
        log.debug(f"TMDb TV search failed for '{title}': {e}")
    return None


# ---------------------------------------------------------------------------
# Name sanitisation
# ---------------------------------------------------------------------------

def sanitise(name: str) -> str:
    """Remove characters that Jellyfin doesn't allow in filenames."""
    name = UNSAFE_CHARS.sub("", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing dots/spaces (Windows compat)
    name = name.rstrip(". ")
    return name


def format_film_name(title: str, year: int | None) -> str:
    """Format: Film Name (Year)"""
    title = sanitise(title)
    if year:
        return f"{title} ({year})"
    return title


def format_show_name(title: str, year: int | None) -> str:
    """Format: Show Name (Year)"""
    title = sanitise(title)
    if year:
        return f"{title} ({year})"
    return title


def format_episode(title: str, year: int | None, season: int, episode: int | list) -> str:
    """Format: Show Name (Year) SXXEXX"""
    base = format_show_name(title, year)
    if isinstance(episode, list):
        ep_str = "".join(f"E{e:02d}" for e in episode)
    else:
        ep_str = f"E{episode:02d}"
    return f"{base} S{season:02d}{ep_str}"


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_video_files(directory: Path) -> list[Path]:
    """Recursively find all video files in a directory."""
    if not directory.exists():
        return []
    files = []
    try:
        for item in directory.rglob("*"):
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                files.append(item)
    except OSError as e:
        log.warning(f"Error scanning {directory}: {e}")
    return files


# ---------------------------------------------------------------------------
# Symlink management
# ---------------------------------------------------------------------------

def create_symlink(source: Path, target: Path):
    """Create a symlink at target pointing to source, creating parent dirs.

    The source path is remapped from the organiser's mount (/zurg/...) to the
    Jellyfin mount path (/mnt/zurg/...) so symlinks resolve inside Jellyfin.
    """
    # Remap: /zurg/films/X → /mnt/zurg/films/X (Jellyfin's view)
    try:
        relative_to_zurg = source.relative_to(ZURG_MOUNT)
        symlink_target = JELLYFIN_ZURG_PATH / relative_to_zurg
    except ValueError:
        symlink_target = source

    if target.exists() or target.is_symlink():
        if target.is_symlink() and os.readlink(target) == str(symlink_target):
            return
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(symlink_target)
    log.info(f"  ✓ {target.relative_to(MEDIA_DIR)} → {symlink_target}")


def cleanup_broken_symlinks(directory: Path):
    """Remove symlinks whose target no longer exists, then prune empty dirs."""
    if not directory.exists():
        return

    removed = 0
    for item in directory.rglob("*"):
        if item.is_symlink() and not item.resolve().exists():
            log.info(f"  ✗ Removing broken symlink: {item.relative_to(MEDIA_DIR)}")
            item.unlink()
            removed += 1

    if removed:
        log.info(f"  Cleaned up {removed} broken symlink(s)")

    # Prune empty directories (bottom-up)
    for dirpath in sorted(directory.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
            log.debug(f"  Removed empty dir: {dirpath}")


# ---------------------------------------------------------------------------
# Processing logic
# ---------------------------------------------------------------------------

def process_films(state: dict) -> dict:
    """Process the Zurg films directory and create film symlinks.

    When multiple source files map to the same film, the one with the
    highest quality score wins.
    """
    processed = state.get("films", {})
    video_files = find_video_files(ZURG_FILMS)

    if not video_files:
        log.info("  No video files found in films directory")
        return processed

    # Collect candidates grouped by target path: {target_str: [(source, score, guess_name, meta)]}
    candidates: dict[str, list] = {}

    for video_path in video_files:
        # Use the torrent folder name (parent) for guessing if available
        # Zurg typically creates: /films/<torrent_name>/<video_file>
        relative = video_path.relative_to(ZURG_FILMS)
        if len(relative.parts) > 1:
            guess_name = relative.parts[0]
        else:
            guess_name = video_path.stem

        guess = guessit(guess_name, {"type": "movie"})
        title = guess.get("title", guess_name)
        year = guess.get("year")

        # Try TMDb for a canonical name
        tmdb = tmdb_search_film(title, year)
        if tmdb:
            title = tmdb["title"]
            year = tmdb.get("year", year)

        film_name = format_film_name(title, year)
        target_file = FILMS_DIR / film_name / f"{film_name}{video_path.suffix}"
        target_str = str(target_file)

        score = score_quality(guess_name)

        if target_str not in candidates:
            candidates[target_str] = []
        candidates[target_str].append((video_path, score, guess_name, title, year))

    # For each target, pick the best candidate
    new_processed = {}
    for target_str, options in candidates.items():
        target_file = Path(target_str)

        if len(options) > 1:
            options.sort(key=lambda x: x[1], reverse=True)
            best = options[0]
            log.info(f"  Film: {best[3]} — {len(options)} versions found, picking best:")
            for src, sc, gn, *_ in options:
                marker = "→" if src == best[0] else " "
                log.info(f"    {marker} {format_score(sc)}  {gn}")
        else:
            best = options[0]

        video_path, score, guess_name, title, year = best
        source_key = str(video_path)

        # Check if this exact source is already linked
        if source_key in processed and processed[source_key].get("target") == target_str:
            new_processed[source_key] = processed[source_key]
            continue

        if len(options) == 1:
            log.info(f"  Film: {guess_name}  {format_score(score)}")

        create_symlink(video_path, target_file)

        new_processed[source_key] = {
            "title": title,
            "year": year,
            "target": target_str,
            "score": score,
        }

    return new_processed


def process_shows(state: dict) -> dict:
    """Process the Zurg shows directory and create TV show symlinks.

    When multiple source files map to the same episode, the one with the
    highest quality score wins.
    """
    processed = state.get("shows", {})
    video_files = find_video_files(ZURG_SHOWS)

    if not video_files:
        log.info("  No video files found in shows directory")
        return processed

    # Collect candidates grouped by target path
    candidates: dict[str, list] = {}

    for video_path in video_files:
        relative = video_path.relative_to(ZURG_SHOWS)
        if len(relative.parts) > 1:
            guess_name = relative.parts[0]
            full_guess = f"{relative.parts[0]} {video_path.name}"
        else:
            guess_name = video_path.stem
            full_guess = video_path.name

        guess = guessit(full_guess, {"type": "episode"})
        title = guess.get("title", guess_name)
        year = guess.get("year")
        season = guess.get("season", 1)
        episode = guess.get("episode")

        if episode is None:
            guess2 = guessit(video_path.name, {"type": "episode"})
            episode = guess2.get("episode")
            if not title or title == guess_name:
                title = guess2.get("title", title)
            if not year:
                year = guess2.get("year")
            season = guess2.get("season", season)

        if episode is None:
            log.warning(f"  Skipping (no episode detected): {video_path.name}")
            continue

        # Try TMDb for a canonical show name
        tmdb = tmdb_search_tv(title, year)
        if tmdb:
            title = tmdb["title"]
            year = tmdb.get("year", year)

        show_name = format_show_name(title, year)
        season_dir = SHOWS_DIR / show_name / f"Season {season:02d}"
        episode_name = format_episode(title, year, season, episode)
        target_file = season_dir / f"{episode_name}{video_path.suffix}"
        target_str = str(target_file)

        score = score_quality(video_path.name)

        if target_str not in candidates:
            candidates[target_str] = []
        candidates[target_str].append((video_path, score, title, year, season, episode))

    # For each target, pick the best candidate
    new_processed = {}
    for target_str, options in candidates.items():
        target_file = Path(target_str)

        if len(options) > 1:
            options.sort(key=lambda x: x[1], reverse=True)
            best = options[0]
            log.info(f"  Show: {best[2]} S{best[4]:02d} — {len(options)} versions, picking best:")
            for src, sc, *_ in options:
                marker = "→" if src == best[0] else " "
                log.info(f"    {marker} {format_score(sc)}  {src.name}")
        else:
            best = options[0]

        video_path, score, title, year, season, episode = best
        source_key = str(video_path)

        # Check if this exact source is already linked
        if source_key in processed and processed[source_key].get("target") == target_str:
            new_processed[source_key] = processed[source_key]
            continue

        if len(options) == 1:
            log.info(f"  Show: {video_path.name}  {format_score(score)}")

        create_symlink(video_path, target_file)

        new_processed[source_key] = {
            "title": title,
            "year": year,
            "season": season,
            "episode": episode if isinstance(episode, int) else list(episode),
            "target": target_str,
            "score": score,
        }

    return new_processed


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_scan():
    """Run a single scan cycle."""
    log.info("Starting scan...")

    state = load_state()

    # Clean up broken symlinks first
    log.info("Checking for broken symlinks...")
    cleanup_broken_symlinks(FILMS_DIR)
    cleanup_broken_symlinks(SHOWS_DIR)

    # Also purge state entries whose sources no longer exist
    for category in ("films", "shows"):
        stale_keys = [
            k for k in state.get(category, {})
            if not Path(k).exists()
        ]
        for k in stale_keys:
            del state[category][k]

    # Process new content
    log.info("Processing films...")
    state["films"] = process_films(state)

    log.info("Processing shows...")
    state["shows"] = process_shows(state)

    save_state(state)

    total = len(state.get("films", {})) + len(state.get("shows", {}))
    log.info(f"Scan complete. Tracking {total} item(s) "
             f"({len(state.get('films', {}))} films, {len(state.get('shows', {}))} shows)")


def main():
    """Entry point — run scan loop."""
    log.info("=" * 60)
    log.info("Media Organiser starting")
    log.info(f"  Zurg mount:     {ZURG_MOUNT}")
    log.info(f"  Jellyfin path:  {JELLYFIN_ZURG_PATH}")
    log.info(f"  Media output:   {MEDIA_DIR}")
    log.info(f"  TMDb API:       {'enabled' if TMDB_API_KEY else 'disabled (set TMDB_API_KEY for better naming)'}")
    log.info(f"  Scan interval:  {SCAN_INTERVAL}s")
    log.info("=" * 60)

    # Ensure output directories exist
    FILMS_DIR.mkdir(parents=True, exist_ok=True)
    SHOWS_DIR.mkdir(parents=True, exist_ok=True)

    # Wait for Zurg mount to become available
    log.info("Waiting for Zurg mount...")
    for attempt in range(60):
        if ZURG_MOUNT.exists() and any(ZURG_MOUNT.iterdir()):
            log.info("Zurg mount detected")
            break
        time.sleep(5)
    else:
        log.warning("Zurg mount not detected after 5 minutes, starting anyway")

    # Initial scan
    run_scan()

    # Continuous loop
    while True:
        log.info(f"Next scan in {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)
        try:
            run_scan()
        except Exception as e:
            log.error(f"Scan failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
