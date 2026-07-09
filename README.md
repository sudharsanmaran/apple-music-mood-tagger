# 🎵 Apple Music Mood Tagger

Automatically organize an Apple Music library by **mood, energy, and language**,
so similar songs live together — and build Smart Playlists that update
themselves. Works on **streamed / DRM Apple Music tracks** (no audio files
required), including regional catalogs (Tamil, etc.) that most BPM/mood
databases don't cover.

> **The motto — organize, then understand, your music:**
> 1. **Now:** auto-group your library by how songs *feel* (mood / energy / groove).
> 2. **Next:** "find songs similar to this one" using each track's audio fingerprint.
> 3. **Later:** skip the boring parts of a song automatically.

## What it does today

For every selected song it:

1. finds the track on **Spotify** (to get an ID),
2. pulls audio features from **[ReccoBeats](https://reccobeats.com)** (free) —
   energy, valence, danceability, tempo, acousticness, and more,
3. classifies it into a mood category (**Groove / Anthem / Intense / Warm /
   Soulful**) and a language (**Tamil / English / Others**),
4. writes everything back into the song's metadata so you can build
   **Smart Playlists** that group similar songs and stay up to date.

Because the data lives on each song (and syncs across your devices via iCloud
Music Library), you tag once and re-tune offline forever.

## Quick start

**Requirements:** macOS with the Music app, Python 3 (standard library only —
no `pip install`), and a free Spotify Developer app.

```sh
# 1. Create a free app at https://developer.spotify.com/dashboard (Web API).
#    Redirect URI can be http://127.0.0.1:8888 . Copy the Client ID + Secret.
export SPOTIFY_CLIENT_ID="your-client-id"
export SPOTIFY_CLIENT_SECRET="your-client-secret"

# 2. In the Music app, select the tracks you want to tag.

# 3. Preview, then run:
python3 apple_music_mood.py --dry-run    # shows what it would do, writes nothing
python3 apple_music_mood.py              # tag new songs
python3 apple_music_mood.py --retune     # re-bucket offline from cached data (no network)
```

The first time, macOS asks to let Terminal control Music — click **OK**.

Then build a Smart Playlist: **File → New → Smart Playlist**, rule
`Grouping contains Groove`. See **[PLAYLISTS.md](PLAYLISTS.md)** for a curated
ready-to-build set with exact rules, **[SMART_PLAYLISTS.md](SMART_PLAYLISTS.md)**
for the cookbook of how to combine any properties, and **[TAGGING.md](TAGGING.md)**
for the field/tag reference.

## How it works

```
Apple Music song (name + artist)
   → Spotify search        → track ID         [needs a free Spotify app; cached after first run]
   → ReccoBeats            → audio features    [free, no key]
   → classify + tag        → write to Music metadata
```

It writes across several fields so you can filter however you like:

| Field | Holds |
|-------|-------|
| Grouping | trait tags + category (`tamil groovy bright … Groove`) |
| Comments | every raw audio number + the Spotify ID (the cache) |
| BPM | tempo |
| Rating | energy ×100 (range-tunable) |
| Movement Number | danceability ×100 (range-tunable) |

Full reference: **[TAGGING.md](TAGGING.md)**.

## Scripts

- **`apple_music_mood.py`** — the main tool (mood/energy/language + BPM via ReccoBeats).
- **`apple_music_similar.py`** — "songs like this one." Select a seed, get a
  playlist of the closest matches by audio-feature distance. **100% offline** —
  uses the numbers already cached in Comments, so it works on your Tamil catalog.
- **`apple_music_bpm.py`** — a minimal, BPM-only alternative using
  [GetSongBPM](https://getsongbpm.com) (no Spotify needed, but weak coverage of
  regional music). Kept as a simpler option.

## Roadmap

See **[ROADMAP.md](ROADMAP.md)** — the path from "organize by mood" to
"find similar songs" to "skip the bad parts."

## Contributing

Contributions welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. Good first
areas: better language detection, mood-threshold tuning, a Deezer bridge to
drop the Spotify dependency, and the "find similar songs" feature.

## Credits

- Audio features by **[ReccoBeats](https://reccobeats.com)**.
- Track lookup via the **Spotify Web API**.
- BPM (legacy script) by **[GetSongBPM](https://getsongbpm.com)**.

## License

[MIT](LICENSE) © 2026 Sudharsan Maran.
