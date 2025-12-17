import argparse
import os
from bb_audio import list_audio_files, load_audio_mono, peak_normalise, save_audio

# Batch normalises all supported audio files in a folder using peak normalisation.
# -------------------------------------------------------------
# BlueByte Audio Tools - Batch Normalisation Script (v1)
# Scans a folder for audio files and normalises each one
# to 90% of full-scale (~ -1 dBFS), saving new versions.
# -------------------------------------------------------------

# --- CLI argument parsing ---
parser = argparse.ArgumentParser(
    description="Batch peak-normalise audio files in a folder.")

parser.add_argument("--folder",
                    type=str,
                    default=".",
                    help="Target folder containing audio files to normalise. Defaults to current directory.")

parser.add_argument("--target_peak",
                    type=float,
                    default=0.9,
                    help="Target peak level for normalisation (0.0 to 1.0). Defaults to 0.9.")

parser.add_argument("--output_folder",
                    type=str,
                    default="",
                    help="Optional output folder to save normalised files. Defaults to the input folder.")

parser.add_argument("--dry_run",
                    action="store_true",
                    help="Show what would be done without actually processing files.")

args = parser.parse_args()

# Folder to scan (current working directory by default)
target_folder = args.folder
target_peak = args.target_peak

# Output folder (optional). If relative, treat it as inside target_folder.
output_folder_arg = args.output_folder.strip()

if output_folder_arg:
    output_folder = (
        output_folder_arg
        if os.path.isabs(output_folder_arg)
        else os.path.join(target_folder, output_folder_arg)
    )

    # Only create folders when not in dry-run mode (dry-run should avoid filesystem writes).
    if not args.dry_run:
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            print("Error creating output folder:", e)
            exit()
else:
    output_folder = target_folder
# --- STEP 1: Find supported audio files in the target folder ---
try:
    audio_files = list_audio_files(target_folder)
except Exception as e:
    print("Error scanning folder:", e)
    exit()

print(f"Scanning folder: {os.path.abspath(target_folder)}")
print(f"Found {len(audio_files)} supported audio file(s).")
print(f"Output folder: {os.path.abspath(output_folder)}")
print(f"Dry run:       {args.dry_run}")

if not audio_files:
    print("No supported audio files found. Nothing to normalise.")
    exit()

# --- STEP 2: Process each valid audio file (load → normalise → save) ---

print()
print("=" * 40)
print(" Blue Byte Batch Normalisation (v1) ")
print("=" * 40)

for path in audio_files:

    filename = os.path.basename(path)

    # Skip files that are already normalized

    if filename.startswith("normalized_"):
        print(f"Skipping already normalized file: {filename}")
        continue

    print(f"Processing: {filename}")

    # Load → normalise → save (handled by reusable module functions)
    try:
        audio, sr = load_audio_mono(path)
        normalized, peak_before, peak_after = peak_normalise(
            audio,
            target_peak=target_peak
        )
    except Exception as e:
        print("  Error:", e)
        continue  # skip this file and move to the next

    # Build a new output filename with a safe prefix to avoid overwriting original
    output_name = "normalized_" + filename
    output_path = os.path.join(output_folder, output_name)

    if args.dry_run:
        print(f"  DRY RUN → Would save to: {os.path.abspath(output_path)}")
        continue

    try:
        save_audio(output_path, normalized, sr)
    except Exception as e:
        print("  Error:", e)
        continue

    print(
        f"  Done → Peak: {peak_before:.4f} → {peak_after:.4f} | Saved as: {output_name}")

if args.dry_run:
    print("Dry run complete. No files were written.")

# Final summary banner for the batch run
print("=" * 40)
print(" Batch normalisation complete.")
print("=" * 40)
