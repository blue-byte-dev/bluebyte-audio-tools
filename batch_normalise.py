import argparse
import os
from bb_audio import list_audio_files, load_audio_mono, peak_normalise, save_audio, should_write_file

# Batch normalises all supported audio files in a folder using peak normalisation.
# -------------------------------------------------------------
# BlueByte Audio Tools - Batch Normalisation Script (v1)
# Scans a folder for audio files and normalises each one
# to a target peak (default 0.9), saving new versions.
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
                    help="Show what would be done without writing output files.")

parser.add_argument("--overwrite",
                    action="store_true",
                    help="Overwrite output files if they already exist.")

parser.add_argument("--format", type=str,
                    default="",
                    help="Optional output audio format (wav, flac). Defaults to input format.")

args = parser.parse_args()

# Folder to scan (current working directory by default)
target_folder = args.folder
target_peak = args.target_peak

# Optional output format (defaults to input format)
output_format = args.format.strip().lower()
allowed_formats = {"wav", "flac"}
if output_format and output_format not in allowed_formats:
    print(f"Error: Unsupported output format '{output_format}'.")
    print("Supported formats are:", ", ".join(sorted(allowed_formats)))
    exit()

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
print(f"Output format: {output_format or 'input'}")

if not audio_files:
    print("No supported audio files found. Nothing to normalise.")
    exit()

# --- STEP 2: Process each valid audio file (load → normalise → save) ---
print()
print("=" * 40)
print(" Blue Byte Batch Normalisation (v1) ")
print("=" * 40)

processed = 0
skipped = 0
written = 0
planned = 0


def process_file(
    path: str,
    output_folder: str,
    target_peak: float,
    dry_run: bool,
    overwrite: bool,
    output_format: str,
) -> str:
    filename = os.path.basename(path)

    # Skip files that are already normalized
    if filename.startswith("normalized_"):
        print(f"Skipping already normalized file: {filename}")
        return "skipped"

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
        return "skipped"  # skip this file and move to the next

    # Build a new output filename with a safe prefix to avoid overwriting original.
    # If output_format is provided, replace the extension (e.g., .wav -> .flac).
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    new_ext = f".{output_format}" if output_format else ext
    output_name = f"normalized_{base}{new_ext}"
    output_path = os.path.join(output_folder, output_name)
    should_write, reason = should_write_file(
        output_path, overwrite=overwrite, dry_run=dry_run
    )

    # Decision output is centralized in bb_audio.should_write_file.
    # Map (should_write, reason) to user-facing messaging and status.
    if not should_write:
        if reason == "dry_run_skip":
            print(
                f"  DRY RUN → Would skip (output exists): {os.path.abspath(output_path)}")
            return "dry_run_skip"
        # reason == "exists"
        print(f"Skipping existing output file: {output_name}")
        return "skipped"

    # should_write is True
    if dry_run:
        if reason == "overwrite":
            print(
                f"  DRY RUN → Would overwrite: {os.path.abspath(output_path)}")
        else:
            # reason == "new"
            print(f"  DRY RUN → Would save to: {os.path.abspath(output_path)}")
        return "dry_run_plan"

    try:
        save_audio(output_path, normalized, sr)
    except Exception as e:
        print("  Error:", e)
        return "skipped"

    print(
        f"  Done → Peak: {peak_before:.4f} → {peak_after:.4f} | Saved as: {output_name}")
    return "written"


for path in audio_files:
    result = process_file(
        path=path,
        output_folder=output_folder,
        target_peak=target_peak,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        output_format=output_format,
    )

    if result == "written":
        processed += 1
        written += 1
    elif result == "skipped":
        processed += 1
        skipped += 1
    elif result == "dry_run_plan":
        processed += 1
        planned += 1
    elif result == "dry_run_skip":
        processed += 1
        skipped += 1

if args.dry_run:
    print("Dry run complete. No files were written.")

print("=" * 40)
print(" Batch summary")
print("=" * 40)
print(f"Files found:     {len(audio_files)}")
print(f"Processed:      {processed}")
print(f"Skipped:        {skipped}")
print(f"Planned:        {planned}")
print(f"Written:        {written}")
print(f"Dry run:        {args.dry_run}")

# Final summary banner for the batch run
print("=" * 40)
print(" Batch normalisation complete.")
print("=" * 40)
