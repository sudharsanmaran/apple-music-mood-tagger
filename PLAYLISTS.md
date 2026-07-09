# Playlists — a curated Smart Playlist system

A **specific, ready-to-build set** of Smart Playlists designed for *this* library
(≈1484 songs, Tamil-heavy, tagged by `apple_music_mood.py`). Where
[SMART_PLAYLISTS.md](SMART_PLAYLISTS.md) is the *cookbook* (how to combine any
properties) and [TAGGING.md](TAGGING.md) is the *field reference*, this file is the
**prescriptive layer**: build exactly these and stop — it's designed to avoid the
usual mess of 50 overlapping lists.

> **Two ways to build these.** For *live, tunable* Smart Playlists, build by hand:
> **File → New → Smart Playlist** (rules below). For an instant *static* version,
> run **`python3 apple_music_playlists.py`** — it creates all of these as regular
> playlists populated now (re-run to refresh; not live). Sizes below are live counts
> at time of writing and will drift as you add songs.

## Design principles (how we avoid over-classification)

1. **Three layers, ~16 playlists, in folders** — not a combo for every tag.
   - **Moods** — the 5 base categories (browse by feel).
   - **For…** — activity mixes (the daily drivers).
   - **Languages** — Tamil/English lenses.
2. **The 80% rule** — if two playlists would share ~80% of their songs, keep one.
3. **Splitting only where needed** — `Groove` alone is **734 songs** (half the
   library), so it's a shuffle-everything bucket; the *useful* lists come from the
   activity/language layers that sub-divide it.
4. **Every playlist:** Match **all** (unless noted), **Live updating ✓**, **Limit
   unchecked** (unless noted). Make three **folders** and drag playlists in.

## The `approx` rule (read once)

**320 songs (22%)** were recovered by clip analysis (tagged `approx`), and their
**energy/tempo run ~+0.1 hot** (a 30s preview samples the loudest hook — see
[TAGGING.md](TAGGING.md)). So:

- 🔒 **Energy-critical playlists exclude them** — add `Grouping does not contain approx`.
- **Mood/vibe/party playlists keep them** — the direction is fine.

🔒 below = "add `Grouping does not contain approx`".

---

## Layer 1 — Moods (folder: **Moods**)

The 5 base categories, one rule each (`Grouping contains <word>`). Your "browse by
feel" buckets.

| Playlist | Rule | ~Size |
|---|---|---|
| Groove | `Grouping contains Groove` | 734 |
| Anthem | `Grouping contains Anthem` | 103 |
| Intense | `Grouping contains Intense` | 71 |
| Warm | `Grouping contains Warm` | 248 |
| Soulful | `Grouping contains Soulful` | 288 |

> `Groove` is huge on purpose — don't shuffle it directly; use Layer 2/3 instead.

## Layer 2 — For… (folder: **For…**) — the daily drivers

Match **all**. These are the mixes you'll actually open.

| Playlist | Rules | ~Size |
|---|---|---|
| 💻 **Focus / work** | `energy-mid` · does not contain `rappy` · does not contain `dark` · does not contain `fast` | 153 |
| 🚗 **Drive / hype** 🔒 | `groovy` · `bright` · `energy-high` · does not contain `approx` | 296 |
| 🎉 **Party** | `groovy` · `energy-high` · `bright` | 421 |
| 🛏 **Wind-down** | `energy-low` · `bright` · `acoustic` | 81 |
| 😴 **Sleep** | `energy-low` · `acoustic` · `slow` | 30 |
| 💔 **Heartbreak** | `dark` · `energy-low` | 214 |
| 🎤 **Rap / hip-hop** | `rappy` | 45 |

## Layer 3 — Languages (folder: **Languages**)

Your two catalogs, crossed with feel. Match **all**.

| Playlist | Rules | ~Size |
|---|---|---|
| Tamil melodies | `tamil` · `Warm` | 178 |
| Tamil dance floor | `tamil` · `groovy` · `energy-high` | 361 |
| English chill | `english` · `energy-low` · `bright` | 48 |
| English hype | `english` · `groovy` · `energy-high` | 104 |

## Precision add-ons (numeric sliders, live-tunable)

The tags are coarse; the hijacked numeric fields are fine sliders (no re-run to
adjust — just edit the rule). See [TAGGING.md](TAGGING.md) for the stars↔energy map.

| Playlist | Rules | ~Size |
|---|---|---|
| 🔥 **Peak energy** 🔒 | `Rating is greater than ★★★★` (energy > 0.80) · does not contain `approx` | 253 |
| 💃 **Max groove** | `Movement Number is greater than 80` (dance > 0.80) | — |
| 🏃 **Running cadence** 🔒 | `BPM in the range 160 to 180` · `energy-high` · does not contain `approx` | — |

## Keep the big lists fresh (a modifier, not more playlists)

Rather than making more playlists, add one rule to any big one:

- **Rotation:** `Last Played is not in the last 2 weeks` → only surfaces songs you
  haven't heard recently, so `Party`/`Tamil dance floor` refresh themselves.
- **Digestible daily mix:** check **Limit to 2 hours**, *selected by* **least
  recently played** → a fresh ~30-song set each session from any big bucket.

## Maintenance (folder: **Inbox**)

| Playlist | Rule | ~Size |
|---|---|---|
| ✋ To fix by hand | `Grouping contains untagged` | 28 |
| 🔍 Approx — review | `Grouping contains approx` | 320 |

---

## Nested rules (for the few OR cases)

To widen a list with an OR, click the **`…`** on a rule to add an indented group
with its own **any/all**. Example — "Tamil, danceable *or* fast":

```
Match all:
   Grouping contains  tamil
   (any:)                          ← the nested group
      Grouping contains  groovy
      Grouping contains  fast
```

Most of the system above is pure `all` (AND); reach for nesting only when a single
bucket genuinely needs two alternatives.
