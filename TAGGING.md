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
| **Comments** | every raw audio number (text, reference) | `energy=0.63 valence=0.52 danceability=0.70 …` | `contains` (exact text only) |
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

- **Bands** (`energy-mid` etc.): edit the threshold constants near the top of
  `apple_music_mood.py`, then re-run with `--force`.
- **Live numeric** (energy via Rating, dance via Movement #, tempo via BPM):
  just edit the Smart Playlist rule — no re-run needed.

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
