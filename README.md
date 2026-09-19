# Python Media Duplicate & Similarity Cleaners

Lightweight, safe, and cross-platform Python scripts to detect and organize duplicate or visually similar images and videos.

---

## 📌 Overview

Managing personal media libraries often leads to clutter from identical backups, re-compressed uploads, resized copies, or bursts of similar footage.

These tools scan your media folder, identify both **exact byte-for-byte duplicates** and **visually similar media**, and safely move redundant files into organized subfolders (`Duplicate/` and `Similar/`).

> [!IMPORTANT]
> **Zero Deletion Guarantee**: No file is ever permanently deleted. Duplicate and similar files are simply moved into separate folders next to the script. You can review and delete them at your convenience.

---

## 🗂️ Included Scripts

| Script | Version | Focus | Dependencies | Notes |
| :--- | :--- | :--- | :--- | :--- |
| [`find_duplicates_images_1.1.py`](find_duplicates_images_1.1.py) | **1.1 (Latest)** | Images & Photos | `Pillow` (Auto-managed) | Auto-installs `Pillow` temporarily if needed, and removes it upon completion |
| [`find_duplicate_videos_1.1.py`](find_duplicate_videos_1.1.py) | **1.1 (Latest)** | Videos & Clips | `opencv-python` (Auto-managed) | Samples frames at start, middle, and end; auto-manages `OpenCV` |
| [`find_duplicates_images_1.0.py`](find_duplicates_images_1.0.py) | **1.0 (Legacy)** | Images & Photos | `Pillow` (Manual) | Requires manual `pip install Pillow` for similar-image detection |

---

## ✨ Key Features

- **Safe Non-Destructive Workflow**:
  - The best copy is kept in place. Extra copies are moved to `Duplicate/` or `Similar/`.
  - If a destination filename already exists, filenames are suffixed (e.g., `_1.jpg`) to prevent accidental overwrites.
- **Two-Tier Match Detection**:
  - **Exact Duplicates**: Identified via SHA-256 cryptographic hashing (100% byte-for-byte identical, matches any format).
  - **Visual Similarity**: Uses perceptual hashing (aHash) to find images and videos that look identical to human eyes (e.g., re-compressed, scaled, or slightly edited).
- **Smart "Best Copy" Retention**:
  - **Exact duplicates**: Retains the first/largest file in the group.
  - **Similar media**: Retains the highest resolution (megapixels / frame dimensions) file, with file size as a tiebreaker.
- **Zero Permanent Footprint (v1.1)**:
  - If required packages (`Pillow` or `opencv-python`) are missing, v1.1 scripts can automatically install them temporarily for the run and uninstall them when finished.
  - If packages were already installed on your system, they remain untouched.
- **Interactive Windows Friendly**:
  - Includes a pause before exit when run in an interactive console, allowing Windows users to double-click and review outputs before the window closes.
- **Reporting & Dry Run**:
  - Export full scan results to CSV.
  - Test scans safely without modifying files using `--dry-run`.

---

## 📁 Supported Formats

### Images ([`find_duplicates_images_1.1.py`](find_duplicates_images_1.1.py))
- **Raster Formats** *(Exact and perceptual similarity)*:
  `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.png`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.heic`, `.heif`, `.ico`, `.avif`
- **Vector & Camera RAW Formats** *(Exact duplicates only)*:
  `.svg`, `.cr2`, `.nef`, `.arw`, `.dng`, `.raf`, `.orf`, `.rw2`

### Videos ([`find_duplicate_videos_1.1.py`](find_duplicate_videos_1.1.py))
- **Video Containers** *(Exact and frame perceptual similarity)*:
  `.mp4`, `.mov`, `.avi`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.3gp`, `.m2ts`, `.ogv`

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.7+ installed ([python.org](https://python.org/downloads)).
- On Windows, make sure to check **"Add python.exe to PATH"** during setup.

### Step 1: Place the Script
Copy the desired script (e.g. [`find_duplicates_images_1.1.py`](find_duplicates_images_1.1.py) or [`find_duplicate_videos_1.1.py`](find_duplicate_videos_1.1.py)) into the directory containing your media.

The scripts scan their **own directory** by default to protect other folders.

### Step 2: Run the Script

#### macOS / Linux
Open Terminal, navigate to your media folder, and execute:
```bash
cd ~/Pictures/MyPhotos
python3 find_duplicates_images_1.1.py
```
Or for videos:
```bash
cd ~/Movies/MyVideos
python3 find_duplicate_videos_1.1.py
```

#### Windows
1. Open Command Prompt, navigate to your media folder, and run:
   ```cmd
   cd C:\Users\YourName\Pictures\MyPhotos
   python find_duplicates_images_1.1.py
   ```
2. **Double-click**: You can also simply double-click the `.py` file in File Explorer. The script will keep the window open after completion until you press `Enter`.

---

## ⚙️ Command-Line Options

Both scripts support command-line arguments for advanced customization:

```bash
python3 find_duplicates_images_1.1.py [OPTIONS]
python3 find_duplicate_videos_1.1.py [OPTIONS]
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--recursive` | Disabled | Recursively search subdirectories inside the folder |
| `--dry-run` | Disabled | Scan and print findings without moving any files |
| `--no-similar` | Disabled | Skip perceptual similarity detection; scan exact duplicates only |
| `--threshold <INT>` | `5` (Images)<br>`15` (Videos) | Maximum Hamming distance difference for similarity (lower is stricter; `0` means near-identical) |
| `--csv <FILE>` | None | Export scan actions (`keep` / `move`) to a CSV file |
| `--version` | None | Display the script version |
| `-h`, `--help` | None | Show usage and argument instructions |

### Examples

**Simulate a recursive image scan without moving any files:**
```bash
python3 find_duplicates_images_1.1.py --recursive --dry-run
```

**Find exact duplicates only (skips dependency check and perceptual hashing):**
```bash
python3 find_duplicates_images_1.1.py --no-similar
```

**Stricter video similarity search and export report to CSV:**
```bash
python3 find_duplicate_videos_1.1.py --threshold 10 --csv video_audit.csv
```

---

## 📊 CSV Export Format

When using `--csv <filename>`, results are exported with the following schema:

| Column | Description |
| :--- | :--- |
| `type` | Match classification: `exact` or `similar` |
| `group` | Group index number grouping matched items together |
| `file` | Absolute path to the file |
| `action` | Action planned: `keep` (original kept in place) or `move` (moved to output folder) |

---

## 🛡️ Output Directory Structure

When duplicates or similar items are found, folders are created next to the script:

```text
MyPhotos/
├── find_duplicates_images_1.1.py
├── photo1.jpg                 <-- Kept (highest quality/resolution)
├── Duplicate/
│   └── photo1_copy.jpg        <-- Moved (byte-identical copy)
└── Similar/
    └── photo1_compressed.jpg  <-- Moved (lower resolution / visual duplicate)
```

---

## 📄 License

This repository is licensed under the [MIT License](LICENSE).