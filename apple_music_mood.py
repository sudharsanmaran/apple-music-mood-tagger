#!/usr/bin/env python3
"""
apple_music_mood.py — tag selected Apple Music tracks by language + mood/energy,
and (bonus) fill their BPM, using free audio features from ReccoBeats.

This works for Apple Music *subscription* tracks (DRM streams) because it never
touches the audio file. For each selected track it:
    1. reads title + artist + duration from the Music app (AppleScript),
    2. finds the matching track on Spotify (to get a Spotify track ID),
    3. looks up that ID on ReccoBeats -> energy, danceability, tempo (BPM),
    4. derives independent trait tags (groovy, bright, energy-mid, rappy, ...)
       plus a suggested category word (Groove/Anthem/Intense/Warm/Soulful),
    5. guesses language (Tamil / English / Others) from genre + ISRC country,
    6. writes them across several fields so you can build Smart Playlists:
         Grouping  = the trait tags + category word  (for "contains" rules)
         Comments  = every raw audio number (reference)
         BPM       = tempo            (range-tunable)
         Rating    = energy x100      (range-tunable; you don't use stars)
         Movement# = danceability x100 (range-tunable; empty classical field)
    See TAGGING.md for the full field + tag-word reference.
    Tracks with no audio data get Grouping "<lang> untagged no-data".

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
         python3 apple_music_mood.py             # fetch new songs, tag them
         python3 apple_music_mood.py --force     # re-fetch + overwrite (reuses
                                                 #   cached Spotify id, so no search)
         python3 apple_music_mood.py --retune    # OFFLINE: re-bucket from cached
                                                 #   Comments data, no network at all
         python3 apple_music_mood.py --no-bpm    # tag mood only, skip BPM

Workflow: fetch each song once (the only rate-limited step); the raw numbers +
Spotify id are saved into Comments. After that, tune the threshold constants
below and run --retune to re-bucket the whole library instantly, offline.
Make the Grouping / BPM columns visible in Music to watch values appear.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"
RECCOBEATS_API = "https://api.reccobeats.com/v1"

REQUEST_PAUSE = 0.5      # seconds between lookups — spreads calls out to stay
                         # under Spotify's rolling ~30s rate-limit window

# ReccoBeats is behind Cloudflare, which bans urllib's default User-Agent
# (error 1010). A browser-like UA gets through.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Category split points (all 0..1). Tune after a dry run.
#   energy   = calm (low) .. intense (high)
#   valence  = sad/dark (low) .. happy/bright (high)
#   dance    = no groove (low) .. very groovy (high)
# Groove is decided by danceability + a small energy floor: a danceable
# rap/party song at mid energy IS a groove, but an ultra-calm steady melody is
# not. Only NON-danceable songs are then split by the high-energy line.
GROOVE_DANCE_MIN = 0.65     # danceability needed to count as a groove
GROOVE_ENERGY_FLOOR = 0.55  # ...but it also needs at least this much energy
ENERGY_HIGH = 0.70          # non-danceable + this energy = Anthem/Intense (powerful/heavy)
VALENCE_SPLIT = 0.50        # at/above = bright/happy; below = dark/sad

# Band edges for the independent TRAIT TAGS written into Grouping. These are
# what you build Smart Playlists from ("Grouping contains groovy"), and a song
# carries every tag it qualifies for — so it can land in multiple playlists.
ENERGY_LOW_MAX = 0.55       # < = energy-low ; < ENERGY_HIGH = energy-mid ; else energy-high
DANCE_GROOVY = 0.65         # >= = "groovy" ; >= 0.50 = "dance-mid" ; else "dance-low"
ACOUSTIC_MIN = 0.50         # >= = "acoustic" ; else "produced"
INSTRUMENTAL_MIN = 0.50     # >= = "instrumental"
SPEECH_RAP_MIN = 0.33       # >= = "rappy" (lots of spoken words / rap)
LIVE_MIN = 0.60             # >= = "live"
TEMPO_SLOW_MAX = 90         # < = "slow" ; < TEMPO_FAST_MIN = "mid-tempo" ; else "fast"
TEMPO_FAST_MIN = 130

# Numeric-field hijacks: store these 0..1 features x100 into spare numeric
# fields so they're RANGE-tunable in Smart Playlists (e.g. "Movement Number >
# 65"). See TAGGING.md. Set a flag False to leave that field untouched.
WRITE_ENERGY_TO_RATING = True       # Rating = energy x100 (you don't use stars)
WRITE_DANCE_TO_MOVEMENT = True      # Movement Number = danceability x100 (empty field)

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
        '(genre of t) & sep & (grouping of t) & sep & (bpm of t as text) & sep & '
        '(comment of t) & linefeed\n'
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
        if len(parts) < 8:
            continue
        dbid, name, artist, dur, genre, grouping, bpm, comment = parts[:8]
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
            "grouping": grouping, "cur_bpm": cur_bpm, "comment": comment,
        })
    return tracks


class RateLimited(Exception):
    """Raised on HTTP 429 so we stop cleanly instead of mislabeling everything."""
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__(f"rate limited; retry after {retry_after}s")


def _fetch_json(url, headers=None, data=None, method=None):
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(e.headers.get("Retry-After", "?"))
        raise


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
    except RateLimited:
        raise
    except Exception:
        items = []
    if not items:
        # Retry as a looser free-text query
        url = f"{SPOTIFY_API}/search?" + urllib.parse.urlencode(
            {"q": f"{_clean(name)} {_clean(artist)}", "type": "track", "limit": 10})
        try:
            items = _fetch_json(url, headers=headers)["tracks"]["items"]
        except RateLimited:
            raise
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
    except RateLimited:
        raise
    except Exception:
        return None
    return content[0] if content else None


# --- Classification ----------------------------------------------------------

def category_label(energy, valence, danceability):
    """Classify on danceability + energy + valence. Returns a CATEGORIES label.

        danceable + enough energy          -> Groove   (move-your-body, any mood)
        high energy, not danceable, dark   -> Intense
        high energy, not danceable, bright -> Anthem
        calm (low energy / not danceable), bright -> Warm
        calm, dark                         -> Soulful

    Danceability is the primary signal: it separates a mid-energy party/rap
    groove (dance ~0.8) from a mid-energy romantic melody (dance ~0.5). The
    energy floor keeps ultra-calm-but-steady songs out of Groove.
    """
    if danceability >= GROOVE_DANCE_MIN and energy >= GROOVE_ENERGY_FLOOR:
        return CATEGORIES["groove"]
    if energy >= ENERGY_HIGH:
        return CATEGORIES["intense"] if valence < VALENCE_SPLIT else CATEGORIES["anthem"]
    return CATEGORIES["warm"] if valence >= VALENCE_SPLIT else CATEGORIES["soulful"]


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


def set_comments(dbid, value):
    safe = value.replace('"', '\\"')
    run_osascript(
        f'tell application "Music" to set comment of '
        f'(first track whose database ID is {dbid}) to "{safe}"')


def set_rating(dbid, value):
    """Rating is 0..100 in Music (= stars x20). We store energy x100 here."""
    run_osascript(
        f'tell application "Music" to set rating of '
        f'(first track whose database ID is {dbid}) to {int(value)}')


def set_movement(dbid, value):
    """Movement Number (classical field, empty in this library). Stores dance x100."""
    run_osascript(
        f'tell application "Music" to set movement number of '
        f'(first track whose database ID is {dbid}) to {int(value)}')


def _band(value, low_edge, high_edge, low, mid, high):
    if value < low_edge:
        return low
    if value < high_edge:
        return mid
    return high


def build_tags(lang, feats, energy, valence, dance, bpm, cat_label):
    """Independent trait tags for the Grouping field. A song carries EVERY tag
    it qualifies for, so Smart Playlists ('Grouping contains groovy') can put
    one song in many lists — no single-category priority needed. The suggested
    category word (Groove/Warm/...) is appended so one-rule playlists also work.
    """
    tags = [lang.lower()]
    tags.append(_band(energy, ENERGY_LOW_MAX, ENERGY_HIGH,
                       "energy-low", "energy-mid", "energy-high"))
    tags.append("groovy" if dance >= DANCE_GROOVY
                else ("dance-mid" if dance >= 0.50 else "dance-low"))
    tags.append("bright" if valence >= VALENCE_SPLIT else "dark")

    ac = feats.get("acousticness")
    if ac is not None:
        tags.append("acoustic" if float(ac) >= ACOUSTIC_MIN else "produced")
    if feats.get("instrumentalness") is not None and float(feats["instrumentalness"]) >= INSTRUMENTAL_MIN:
        tags.append("instrumental")
    if feats.get("speechiness") is not None and float(feats["speechiness"]) >= SPEECH_RAP_MIN:
        tags.append("rappy")
    if feats.get("liveness") is not None and float(feats["liveness"]) >= LIVE_MIN:
        tags.append("live")
    if bpm:
        tags.append(_band(bpm, TEMPO_SLOW_MAX, TEMPO_FAST_MIN, "slow", "mid-tempo", "fast"))

    tags.append(cat_label.split(" (")[0])   # the suggested category word
    return " ".join(tags)


def full_comments(feats, bpm, spotify_id=None):
    """Every raw audio number we have, stored in Comments. Doubles as a cache:
    the numbers let us re-bucket offline (--retune), and spotify=<id> lets a
    re-fetch skip the (rate-limited) Spotify search."""
    parts = []
    for k in ("energy", "valence", "danceability", "acousticness",
              "instrumentalness", "speechiness", "liveness", "loudness"):
        v = feats.get(k)
        if v is not None:
            parts.append(f"{k}={float(v):.2f}")
    if bpm:
        parts.append(f"tempo={bpm}")
    for k in ("key", "mode", "isrc"):
        if feats.get(k) is not None:
            parts.append(f"{k}={feats[k]}")
    if spotify_id:
        parts.append(f"spotify={spotify_id}")
    return " ".join(parts)


def parse_comments(text):
    """Parse a Comments string we wrote back into a feature dict (+ spotify id).
    Returns {} if it doesn't look like our cache."""
    if not text or "energy=" not in text:
        return {}
    out = {}
    for tok in text.split():
        if "=" not in tok:
            continue
        k, _, v = tok.partition("=")
        if k in ("energy", "valence", "danceability", "acousticness",
                 "instrumentalness", "speechiness", "liveness", "loudness"):
            try:
                out[k] = float(v)
            except ValueError:
                pass
        elif k == "tempo":
            try:
                out["tempo"] = int(float(v))
            except ValueError:
                pass
        elif k in ("key", "mode", "isrc", "spotify"):
            out[k] = v
    return out


def classify_and_write(tr, feats, spotify_id, args):
    """Classify a feature dict and write all fields. Used by both the network
    fetch path and the offline --retune path. Returns 'tagged' or 'untagged'."""
    label = f'{tr["name"]} — {tr["artist"]}'

    if not feats or feats.get("energy") is None:
        lang = language_bucket(tr["genre"], None)
        grouping = f"{lang.lower()} untagged no-data"
        if args.dry_run:
            print(f"  ----    {label}  ->  '{grouping}'")
        else:
            try:
                set_grouping(tr["dbid"], grouping)
                print(f"  untag   {label}  ->  '{grouping}'")
            except RuntimeError as e:
                print(f"  FAIL    {label}  ({e})")
        return "untagged"

    energy = float(feats["energy"])
    valence = float(feats.get("valence") or 0.5)
    dance = float(feats.get("danceability") or 0.0)
    cat = category_label(energy, valence, dance)
    lang = language_bucket(tr["genre"], feats.get("isrc"))

    bpm = None
    if feats.get("tempo"):
        try:
            bpm = int(round(float(feats["tempo"])))
        except (ValueError, TypeError):
            bpm = None

    grouping = build_tags(lang, feats, energy, valence, dance, bpm, cat)
    comments = full_comments(feats, bpm, spotify_id or feats.get("spotify"))
    rating = round(energy * 100)
    movement = round(dance * 100)
    nums = f"[rating={rating} mvt={movement}" + (f" bpm={bpm}]" if bpm else "]")

    if args.dry_run:
        print(f"  ----    {label}\n            {grouping}   {nums}")
        return "tagged"
    try:
        set_grouping(tr["dbid"], grouping)
        if not args.no_comments:
            set_comments(tr["dbid"], comments)
        if bpm and not args.no_bpm and (not tr["cur_bpm"] or args.force or args.retune):
            set_bpm(tr["dbid"], bpm)
        if WRITE_ENERGY_TO_RATING:
            set_rating(tr["dbid"], rating)
        if WRITE_DANCE_TO_MOVEMENT:
            set_movement(tr["dbid"], movement)
        print(f"  tag     {label}\n            {grouping}   {nums}")
        return "tagged"
    except RuntimeError as e:
        print(f"  FAIL    {label}  ({e})")
        return "untagged"


# --- Main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Tag Apple Music tracks by language + mood, and fill BPM.")
    p.add_argument("--dry-run", action="store_true", help="Show results; write nothing")
    p.add_argument("--force", action="store_true", help="Re-fetch + overwrite even if already tagged")
    p.add_argument("--retune", action="store_true",
                   help="Re-bucket from cached Comments data only — NO network, no rate limit")
    p.add_argument("--batch", type=int, default=0, metavar="N",
                   help="Stop after N newly-fetched songs (rate-limit-safe chunking; 0 = no limit)")
    p.add_argument("--no-bpm", action="store_true", help="Tag mood only; don't write BPM")
    p.add_argument("--no-comments", action="store_true", help="Don't write raw audio numbers into Comments")
    args = p.parse_args()

    if not args.retune and (not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET):
        sys.exit("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars first "
                 "(see setup notes at the top of this file). Or use --retune (offline).")

    try:
        tracks = get_selected_tracks()
    except RuntimeError as e:
        sys.exit(f"Couldn't read the Music selection. Is Music open with tracks selected?\n{e}")
    if not tracks:
        sys.exit("No tracks selected. Select songs in Music, then run again.")

    mode = "RETUNE (offline)" if args.retune else "FETCH"
    print(f"Selected {len(tracks)} track(s).  Mode: {mode}\n")
    tagged = untagged = skipped = fetched = 0

    for tr in tracks:
        label = f'{tr["name"]} — {tr["artist"]}'
        cached = parse_comments(tr.get("comment", ""))

        # --- offline re-tune: re-bucket from the numbers already in Comments ---
        if args.retune:
            if not cached:
                print(f"  skip    {label}  (no cached data — fetch it once first)")
                skipped += 1
                continue
            status = classify_and_write(tr, cached, None, args)
            tagged += (status == "tagged"); untagged += (status == "untagged")
            continue

        # --- network fetch ---
        # "Done" = we already have cached numbers, OR we already tried and found
        # none. Old-format tags (grouping set but Comments empty) are NOT done,
        # so they get refreshed without needing --force.
        already = bool(cached) or ("untagged no-data" in (tr["grouping"] or ""))
        if already and not args.force:
            print(f"  skip    {label}  (already done)")
            skipped += 1
            continue

        spotify_id = cached.get("spotify")   # reuse cached id -> skip the search
        try:
            if not spotify_id:
                spotify_id = spotify_find_track(tr["name"], tr["artist"], tr["dur_sec"])
            feats = reccobeats_features(spotify_id) if spotify_id else None
        except RateLimited as e:
            print(f"\n⚠  Rate limited by the API (Retry-After: {e.retry_after}s).")
            print(f"   Tagged {tagged} song(s) before the limit. Wait, then re-run —")
            print(f"   already-tagged songs are skipped automatically (no --force needed).")
            break
        time.sleep(REQUEST_PAUSE)

        status = classify_and_write(tr, feats, spotify_id, args)
        tagged += (status == "tagged"); untagged += (status == "untagged")

        fetched += 1
        if args.batch and fetched >= args.batch:
            print(f"\n— Batch limit ({args.batch}) reached. Re-run to continue; "
                  f"already-tagged songs are skipped automatically.")
            break

    print(f"\nDone. Tagged: {tagged}   Untagged (no data): {untagged}   Skipped: {skipped}")
    if untagged:
        print("Untagged = no Spotify/ReccoBeats data (older or brand-new tracks).\n"
              "Grouped as '<lang> untagged no-data' — sort by Grouping to fix by hand.")


if __name__ == "__main__":
    main()
