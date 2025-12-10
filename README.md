# 🎧 BlueByte Audio Tools  
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/Status-Active-green.svg)

A growing collection of Python‑based audio utilities for loading, analyzing, normalizing, scanning, and batch‑processing sound files.  
Designed for audio engineers, music producers, sound designers, game developers, and machine‑learning dataset creators.

This repository evolves weekly as part of a structured 12‑week development plan.

---

## 🚀 Overview

BlueByte Audio Tools provides lightweight, robust, and reliable audio-processing scripts powered by:

- **librosa**  
- **numpy**  
- **soundfile**  
- **matplotlib**

Every script includes input validation, error handling, clean terminal output, and safe‑file operations.

---

# 📂 Tools Included

---

## 🔹 `load_audio.py`
A waveform viewer and audio inspection tool.

### **Features**
- Validates file existence  
- Checks extension (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Loads audio with error handling  
- Displays:
  - File name  
  - Sample rate  
  - Duration  
  - Number of samples  
- Renders waveform via matplotlib  

### **Usage**
```bash
python3 load_audio.py
```

---

## 🔹 `normalise_single.py`
A safe single‑file peak‑normalization utility.

### **Features**
- Validates file and extension  
- Loads audio safely  
- Computes original peak amplitude  
- Normalizes to 90% of full‑scale (~ −1 dBFS headroom)  
- Outputs a cleanly prefixed file  
- Prints a detailed processing summary  

### **Usage**
```bash
python3 normalise_single.py
```

---

## 🔹 `folder_scanner.py`
A file‑system helper that identifies all supported audio files in a folder.

### **Features**
- Reads directory contents  
- Filters valid audio formats (`.wav`, `.flac`, `.ogg`, `.aiff`, `.aif`)  
- Skips folders and unsupported entries  
- Prints a neatly ordered, numbered file list  
- Provides the foundation for all batch operations  

### **Usage**
```bash
python3 folder_scanner.py
```
Scans the current directory by default.  
Modify `target_folder = "."` inside the script to scan other locations.

---

## 🔹 `batch_normalise.py`
A batch peak‑normalisation processor for multiple audio files.

### **Features**
- Scans a directory for valid audio files  
- Loads each file safely with error handling  
- Skips silent files  
- Normalizes all files to 90% of full‑scale (~ −1 dBFS)  
- Saves new files using a safe `normalized_` prefix  
- Outputs per‑file results and a final batch report  

### **Usage**
```bash
python3 batch_normalise.py
```
Processes all supported audio files in the current directory.

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

### Normalize a single file:
```bash
python3 normalise_single.py
```

### Scan a folder:
```bash
python3 folder_scanner.py
```

### Batch-normalize all files:
```bash
python3 batch_normalise.py
```

Ensure the input files exist in the directory you are scanning or processing.

---

# 📅 Roadmap (12‑Week Development Plan)

- ✔ Audio loader (`load_audio.py`)  
- ✔ Single‑file peak normalizer (`normalise_single.py`)  
- ✔ Folder scanner (batch foundation) (`folder_scanner.py`)  
- ✔ Batch normaliser v1 (`batch_normalise.py`)  
- 🔜 Batch format conversion (WAV ↔ MP3 ↔ FLAC)  
- 🔜 LUFS loudness analyzer  
- 🔜 Noise‑reduction utility  
- 🔜 Spectral analysis toolkit  
- 🔜 Modular CLI pipeline interface  
- 🔜 GUI desktop version (Tkinter or Electron‑Python)

This repository expands every week with new tools and improvements.

---

# 👤 Author  
**Blue Byte**  
Audio Programmer • DSP Developer • Electronic Music Producer  

More tools, DSP utilities, and batch‑processing modules coming soon.