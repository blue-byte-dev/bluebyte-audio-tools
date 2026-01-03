# 🎧 BlueByte Audio Tools
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/Status-Active-green.svg)

A growing collection of Python‑based audio utilities for loading, analyzing, normalizing, scanning, and batch‑processing sound files.  
Designed for audio engineers, music producers, sound designers, game developers, and machine‑learning dataset creators.

This repository evolves weekly as part of a structured 12‑week development plan.

---

## 🚀 Overview

BlueByte Audio Tools provides lightweight, robust, and reliable audio-processing scripts powered by:

- **librosa**  
- **numpy**  
- **soundfile**  
- **matplotlib**

Every script includes input validation, error handling, clean terminal output, and safe‑file operations.

As of the current development stage, all tools share a common backend engine (`bb_audio.py`) that centralizes audio loading, validation, normalization logic, file handling, and safety checks. This ensures consistency, easier maintenance, and future readiness for CLI and GUI interfaces.

## ✅ Code Quality & Testing

All core backend logic is fully unit-tested using **pytest**.

- Deterministic functions are covered with pure unit tests
- File-system behavior is tested using temporary directories
- Audio I/O is tested via mocking (no real decoding required)
- Safety logic (dry-run, overwrite protection, skip rules) is explicitly verified
- FFmpeg stderr parsing is validated via unit tests (including multiline true-peak blocks)

An end-to-end **integration sanity check** has also been performed using real audio files to confirm correct behavior of the full processing pipeline.

This ensures the project is safe to refactor, extend, and maintain over time.

---

# 📂 Tools Included

---

## 🔹 `bb_audio.py` (Core Backend Engine)
A reusable internal module that powers all BlueByte Audio Tools.

### **Responsibilities**
- Defines supported audio formats in one place  
- Scans folders and returns valid audio file paths  
- Loads audio safely while preserving sample rate  
- Performs peak normalization with safety checks  
- Handles audio file writing with robust error reporting  
- Centralizes write-decision logic (skip / overwrite / dry-run) via `should_write_file()`
- Provides reusable peak utilities (`peak_value()` and `peak_normalise()`) used across tools
- Provides a single safe-save path via `save_audio()` (consistent error handling and messages)
- Keeps file discovery consistent across tools via `list_audio_files()` (same extension rules everywhere)
- Reduces duplication across CLI tools (batch normalise, LUFS analysis, future tools)

### **Public API (Functions)**
The backend exposes a small, stable function surface:

- `list_audio_files(folder)` → returns supported audio file paths
- `load_audio_mono(path)` → loads audio as mono while preserving sample rate
- `peak_value(audio)` → returns sample peak (linear)
- `peak_normalise(audio, target_peak)` → returns normalised audio + safety checks
- `save_audio(path, audio, sr)` → writes audio to disk safely
- `should_write_file(path, overwrite, dry_run)` → returns `(ok_to_write, reason)` where reason is one of: `new`, `overwrite`, `skip`, `dry_run`

This module is not intended to be run directly.  
It exists to keep tool behavior consistent (same file rules, same safety rules, same error handling).
All user-facing scripts import and rely on this shared engine.

---

## 🔹 `load_audio.py`
A waveform viewer and audio inspection tool.

### **Features**
- Validates file existence  
- Checks extension (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Loads audio with error handling  
- Displays:
  - File name  
  - Sample rate  
  - Duration  
  - Number of samples  
- Renders waveform via matplotlib  

### **Usage**
```bash
python3 load_audio.py
```

---

## 🔹 `normalise_single.py`
A safe single‑file peak‑normalization utility.

### **Features**
- Validates file and extension  
- Loads audio safely  
- Computes original peak amplitude  
- Normalizes to 90% of full‑scale (~ −1 dBFS headroom)  
- Outputs a cleanly prefixed file  
- Prints a detailed processing summary  

### **Usage**
```bash
python3 normalise_single.py
```

---

## 🔹 `folder_scanner.py`
A file‑system helper that identifies all supported audio files in a folder.

### **Features**
- Reads directory contents  
- Filters valid audio formats (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Skips folders and unsupported entries  
- Prints a neatly ordered, numbered file list  
- Provides the foundation for all batch operations  

### **Usage**
```bash
python3 folder_scanner.py
```
Scans the current directory by default.  
Modify `target_folder = "."` inside the script to scan other locations.

---

## 🔹 `batch_normalise.py`
A batch peak‑normalisation processor for multiple audio files.

### **Features**
- Scans a directory for valid audio files  
- Loads each file safely with error handling  
- Skips silent files  
- Normalizes all files to 90% of full‑scale (~ −1 dBFS)  
- Saves new files using a safe `normalized_` prefix  
- Outputs per‑file results and a final batch report  
- Configurable target peak via CLI (`--target_peak`)
- Optional output folder to keep original files untouched (`--output_folder`)
- Automatically skips already-normalized files
- Safe repeated runs without recursive normalization
- Dry-run mode to preview processing without writing any files (`--dry_run`)
- Supports optional WAV and FLAC output format conversion via CLI (`--format`)
- Explicit dry-run messaging that explains skips, overwrites, and writes
- End-of-run batch summary with processed, skipped, and written counts
- Fully covered by unit tests with verified real-world integration behavior

### **Usage**
```bash
# Normalize all supported audio files in the current directory
python3 batch_normalise.py

# Set a custom target peak
python3 batch_normalise.py --target_peak 0.8

# Normalize files from a specific folder
python3 batch_normalise.py --folder ./audio

# Save normalized files to a separate output folder
python3 batch_normalise.py --output_folder normalized_out

# Preview what would be processed without saving files
python3 batch_normalise.py --dry_run

# Convert normalized output to FLAC
python3 batch_normalise.py --format flac

# Preview batch behavior without writing files
python3 batch_normalise.py --dry_run --output_folder normalized_out
```

### **Behavior Notes**
- Files starting with `normalized_` are skipped automatically to prevent recursive processing.
- Output files are prefixed with `normalized_` to avoid overwriting originals.
- Dry-run mode performs all checks and calculations but never creates folders or writes files.
- Dry-run mode reports what *would* happen, including skips and overwrites, without writing files.
- Batch summary statistics are printed at the end of every run.

---

## 🔹 `lufs_analyse.py`
A professional loudness analysis utility supporting both Python-based and FFmpeg-based measurement engines.

### **Features**
- Integrated LUFS measurement (ITU-R BS.1770 compliant)
- Optional engine selection:
  - Python engine (`pyloudnorm`) for fast, dependency-light analysis
  - FFmpeg engine for industry-standard reference measurements
- Optional comparison mode (`--compare`) to validate Python results against FFmpeg
- Reports:
  - Integrated LUFS
  - Momentary max loudness
  - Short-term max loudness
  - Loudness Range (LRA)
  - Sample peak (dBFS)
  - True Peak (dBTP, FFmpeg engine)
- Graceful handling of silence and very short audio
- Fully unit-tested FFmpeg parsing logic
- Target LUFS compliance reporting (`--target_lufs`, `--tolerance`)
- Optional gain application to create a loudness-targeted file (`--apply`)
- Safety default: **no file is written** when already within tolerance; use `--force_apply` to write anyway
- Dry-run support for apply mode (`--dry_run`) to preview the write without creating output
- Custom output path for apply mode (`--output`)
- Target reference selection in compare mode (uses **FFmpeg integrated** as the reference)

### **Usage**
```bash
# Analyze a file using the Python engine
python3 lufs_analyse.py audio.wav

# Use FFmpeg as the loudness engine
python3 lufs_analyse.py audio.wav --engine ffmpeg

# Compare Python and FFmpeg results
python3 lufs_analyse.py audio.wav --compare

# Check a file against a target loudness (compliance report)
python3 lufs_analyse.py audio.wav --target_lufs -14

# Apply the suggested gain and write a new file (skips writing if already compliant)
python3 lufs_analyse.py audio.wav --target_lufs -14 --apply

# Force writing even if the file is already within tolerance
python3 lufs_analyse.py audio.wav --target_lufs -14 --apply --force_apply

# Preview the apply step without writing anything
python3 lufs_analyse.py audio.wav --target_lufs -14 --apply --dry_run

# Write to a custom output path
python3 lufs_analyse.py audio.wav --target_lufs -14 --apply --output out/audio_-14.wav
```

---

# 🛠 Installation

Clone the repository:

```bash
git clone https://github.com/blue-byte-dev/bluebyte-audio-tools.git
cd bluebyte-audio-tools
```

Create a virtual environment (macOS/Linux):

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install numpy librosa matplotlib soundfile pyloudnorm
pip install -U pip
```

---

# ▶️ Running the Tools

### Load and visualize audio:
```bash
python3 load_audio.py
```

### Normalize a single file:
```bash
python3 normalise_single.py
```

### Scan a folder:
```bash
python3 folder_scanner.py
```

### Batch-normalize all files:
```bash
python3 batch_normalise.py
```

Ensure the input files exist in the directory you are scanning or processing.

### Analyze loudness (LUFS):
```bash
python3 lufs_analyse.py your_audio.wav
```

### Target LUFS compliance + optional apply:
```bash
# Compliance report against -14 LUFS
python3 lufs_analyse.py your_audio.wav --target_lufs -14

# Apply gain and write a targeted version (writes only if not compliant unless forced)
python3 lufs_analyse.py your_audio.wav --target_lufs -14 --apply
python3 lufs_analyse.py your_audio.wav --target_lufs -14 --apply --force_apply
```

---

# 📅 Roadmap (12‑Week Development Plan)

- ✔ Audio loader (`load_audio.py`)  
- ✔ Single‑file peak normalizer (`normalise_single.py`)  
- ✔ Folder scanner (batch foundation) (`folder_scanner.py`)  
- ✔ Batch normaliser v1 (`batch_normalise.py`)  
- ✔ Shared backend engine refactor (`bb_audio.py`)
- ✔ Batch format conversion (WAV ↔ FLAC)
- ✔ Full unit test coverage for backend engine (`bb_audio.py`)
- ✔ LUFS loudness analyzer with FFmpeg validation (`lufs_analyse.py`)
- ✔ Target LUFS compliance + apply mode (`--target_lufs`, `--apply`, `--force_apply`)
- 🔜 Noise‑reduction utility  
- 🔜 Spectral analysis toolkit  
- 🔜 Modular CLI pipeline interface  
- 🔜 GUI desktop version (Tkinter or Electron‑Python)
- ✔ Dry‑run mode (`--dry_run`)
- ✔ Overwrite protection flag (`--overwrite`)
- 🔜 Additional loudness‑based normalization (LUFS)
- 🔜 Cross‑platform GUI frontend

This repository expands every week with new tools and improvements.

---

# 👤 Author  
**Blue Byte**  
Audio Programmer • DSP Developer • Electronic Music Producer  

More tools, DSP utilities, and batch‑processing modules coming soon.