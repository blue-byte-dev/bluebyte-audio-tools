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