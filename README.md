# apple-music-bpm

A small Python script that fills the **BPM** field of selected Apple Music
tracks (macOS) by looking up each song's tempo in the free GetSongBPM database.

It works for streamed Apple Music tracks too, because it never touches the audio
file — it reads each track's title + artist from the Music app via AppleScript,
looks the tempo up online, and writes the number back.

## Usage

1. Get a free API key at <https://getsongbpm.com/api> and paste it into the
   `API_KEY` line near the top of `apple_music_bpm.py`.
2. Open the Music app, open a playlist, and select the tracks you want.
3. Run:

   ```sh
   python3 apple_music_bpm.py --dry-run   # preview, writes nothing
   python3 apple_music_bpm.py             # fill in BPM for the selection
   python3 apple_music_bpm.py --force     # overwrite BPM even if already set
   ```

No pip installs needed — it uses only Python 3's standard library plus
`osascript`.

## apple_music_mood.py

Tags selected tracks by **language + mood/energy** into the Grouping field
(e.g. `Tamil / Groove (upbeat + danceable)`), and fills BPM — using free audio
features from [ReccoBeats](https://reccobeats.com) (energy, valence,
danceability, tempo). Categories come from the energy×valence emotional map:
**Groove / Anthem / Intense / Warm / Soulful** (and `Untagged` when no data is
found). Works for Apple Music subscription streams, including regional/Tamil
tracks that BPM databases don't cover.

Setup: register a free [Spotify Developer app](https://developer.spotify.com/dashboard)
(used only to look up track IDs), then:

```sh
export SPOTIFY_CLIENT_ID="..."
export SPOTIFY_CLIENT_SECRET="..."
python3 apple_music_mood.py --dry-run
```

## Credits

BPM data provided by [GetSongBPM](https://getsongbpm.com).
Audio features provided by [ReccoBeats](https://reccobeats.com).
