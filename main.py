"""Balloon Shooter 3D - run this file to play.

    python main.py            # play
    python main.py --help     # options (start a mode directly, window size, ...)
"""

import sys

from balloon_shooter.app import main

if __name__ == "__main__":
    sys.exit(main())
