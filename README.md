# Panel Editor

Manhwa/manhwa panel editor GUI for merging, detecting, cropping, and exporting manga panels.

## Features
- 📁 **Merge Folder** — stitch all images from a folder into one tall strip, auto-detect panels
- 📂 **Open Folder** — load images from a folder
- **Auto Detect** — computer vision panel detection
- **Delete/A-B creation/Resize/Snap** — full panel editing
- **Export PNGs** — save panels as separate images
- **AI Refine** — Gemini-powered merge/split suggestions

## Requirements
```
pip install opencv-python numpy pillow google-genai
```

## Usage
```
python panel_editor.py
```
