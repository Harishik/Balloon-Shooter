"""Record a short gameplay trailer straight from the game and encode it.

The game runs with its autoplay bot and ``--record``, which saves every frame
at a fixed frame rate, so the result is smooth even on a slow machine or a
virtual display. The clips are joined with crossfades into an MP4, and a
smaller GIF is made for the README.

    python tools/make_trailer.py                      # needs a display
    xvfb-run -a -s "-screen 0 1280x720x24" python tools/make_trailer.py

Requires ffmpeg on the PATH.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
FADE = 0.5   # seconds of crossfade between clips

# (name, extra game arguments, keep from, keep until) in game seconds
CLIPS = [
    ("menu", ["--script", "3.4:modes"], 0.4, 5.4),
    ("time-attack", ["--mode", "time", "--difficulty", "easy", "--autoplay", "relaxed"], 7.0, 15.0),
    ("survival", ["--mode", "survival", "--difficulty", "easy", "--autoplay", "relaxed"], 8.0, 12.5),
    ("zen", ["--mode", "zen", "--difficulty", "easy", "--autoplay", "relaxed"], 8.0, 12.5),
]


def record(name, extra, start, end, work, seed):
    frames = os.path.join(work, name)
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "--mute", "--seed", str(seed),
           "--data-dir", os.path.join(work, "data-" + name), "--record", frames,
           "--record-fps", str(FPS), "--quit-after", f"{end + 0.2:.2f}"] + extra
    print(f"recording {name} ({end - start:.1f}s)...", flush=True)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    first = int(round(start * FPS))
    count = int(round((end - start) * FPS))
    return frames, first, count


def encode(clips, mp4, gif, gif_width, gif_fps):
    inputs, filters = [], []
    for i, (frames, first, count) in enumerate(clips):
        inputs += ["-framerate", str(FPS), "-start_number", str(first),
                   "-i", os.path.join(frames, "frame_%05d.png")]
        filters.append(f"[{i}:v]trim=end_frame={count},setpts=PTS-STARTPTS,format=yuv420p[c{i}]")
    # chain crossfades: each fade starts FADE seconds before the running total ends
    last, total = "c0", clips[0][2] / FPS
    for i in range(1, len(clips)):
        out = f"x{i}"
        filters.append(f"[{last}][c{i}]xfade=transition=fade:duration={FADE}:offset={total - FADE:.3f}[{out}]")
        last, total = out, total + clips[i][2] / FPS - FADE
    os.makedirs(os.path.dirname(mp4), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", f"[{last}]", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], check=True)
    palette = (f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[a][b];"
               "[a]palettegen=max_colors=128:stats_mode=diff[p];"
               "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", palette, "-loop", "0", gif],
                   check=True)
    print(f"{mp4}: {os.path.getsize(mp4) / 1e6:.1f} MB, {total:.1f}s")
    print(f"{gif}: {os.path.getsize(gif) / 1e6:.1f} MB")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=os.path.join(ROOT, "docs", "media"))
    p.add_argument("--gif-width", type=int, default=640)
    p.add_argument("--gif-fps", type=int, default=12)
    p.add_argument("--seed", type=int, default=21)
    p.add_argument("--keep", action="store_true", help="keep the recorded frames")
    args = p.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required")
    work = tempfile.mkdtemp(prefix="trailer-")
    try:
        clips = [record(name, extra, start, end, work, args.seed) for name, extra, start, end in CLIPS]
        encode(clips, os.path.join(args.out, "trailer.mp4"), os.path.join(args.out, "trailer.gif"),
               args.gif_width, args.gif_fps)
    finally:
        if args.keep:
            print("frames kept in", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
