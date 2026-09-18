# Atlas to GIF Converter

A modern, lightweight desktop GUI application built with **CustomTkinter** and **Pillow** designed to slice 2D texture atlases (Starling / Sparrow XML format) and export them into smooth, transparent animated **GIFs**.

Tailor-made for 2D game animators and modders working with spritesheets (including Friday Night Funkin' assets and compatible game frameworks).

---

## Key Features

- **Atlas & Spritesheet Parsing:** Reads Starling/Sparrow XML formats and automatically detects the corresponding PNG file in the same directory.
- **FNF JSON Offsets Support:** Automatically looks up and parses companion `.json` configuration files to retrieve character animation offset data.
- **Interactive Live Preview:** Real-time playback loop for individual animations or full sequences with dynamic canvas resizing (can be toggled on/off).
- **Manual Offset Adjustments:** Fine-tune X/Y frame alignment on the fly via keyboard controls without touching XML files.
- **Sequence Queueing:** Combine multiple animation states (e.g., *idle*, *singUP*, *singRIGHT*) into a custom playback order and export them as a single continuous GIF.
- **Global Bounding Box Calculation:** Prevents sprite clipping and awkward frame jitter by automatically computing a unified canvas size across all frames.
- **Clean GIF Encoding:** Retains crisp alpha transparency with configurable FPS (1–60) and scaling (0.25x–5.0x).

---

## Installation & Setup

### Prerequisites

- **Python 3.8+**

### Install Dependencies

Install the required packages using `pip`:

```bash
pip install customtkinter pillow
```

---

## Quick Start

1. Click **Browse...** next to **Atlas XML** and select your descriptor file (the matching `.png` and `.json` files are auto-detected if located in the same folder).
2. Select any animation in the **Available Animations** list on the left.
3. Click **Add ➔** (or double-click) to move animations into the **Export Queue**.
4. Arrange the playback sequence using the **Up ▲** and **Down ▼** buttons.
5. *(Optional)* Adjust offsets with the arrow keys and preview the loop using **Play Queue**.
6. Set your desired **FPS** and **Scale** sliders.
7. Click **Export GIF** to choose the destination file.

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Delete` | Remove the selected animation from the export queue |
| `←` / `→` / `↑` / `↓` | Nudge active animation offset by **1 px** |
| `Shift` + `←` / `→` / `↑` / `↓` | Nudge active animation offset by **10 px** |

---
