"""Unified CLI entry point for CLMP."""
import argparse
import sys
from clmp import __version__


def main():
    parser = argparse.ArgumentParser(
        prog='clmp',
        description='CLMP — CLI Movie Package. Encode and play ASCII cinema in your terminal.',
    )
    parser.add_argument(
        '-v', '--version', action='version',
        version=f'clmp {__version__}'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ── encode ──────────────────────────────────────────────────────────
    enc = subparsers.add_parser(
        'encode',
        help='Encode an MP4 into a .clmp ASCII-cinema file',
        description='Encode an MP4 into a .clmp ASCII-cinema file.'
    )
    enc.add_argument('input', help='Source .mp4 file')
    enc.add_argument('output', help='Destination .clmp file')
    enc.add_argument('--fps', type=float, default=12,
                     help='Target playback fps (default 12)')
    enc.add_argument('--width', type=int, default=160,
                     help='ASCII columns (default 160)')
    enc.add_argument('--height', type=int, default=45,
                     help='ASCII rows (default 45)')

    # ── play ────────────────────────────────────────────────────────────
    pl = subparsers.add_parser(
        'play',
        help='Play a .clmp ASCII-cinema file in the terminal',
        description='Play a .clmp ASCII-cinema file in the terminal.'
    )
    pl.add_argument('file', help='.clmp file to play')
    pl.add_argument('--no-scale', action='store_true',
                    help='Disable auto terminal scaling')
    pl.add_argument('--no-color', action='store_true',
                    help='Disable color output')
    pl.add_argument('--no-audio', action='store_true',
                    help='Disable audio playback')
    pl.add_argument('--loop', action='store_true',
                    help='Loop the video')
    pl.add_argument('--speed', type=float, default=1.0,
                    help='Playback speed multiplier (default 1.0)')

    # ── set ─────────────────────────────────────────────────────────────
    st = subparsers.add_parser(
        'set',
        help='Configure CLMP playback settings',
        description='Configure CLMP playback settings.'
    )
    st.add_argument('--jump', type=float,
                    help='Seconds to jump for left/right arrows')
    st.add_argument('--vol-step', type=float,
                    help='Volume increment %% (e.g. 5 for 5%%)')
    st.add_argument('--volume', type=float,
                    help='Default starting volume %% (e.g. 80)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == 'encode':
        from clmp.encode import main as encode_main
        encode_main(args)
    elif args.command == 'play':
        from clmp.play import main as play_main
        play_main(args)
    elif args.command == 'set':
        from clmp.settings import main as settings_main
        settings_main(args)


if __name__ == '__main__':
    main()
