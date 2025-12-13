import os
from bb_audio import list_audio_files

# -------------------------------------------------------------
# BlueByte Audio Tools - Folder Scanner
# Scans a folder, finds supported audio files, and lists them.
# This is the foundation for future batch tools.
# -------------------------------------------------------------

# Folder to scan (Current folder by default)
target_folder = "."

# --- STEP 1: Find supported audio files in the target folder ---
try:
    audio_files = list_audio_files(target_folder)
except Exception as e:
    print(f"Error reading folder '{target_folder}':", e)
    exit()

print(f"Scanning folder: {os.path.abspath(target_folder)}")
print(f"Found {len(audio_files)} supported audio file(s).")

print()
print("=" * 40)
print(" Blue Byte Folder Scanner")
print("=" * 40)

if not audio_files:
    print("No supported audio files found.")
else:
    print(f"Found {len(audio_files)} supported audio file(s):")
    for idx, path in enumerate(audio_files, start=1):
        print(f"{idx: 2d}. {os.path.basename(path)}")

print("=" * 40)
