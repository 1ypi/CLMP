# CLMP — CLI Movie Package

Turn any MP4 video into a high-performance colored ASCII animation that plays entirely in your terminal — with audio.

## Demo

```bash
python play.py movie.clmp
```

## Features

- **Blazing Fast Delta-Rendering** — Uses a virtual back-buffer to only update changed characters, enabling 120+ FPS playback in native terminals.
- **Colored ASCII art** — each character is tinted with the original pixel color using 24-bit ANSI truecolor.
- **Frame-Dropping Audio Sync** — Professional audio-led synchronization that automatically drops video frames to stay perfectly locked to the audio clock.
- **Embedded audio** — audio is extracted as OGG Vorbis and played back in sync via `sounddevice`.
- **Full playback controls** — pause, speed up/down, seek, volume, quit.
- **Persistent Settings** — Customize your experience (jump size, volume steps) via the new `set.py` tool.
- **Auto-scaling** — fits to any terminal size using nearest-neighbor resampling.
- **Compact format** — frames are zlib-compressed, audio stored as OGG Vorbis.
- **Cross-platform** — works on Windows, macOS, and Linux.

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

### Configure

Use the `set.py` tool to customize your playback experience. These settings are saved in `settings.json`.

```bash
# Set jump distance to 5 seconds
python set.py --jump 5

# Set volume increments to 5%
python set.py --vol-step 5

# Set default starting volume
python set.py --volume 50
```

### Controls

| Key | Action |
|-----|--------|
| `Space` | Pause / resume |
| `+` / `-` | Speed up / slow down (±0.25x) |
| `↑` / `↓` | Volume up / down (Customizable step) |
| `←` / `→` | Seek backward / forward (Customizable seconds) |
| `q` | Quit |

## .clmp Format (v4)

Binary file layout (little-endian):

```
┌─────────────────────────────────────────┐
│ Header (79 bytes)                       │
│   4s   magic          "CLMP"            │
│   B    version        4                 │
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
