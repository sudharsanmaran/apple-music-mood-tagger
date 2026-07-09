# Tagging reference — how songs are grouped

This explains exactly what `apple_music_mood.py` writes to each song, every tag
word it uses, and how to build Smart Playlists from it.

## The pipeline

```
song in Apple Music
  → find it on Spotify (get track id)        [needs your Spotify key]
  → look up audio features on ReccoBeats      [free, no key]
  → derive tags + suggested category
  → write them into 5 fields (below)
```

A song with no Spotify match or no ReccoBeats data is left honest: Grouping =
`<lang> untagged no-data` (no guessing). Find these and tag them by hand.

## What goes into each field

| Field | What we store | Example | How to filter in a Smart Playlist |
|---|---|---|---|
| **Grouping** | trait tags + category word (text) | `tamil energy-mid groovy bright produced mid-tempo Groove` | `contains` a word |
| **Comments** | raw audio numbers + `spotify=<id>` cache; or a no-data marker (`no-audio-data` / `no-spotify-match` / `extract-failed`); `src=analysis` marks clip-analysed features | `energy=0.63 … spotify=abc src=analysis` | `contains` (exact text only) |
| **BPM** | tempo, rounded | `120` | `is greater than` / `in the range` |
| **Rating** | energy × 100 (= stars × 20) | `63` ≈ 3 stars | `Rating is greater than ★★★` |
| **Movement Number** | danceability × 100 | `70` | `Movement Number is greater than 65` |

> ⚠️ **Rating and Movement Number are hijacked.** Rating no longer means your
> star favourites; Movement Number is a classical-music field we repurposed
> (it was empty). Both were chosen because you don't use them.

## Tag vocabulary (the words in Grouping)

Each song carries **every** tag it qualifies for, so it can appear in several
playlists at once. Words and the thresholds that produce them:

### Language (one of)
| Tag | Meaning |
|---|---|
| `tamil` | Apple genre says Tamil, **or** ISRC country = IN |
| `english` | released outside India (ISRC ≠ IN) |
| `others` | other Indian languages, or unknown |

### Energy band (one of) — *master "intensity" dial*
| Tag | energy value |
|---|---|
| `energy-low` | < 0.55 |
| `energy-mid` | 0.55 – 0.70 |
| `energy-high` | ≥ 0.70 |

### Danceability band (one of) — *"groove"*
| Tag | danceability |
|---|---|
| `groovy` | ≥ 0.65 |
| `dance-mid` | 0.50 – 0.65 |
| `dance-low` | < 0.50 |

### Mood (one of)
| Tag | valence |
|---|---|
| `bright` | ≥ 0.50 (happy / positive) |
| `dark` | < 0.50 (sad / serious) |

### Texture flags (added when true)
| Tag | when |
|---|---|
| `acoustic` | acousticness ≥ 0.50 (else `produced`) |
| `instrumental` | instrumentalness ≥ 0.50 |
| `rappy` | speechiness ≥ 0.33 (lots of spoken words / rap) |
| `live` | liveness ≥ 0.60 |

### Tempo band (one of)
| Tag | bpm |
|---|---|
| `slow` | < 90 |
| `mid-tempo` | 90 – 130 |
| `fast` | ≥ 130 |

### Suggested category (one of) — *a ready-made single bucket*
Derived by priority: **danceable+energy → Groove**, else **high-energy → Anthem
(bright) / Intense (dark)**, else **calm → Warm (bright) / Soulful (dark)**.

| Word | Meaning |
|---|---|
| `Groove` | upbeat + danceable |
| `Anthem` | upbeat + powerful, not danceable |
| `Intense` | high energy + dark / serious |
| `Warm` | calm + pleasant |
| `Soulful` | calm + sad |

### Provenance flag (added when true)
| Tag | Meaning |
|---|---|
| `approx` | Features came from **clip analysis** of a 30s preview (via `--retry-nodata`'s fallback), **not** Spotify's model. Comments also carry `src=analysis`. Used for regional tracks Spotify/ReccoBeats' lookup doesn't cover. |

> ⚠️ **`approx` energy runs hot.** A 30s preview samples the loudest, catchiest
> section (the hook), so extracted **energy (and tempo) skew high** vs. the full
> track — measured ~+0.1 higher energy, landing in `energy-high` about twice as
> often. Danceability/valence are steadier. Trust the *direction*, not the exact
> number, and **exclude `approx` from energy-critical playlists** with
> `Grouping does not contain approx` (or review them via `Grouping contains approx`).

## Smart Playlist recipes

**Ready-made categories** (one rule each, Grouping `contains` the word):

| Playlist | Rule |
|---|---|
| Groove | Grouping contains `Groove` |
| Anthem | Grouping contains `Anthem` |
| Intense | Grouping contains `Intense` |
| Warm | Grouping contains `Warm` |
| Soulful | Grouping contains `Soulful` |
| Untagged (sort by hand) | Grouping contains `untagged` |

**Custom combos** (Match `all`, mix tags + numbers):

| Want | Rules |
|---|---|
| Tamil dance bangers over 130 BPM | Grouping contains `tamil` · Grouping contains `groovy` · BPM > 130 |
| Calm Tamil melodies | Grouping contains `tamil` · Grouping contains `energy-low` · Grouping contains `bright` |
| High-energy songs (live tunable) | Rating > ★★★★  (= energy > 0.80) |
| Very groovy (live tunable) | Movement Number > 75 (= dance > 0.75) |
| Tamil rap | Grouping contains `tamil` · Grouping contains `rappy` |

Always: **uncheck "Limit to N items"**, keep **"Live updating"** on.

## Tuning the boundaries

- **Live numeric** (energy via Rating, dance via Movement #, tempo via BPM):
  just edit the Smart Playlist rule — no re-run needed.
- **Bands / categories** (`energy-mid`, Groove vs Anthem, etc.): edit the
  threshold constants near the top of `apple_music_mood.py`, then run
  **`--retune`** — it re-buckets every selected song from the numbers already
  saved in Comments. **No network, no rate limit, instant.**

## Caching — why you only fetch each song once

Every song's Comments holds its raw numbers **and** `spotify=<id>`. So:

- **`--retune`** re-classifies from Comments alone (no API calls).
- **`--force`** (re-fetch) reuses the saved `spotify=<id>` to skip the
  rate-limited Spotify search and go straight to ReccoBeats.
- A normal run **skips** any song that already has a Grouping value.

The only time the rate-limited Spotify search runs is the **first** time a song
is seen. Everything after that is cached.

## Incremental workflow (as your library grows)

1. Keep a **regular playlist** of songs you want to organize; add to it over time.
2. Run `python3 apple_music_mood.py` on it whenever you've added songs. The
   script **skips any song that already has a Grouping — before making any API
   call** — so re-runs only do work on *new* songs. No duplicate lookups, ever.
3. For the first big pass (or to stay well under rate limits), chunk it:
   `python3 apple_music_mood.py --batch 100` — it stops after 100 newly-fetched
   songs; just re-run to continue where it left off.
4. *(Optional)* A Smart Playlist with `Grouping is empty` gives you a live
   "still to tag" queue.

## Notes

- **Sync:** with Sync Library on (it is), all of this syncs to your other
  devices within a few minutes.
- **Rate limits:** Spotify limits how many lookups you can do in a short
  window. Tag in batches (e.g. a few hundred at a time). If you get a
  "Rate limited" message, wait and re-run — already-tagged songs are skipped.
- **Language caveat:** a Tamil song released on a foreign label (ISRC ≠ IN)
  with a non-Tamil Apple genre can be mislabeled `english` (e.g. *Lesa Lesa*).
  Fix by hand or edit the genre.
- **BPM half/double:** auto-detected tempo is occasionally half or double the
  real value. Spot-check if you rely on exact BPM.
