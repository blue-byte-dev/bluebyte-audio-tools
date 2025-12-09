# 🎧 BlueByte Audio Tools  
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/Status-Active-green.svg)

A growing collection of Python-based audio utilities for loading, inspecting, normalizing, scanning, and processing sound files.  
Designed for audio engineers, music producers, game developers, podcasters, and ML dataset creators.

This repository is being expanded weekly as part of a structured 12‑week development plan.

---

## 🚀 Overview

This toolkit provides lightweight, robust audio-processing scripts built using:

- **librosa**
- **numpy**
- **soundfile**
- **matplotlib**

Each tool includes strict error handling, clean terminal output, and reliable performance.

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
A clean single‑file peak-normalization tool.

### **Features**
- Validates file and extension  
- Loads audio safely  
- Computes original peak  
- Normalizes to 90% of full-scale (~ −1 dBFS)  
- Saves output using a safe prefixed filename  
- Prints a clean, formatted summary  

### **Usage**
```bash
python3 normalise_single.py
```

---

## 🔹 `folder_scanner.py`
A utility script that scans a folder and lists all supported audio files.

### **Features**
- Reads the contents of a directory  
- Filters valid audio formats (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Skips folders and unsupported files  
- Prints a clean, numbered list of matched audio files  
- Forms the backbone for future batch-processing tools  

### **Usage**
```bash
python3 folder_scanner.py
```
Scans the current directory by default.  
Modify `target_folder = "."` inside the script to scan a different folder.

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

### Scan a folder:
```bash
python3 folder_scanner.py
```

Ensure the input files exist in the folder you are scanning.

---

# 📅 Roadmap (12‑Week Development Plan)

- ✔ Audio loader (`load_audio.py`)
- ✔ Single‑file peak normalizer (`normalise_single.py`)
- ✔ Folder scanner (batch foundation) (`folder_scanner.py`)
- 🔜 Batch normalization  
- 🔜 Batch format conversion (WAV ↔ MP3 ↔ FLAC)  
- 🔜 LUFS loudness analyzer  
- 🔜 Noise‑reduction utility  
- 🔜 Spectral analysis toolkit  
- 🔜 CLI pipeline interface  
- 🔜 GUI version (Tkinter or Electron‑Python)

This repository will expand weekly as part of an active development schedule.

---

# 👤 Author  
**Blue Byte**  
Audio Programmer • DSP Developer • Electronic Music Producer  

More tools and features coming soon.