# CLMP — CLI Movie Package

Turn any MP4 video into a colored ASCII animation that plays entirely in your terminal — with audio.

## Demo

```
python play.py movie.clmp
```

## Features

- **Colored ASCII art** — each character is tinted with the original pixel color using 24-bit ANSI truecolor
- **Embedded audio** — audio is extracted as OGG Vorbis and played back in sync via `sounddevice`
- **Full playback controls** — pause, speed up/down, seek, volume, quit
- **Auto-scaling** — fits to any terminal size using nearest-neighbor resampling
- **Compact format** — frames are zlib-compressed, audio stored as OGG Vorbis
- **Cross-platform** — works on Windows, macOS, and Linux

## Requirements

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) — must be on your PATH (used for audio extraction and decoding)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Encode

Convert an MP4 to a `.clmp` file:

```bash
python encode.py input.mp4 output.clmp
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--fps` | `12` | Target playback framerate |
| `--width` | `160` | ASCII columns |
| `--height` | `45` | ASCII rows |

### Play

```bash
python play.py output.clmp
```

Options:

| Flag | Description |
|------|-------------|
| `--speed 1.0` | Initial playback speed multiplier |
| `--loop` | Loop the video |
| `--no-scale` | Disable auto terminal scaling |
| `--no-color` | Disable colored output |
| `--no-audio` | Disable audio playback |

### Controls

| Key | Action |
|-----|--------|
| `Space` | Pause / resume |
| `+` / `-` | Speed up / slow down (±0.25x) |
| `↑` / `↓` | Volume up / down (±10%) |
| `←` / `→` | Seek backward / forward 10 seconds |
| `q` | Quit |

## .clmp Format (v3)

Binary file layout (little-endian):

```
┌─────────────────────────────────────────┐
│ Header (79 bytes)                       │
│   4s   magic          "CLMP"            │
│   B    version        3                 │
│   H    cols           ASCII width       │
│   H    rows           ASCII height      │
│   f    fps            playback fps      │
│   I    frame_count    number of frames  │
│   64s  source_name    original filename │
├─────────────────────────────────────────┤
│ Frames (repeated × frame_count)         │
│   I    ascii_size     compressed size   │
│   ...  ascii_data     zlib(ASCII text)  │
│   I    color_size     compressed size   │
│   ...  color_data     zlib(RGB bytes)   │
├─────────────────────────────────────────┤
│ Audio                                   │
│   I    audio_size     0 = no audio      │
│   ...  audio_data     raw OGG bytes     │
└─────────────────────────────────────────┘
```
