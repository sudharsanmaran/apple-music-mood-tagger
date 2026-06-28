# Contributing

Thanks for your interest! This is a small, dependency-free Python tool for
organizing an Apple Music library. Contributions of all sizes are welcome.

## Project layout

| File | What it is |
|------|------------|
| `apple_music_mood.py` | the main tool — tagging, classification, caching |
| `apple_music_bpm.py` | minimal BPM-only alternative (GetSongBPM) |
| `TAGGING.md` | reference: every field, tag word, threshold, playlist recipe |
| `ROADMAP.md` | the three-stage vision |

## Dev setup

- macOS with the Music app, and Python 3 (standard library only — **no
  dependencies**, no virtualenv needed).
- A free [Spotify Developer app](https://developer.spotify.com/dashboard) for
  the track lookup; export `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`.
- The script talks to Music via `osascript` (AppleScript). The first run
  triggers a macOS permission prompt to let your terminal control Music.

## How it's organized internally

- **Lookup:** `spotify_find_track` (name → id) → `reccobeats_features` (id → numbers).
- **Classify:** `category_label` (mood) and `language_bucket` (language), driven
  by the threshold constants near the top of the file.
- **Write:** `build_tags` (Grouping), `full_comments` (Comments cache),
  `set_bpm` / `set_rating` / `set_movement`.
- **Cache:** features + Spotify id are stored in Comments; `parse_comments`
  reads them back so `--retune` works fully offline.

## Guidelines

- **No new dependencies.** Keep it standard-library + `osascript` only.
- **Never guess data.** If a lookup fails, tag the song `untagged no-data` —
  don't fabricate a category from a wrong match.
- **Tunable, not hard-coded.** New behaviour should be driven by a named
  constant near the top, so users can adjust without reading the logic.
- **Test offline where possible.** Classification/tag functions can be tested
  with mock feature dicts (no network); see how thresholds map to categories.
- Keep changes small and focused; explain *why* in the PR.

## Good first contributions

- **Language detection** — Tamil songs on foreign labels (ISRC ≠ IN) get
  mislabeled `english`. A better heuristic would help a lot.
- **Deezer bridge** — Deezer exposes ISRC for free without a key; a working
  Deezer → ISRC → ReccoBeats path would remove the Spotify dependency entirely.
- **`--batch N`** — stop a fetch run after N songs to stay under rate limits.
- **Find similar songs** (Roadmap Stage 2) — nearest-neighbour over the feature
  vectors already stored in Comments.

## Reporting issues

Include: macOS + Music version, a sample of the script's output, and (for
mistagged songs) the `(e=… v=… d=…)` numbers it printed.
