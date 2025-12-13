# -------------------------------------------------------------
# BlueByte Audio Tools - Single File Normalization Script
# Normalizes an audio file to 90% of full-scale (≈ -1 dBFS)
# Includes: safety checks, extension validation, error handling
# -------------------------------------------------------------

import os
from bb_audio import ALLOWED_EXTENSIONS, load_audio_mono, peak_normalise, save_audio

file_path = "test.wav"           # Input file

# --- SAFETY CHECK 1: Does file exist? ---
if not os.path.exists(file_path):
    print(f"Error: File '{file_path}' does not exist in this folder!")
    exit()

# Extract file extension and convert to lowercase
_, ext = os.path.splitext(file_path)
ext = ext.lower()

# --- SAFETY CHECK 2: Is file type supported? ---
if ext not in ALLOWED_EXTENSIONS:
    print(f"Error: File '{file_path}' has unsupported type '{ext}'.")
    print("Supported file types are:", ", ".join(sorted(ALLOWED_EXTENSIONS)))
    exit()

# --- SAFETY CHECK 3: Attempt to load audio safely ---
try:
    audio, sr = load_audio_mono(file_path)
except Exception as e:
    print("Error loading audio file:", e)
    exit()

# Peak-normalise to 90% of full-scale (≈ -1 dBFS headroom)
try:
    normalized, peak_before, peak_after = peak_normalise(
        audio, target_peak=0.9)
except Exception as e:
    print("Error:", e)
    exit()

# Output path
output_path = "normalized_" + os.path.basename(file_path)

# Save result
save_audio(output_path, normalized, sr)

print("=" * 40)
print(" Blue Byte Normalization Tool ")
print("=" * 40)
print(f"Input File:       {file_path}")
print(f"Sample Rate:      {sr} Hz")
print(f"Original Peak:    {peak_before:.4f}")
print(f"New Peak:         {peak_after:.4f}")
print(f"Output File:      {output_path}")
print("=" * 40)
