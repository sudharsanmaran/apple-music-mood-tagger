# Roadmap

The project grows in three stages. Each builds on the audio fingerprint we
already collect for every song (energy, valence, danceability, tempo,
acousticness, speechiness, …) and store in the Comments field.

## ✅ Stage 1 — Organize (now)

Group the library by how songs *feel*.

- [x] Look up audio features for streamed/DRM tracks (Spotify → ReccoBeats)
- [x] Classify into mood categories (Groove / Anthem / Intense / Warm / Soulful)
- [x] Detect language (Tamil / English / Others)
- [x] Write tags + raw numbers + BPM into Music metadata; Smart-Playlist-ready
- [x] Cache everything on the song so re-tuning is offline + instant (`--retune`)
- [ ] Improve language detection (foreign-label Tamil songs misread as English)
- [ ] Optional Deezer bridge to drop the Spotify dependency
- [ ] `--batch N` for rate-limit-safe first passes

## 🔜 Stage 2 — Find similar songs

Every song already has a feature vector. Similarity = distance between vectors.

- [ ] "Songs like this one" — nearest neighbours in feature space
  (energy/valence/danceability/tempo/acousticness), optionally within the same
  language or composer
- [ ] Auto-generate a playlist seeded from a song or a small set
- [ ] Tunable distance weights (e.g. weight groove + energy higher than key)
- [ ] Cluster the library into N natural groupings instead of fixed categories

## 🧪 Stage 3 — Skip the bad parts

Play only the good sections of a song.

- [ ] Trim dead intros/outros using Music's **Start/Stop time** fields
  (set per-track so playback skips them) — derivable from energy/onset over time
- [ ] Research mid-song "skip a boring section" (Apple can only trim start/end
  natively, so this may need a companion player or AppleScript-driven seeking)
- [ ] Per-song "best 60 seconds" markers for quick previews

## How to help

Pick any unchecked item and open an issue/PR. Stage 2 ("find similar") is the
most-requested next step and the design is straightforward — see
[CONTRIBUTING.md](CONTRIBUTING.md).
