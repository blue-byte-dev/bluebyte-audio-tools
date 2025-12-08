# -------------------------------------------------------------
# BlueByte Audio Tools - Single File Normalization Script
# Normalizes an audio file to 90% of full-scale (≈ -1 dBFS)
# Includes: safety checks, extension validation, error handling
# -------------------------------------------------------------

import librosa
import soundfile as sf
import numpy as np
import os

file_path = "test.wav"           # Input file
allowed_extensions = {".wav", ".flac", ".ogg",
                      ".aiff", ".aif"}  # Allowed audio file extensions

# --- SAFETY CHECK 1: Does file exist? ---
if not os.path.exists(file_path):
    print(f"Error: File '{file_path}' does not exist in this folder!")
    exit()

# Extract file extension and convert to lowercase
_, ext = os.path.splitext(file_path)
ext = ext.lower()

# --- SAFETY CHECK 2: Is file type supported? ---
if ext not in allowed_extensions:
    print(f"Error: File '{file_path}' has unsupported type '{ext}'.")
    print("Supported file types are:", ", ".join(sorted(allowed_extensions)))
    exit()

# --- SAFETY CHECK 3: Attempt to load audio safely ---
try:
    audio, sr = librosa.load(file_path, sr=None, mono=True)
except Exception as e:
    print("Error loading audio file:", e)
    exit()

# Compute original peak
peak_before = np.max(np.abs(audio))

# Avoid division by zero
if peak_before == 0:
    print("Error: Audio file is silent. Cannot normalize")
    exit()

# Normalize audio to 90% of full-scale (≈ -1 dBFS headroom)
normalized = audio / peak_before * 0.9

# Compute new peak
peak_after = np.max(np.abs(normalized))

# Output path
output_path = "normalized_" + os.path.basename(file_path)

# Save result
sf.write(output_path, normalized, sr)

print("=" * 40)
print(" Blue Byte Normalization Tool ")
print("=" * 40)
print(f"Input File:       {file_path}")
print(f"Sample Rate:      {sr} Hz")
print(f"Original Peak:    {peak_before:.4f}")
print(f"New Peak:         {peak_after:.4f}")
print(f"Output File:      {output_path}")
print("=" * 40)
