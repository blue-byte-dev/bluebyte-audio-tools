# 🎧 BlueByte Audio Tools  
High-quality Python tools for audio processing, normalization, analysis, and DSP workflows.

This repository contains lightweight, practical audio utilities built in Python using:
- **librosa**
- **soundfile**
- **numpy**
- **matplotlib**

These tools are designed for:
- Audio engineers  
- Music producers  
- Podcasters  
- Game audio designers  
- Machine learning dataset creators  

More tools will be added continuously as part of a 12-week development roadmap.

---

# 🚀 Tools Included

## 1. `load_audio.py`
A simple but essential utility that:
- Loads audio files into a NumPy array  
- Prints sample rate & duration  
- Displays a waveform using matplotlib  

**Features**
- Supports WAV/MP3 and more  
- Optional mono conversion  
- Perfect for debugging or quick inspection  

---

## 2. `normalise_single.py`  
A peak normalization tool that:
- Loads an audio file  
- Detects the maximum absolute peak  
- Normalizes audio to **90% of full scale** (≈ –1 dBFS headroom)  
- Saves the result as a clean, safe WAV file

**Features**
- Prevents clipping  
- Good for bulk processing pipelines  
- Ideal pre-processing for:
  - Podcasts  
  - Voiceovers  
  - Sample packs  
  - ML datasets  

A batch version of this tool is in development.

---

# 📁 Project Structure
```
bluebyte-audio-tools/
│
├── load_audio.py
├── normalise_single.py
├── README.md
└── .gitignore
```

The `venv/` folder and audio test files are intentionally excluded using `.gitignore`.

---

# 🛠️ Installation

Clone the repository:

```bash
git clone https://github.com/blue-byte-dev/bluebyte-audio-tools.git
cd bluebyte-audio-tools
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install numpy librosa soundfile matplotlib
```

---

# ▶️ Usage

### Run the audio loader:
```bash
python3 load_audio.py
```

### Run the normalization tool:
```bash
python3 normalise_single.py
```

Make sure a test audio file (e.g., `test.wav`) exists in the folder.

---

# 📅 Roadmap (12-Week Development Plan)

- ✔ Basic audio loading tool (`load_audio.py`)
- ✔ Single-file peak normalizer (`normalise_single.py`)
- 🔜 Batch normalization (multi-file processing)
- 🔜 Loudness/LUFS-target normalization tool
- 🔜 Batch format converter (WAV ↔ MP3 ↔ FLAC)
- 🔜 Automated podcast cleanup (noise reduction, leveling)
- 🔜 Spectral analysis & plotting utilities
- 🔜 CLI interface for full audio pipelines
- 🔜 GUI-based version (Tkinter or Electron-Python)

This repository will expand weekly with new tools.

---

# 👤 Author  
**Blue Byte**  
Audio Programmer • DSP Learner • Music Producer  

More tools and features coming soon.