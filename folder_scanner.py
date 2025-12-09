import os

# -------------------------------------------------------------
# BlueByte Audio Tools - Folder Scanner
# Scans a folder, finds supported audio files, and lists them.
# This is the foundation for future batch tools.
# -------------------------------------------------------------

# Folder to scan (Current folder by default)
target_folder = "."

# Supported audio file extensions
allowed_extensions = {".wav", ".flac", ".ogg", ".aiff", ".aif"}

# --- STEP 1: List all entries in the target folder ---
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

    # Skip if it's a folder, not a file
    if not os.path.isfile(full_path):
        continue

    # Extract and normalize extension
    _, ext = os.path.splitext(name)
    ext = ext.lower()

    # Skip unsupported extensions
    if ext not in allowed_extensions:
        continue

    audio_files.append(full_path)

print()
print("=" * 40)
print(" Blue Byte Folder Scanner")
print("=" * 40)

if not audio_files:
    print("No supported audio files found.")
else:
    print(f"Found {len(audio_files)} supported audio file(s):")
    for idx, path in enumerate(sorted(audio_files), start=1):
        print(f"{idx: 2d}. {os.path.basename(path)}")

print("=" * 40)
