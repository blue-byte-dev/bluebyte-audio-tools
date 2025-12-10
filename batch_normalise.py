import os
import librosa
import soundfile as sf
import numpy as np

# Batch normalises all supported audio files in a folder using peak normalisation.
# -------------------------------------------------------------
# BlueByte Audio Tools - Batch Normalisation Script (v1)
# Scans a folder for audio files and normalises each one
# to 90% of full-scale (~ -1 dBFS), saving new versions.
# -------------------------------------------------------------

# Folder to scan (current working directory by default)
target_folder = "."

# Supported audio file extensions (peak-normalised in this batch run)
allowed_extensions = {".wav", ".flac", ".ogg", ".aiff", ".aif"}

# --- STEP 1: List all entries in the target folder ---
# Try to read all entries (files and subfolders) from the target folder
try:
    entries = os.listdir(target_folder)
except Exception as e:
    print(f"Error reading folder '{target_folder}':", e)
    exit()

print(f"Scanning folder: {os.path.abspath(target_folder)}")
print(f"Found {len(entries)} entries (files and folders total).")

# --- STEP 2: Filter only supported audio files ---
audio_files = []

for name in entries:
    full_path = os.path.join(target_folder, name)

    # Skip this entry if it is a directory (we only process files)
    if not os.path.isfile(full_path):
        continue

    # Extract file extension from the name and convert to lowercase
    _, ext = os.path.splitext(name)
    ext = ext.lower()

    # Skip this file if its extension is not in the supported list
    if ext not in allowed_extensions:
        continue

    audio_files.append(full_path)

if not audio_files:
    print("No supported audio files found. Nothing to normalise.")
    exit()

# --- STEP 3: Process each valid audio file (load → normalise → save) ---

print()
print("=" * 40)
print(" Blue Byte Batch Normalisation (v1) ")
print("=" * 40)

for path in sorted(audio_files):
    print(f"Processing: {os.path.basename(path)}")

    # Try to load audio safely
    try:
        audio, sr = librosa.load(path, sr=None, mono=True)
    except Exception as e:
        print("  Error loading file", e)
        continue     # skip this file and move to the next

    # Peak detection: find the maximum absolute sample value
    peak_before = np.max(np.abs(audio))

    # Skip silent files
    if peak_before == 0:
        print("  Skipped file is silent (peak = 0).")
        continue

    # Apply peak normalisation to 90% of full-scale (~ -1 dBFS headroom)
    normalized = audio / peak_before * 0.9

    # Compute new peak
    peak_after = np.max(np.abs(normalized))

    # Build a new output filename with a safe prefix to avoid overwriting original
    output_name = "normalized_" + os.path.basename(path)
    output_path = os.path.join(target_folder, output_name)

    # Save file
    try:
        sf.write(output_path, normalized, sr)
    except Exception as e:
        print("  Error saving file:", e)
        continue

    # Print per-file summary line
    print(
        f"  Done → Peak: {peak_before:.4f} → {peak_after:.4f} | Saved as: {output_name}")

# Final summary banner for the batch run
print("=" * 40)
print(" Batch normalisation complete.")
print("=" * 40)
