"""The application: window, state machine, input, shooting and game feel."""

import os
import random
import sys

from panda3d.core import loadPrcFileData

from . import config as C


def configure(args):
    """Panda3D settings that must be set before ShowBase is created."""
    s = args.store.settings
    w, h = args.size
    prc = [
        f"window-title {C.TITLE}",
        f"win-size {w} {h}",
        f"fullscreen {'#t' if s.fullscreen and not args.windowed else '#f'}",
        "sync-video #t",
        "textures-power-2 none",
        "show-frame-rate-meter #f",
        "notify-level-device error",
        "notify-level-glgsg warning",
        "audio-cache-limit 64",
        "default-far 5000",
        "default-near 0.05",
    ]
    if s.quality == "high" and not args.no_msaa:
        prc += ["framebuffer-multisample 1", "multisamples 4"]
    if args.mute or os.environ.get("BALLOON_SHOOTER_NOAUDIO"):
        prc.append("audio-library-name null")
    loadPrcFileData("balloon-shooter", "\n".join(prc))


# ShowBase is imported lazily so `configure` runs first.
def run(args):
    configure(args)
    from .game import Game
    game = Game(args)
    game.run()
    return 0


def parse_args(argv=None):
    import argparse

    from .storage import Store

    p = argparse.ArgumentParser(description=C.TITLE)
    p.add_argument("--mode", choices=list(C.MODES), help="skip the menu and start this mode")
    p.add_argument("--difficulty", choices=list(C.DIFFICULTIES), help="difficulty for --mode")
    p.add_argument("--windowed", action="store_true", help="ignore the fullscreen setting")
    p.add_argument("--size", type=lambda s: tuple(int(v) for v in s.lower().split("x")), default=(1280, 720),
                   help="window size, e.g. 1600x900")
    p.add_argument("--mute", action="store_true", help="disable audio")
    p.add_argument("--no-msaa", action="store_true", help="disable anti-aliasing")
    p.add_argument("--seed", type=int, default=None)
    # automation hooks used for screenshots and smoke tests
    p.add_argument("--autoplay", action="store_true", help="let a bot play (demo / testing)")
    p.add_argument("--screenshot", action="append", default=[], metavar="T:PATH",
                   help="save a screenshot at T seconds, e.g. 12:shots/play.png (repeatable)")
    p.add_argument("--quit-after", type=float, default=0.0, help="exit after N seconds")
    p.add_argument("--data-dir", default=None, help="where settings and scores are saved")
    p.add_argument("--script", default="", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    args.store = Store(args.data_dir)
    if args.seed is not None:
        random.seed(args.seed)
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
