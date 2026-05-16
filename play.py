# python play.py movie.clmp [--loop] [--speed 1.0] [--no-scale] [--no-color] [--no-audio]
import struct
import zlib
import sys
import os
import time
import argparse
import threading
import json

SETTINGS_FILE = 'settings.json'
DEFAULT_SETTINGS = {
    'jump_seconds': 10.0,
    'volume_step': 0.1,
    'last_volume': 0.8
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            settings = DEFAULT_SETTINGS.copy()
            settings.update(data)
            return settings
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    import msvcrt
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
else:
    import tty
    import termios
    import select
try:
    import numpy as np
    import sounddevice as sd
    HAS_AUDIO_SUPPORT = True
except ImportError:
    HAS_AUDIO_SUPPORT = False
MAGIC   = b'CLMP'
HIDE_CURSOR = '\033[?25l'
SHOW_CURSOR = '\033[?25h'
CLEAR_SCREEN = '\033[2J'
HOME        = '\033[H'
RESET_COLOR = '\033[0m'
def term_size():
    try:
        ts = os.get_terminal_size()
        return ts.columns, ts.lines
    except OSError:
        return 80, 24
class KeyReader:
    def __init__(self):
        self._key  = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._t    = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        if not IS_WINDOWS:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
    def _run(self):
        while not self._stop.is_set():
            if IS_WINDOWS:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ('\xe0', '\x00'):
                        ch2 = msvcrt.getwch()
                        arrow = {'H': 'UP', 'P': 'DOWN', 'K': 'LEFT', 'M': 'RIGHT'}.get(ch2)
                        if arrow:
                            with self._lock:
                                self._key = arrow
                    else:
                        with self._lock:
                            self._key = ch
                else:
                    time.sleep(0.02)
            else:
                r, _, _ = select.select([sys.stdin], [], [], 0.02)
                if r:
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':
                        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                        if r2:
                            ch2 = sys.stdin.read(1)
                            if ch2 == '[':
                                ch3 = sys.stdin.read(1)
                                arrow = {'A': 'UP', 'B': 'DOWN', 'D': 'LEFT', 'C': 'RIGHT'}.get(ch3)
                                if arrow:
                                    with self._lock:
                                        self._key = arrow
                    else:
                        with self._lock:
                            self._key = ch
    def get(self):
        with self._lock:
            k, self._key = self._key, None
            return k
    def close(self):
        self._stop.set()
        if not IS_WINDOWS:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
class AudioPlayer:
    def __init__(self, audio_data: bytes, volume: float = 0.8):
        import subprocess as sp
        cmd = ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '44100', '-ac', '2', 'pipe:1']
        kw = {'stdout': sp.PIPE, 'stderr': sp.DEVNULL}
        if IS_WINDOWS:
            kw['creationflags'] = 0x08000000
        result = sp.run(cmd, input=audio_data, **kw)
        raw = result.stdout
        self.sample_rate = 44100
        self.channels = 2
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        self.samples = samples.reshape(-1, self.channels)
        self.total_samples = len(self.samples)
        self.duration = self.total_samples / self.sample_rate
        self._position = 0.0
        self._speed = 1.0
        self._volume = volume
        self._playing = False
        self._stream = None
    def _callback(self, outdata, frames, time_info, status):
        if not self._playing:
            outdata[:] = 0
            return
        pos = self._position
        spd = self._speed
        vol = self._volume
        indices = (np.arange(frames, dtype=np.float64) * spd + pos).astype(np.int64)
        self._position = pos + frames * spd
        valid = (indices >= 0) & (indices < self.total_samples)
        safe_idx = np.clip(indices, 0, self.total_samples - 1)
        outdata[:] = 0
        outdata[valid] = self.samples[safe_idx[valid]] * vol
    def start(self):
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='float32',
            callback=self._callback,
            blocksize=2048
        )
        self._playing = True
        self._stream.start()
    def seek(self, time_sec: float):
        self._position = max(0.0, min(time_sec * self.sample_rate, float(self.total_samples)))
    def set_speed(self, speed: float):
        self._speed = speed
    def set_volume(self, delta: float):
        self._volume = max(0.0, min(1.0, self._volume + delta))
    @property
    def volume(self):
        return self._volume
    @property
    def current_time(self):
        return self._position / self.sample_rate
    def pause(self):
        self._playing = False
    def resume(self):
        self._playing = True
    def stop(self):
        self._playing = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
HEADER_FMT  = '<4sBHHfI64s'
HEADER_SIZE = struct.calcsize(HEADER_FMT)
def read_header(f):
    raw = f.read(HEADER_SIZE)
    if len(raw) < HEADER_SIZE:
        sys.exit('[ERROR] File too short — not a valid .clmp file.')
    magic, version, cols, rows, fps, frame_count, src_name = struct.unpack(HEADER_FMT, raw)
    if magic != MAGIC:
        sys.exit('[ERROR] Not a .clmp file (bad magic bytes).')
    src_name = src_name.rstrip(b'\x00').decode('utf-8', errors='replace')
    return {'cols': cols, 'rows': rows, 'fps': fps,
            'frame_count': frame_count, 'src_name': src_name, 'version': version}
def iter_frames_v1(f, frame_count):
    for _ in range(frame_count):
        size_raw = f.read(4)
        if len(size_raw) < 4:
            return
        (size,) = struct.unpack('<I', size_raw)
        yield zlib.decompress(f.read(size)), None
def iter_frames_v2_plus(f, frame_count):
    for _ in range(frame_count):
        size_raw = f.read(4)
        if len(size_raw) < 4:
            return
        (size,) = struct.unpack('<I', size_raw)
        ascii_data = zlib.decompress(f.read(size))
        size_raw = f.read(4)
        if len(size_raw) < 4:
            return
        (size,) = struct.unpack('<I', size_raw)
        color_data = zlib.decompress(f.read(size))
        yield ascii_data, color_data
def read_audio(f):
    size_raw = f.read(4)
    if not size_raw or len(size_raw) < 4:
        return None
    (size,) = struct.unpack('<I', size_raw)
    if size == 0:
        return None
    return f.read(size)
def delta_render_frame(ascii_text: str, color_data: bytes, cols: int, 
                       pad_x: int, pad_y: int, back_buffer: dict, force_redraw: bool) -> str:
    lines = ascii_text.split('\n')
    out = []
    prev_r, prev_g, prev_b = -1, -1, -1
    
    for r_idx, line in enumerate(lines):
        row_start = r_idx * cols * 3
        c_idx = 0
        while c_idx < len(line):
            ch = line[c_idx]
            off = row_start + c_idx * 3
            if color_data is not None and off + 2 < len(color_data):
                cr = color_data[off] & 0xF0
                cg = color_data[off+1] & 0xF0
                cb = color_data[off+2] & 0xF0
            else:
                cr, cg, cb = 240, 240, 240
            
            cell_key = (r_idx, c_idx)
            new_val = (ch, cr, cg, cb)
            
            if force_redraw or back_buffer.get(cell_key) != new_val:
                out.append(f"\033[{pad_y + r_idx + 1};{pad_x + c_idx + 1}H")
                
                while c_idx < len(line):
                    ch = line[c_idx]
                    off = row_start + c_idx * 3
                    if color_data is not None and off + 2 < len(color_data):
                        cr = color_data[off] & 0xF0
                        cg = color_data[off+1] & 0xF0
                        cb = color_data[off+2] & 0xF0
                    else:
                        cr, cg, cb = 240, 240, 240
                    
                    cell_key = (r_idx, c_idx)
                    new_val = (ch, cr, cg, cb)
                    
                    if not force_redraw and back_buffer.get(cell_key) == new_val:
                        break
                    
                    back_buffer[cell_key] = new_val
                    if ch == ' ':
                        out.append(' ')
                        prev_r, prev_g, prev_b = -1, -1, -1
                    elif cr == prev_r and cg == prev_g and cb == prev_b:
                        out.append(ch)
                    else:
                        out.append(f"\033[38;2;{cr};{cg};{cb}m{ch}")
                        prev_r, prev_g, prev_b = cr, cg, cb
                    c_idx += 1
            else:
                c_idx += 1
    return "".join(out)
def scale_ascii_color(ascii_data: bytes, color_data: bytes,
                      src_cols: int, src_rows: int,
                      dst_cols: int, dst_rows: int):
    lines = ascii_data.decode('ascii').split('\n')
    src_rows = min(src_rows, len(lines))
    out_ascii_lines = []
    out_color = bytearray()
    for dr in range(dst_rows):
        sr = min(int(dr / dst_rows * src_rows), len(lines) - 1)
        src_line = lines[sr]
        new_line = []
        for dc in range(dst_cols):
            sc = min(int(dc / dst_cols * src_cols), max(len(src_line) - 1, 0))
            new_line.append(src_line[sc] if sc < len(src_line) else ' ')
            if color_data is not None:
                off = (sr * src_cols + sc) * 3
                if off + 2 < len(color_data):
                    out_color.extend(color_data[off:off+3])
                else:
                    out_color.extend(b'\xff\xff\xff')
        out_ascii_lines.append(''.join(new_line))
    ascii_text = '\n'.join(out_ascii_lines)
    return ascii_text, bytes(out_color) if color_data is not None else None
def render_hud(width: int, fps: float, frame: int, total: int,
               paused: bool, speed: float, has_audio: bool, volume: float, is_lagging: bool) -> str:
    bar_w   = max(10, width - 85)
    pct     = frame / max(total, 1)
    filled  = int(pct * bar_w)
    bar     = '\u2588' * filled + '\u2591' * (bar_w - filled)
    status  = 'PAUSED' if paused else f'{fps*speed:.1f}fps'
    vol_str = f' vol:{int(volume*100)}%' if has_audio else ''
    hud_base = f' [{bar}] {frame:>5}/{total}  {status}  spd:{speed:.1f}x{vol_str}  q=quit'
    
    safe_width = max(1, width - 1)
    hud = RESET_COLOR + hud_base[:safe_width].ljust(safe_width)
    if is_lagging and safe_width > 15:
        hud = hud[:-8] + '\033[31;1m LAGGING\033[0m'
    return hud
def play(path: str, auto_scale: bool, loop: bool, speed: float, use_color: bool, use_audio: bool):
    print(HIDE_CURSOR, end='', flush=True)
    kr = KeyReader()
    try:
        _play_loop(path, auto_scale, loop, speed, kr, use_color, use_audio)
    except KeyboardInterrupt:
        pass
    finally:
        kr.close()
        print(SHOW_CURSOR, flush=True)
        print(RESET_COLOR)
def _play_loop(path, auto_scale, loop, speed, kr, use_color, use_audio):
    audio_player = None
    try:
        while True:
            with open(path, 'rb') as f:
                meta = read_header(f)
                cols, rows = meta['cols'], meta['rows']
                fps        = meta['fps']
                total      = meta['frame_count']
                version    = meta['version']
                print(f"{CLEAR_SCREEN}{HOME}  Loading {total} frames...", flush=True)
                if version >= 2:
                    frames = list(iter_frames_v2_plus(f, total))
                else:
                    frames = list(iter_frames_v1(f, total))
                audio_data = None
                if version >= 3 and use_audio:
                    audio_data = read_audio(f)
            has_color = version >= 2 and use_color
            has_audio = False
            settings = load_settings()
            jump_sec = settings['jump_seconds']
            vol_step = settings['volume_step']
            last_vol = settings['last_volume']
            
            if audio_data is not None and HAS_AUDIO_SUPPORT:
                audio_player = AudioPlayer(audio_data, volume=last_vol)
                has_audio = True
            elif audio_data is not None and not HAS_AUDIO_SUPPORT:
                print(f"{HOME}  [WARN] pip install sounddevice numpy  for audio", flush=True)
                time.sleep(2)
            frame_idx  = 0
            paused     = False
            spd        = speed
            spf        = 1.0 / (fps * spd)
            last_tick  = time.perf_counter()
            lag_frames = 0
            
            back_buffer = {}
            last_term_w = 0
            last_term_h = 0
            if has_audio:
                audio_player.set_speed(spd)
                audio_player.start()
            while frame_idx < len(frames):
                key = kr.get()
                if key in ('q', 'Q'):
                    return
                elif key == ' ':
                    paused = not paused
                    if has_audio:
                        if paused:
                            audio_player.pause()
                        else:
                            audio_player.resume()
                elif key == '+':
                    spd = min(spd + 0.25, 8.0)
                    spf = 1.0 / (fps * spd)
                    if has_audio:
                        audio_player.set_speed(spd)
                elif key == '-':
                    spd = max(spd - 0.25, 0.25)
                    spf = 1.0 / (fps * spd)
                    if has_audio:
                        audio_player.set_speed(spd)
                elif key == 'UP':
                    if has_audio:
                        audio_player.set_volume(vol_step)
                        settings['last_volume'] = audio_player.volume
                        save_settings(settings)
                elif key == 'DOWN':
                    if has_audio:
                        audio_player.set_volume(-vol_step)
                        settings['last_volume'] = audio_player.volume
                        save_settings(settings)
                elif key == 'RIGHT':
                    jump = int(jump_sec * fps)
                    frame_idx = min(len(frames) - 1, frame_idx + jump)
                    if has_audio:
                        audio_player.seek(frame_idx / fps)
                elif key == 'LEFT':
                    jump = int(jump_sec * fps)
                    frame_idx = max(0, frame_idx - jump)
                    if has_audio:
                        audio_player.seek(frame_idx / fps)
                if paused:
                    time.sleep(0.05)
                    continue
                if has_audio and not paused:
                    video_time = frame_idx / fps
                    audio_time = audio_player.current_time
                    drift = video_time - audio_time
                    if drift > 0.02:
                        time.sleep(min(drift, 0.1))
                    elif drift < -0.1:
                        frame_idx += 1
                        continue
                    else:
                        now = time.perf_counter()
                        diff = now - last_tick
                        if diff < spf:
                            time.sleep(spf - diff)
                    last_tick = time.perf_counter()
                else:
                    now = time.perf_counter()
                    diff = now - last_tick
                    if diff < spf:
                        time.sleep(spf - diff)
                    last_tick = time.perf_counter()
                term_w, term_h = term_size()
                render_start = time.perf_counter()
                
                force_redraw = False
                if term_w != last_term_w or term_h != last_term_h:
                    sys.stdout.write(CLEAR_SCREEN)
                    back_buffer.clear()
                    last_term_w = term_w
                    last_term_h = term_h
                    force_redraw = True

                view_h = max(1, term_h - 1)
                view_w = term_w
                ascii_data, color_data = frames[frame_idx]
                if auto_scale and (cols != view_w or rows != view_h):
                    aspect_ratio = cols / rows
                    target_w = view_w
                    target_h = int(target_w / aspect_ratio)
                    if target_h > view_h:
                        target_h = view_h
                        target_w = int(target_h * aspect_ratio)
                    target_w = max(1, target_w)
                    target_h = max(1, target_h)

                    ascii_text, scaled_color = scale_ascii_color(
                        ascii_data, color_data, cols, rows, target_w, target_h)
                    display_cols = target_w
                    display_rows = target_h
                else:
                    ascii_text = ascii_data.decode('ascii')
                    scaled_color = color_data
                    display_cols = cols
                    display_rows = rows
                
                pad_x = max(0, (view_w - display_cols) // 2)
                pad_y = max(0, (view_h - display_rows) // 2)

                art = delta_render_frame(ascii_text, scaled_color if has_color else None, 
                                         display_cols, pad_x, pad_y, back_buffer, force_redraw)

                vol = audio_player.volume if has_audio else 0
                is_lagging = lag_frames > 5
                hud = render_hud(term_w, fps, frame_idx + 1, len(frames), paused, spd, has_audio, vol, is_lagging)
                
                hud_pos = f"\033[{term_h};1H"
                sys.stdout.write(HOME + art + hud_pos + hud)
                sys.stdout.flush()
                
                render_time = time.perf_counter() - render_start
                if render_time > spf * 1.1:
                    lag_frames += 1
                else:
                    lag_frames = max(0, lag_frames - 1)
                    
                frame_idx += 1
            if audio_player:
                audio_player.stop()
                audio_player = None
            if not loop:
                break
        sys.stdout.write(HOME + CLEAR_SCREEN)
        print('\n  Playback complete.  Press any key to exit...\n')
        time.sleep(1)
    finally:
        if audio_player:
            audio_player.stop()
def main():
    import ffmpeg_check
    ffmpeg_check.ensure_ffmpeg()
    ap = argparse.ArgumentParser(
        description='Play a .clmp ASCII-cinema file in the terminal.'
    )
    ap.add_argument('file',                              help='.clmp file to play')
    ap.add_argument('--no-scale', action='store_true',   help='Disable auto terminal scaling')
    ap.add_argument('--no-color', action='store_true',   help='Disable color output')
    ap.add_argument('--no-audio', action='store_true',   help='Disable audio playback')
    ap.add_argument('--loop',     action='store_true',   help='Loop the video')
    ap.add_argument('--speed',    type=float, default=1.0,
                    help='Playback speed multiplier (default 1.0)')
    args = ap.parse_args()
    if not os.path.isfile(args.file):
        sys.exit(f"[ERROR] File not found: '{args.file}'")
    with open(args.file, 'rb') as f:
        meta = read_header(f)
    ver = meta['version']
    color_info = 'yes' if ver >= 2 else 'no (v1)'
    audio_info = 'yes' if ver >= 3 else 'no'
    print(f"\n  clmp-play")
    print(f"  {'='*50}")
    print(f"  File    : {args.file}")
    print(f"  Source  : {meta['src_name']}")
    print(f"  Size    : {meta['cols']}x{meta['rows']} ASCII")
    print(f"  FPS     : {meta['fps']:.2f}")
    print(f"  Frames  : {meta['frame_count']}")
    print(f"  Color   : {color_info}")
    print(f"  Audio   : {audio_info}")
    print(f"  Controls: SPACE=pause  +/-=speed  arrows=seek/vol  q=quit")
    print()
    time.sleep(1)
    play(args.file, not args.no_scale, args.loop, args.speed,
         not args.no_color, not args.no_audio)
if __name__ == '__main__':
    main()
