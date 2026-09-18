#!/usr/bin/env python3
"""
Find duplicate and similar-looking images, and move the extra copies out
of the way.

============================================================
 HOW TO RUN THIS SCRIPT (Windows and macOS)
============================================================

STEP 1 -- Put this file in the right place
    Copy "find_duplicates.py" directly into the folder that contains
    your photos. The script always scans the folder IT is saved in,
    not wherever you happen to open a terminal from.

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
      1. Navigate to your photos folder, e.g.:
           cd "C:\\Users\\YourName\\Pictures\\MyPhotos"
      2. Run:
           python find_duplicates.py
      3. A window opens, scans your photos, and waits for you to press
         Enter before it closes -- so you have time to read the results.
      (Double-clicking the file also works, for the same reason.)

    macOS (Terminal):
      1. Navigate to your photos folder, e.g.:
           cd ~/Pictures/MyPhotos
      2. Run:
           python3 find_duplicates.py
      (Double-clicking in Finder usually won't work -- Finder opens
      .py files in a text editor rather than running them.)

STEP 4 -- (Optional) Enable similar-image detection
    By default the script always finds EXACT duplicate files. To also
    catch photos that just LOOK the same (resized, re-saved, lightly
    edited copies), install one extra package, once, on this machine:
        python -m pip install Pillow      (Windows)
        python3 -m pip install Pillow     (macOS)
    Without this, the script still works fine -- it just skips that
    extra check and tells you how to turn it on.

WHAT IT DOES TO YOUR FILES
    Nothing is ever deleted. For every group of matching photos, ONE
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
        file is chosen by resolution first (the higher-megapixel, more
        detailed image), then by file size as a tiebreaker between
        equal resolutions. The rest are treated as the lower-quality
        copies and moved.

Two kinds of matches are found:

  1. Exact duplicates -- files with identical content (SHA-256 hash), so
     always the same size. No extra setup needed for this part. Works
     for ANY file type since it just compares raw bytes, including
     vector and RAW camera formats.
     For each group, the largest copy is kept and the rest are moved
     into a "Duplicate" folder created next to this script.

  2. Similar images -- photos that look the same to the eye but aren't
     byte-identical (resized, re-compressed, saved in a different
     format, lightly edited). Detected with a perceptual hash, which
     requires the Pillow library: `pip install Pillow` (one-time, per
     machine). If Pillow isn't installed, this script still runs and
     finds exact duplicates -- it just skips the similar-image step and
     tells you how to enable it.
     For each group, the best copy (highest resolution) is kept and the
     rest are moved into a "Similar" folder created next to this script.

Supported file types:
  Raster (checked for both exact AND similar matches):
    .jpg .jpeg .jpe .jfif .png .gif .bmp .tiff .tif .webp .heic .heif
    .ico .avif
  Vector / camera RAW (checked for exact duplicates only -- Pillow can't
  decode these into pixels for a similarity check without extra libraries):
    .svg .cr2 .nef .arw .dng .raf .orf .rw2

Optional command-line flags (advanced -- plain `python find_duplicates.py`
with no flags is all most people need):
  python find_duplicates.py                   # scan this script's folder
  python3 find_duplicates.py                  # same, on macOS/Linux
  python find_duplicates.py --recursive        # also scan subfolders
  python find_duplicates.py --dry-run          # only report, don't move anything
  python find_duplicates.py --no-similar       # skip similar-image detection
  python find_duplicates.py --threshold 8      # looser similarity match (default: 5)
  python find_duplicates.py --csv report.csv
"""

import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path

RASTER_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".bmp",
    ".tiff", ".tif", ".webp", ".heic", ".heif", ".ico", ".avif",
}

# Vector and camera-RAW formats: matched for exact duplicates (which just
# compare raw file bytes, so any format works), but plain Pillow can't
# decode these into pixels, so they're skipped for similar-image detection.
NON_RASTER_EXTENSIONS = {
    ".svg", ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2",
}

IMAGE_EXTENSIONS = RASTER_EXTENSIONS | NON_RASTER_EXTENSIONS

SCRIPT_DIR = Path(__file__).resolve().parent
DUPLICATE_FOLDER_NAME = "Duplicate"
SIMILAR_FOLDER_NAME = "Similar"


def find_image_files(root: Path, recursive: bool, skip_dirs):
    pattern = "**/*" if recursive else "*"
    for path in root.glob(pattern):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
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


def average_hash(path: Path, hash_size: int = 8):
    """Perceptual fingerprint of an image's look, independent of file format/size. Returns an int bitmask, or None on failure."""
    import warnings
    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with Image.open(path) as img:
                img = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
                pixels = list(img.getdata())
    except Exception as e:
        print(f"  [skip] could not read image data for {path}: {e}", file=sys.stderr)
        return None
    avg = sum(pixels) / len(pixels)
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | (1 if pixel >= avg else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def find_similar_groups(files, threshold: int):
    """Group files whose perceptual hashes are within `threshold` bits of each other."""
    hashes = []
    for path in files:
        h = average_hash(path)
        if h is not None:
            hashes.append((path, h))

    groups = []
    used = set()
    for i, (path_a, hash_a) in enumerate(hashes):
        if path_a in used:
            continue
        group = [path_a]
        for path_b, hash_b in hashes[i + 1:]:
            if path_b in used:
                continue
            if hamming_distance(hash_a, hash_b) <= threshold:
                group.append(path_b)
                used.add(path_b)
        if len(group) > 1:
            used.add(path_a)
            groups.append(group)
    return groups


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def split_keep_and_move(group):
    """Keep the largest file (alphabetical on ties), move the rest.

    Used for exact-duplicate groups, where every file is byte-for-byte
    identical -- so this pick has no effect on quality, it's just a
    deterministic way to choose which filename survives.
    """
    ordered = sorted(group, key=lambda p: (-p.stat().st_size, p.name))
    return ordered[0], ordered[1:]


def image_pixel_count(path: Path):
    """Width x height of an image, or None if it can't be read. Requires Pillow."""
    from PIL import Image

    try:
        with Image.open(path) as img:
            width, height = img.size
            return width * height
    except Exception:
        return None


def split_best_and_worst(group):
    """Keep the best-quality file, move the rest.

    "Best" is judged by resolution (megapixels) first, since that's the
    most reliable sign of real image quality -- a bigger picture has
    more actual detail. File size breaks ties between equal resolutions
    (e.g. a less-compressed, cleaner copy), and filename breaks any
    remaining tie so the result is deterministic.
    """
    pixel_counts = {path: image_pixel_count(path) for path in group}

    def quality_key(path):
        pixels = pixel_counts[path]
        return (-(pixels if pixels is not None else -1), -path.stat().st_size, path.name)

    ordered = sorted(group, key=quality_key)
    return ordered[0], ordered[1:]


def format_dimensions(path: Path) -> str:
    pixels = image_pixel_count(path)
    if pixels is None:
        return "resolution unknown"
    megapixels = pixels / 1_000_000
    return f"{megapixels:.1f}MP"


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
        detail = f", {format_dimensions(keep)}" if show_resolution else ""
        print(f"    keep: {keep.name}  ({human_size(keep.stat().st_size)}{detail})")
        for path in move:
            detail = f", {format_dimensions(path)}" if show_resolution else ""
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


def run():
    parser = argparse.ArgumentParser(
        description="Find duplicate and similar images next to this script and move extras out of the way."
    )
    parser.add_argument("--recursive", action="store_true", help="Also scan subfolders")
    parser.add_argument("--dry-run", action="store_true", help="Only report matches, don't move any files")
    parser.add_argument("--no-similar", action="store_true", help="Skip similar-image detection, exact duplicates only")
    parser.add_argument("--threshold", type=int, default=5, help="Max difference for similar-image matches (default: 5, lower = stricter, 0 = near-identical only)")
    parser.add_argument("--csv", metavar="FILE", help="Write results to a CSV file")
    args = parser.parse_args()

    duplicate_dir = SCRIPT_DIR / DUPLICATE_FOLDER_NAME
    similar_dir = SCRIPT_DIR / SIMILAR_FOLDER_NAME

    print(f"Scanning {SCRIPT_DIR} ({'recursive' if args.recursive else 'top-level only'})...")
    files = list(find_image_files(SCRIPT_DIR, args.recursive, [duplicate_dir, similar_dir]))
    print(f"Found {len(files)} image file(s).")

    print("\nHashing files to find exact duplicates...")
    exact_groups = find_exact_duplicate_groups(files)
    exact_plan = report_groups("Exact duplicates", exact_groups, split_keep_and_move) if exact_groups else []
    if not exact_groups:
        print("\nExact duplicates: none found.")

    # Files already flagged as exact duplicates are excluded from similarity
    # search -- there's no point comparing copies we're already moving.
    exact_matched = {path for group in exact_groups for path in group}
    remaining_files = [path for path in files if path not in exact_matched]

    similar_groups = []
    if not args.no_similar:
        try:
            import PIL  # noqa: F401
        except ImportError:
            print(
                "\nSkipping similar-image detection: Pillow is not installed.\n"
                "To enable it, run this once:\n"
                "  python -m pip install Pillow\n"
                "(or use --no-similar to silence this message)",
                file=sys.stderr,
            )
        else:
            rasterizable = [p for p in remaining_files if p.suffix.lower() in RASTER_EXTENSIONS]
            skipped_count = len(remaining_files) - len(rasterizable)
            if skipped_count:
                print(
                    f"\nNote: skipping {skipped_count} file(s) for similar-image detection "
                    f"(vector/RAW formats like .svg aren't supported for this check)."
                )
            print("\nComputing perceptual hashes to find similar images...")
            similar_groups = find_similar_groups(rasterizable, args.threshold)

    similar_plan = report_groups(
        f"Similar images (threshold={args.threshold})", similar_groups, split_best_and_worst, show_resolution=True
    ) if similar_groups else []
    if not args.no_similar and not similar_groups:
        print("\nSimilar images: none found.")

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
        f"and {moved_similar} similar image(s) into {similar_dir}."
    )


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
