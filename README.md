# 🎧 BlueByte Audio Tools  
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/Status-Active-green.svg)

A growing collection of Python-based audio utilities for loading, inspecting, normalizing, and processing sound files.  
Designed for audio engineers, music producers, game developers, podcasters, and ML dataset creators.

---

## 🚀 Overview
This repository contains lightweight, robust DSP tools built using:

- **librosa**
- **numpy**
- **soundfile**
- **matplotlib**

Each script includes strict error handling, clean output formatting, and practical utility for real-world workflows.  
New tools are added weekly as part of a 12‑week development plan.

---

# 📂 Tools Included

---

## 🔹 `load_audio.py`
A robust audio inspection and waveform viewer.

### **Features**
- Verifies file existence  
- Validates extension (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Handles loading errors gracefully  
- Prints:
  - File name  
  - Sample rate  
  - Duration  
  - Number of samples  
- Displays waveform using matplotlib  

### **Usage**
```bash
python3 load_audio.py
```

---

## 🔹 `normalise_single.py`
A clean single‑file peak normalization utility.

### **Features**
- Validates file and extension  
- Handles load errors safely  
- Computes original peak  
- Normalizes audio to 90% of full-scale (~ −1 dBFS headroom)  
- Saves normalized file with a safe prefix  
- Prints a clean, formatted summary  

### **Usage**
```bash
python3 normalise_single.py
```

---

# 🛠 Installation

Clone the repository:

```bash
git clone https://github.com/blue-byte-dev/bluebyte-audio-tools.git
cd bluebyte-audio-tools
```

Create a virtual environment (macOS/Linux):

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install numpy librosa matplotlib soundfile
```

---

# ▶️ Running the Tools

### Load and visualize audio:
```bash
python3 load_audio.py
```

### Normalize a file:
```bash
python3 normalise_single.py
```

Ensure the input file (`test.wav` or another file of your choosing) exists in the folder.

---

# 📅 Roadmap (12‑Week Development Plan)

- ✔ Audio loader (`load_audio.py`)
- ✔ Single‑file peak normalizer (`normalise_single.py`)
- 🔜 Batch normalization  
- 🔜 Batch format conversion (WAV ↔ MP3 ↔ FLAC)  
- 🔜 LUFS loudness tools  
- 🔜 Noise‑reduction utility  
- 🔜 Spectral analysis toolkit  
- 🔜 CLI pipeline interface  
- 🔜 GUI version (Tkinter or Electron‑Python)

This repository will expand weekly as part of an active development schedule.

---

# 👤 Author  
**Blue Byte**  
Audio Programmer • DSP Student • Electronic Music Producer  

More tools and features coming soon.