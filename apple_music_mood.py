#!/usr/bin/env python3
"""
apple_music_mood.py — tag selected Apple Music tracks by language + mood/energy,
and (bonus) fill their BPM, using free audio features from ReccoBeats.

This works for Apple Music *subscription* tracks (DRM streams) because it never
touches the audio file. For each selected track it:
    1. reads title + artist + duration from the Music app (AppleScript),
    2. finds the matching track on Spotify (to get a Spotify track ID),
    3. looks up that ID on ReccoBeats -> energy, danceability, tempo (BPM),
    4. buckets it on the energy x valence map into one of:
         Groove / Anthem / Intense / Warm / Soulful,
    5. guesses language (Tamil / English / Others) from genre + ISRC country,
    6. writes "Tamil / Groove (upbeat + danceable)" into Grouping (and BPM).
    Tracks with no audio data are written as "<lang> / Untagged (no data)".

------------------------------------------------------------------------------
ONE-TIME SETUP
------------------------------------------------------------------------------
ReccoBeats needs no key. Spotify search needs a free developer app:
    1. Go to https://developer.spotify.com/dashboard  -> Create app.
       Redirect URI can be anything (e.g. http://localhost). No backlink needed.
    2. Copy the Client ID and Client Secret.
    3. In the SAME Terminal window you run this from:
         export SPOTIFY_CLIENT_ID="your-client-id"
         export SPOTIFY_CLIENT_SECRET="your-client-secret"
No pip installs needed. Standard library + osascript only.

------------------------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------------------------
    1. In Music, open a playlist and SELECT the tracks (Cmd-A = all in list).
    2. In Terminal:
         python3 apple_music_mood.py --dry-run   # preview, writes nothing
         python3 apple_music_mood.py             # write Grouping (+ BPM)
         python3 apple_music_mood.py --force     # overwrite existing values
         python3 apple_music_mood.py --no-bpm    # tag mood only, skip BPM
Make the Grouping / BPM columns visible in Music to watch values appear.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"
RECCOBEATS_API = "https://api.reccobeats.com/v1"

REQUEST_PAUSE = 0.25     # seconds between lookups, to be polite

# ReccoBeats is behind Cloudflare, which bans urllib's default User-Agent
# (error 1010). A browser-like UA gets through.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Category split points (all 0..1). Tune after a dry run.
#   energy   = calm (low) .. intense (high)
#   valence  = sad/dark (low) .. happy/bright (high)
#   dance    = no groove (low) .. very groovy (high)
ENERGY_SPLIT = 0.55    # at/above = energetic; below = calm
VALENCE_SPLIT = 0.50   # at/above = bright/happy; below = dark/sad
DANCE_SPLIT = 0.65     # within energetic+bright: at/above = Groove, below = Anthem

# Human-readable category labels (the bracket hints make them self-explanatory
# inside the Music Grouping column). These map onto the energy x valence map.
CATEGORIES = {
    "groove":   "Groove (upbeat + danceable)",
    "anthem":   "Anthem (upbeat + powerful)",
    "intense":  "Intense (heavy / serious)",
    "warm":     "Warm (calm + pleasant)",
    "soulful":  "Soulful (calm + sad)",
    "untagged": "Untagged (no data)",
}

# Genre/region markers that mean "Tamil" vs "Other Indian".
TAMIL_MARKERS = ("tamil", "kollywood")
INDIAN_MARKERS = (
    "indian", "desi", "filmi", "bollywood", "telugu", "malayalam",
    "kannada", "hindi", "carnatic", "punjabi", "bhangra",
)
# ---------------------------------------------------------------------------


def run_osascript(script):
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.rstrip("\n")


def get_selected_tracks():
    """Return list of dicts for the current Music selection.
    Uses an unlikely field separator so commas/tabs in titles are safe."""
    SEP = "␟"  # symbol for unit separator; won't appear in song metadata
    script = (
        'tell application "Music"\n'
        '    set out to ""\n'
        '    set sep to "' + SEP + '"\n'
        '    repeat with t in selection\n'
        '        try\n'
        '            set out to out & (database ID of t as text) & sep & '
        '(name of t) & sep & (artist of t) & sep & (duration of t as text) & sep & '
        '(genre of t) & sep & (grouping of t) & sep & (bpm of t as text) & linefeed\n'
        '        end try\n'
        '    end repeat\n'
        '    return out\n'
        'end tell'
    )
    raw = run_osascript(script)
    tracks = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split(SEP)
        if len(parts) < 7:
            continue
        dbid, name, artist, dur, genre, grouping, bpm = parts[:7]
        try:
            dur_sec = float(dur)
        except ValueError:
            dur_sec = 0.0
        try:
            cur_bpm = int(bpm)
        except ValueError:
            cur_bpm = 0
        tracks.append({
            "dbid": dbid, "name": name, "artist": artist,
            "dur_sec": dur_sec, "genre": genre,
            "grouping": grouping, "cur_bpm": cur_bpm,
        })
    return tracks


def _fetch_json(url, headers=None, data=None, method=None):
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs, data=data, method=method)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- Spotify -----------------------------------------------------------------

_spotify_token = {"value": None}


def spotify_token():
    if _spotify_token["value"]:
        return _spotify_token["value"]
    creds = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    headers = {
        "Authorization": "Basic " + base64.b64encode(creds).decode(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    token = _fetch_json(SPOTIFY_TOKEN_URL, headers=headers, data=data)["access_token"]
    _spotify_token["value"] = token
    return token


def _clean(title):
    """Trim feat/version tags that hurt search matching."""
    return title.split("(")[0].split("[")[0].split(" - ")[0].strip()


def spotify_find_track(name, artist, dur_sec):
    """Search Spotify and return the best-match track id, scoring by artist
    overlap and duration closeness. None if no hit."""
    q = f'track:{_clean(name)} artist:{_clean(artist)}'
    url = f"{SPOTIFY_API}/search?" + urllib.parse.urlencode(
        {"q": q, "type": "track", "limit": 10})
    headers = {"Authorization": "Bearer " + spotify_token()}
    try:
        items = _fetch_json(url, headers=headers)["tracks"]["items"]
    except Exception:
        items = []
    if not items:
        # Retry as a looser free-text query
        url = f"{SPOTIFY_API}/search?" + urllib.parse.urlencode(
            {"q": f"{_clean(name)} {_clean(artist)}", "type": "track", "limit": 10})
        try:
            items = _fetch_json(url, headers=headers)["tracks"]["items"]
        except Exception:
            return None
    if not items:
        return None

    artist_lc = artist.lower()
    junk = ("remix", "sped up", "slowed", "lofi", "lo-fi", "instrumental",
            "cover", "karaoke", "live")

    def score(it):
        s = 0.0
        names = [a["name"].lower() for a in it.get("artists", [])]
        if any(a in artist_lc or artist_lc in a for a in names):
            s += 3.0
        if dur_sec and it.get("duration_ms"):
            diff = abs(it["duration_ms"] / 1000.0 - dur_sec)
            s += max(0.0, 2.0 - diff / 5.0)   # within ~10s gives most of it
        tl = it["name"].lower()
        if any(j in tl for j in junk) and not any(j in name.lower() for j in junk):
            s -= 2.0
        s += it.get("popularity", 0) / 100.0
        return s

    best = max(items, key=score)
    return best["id"]


# --- ReccoBeats --------------------------------------------------------------

def reccobeats_features(spotify_id):
    """Return dict with energy/danceability/tempo for a Spotify track id, or None."""
    url = f"{RECCOBEATS_API}/audio-features?" + urllib.parse.urlencode({"ids": spotify_id})
    try:
        content = _fetch_json(url, headers={"Accept": "application/json"}).get("content") or []
    except Exception:
        return None
    return content[0] if content else None


# --- Classification ----------------------------------------------------------

def category_label(energy, valence, danceability):
    """Map a track onto the energy x valence emotional map (Russell circumplex),
    splitting the busy upbeat region by danceability. Returns a CATEGORIES label.

        energetic + dark            -> Intense
        energetic + bright + groovy -> Groove
        energetic + bright + steady -> Anthem
        calm + bright               -> Warm
        calm + dark                 -> Soulful
    """
    energetic = energy >= ENERGY_SPLIT
    bright = valence >= VALENCE_SPLIT
    if energetic:
        if not bright:
            return CATEGORIES["intense"]
        return CATEGORIES["groove"] if danceability >= DANCE_SPLIT else CATEGORIES["anthem"]
    return CATEGORIES["warm"] if bright else CATEGORIES["soulful"]


def language_bucket(music_genre, isrc):
    """Guess language from Apple's genre tag first (the only Tamil-specific
    signal), then the ISRC country code (first 2 chars; 'IN' = India).

    NOTE: ISRC country can't tell Tamil from Hindi/Telugu, so an Indian track
    with no 'Tamil' genre tag defaults to Tamil here (this library is
    Tamil-dominant). Flip that default below if you have lots of other-Indian.
    """
    mg = (music_genre or "").lower()
    country = (isrc or "")[:2].upper()
    if any(m in mg for m in TAMIL_MARKERS):
        return "Tamil"
    if any(m in mg for m in INDIAN_MARKERS):
        return "Others"            # genre explicitly names another Indian lang
    if country == "IN":
        return "Tamil"             # Indian release, no other marker -> assume Tamil
    if country:                    # released elsewhere
        return "English"
    return "Others"                # unknown


# --- Music writes ------------------------------------------------------------

def set_grouping(dbid, value):
    safe = value.replace('"', '\\"')
    run_osascript(
        f'tell application "Music" to set grouping of '
        f'(first track whose database ID is {dbid}) to "{safe}"')


def set_bpm(dbid, bpm):
    run_osascript(
        f'tell application "Music" to set bpm of '
        f'(first track whose database ID is {dbid}) to {bpm}')


# --- Main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Tag Apple Music tracks by language + mood, and fill BPM.")
    p.add_argument("--dry-run", action="store_true", help="Show results; write nothing")
    p.add_argument("--force", action="store_true", help="Overwrite Grouping/BPM even if already set")
    p.add_argument("--no-bpm", action="store_true", help="Tag mood only; don't write BPM")
    args = p.parse_args()

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        sys.exit("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars first "
                 "(see setup notes at the top of this file).")

    try:
        tracks = get_selected_tracks()
    except RuntimeError as e:
        sys.exit(f"Couldn't read the Music selection. Is Music open with tracks selected?\n{e}")
    if not tracks:
        sys.exit("No tracks selected. Select songs in Music, then run again.")

    print(f"Selected {len(tracks)} track(s).\n")
    tagged = untagged = skipped = 0

    for tr in tracks:
        label = f'{tr["name"]} — {tr["artist"]}'
        if tr["grouping"] and not args.force:
            print(f"  skip    {label}  (grouping already '{tr['grouping']}')")
            skipped += 1
            continue

        spotify_id = spotify_find_track(tr["name"], tr["artist"], tr["dur_sec"])
        feats = reccobeats_features(spotify_id) if spotify_id else None
        time.sleep(REQUEST_PAUSE)

        # No usable audio data -> group it for manual sorting, never guess.
        if not feats or feats.get("energy") is None:
            lang = language_bucket(tr["genre"], None)
            grouping = f"{lang} / {CATEGORIES['untagged']}"
            why = "no Spotify match" if not spotify_id else "no ReccoBeats data"
            if args.dry_run:
                print(f"  ----    {label}  ->  '{grouping}'  ({why})")
            else:
                try:
                    set_grouping(tr["dbid"], grouping)
                    print(f"  untag   {label}  ->  '{grouping}'  ({why})")
                except RuntimeError as e:
                    print(f"  FAIL    {label}  (couldn't write: {e})")
            untagged += 1
            continue

        energy = float(feats["energy"])
        valence = float(feats.get("valence") or 0.5)
        dance = float(feats.get("danceability") or 0.0)
        cat = category_label(energy, valence, dance)
        lang = language_bucket(tr["genre"], feats.get("isrc"))
        grouping = f"{lang} / {cat}"

        bpm = None
        if feats.get("tempo"):
            try:
                bpm = int(round(float(feats["tempo"])))
            except (ValueError, TypeError):
                bpm = None

        detail = f"e={energy:.2f} v={valence:.2f} d={dance:.2f}"
        if bpm:
            detail += f" bpm={bpm}"

        if args.dry_run:
            print(f"  ----    {label}  ->  '{grouping}'  ({detail})")
            tagged += 1
        else:
            try:
                set_grouping(tr["dbid"], grouping)
                if bpm and not args.no_bpm and (not tr["cur_bpm"] or args.force):
                    set_bpm(tr["dbid"], bpm)
                print(f"  tag     {label}  ->  '{grouping}'  ({detail})")
                tagged += 1
            except RuntimeError as e:
                print(f"  FAIL    {label}  (couldn't write: {e})")

    print(f"\nDone. Tagged: {tagged}   Untagged (no data): {untagged}   Skipped: {skipped}")
    if untagged:
        print("Untagged = no Spotify/ReccoBeats data (older or brand-new tracks).\n"
              "They're grouped as '... / Untagged (no data)' — sort by Grouping in\n"
              "Music to find and assign them by hand.")


if __name__ == "__main__":
    main()
