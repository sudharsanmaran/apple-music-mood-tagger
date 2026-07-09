#!/usr/bin/env python3
"""
apple_music_playlists.py — build the curated PLAYLISTS.md set as regular
(STATIC) playlists in Apple Music.

WHY STATIC: Apple's AppleScript can't create Smart Playlists with live rules, and
it can't nest playlists into folders. So this creates regular playlists populated
with the matching tracks NOW, grouped by a name prefix ("For — Focus") so they
cluster in the sidebar. They're snapshots — re-run to refresh as your library
grows. For live, tunable, folder-able playlists, hand-build them from PLAYLISTS.md.

It reads the WHOLE library (library playlist 1), not the current selection, so you
don't need to select anything.

USAGE:
    python3 apple_music_playlists.py            # create / refresh all
    python3 apple_music_playlists.py --dry-run  # show names + counts, create nothing
    python3 apple_music_playlists.py --only For # only groups whose prefix matches
"""

import argparse
import sys

import apple_music_mood as core   # reuse run_osascript

SEP = " — "     # "For — Focus"; prefixes cluster related lists in the sidebar
G = 'grouping contains '
NOT = 'grouping does not contain '

# (group, name, AppleScript `whose` predicate) — mirrors PLAYLISTS.md exactly.
# 'approx' is excluded from the energy-critical lists (extracted energy runs hot).
PLAYLISTS = [
    ("Mood", "Groove",            G + '"Groove"'),
    ("Mood", "Anthem",            G + '"Anthem"'),
    ("Mood", "Intense",           G + '"Intense"'),
    ("Mood", "Warm",              G + '"Warm"'),
    ("Mood", "Soulful",           G + '"Soulful"'),

    ("For",  "Focus",             G + '"energy-mid" and ' + NOT + '"rappy" and '
                                  + NOT + '"dark" and ' + NOT + '"fast"'),
    ("For",  "Drive",             G + '"groovy" and ' + G + '"bright" and '
                                  + G + '"energy-high" and ' + NOT + '"approx"'),
    ("For",  "Party",             G + '"groovy" and ' + G + '"energy-high" and ' + G + '"bright"'),
    ("For",  "Wind-down",         G + '"energy-low" and ' + G + '"bright" and ' + G + '"acoustic"'),
    ("For",  "Sleep",             G + '"energy-low" and ' + G + '"acoustic" and ' + G + '"slow"'),
    ("For",  "Heartbreak",        G + '"dark" and ' + G + '"energy-low"'),
    ("For",  "Rap",               G + '"rappy"'),

    ("Lang", "Tamil melodies",    G + '"tamil" and ' + G + '"Warm"'),
    ("Lang", "Tamil dance floor", G + '"tamil" and ' + G + '"groovy" and ' + G + '"energy-high"'),
    ("Lang", "English chill",     G + '"english" and ' + G + '"energy-low" and ' + G + '"bright"'),
    ("Lang", "English hype",      G + '"english" and ' + G + '"groovy" and ' + G + '"energy-high"'),

    ("Peak", "Peak energy",       'rating > 80 and ' + NOT + '"approx"'),
    ("Peak", "Max groove",        'movement number > 80'),
    ("Peak", "Running 160-180",   'bpm >= 160 and bpm <= 180 and ' + G + '"energy-high" and '
                                  + NOT + '"approx"'),

    ("Inbox", "To fix",           G + '"untagged"'),
    ("Inbox", "Approx review",    G + '"approx"'),
]


def _esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def count(pred):
    return int(core.run_osascript(
        'tell application "Music" to return (count of '
        '(every track of library playlist 1 whose ' + pred + '))'))


def build(name, pred):
    """Create the playlist if absent, clear it, then fill with matching tracks.
    One AppleScript call (bulk duplicate), so it's fast even for big lists."""
    esc = _esc(name)
    core.run_osascript(
        'tell application "Music"\n'
        f'    if not (exists (user playlist "{esc}")) then '
        f'make new user playlist with properties {{name:"{esc}"}}\n'
        f'    try\n        delete every track of user playlist "{esc}"\n    end try\n'
        f'    duplicate (every track of library playlist 1 whose {pred}) '
        f'to user playlist "{esc}"\n'
        'end tell')


def main():
    p = argparse.ArgumentParser(description="Build the PLAYLISTS.md set as static playlists.")
    p.add_argument("--dry-run", action="store_true", help="Show names + counts; create nothing")
    p.add_argument("--only", metavar="PREFIX", help="Only build groups whose prefix matches (e.g. For)")
    args = p.parse_args()

    defs = [d for d in PLAYLISTS if not args.only or args.only.lower() in d[0].lower()]
    if not defs:
        sys.exit(f"No groups match --only {args.only!r}. Prefixes: Mood, For, Lang, Peak, Inbox.")

    print(f"{'Previewing' if args.dry_run else 'Building'} {len(defs)} static playlist(s) "
          f"from the whole library.\n")
    done = 0
    for group, base, pred in defs:
        name = f"{group}{SEP}{base}"
        try:
            n = count(pred)
        except RuntimeError as e:
            print(f"  ERR    {name}  (predicate failed: {e})")
            continue
        if args.dry_run:
            print(f"  {n:5}  {name}")
            continue
        try:
            build(name, pred)
            print(f"  {n:5}  built   {name}")
            done += 1
        except RuntimeError as e:
            print(f"  FAIL   {name}  ({e})")

    if args.dry_run:
        print("\n(dry run — nothing created)")
        return
    print(f"\nDone. Built/refreshed {done} playlist(s).")
    print("These are STATIC snapshots — re-run this to refresh as your library grows.\n"
          "Drag them into folders in Music by hand if you want folder grouping.")


if __name__ == "__main__":
    main()
