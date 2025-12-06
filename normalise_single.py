import librosa
import soundfile as sf
import numpy as np

file_path = "test.wav"           # Input file
output_path = "normalized.wav"   # Output file

# Load audio
audio, sr = librosa.load(file_path, sr=None, mono=True)

# Find peak amplitude
peak = np.max(np.abs(audio))

# Normalize to 90% peak (safe headroom)
normalized = audio / peak * 0.9

# Save result
sf.write(output_path, normalized, sr)

print("Normalization complete!")
print("Saved as:", output_path)
