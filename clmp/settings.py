import argparse
import json
import os

SETTINGS_DIR = os.path.join(os.path.expanduser('~'), '.clmp')
SETTINGS_FILE = os.path.join(SETTINGS_DIR, 'settings.json')

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
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Configure CLMP playback settings.")
        parser.add_argument('--jump', type=float, help='Number of seconds to jump for left/right arrows')
        parser.add_argument('--vol-step', type=float, help='Volume increment percentage (e.g. 5 for 5%%, 10 for 10%%) for up/down arrows')
        parser.add_argument('--volume', type=float, help='Set the default starting volume percentage (e.g. 80)')
        args = parser.parse_args()

    settings = load_settings()
    changed = False

    if args.jump is not None:
        settings['jump_seconds'] = float(args.jump)
        print(f"Set jump_seconds to {settings['jump_seconds']}s")
        changed = True

    if args.vol_step is not None:
        settings['volume_step'] = max(0.01, min(1.0, float(args.vol_step) / 100.0))
        print(f"Set volume_step to {settings['volume_step'] * 100:.1f}%")
        changed = True

    if args.volume is not None:
        settings['last_volume'] = max(0.0, min(1.0, float(args.volume) / 100.0))
        print(f"Set starting volume to {settings['last_volume'] * 100:.1f}%")
        changed = True

    if changed:
        save_settings(settings)
        print("Settings saved successfully!")
    else:
        print("Current settings:")
        for k, v in settings.items():
            if 'volume' in k or 'step' in k:
                print(f"  {k}: {v * 100:.1f}%")
            else:
                print(f"  {k}: {v}")

if __name__ == '__main__':
    main()
