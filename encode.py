# python encode.py video.mp4 output.clmp [--fps 12] [--width 160] [--height 45]
import cv2
import numpy as np
import struct
import zlib
import argparse
import sys
import os
import time
import subprocess
ASCII_RAMP = ' .\'`^",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$'
RAMP_LEN   = len(ASCII_RAMP)
MAGIC   = b'CLMP'
VERSION = 4
def frame_to_ascii_color(frame_bgr: np.ndarray, cols: int, rows: int):
    small = cv2.resize(frame_bgr, (cols, rows), interpolation=cv2.INTER_AREA)
    grey  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    lines = []
    for row in grey:
        line = ''.join(ASCII_RAMP[int(p / 255 * (RAMP_LEN - 1))] for p in row)
        lines.append(line)
    ascii_bytes = '\n'.join(lines).encode('ascii')
    color_bytes = rgb.tobytes()
    return ascii_bytes, color_bytes
def extract_audio(src: str, duration: float) -> bytes:
    kwargs = {'capture_output': True, 'timeout': 300}
    if sys.platform == 'win32':
        kwargs['creationflags'] = 0x08000000
    try:
        cmd = [
            'ffmpeg', '-y', '-i', src, '-vn',
            '-t', str(duration),
            '-c:a', 'libvorbis', '-q:a', '4',
            '-f', 'ogg', 'pipe:1'
        ]
        result = subprocess.run(cmd, **kwargs)
        if result.returncode == 0 and len(result.stdout) > 0:
            return result.stdout
        cmd = [
            'ffmpeg', '-y', '-i', src, '-vn',
            '-t', str(duration),
            '-c:a', 'pcm_s16le', '-ar', '44100', '-ac', '2',
            '-f', 'wav', 'pipe:1'
        ]
        result = subprocess.run(cmd, **kwargs)
        if result.returncode == 0 and len(result.stdout) > 44:
            return result.stdout
    except FileNotFoundError:
        print("\n  [WARN] ffmpeg not found — skipping audio extraction")
    except subprocess.TimeoutExpired:
        print("\n  [WARN] Audio extraction timed out")
    return b''
def encode(src: str, dst: str, target_fps: float, cols: int, rows: int):
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"[ERROR] Cannot open '{src}'")
    src_fps       = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ret, test_frame = cap.read()
    if ret:
        src_h, src_w = test_frame.shape[:2]
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    else:
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec  = total_frames / src_fps if src_fps > 0 else 0
    
    char_aspect = 0.5
    video_aspect = src_w / src_h if src_h > 0 else 1.0
    max_cols = cols
    max_rows = rows
    cols = max_cols
    rows = int(cols / (video_aspect / char_aspect))
    if rows > max_rows:
        rows = max_rows
        cols = int(rows * (video_aspect / char_aspect))
    cols = max(1, cols)
    rows = max(1, rows)

    frame_step = max(1, round(src_fps / target_fps))
    actual_fps = src_fps / frame_step
    print(f"  Source  : {src_w}x{src_h}  {src_fps:.2f} fps  {total_frames} frames  ({duration_sec:.1f}s)")
    print(f"  Output  : {cols}x{rows} ASCII  {actual_fps:.2f} fps  (color + audio)")
    print(f"  Encoding frames...", flush=True)
    frames_data = []
    frame_idx   = 0
    encoded     = 0
    t0          = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_step == 0:
            ascii_bytes, color_bytes = frame_to_ascii_color(frame, cols, rows)
            compressed_ascii = zlib.compress(ascii_bytes, level=6)
            compressed_color = zlib.compress(color_bytes, level=6)
            frames_data.append((compressed_ascii, compressed_color))
            encoded += 1
            pct = int(frame_idx / max(total_frames, 1) * 40)
            bar = '[' + '#' * pct + '-' * (40 - pct) + ']'
            elapsed = time.time() - t0
            sys.stdout.write(f"\r  {bar} {encoded} frames  {elapsed:.1f}s")
            sys.stdout.flush()
        frame_idx += 1
    cap.release()
    print(f"\n  Done encoding {encoded} frames in {time.time()-t0:.1f}s")
    print(f"  Extracting audio...", end=' ', flush=True)
    audio_raw = extract_audio(src, duration_sec)
    if audio_raw:
        print(f"done  ({len(audio_raw)/1048576:.2f} MB)")
    else:
        print("no audio found")
    header = struct.pack(
        '<4sBHHfI64s',
        MAGIC,
        VERSION,
        cols,
        rows,
        actual_fps,
        len(frames_data),
        os.path.basename(src).encode('utf-8')[:64].ljust(64, b'\x00'),
    )
    print(f"  Writing '{dst}'...", end=' ', flush=True)
    with open(dst, 'wb') as f:
        f.write(header)
        for compressed_ascii, compressed_color in frames_data:
            f.write(struct.pack('<I', len(compressed_ascii)))
            f.write(compressed_ascii)
            f.write(struct.pack('<I', len(compressed_color)))
            f.write(compressed_color)
        f.write(struct.pack('<I', len(audio_raw)))
        if audio_raw:
            f.write(audio_raw)
    size_mb = os.path.getsize(dst) / 1_048_576
    print(f"done  ({size_mb:.2f} MB)")
def main():
    import ffmpeg_check
    ffmpeg_check.ensure_ffmpeg()
    ap = argparse.ArgumentParser(
        description='Encode an MP4 into a .clmp ASCII-cinema file.'
    )
    ap.add_argument('input',          help='Source .mp4 file')
    ap.add_argument('output',         help='Destination .clmp file')
    ap.add_argument('--fps',    type=float, default=12,
                    help='Target playback fps (default 12)')
    ap.add_argument('--width',  type=int,   default=160,
                    help='ASCII columns (default 160)')
    ap.add_argument('--height', type=int,   default=45,
                    help='ASCII rows (default 45)')
    args = ap.parse_args()
    if not args.output.endswith('.clmp'):
        args.output += '.clmp'
    print(f"\n  clmp-encode v{VERSION}")
    print(f"  {'='*50}")
    encode(args.input, args.output, args.fps, args.width, args.height)
    print(f"\n  Play with:  python3 play.py {args.output}\n")
if __name__ == '__main__':
    main()
