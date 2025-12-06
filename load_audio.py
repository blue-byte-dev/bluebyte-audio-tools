import librosa
import matplotlib.pyplot as plt

# Path to your audio file in the same folder as this script
file_path = "test.wav"

# Load audio (mono=True to keep it lighter, sr=None to keep original sample rate)
audio, sr = librosa.load(file_path, sr=None, mono=True)

# Compute duration
duration_seconds = len(audio) / sr

# Print clean info to the terminal
print("Sample rate:", sr, "Hz")
print("Duration:", round(duration_seconds, 2), "seconds")

# Plot the waveform
plt.figure(figsize=(12, 4))
plt.plot(audio)
plt.title("Waveform of test.wav")
plt.xlabel("Samples")
plt.ylabel("Amplitude")
plt.tight_layout()
plt.show()
