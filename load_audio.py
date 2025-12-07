import librosa
import matplotlib.pyplot as plt
import os

# Path to your audio file in the same folder as this script
file_path = "test.wav"
# Allowed audio file extensions
allowed_extensions = {".wav", ".flac", ".ogg", ".aiff", ".aif"}

# --- SAFETY CHECK 1: Does file exist? ---
if not os.path.exists(file_path):
    print(f"Error: File '{file_path}' does not exist in this folder!")
    exit()

# --- SAFETY CHECK 2: Is file type supported? ---
_, ext = os.path.splitext(file_path)
ext = ext.lower()
if ext not in allowed_extensions:
    print(f"Error: File: '{file_path}' has unsupported type '{ext}'.")
    print("Supported file types are:", ", ".join(sorted(allowed_extensions)))
    exit()

# --- SAFETY CHECK 3: Attempt to load audio safely ---
try:
    audio, sr = librosa.load(file_path, sr=None, mono=True)
except Exception as e:
    print("Error loading audio file:", e)
    exit()

# Compute duration
duration_seconds = len(audio) / sr

# Print clean info to the terminal
print("=" * 40)
print(" Blue Byte Audio File Info ")
print("=" * 40)
print(f"File: {file_path}")
print(f"Sample Rate: {sr} Hz")
print(f"Duration: {duration_seconds:.2f} seconds")
print(f"Samples: {len(audio)}")
print("=" * 40)

# Plot the waveform
plt.figure(figsize=(12, 4))
plt.plot(audio)
plt.title("Waveform of test.wav")
plt.xlabel("Samples")
plt.ylabel("Amplitude")
plt.tight_layout()
plt.show()
