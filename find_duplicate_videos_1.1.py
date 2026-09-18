#!/usr/bin/env python3
"""
Find duplicate and similar-looking videos, and move the extra copies out
of the way.

Version: 1.1

============================================================
 HOW TO RUN THIS SCRIPT (Windows and macOS)
============================================================

STEP 1 -- Put this file in the right place
    Copy "find_duplicate_videos_1.1.py" directly into the folder that
    contains your videos. The script always scans the folder IT is
    saved in, not wherever you happen to open a terminal from.

STEP 2 -- Make sure Python 3 is installed
    Windows:
      1. Open "Command Prompt" (search for it in the Start menu).
      2. Type:  python --version
      3. If you see a version number (e.g. "Python 3.12.6"), you're
         set -- skip to Step 3.
      4. If you get an error instead, install Python from
         https://python.org/downloads -- during setup, tick the box
         that says "Add python.exe to PATH" before clicking Install.

    macOS:
      1. Open "Terminal" (Cmd+Space, type Terminal, press Enter).
      2. Type:  python3 --version
      3. Modern Macs come with Python 3 preinstalled, so this usually
         already works. If it doesn't, install Python from
         https://python.org/downloads.

STEP 3 -- Run the script
    Windows (Command Prompt):
      1. Navigate to your videos folder, e.g.:
           cd "C:\\Users\\YourName\\Videos\\MyClips"
      2. Run:
           python find_duplicate_videos_1.1.py
      3. A window opens, scans your videos, and waits for you to press
         Enter before it closes -- so you have time to read the results.
      (Double-clicking the file also works, for the same reason.)

    macOS (Terminal):
      1. Navigate to your videos folder, e.g.:
           cd ~/Movies/MyClips
      2. Run:
           python3 find_duplicate_videos_1.1.py
      (Double-clicking in Finder usually won't work -- Finder opens
      .py files in a text editor rather than running them.)

STEP 4 -- Similar-video detection (automatic, no setup needed)
    To catch videos that just LOOK the same (re-encoded, resized,
    trimmed, saved in a different format), not just exact duplicates,
    this script needs the OpenCV library. You don't need to install
    anything yourself: if OpenCV isn't already on your machine, the
    script installs it automatically the first time it needs it, uses
    it for that run, and then removes it again afterwards -- so it
    leaves nothing extra behind on your computer. This is a bigger
    download (tens of MB) than a typical package, so the first run
    will take longer and needs an internet connection; if none is
    available, the script just skips the similar-video check and
    still finds exact duplicates fine. Analyzing video frames is also
    slower than photos, so expect this step to take a while on large
    video collections.
    (If OpenCV was already installed before you ran this script --
    e.g. you use it for something else -- it's left alone, not removed.)

WHAT IT DOES TO YOUR FILES
    Nothing is ever deleted. For every group of matching videos, ONE
    file is left where it is and every other copy in that group is
    MOVED (not deleted) into a new folder created next to this script:
      - "Duplicate" folder  -> exact, byte-for-byte identical copies
      - "Similar" folder    -> visually similar but not identical copies
    You can always look through those folders afterwards and delete
    anything you're sure you don't need, or move things back.

    Which copy is kept:
      - In a "Duplicate" group, every file is byte-for-byte identical,
        so it makes no difference which one survives -- quality is the
        same either way.
      - In a "Similar" group, the files actually differ, so the KEPT
        file is chosen by resolution first (the higher-resolution, more
        detailed video), then by file size as a tiebreaker between
        equal resolutions. The rest are treated as the lower-quality
        copies and moved.

Two kinds of matches are found:

  1. Exact duplicates -- files with identical content (SHA-256 hash), so
     always the same size. No extra setup needed for this part. Works
     for any video file type since it just compares raw bytes.
     For each group, the largest copy is kept and the rest are moved
     into a "Duplicate" folder created next to this script.

  2. Similar videos -- clips that look the same but aren't byte-
     identical (re-encoded, resized, saved in a different container,
     lightly trimmed). Detected by sampling a few frames from each
     video (near the start, middle, and end) and perceptually hashing
     them, the same idea used for similar-image detection but applied
     to video frames. Requires OpenCV. This script installs OpenCV
     automatically if it's missing and removes it again when the run
     finishes -- see STEP 4 above. If installing it fails (e.g. no
     internet), this script still runs and finds exact duplicates --
     it just skips the similar-video step.
     For each group, the best copy (highest resolution) is kept and the
     rest are moved into a "Similar" folder created next to this script.

Supported file types:
    .mp4 .mov .avi .mkv .wmv .flv .webm .m4v .mpg .mpeg .3gp .ts .m2ts .ogv

Optional command-line flags (advanced -- plain `python find_duplicate_videos_1.1.py`
with no flags is all most people need):
  python find_duplicate_videos_1.1.py                  # scan this script's folder
  python3 find_duplicate_videos_1.1.py                 # same, on macOS/Linux
  python find_duplicate_videos_1.1.py --recursive       # also scan subfolders
  python find_duplicate_videos_1.1.py --dry-run         # only report, don't move anything
  python find_duplicate_videos_1.1.py --no-similar      # skip similar-video detection
  python find_duplicate_videos_1.1.py --threshold 25    # looser similarity match (default: 15)
  python find_duplicate_videos_1.1.py --csv report.csv
  python find_duplicate_videos_1.1.py --version         # print the script version
"""

import argparse
import csv
import hashlib
import importlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

__version__ = "1.1"

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".m2ts", ".ogv",
}

# Fractions of the way through each video to sample a frame from, for the
# similar-video perceptual fingerprint (near the start, middle, and end).
SAMPLE_POINTS = (0.1, 0.5, 0.9)
HASH_SIZE = 8  # each sampled frame becomes an 8x8 = 64-bit fingerprint

SCRIPT_DIR = Path(__file__).resolve().parent
DUPLICATE_FOLDER_NAME = "Duplicate"
SIMILAR_FOLDER_NAME = "Similar"


def find_video_files(root: Path, recursive: bool, skip_dirs):
    pattern = "**/*" if recursive else "*"
    for path in root.glob(pattern):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if any(is_inside(path, skip_dir) for skip_dir in skip_dirs):
            continue  # already inside an output folder, don't re-scan it
        yield path


def is_inside(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def find_exact_duplicate_groups(files):
    by_hash = {}
    for path in files:
        try:
            digest = sha256_of_file(path)
        except OSError as e:
            print(f"  [skip] could not read {path}: {e}", file=sys.stderr)
            continue
        by_hash.setdefault(digest, []).append(path)
    return [group for group in by_hash.values() if len(group) > 1]


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def video_dimensions(path: Path):
    """(width, height) of a video, or None if it can't be read. Requires OpenCV."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            return None
        return width, height
    finally:
        cap.release()


def frame_fingerprint(path: Path):
    """Perceptual fingerprint of a video's visual content: one average-hash
    per sampled frame (start/middle/end). Returns a tuple of ints, or None
    on failure. Requires OpenCV."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not frame_count or frame_count <= 0:
            return None

        hashes = []
        for fraction in SAMPLE_POINTS:
            frame_index = max(0, min(int(frame_count * fraction), int(frame_count) - 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                return None
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (HASH_SIZE, HASH_SIZE), interpolation=cv2.INTER_AREA)
            avg = small.mean()
            bits = 0
            for pixel in small.flatten():
                bits = (bits << 1) | (1 if pixel >= avg else 0)
            hashes.append(bits)
        return tuple(hashes)
    except Exception as e:
        print(f"  [skip] could not read video frames for {path}: {e}", file=sys.stderr)
        return None
    finally:
        cap.release()


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def fingerprint_distance(fp_a, fp_b) -> int:
    return sum(hamming_distance(a, b) for a, b in zip(fp_a, fp_b))


def find_similar_groups(files, threshold: int):
    """Group files whose frame fingerprints are within `threshold` bits of each other."""
    fingerprints = []
    for path in files:
        fp = frame_fingerprint(path)
        if fp is not None:
            fingerprints.append((path, fp))

    groups = []
    used = set()
    for i, (path_a, fp_a) in enumerate(fingerprints):
        if path_a in used:
            continue
        group = [path_a]
        for path_b, fp_b in fingerprints[i + 1:]:
            if path_b in used:
                continue
            if fingerprint_distance(fp_a, fp_b) <= threshold:
                group.append(path_b)
                used.add(path_b)
        if len(group) > 1:
            used.add(path_a)
            groups.append(group)
    return groups


def split_keep_and_move(group):
    """Keep the largest file (alphabetical on ties), move the rest.

    Used for exact-duplicate groups, where every file is byte-for-byte
    identical -- so this pick has no effect on quality, it's just a
    deterministic way to choose which filename survives.
    """
    ordered = sorted(group, key=lambda p: (-p.stat().st_size, p.name))
    return ordered[0], ordered[1:]


def split_best_and_worst(group):
    """Keep the best-quality file, move the rest.

    "Best" is judged by resolution first, since that's the most direct
    sign of real video quality. File size breaks ties between equal
    resolutions (e.g. a less-compressed, cleaner copy), and filename
    breaks any remaining tie so the result is deterministic.
    """
    dimensions = {path: video_dimensions(path) for path in group}

    def quality_key(path):
        dims = dimensions[path]
        pixels = (dims[0] * dims[1]) if dims else -1
        return (-pixels, -path.stat().st_size, path.name)

    ordered = sorted(group, key=quality_key)
    return ordered[0], ordered[1:]


def format_resolution(path: Path) -> str:
    dims = video_dimensions(path)
    if dims is None:
        return "resolution unknown"
    return f"{dims[0]}x{dims[1]}"


def unique_destination(target_dir: Path, path: Path) -> Path:
    dest = target_dir / path.name
    counter = 1
    while dest.exists():
        dest = target_dir / f"{path.stem}_{counter}{path.suffix}"
        counter += 1
    return dest


def report_groups(label, groups, split_fn, show_resolution=False):
    print(f"\n{label}: {len(groups)} group(s)")
    plan = []
    for i, group in enumerate(groups, 1):
        keep, move = split_fn(group)
        plan.append((keep, move))
        print(f"\n  Group {i}:")
        detail = f", {format_resolution(keep)}" if show_resolution else ""
        print(f"    keep: {keep.name}  ({human_size(keep.stat().st_size)}{detail})")
        for path in move:
            detail = f", {format_resolution(path)}" if show_resolution else ""
            print(f"    move: {path.name}  ({human_size(path.stat().st_size)}{detail})")
    return plan


def move_plan(plan, target_dir: Path):
    if not plan:
        return 0
    target_dir.mkdir(exist_ok=True)
    moved = 0
    for keep, move in plan:
        for path in move:
            dest = unique_destination(target_dir, path)
            try:
                shutil.move(str(path), str(dest))
                print(f"  moved: {path.name} -> {target_dir.name}/{dest.name}")
                moved += 1
            except OSError as e:
                print(f"  [error] could not move {path}: {e}", file=sys.stderr)
    return moved


def pip_install(pip_name: str) -> bool:
    """Try to install a package with pip, working around a couple of common
    permission setups. Returns True on success."""
    base_cmd = [sys.executable, "-m", "pip", "install", "--quiet", pip_name]
    for cmd in (base_cmd, base_cmd + ["--user"]):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
        except OSError:
            pass
    return False


def pip_uninstall(pip_name: str) -> None:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "--quiet", "-y", pip_name],
            capture_output=True, text=True,
        )
    except OSError:
        pass


def ensure_package(import_name: str, pip_name: str):
    """Make sure `import_name` can be imported, installing `pip_name` via
    pip if it's missing so friends never have to run pip themselves.

    Returns (available, installed_by_us). `installed_by_us` is True only
    when THIS run installed the package -- so the caller knows it's safe
    to remove it again afterwards without deleting something the user
    already had on their machine for other reasons.
    """
    try:
        importlib.import_module(import_name)
        return True, False
    except ImportError:
        pass

    print(f"\n{pip_name} is not installed. Installing it now (temporarily, just for this run)...")
    if not pip_install(pip_name):
        print(
            f"Could not automatically install {pip_name}. You can install it yourself with:\n"
            f"  {sys.executable} -m pip install {pip_name}",
            file=sys.stderr,
        )
        return False, False

    importlib.invalidate_caches()
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"{pip_name} installed but could not be imported. Skipping this feature.", file=sys.stderr)
        return False, True  # installed, but unusable -- still clean it up afterwards

    print(f"{pip_name} installed.")
    return True, True


def run():
    parser = argparse.ArgumentParser(
        description="Find duplicate and similar videos next to this script and move extras out of the way."
    )
    parser.add_argument("--recursive", action="store_true", help="Also scan subfolders")
    parser.add_argument("--dry-run", action="store_true", help="Only report matches, don't move any files")
    parser.add_argument("--no-similar", action="store_true", help="Skip similar-video detection, exact duplicates only")
    parser.add_argument("--threshold", type=int, default=15, help="Max difference for similar-video matches (default: 15, lower = stricter, 0 = near-identical only)")
    parser.add_argument("--csv", metavar="FILE", help="Write results to a CSV file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    duplicate_dir = SCRIPT_DIR / DUPLICATE_FOLDER_NAME
    similar_dir = SCRIPT_DIR / SIMILAR_FOLDER_NAME

    print(f"find_duplicate_videos_1.1.py v{__version__}")
    print(f"Detected OS: {platform.system()} ({platform.platform()})")
    print(f"Scanning {SCRIPT_DIR} ({'recursive' if args.recursive else 'top-level only'})...")
    files = list(find_video_files(SCRIPT_DIR, args.recursive, [duplicate_dir, similar_dir]))
    print(f"Found {len(files)} video file(s).")

    print("\nHashing files to find exact duplicates (this can take a while for large videos)...")
    exact_groups = find_exact_duplicate_groups(files)
    exact_plan = report_groups("Exact duplicates", exact_groups, split_keep_and_move) if exact_groups else []
    if not exact_groups:
        print("\nExact duplicates: none found.")

    # Files already flagged as exact duplicates are excluded from similarity
    # search -- there's no point comparing copies we're already moving.
    exact_matched = {path for group in exact_groups for path in group}
    remaining_files = [path for path in files if path not in exact_matched]

    similar_groups = []
    opencv_installed_by_us = False
    try:
        if not args.no_similar:
            available, opencv_installed_by_us = ensure_package("cv2", "opencv-python")
            if not available:
                print("Skipping similar-video detection (use --no-similar to silence this message).", file=sys.stderr)
            else:
                print("\nSampling frames to find similar videos (this can take a while)...")
                similar_groups = find_similar_groups(remaining_files, args.threshold)

        similar_plan = report_groups(
            f"Similar videos (threshold={args.threshold})", similar_groups, split_best_and_worst, show_resolution=True
        ) if similar_groups else []
        if not args.no_similar and not similar_groups:
            print("\nSimilar videos: none found.")

        if args.csv:
            with open(args.csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["type", "group", "file", "action"])
                for i, (keep, move) in enumerate(exact_plan, 1):
                    writer.writerow(["exact", i, str(keep), "keep"])
                    for path in move:
                        writer.writerow(["exact", i, str(path), "move"])
                for i, (keep, move) in enumerate(similar_plan, 1):
                    writer.writerow(["similar", i, str(keep), "keep"])
                    for path in move:
                        writer.writerow(["similar", i, str(path), "move"])
            print(f"\nCSV report written to {args.csv}")

        if args.dry_run:
            print("\nDry run: no files were moved.")
            return

        moved_exact = move_plan(exact_plan, duplicate_dir)
        moved_similar = move_plan(similar_plan, similar_dir)

        print(
            f"\nDone. Moved {moved_exact} exact duplicate(s) into {duplicate_dir} "
            f"and {moved_similar} similar video(s) into {similar_dir}."
        )
    finally:
        if opencv_installed_by_us:
            print("\nCleaning up: removing the OpenCV library this run installed temporarily...")
            pip_uninstall("opencv-python")


def main():
    # On Windows, double-clicking this file opens a console that closes the
    # instant the script finishes, so any output (including errors) would
    # flash by unseen. Pause before exiting when running interactively so
    # the window stays open; skip the pause when stdin isn't a real console
    # (e.g. run from an automated script) to avoid hanging forever.
    try:
        run()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        if sys.stdin.isatty():
            try:
                input("\nPress Enter to exit...")
            except (EOFError, KeyboardInterrupt):
                pass


if __name__ == "__main__":
    main()
