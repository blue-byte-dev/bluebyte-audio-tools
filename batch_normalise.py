import os
from bb_audio import list_audio_files, load_audio_mono, peak_normalise, save_audio

# Batch normalises all supported audio files in a folder using peak normalisation.
# -------------------------------------------------------------
# BlueByte Audio Tools - Batch Normalisation Script (v1)
# Scans a folder for audio files and normalises each one
# to 90% of full-scale (~ -1 dBFS), saving new versions.
# -------------------------------------------------------------

# Folder to scan (current working directory by default)
target_folder = "."

# --- STEP 1: Find supported audio files in the target folder ---
try:
    audio_files = list_audio_files(target_folder)
except Exception as e:
    print("Error scanning folder:", e)
    exit()

print(f"Scanning folder: {os.path.abspath(target_folder)}")
print(f"Found {len(audio_files)} supported audio file(s).")

if not audio_files:
    print("No supported audio files found. Nothing to normalise.")
    exit()

# --- STEP 2: Process each valid audio file (load → normalise → save) ---

print()
print("=" * 40)
print(" Blue Byte Batch Normalisation (v1) ")
print("=" * 40)

for path in sorted(audio_files):
    print(f"Processing: {os.path.basename(path)}")

    # Load → normalise → save (handled by reusable module functions)
    try:
        audio, sr = load_audio_mono(path)
        normalized, peak_before, peak_after = peak_normalise(
            audio, target_peak=0.9)
    except Exception as e:
        print("  Error:", e)
        continue  # skip this file and move to the next

    # Build a new output filename with a safe prefix to avoid overwriting original
    output_name = "normalized_" + os.path.basename(path)
    output_path = os.path.join(target_folder, output_name)

    try:
        save_audio(output_path, normalized, sr)
    except Exception as e:
        print("  Error:", e)
        continue

    print(
        f"  Done → Peak: {peak_before:.4f} → {peak_after:.4f} | Saved as: {output_name}")

# Final summary banner for the batch run
print("=" * 40)
print(" Batch normalisation complete.")
print("=" * 40)
