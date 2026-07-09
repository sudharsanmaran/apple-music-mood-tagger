# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Command-line tools that organize an **Apple Music** library by mood, energy, and
language, then find similar songs — working on **streamed/DRM tracks** (no audio
files needed), including regional catalogs (Tamil, etc.) that most mood/BPM
databases don't cover. macOS-only.

## Commands

No build step, no dependencies (Python 3 standard library + `osascript` only),
no virtualenv. There is **no automated test suite** — verify by running against a
real Music selection or by calling classification functions with mock feature
dicts (they're pure and network-free).

```sh
# Main tagger (needs Spotify creds in env):
export SPOTIFY_CLIENT_ID="..." SPOTIFY_CLIENT_SECRET="..."
python3 apple_music_mood.py --dry-run     # preview, writes nothing
python3 apple_music_mood.py               # fetch + tag NEW songs only
python3 apple_music_mood.py --retune      # OFFLINE re-bucket from cached data
python3 apple_music_mood.py --force       # from scratch: re-search Spotify + overwrite
python3 apple_music_mood.py --retry-nodata        # retry stuck no-data songs: lookup, then clip-analysis fallback
python3 apple_music_mood.py --retry-nodata --force # also revisit 'extract-failed' + re-search from scratch
python3 apple_music_mood.py --batch 100   # stop after 100 newly-fetched songs

python3 apple_music_similar.py            # playlist of songs like the selection (offline)
python3 apple_music_bpm.py                # BPM-only legacy alternative (GetSongBPM key)
```

All three tools operate on the **current selection in the Music app** (or, for
`apple_music_similar.py`, scan the whole library for candidates). The first run
triggers a macOS prompt to let the terminal control Music — this must be accepted.

## Architecture

Pipeline (per selected song):
`Music app (title/artist/genre) → Spotify search (→ track id) → ReccoBeats (id → audio features) → classify → write back to Music metadata`

**The song's own metadata IS the database.** There is no external store. Each
song's `Comments` field holds either the full cache (`energy=… spotify=<id>`) or a
no-data marker (`no-audio-data spotify=<id>` when Spotify matched but ReccoBeats had
nothing yet, or `no-spotify-match`). `parse_comments` reads all three shapes;
`'energy' in result` distinguishes "has real audio data" from a no-data marker. This
is the load-bearing design idea:
- A normal run fetches **only brand-new (unseen) songs**, skipping both tagged and
  no-data songs before any API call — so re-runs never re-hit rate limits.
- `--retune` re-classifies from cached numbers alone (no network) — applies new
  thresholds instantly across the library.
- `--force` = **from scratch**: re-search Spotify (ignore cached id) + refetch +
  overwrite everything selected. Use it to re-validate a possibly-wrong id.
- `--retry-nodata` re-attempts **only** the stuck `no-data` songs: first the
  ReccoBeats **lookup** (reusing the cached id), then a **clip-analysis fallback** —
  fetch a free 30s **Deezer** MP3 preview and POST it to ReccoBeats'
  `/v1/analysis/audio-features` (`extract_features` → `reccobeats_extract`). Preview
  matching is exact-first: **Tier 1** by ISRC (Spotify id → `/tracks` → ISRC → Deezer
  `/track/isrc:`), **Tier 2** a duration-gated fuzzy Deezer search that refuses
  rather than guess. Extracted features are **approximate** — tagged `approx` in
  Grouping + `src=analysis` in Comments. If both lookup and extraction fail, the
  song is marked `extract-failed` and skipped on later `--retry-nodata` runs;
  `--force` revisits it. This is the fix for regional catalogs ReccoBeats' lookup
  doesn't cover.
- The **Spotify search is the expensive, rate-limited step; ReccoBeats is cheap** —
  so a found id is always banked (even on no-data) and reused, never re-searched
  unless `--force`.
- `apple_music_similar.py` reads the cached vectors and ranks by weighted Euclidean
  distance — fully offline, which is why it works on regional catalogs.

**Match confidence:** `spotify_find_track` scores by artist overlap, title-word
overlap, and duration, and returns `None` below `MATCH_MIN_SCORE` rather than banking
a low-confidence guess (which would pin a song to a wrong track's features forever).

**Fields written** (see `TAGGING.md` for the full reference):
`Grouping` = trait tags + a category word (for Smart Playlist `contains` rules);
`Comments` = raw numbers + Spotify id (the cache); `BPM` = tempo; `Rating` =
energy×100; `Movement Number` = danceability×100. Rating and Movement Number are
**deliberately hijacked** spare numeric fields so they're range-tunable in Smart
Playlists — don't "fix" them to their nominal meanings.

**Files:**
- `apple_music_mood.py` — the main tool and the shared core. `apple_music_similar.py`
  imports it (`import apple_music_mood as core`) to reuse `run_osascript`,
  `parse_comments`, and `get_selected_tracks`.
- `apple_music_similar.py` — offline nearest-neighbour (Roadmap Stage 2). Tune via
  the `WEIGHTS` dict.
- `apple_music_bpm.py` — standalone legacy BPM-only tool (GetSongBPM, no Spotify).
  Fully independent; does not import the core.

**Classification** lives in `category_label` (Groove/Anthem/Intense/Warm/Soulful),
`language_bucket` (Tamil/English/Others), and `build_tags` (independent trait
tags). All decisions are driven by named threshold constants at the top of
`apple_music_mood.py` — new tuning knobs belong there, not inline.

## Conventions (from CONTRIBUTING.md)

- **No new dependencies** — standard library + `osascript` only.
- **Never fabricate data.** If a lookup fails, tag the song `<lang> untagged
  no-data`; never invent a category from a bad match.
- **Tunable, not hard-coded.** New behaviour should be a named constant near the
  top of the file so users can adjust without reading the logic.

## Non-obvious gotchas

- **ReccoBeats sits behind Cloudflare**, which bans urllib's default User-Agent
  (error 1010). A browser-like `USER_AGENT` is required on every request.
- **AppleScript field separator** is `␟` (unit separator), chosen because it can't
  appear in song metadata — don't switch to comma/tab.
- **`RateLimited` (HTTP 429)** breaks the loop cleanly rather than mislabeling
  songs; `REQUEST_PAUSE = 0.5s` spreads calls under Spotify's rolling window.
- **Tracks whose metadata can't be written** are detected by `_not_editable` and
  reported as `NOLIB` (not raw `FAIL`): -1731 "Unknown object type" (not in
  Library) and -10006 "not modifiable" (Apple Music cloud/streaming track,
  read-only). Both are fixed by Add to Library / download, then re-run.
- **Language detection defaults Indian releases to Tamil** (this library is
  Tamil-dominant); a Tamil song on a foreign label can be mislabeled `english`.
