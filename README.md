# Atlas to GIF Converter

A modern, lightweight desktop GUI application built with **CustomTkinter** and **Pillow** designed to slice 2D texture atlases (Starling / Sparrow XML format) and export them into smooth, transparent animated **GIFs** or **PNG Sequences**.

Tailor-made for 2D game animators and modders working with spritesheets (including Friday Night Funkin' assets and compatible game frameworks).

---

## Key Features

- **Atlas & Spritesheet Parsing:** Reads Starling/Sparrow XML formats and automatically detects the corresponding PNG file in the same directory.
- **FNF JSON Offsets Support:** Automatically looks up and parses companion `.json` configuration files to retrieve character animation offset data.
- **Interactive Live Preview & Camera Controls:** Real-time playback loop with mouse-wheel zoom (15% to 600%), right-click/middle-click canvas panning, and instant double-click camera reset.
- **Flexible Export Formats & Modes:**
  - **Formats:** Export as transparent animated **GIFs** or numbered **PNG Sequences** (`frame_0000.png`) ready for Adobe Animate, Blender, or video editors.
  - **Export Modes:** Merge queued animations into a single file, export each queued animation to a separate file, or batch-export all animations directly from the XML atlas.
  - **Looping Control:** Optional infinite loop setting for GIF exports.
- **Manual Offset Adjustments:** Fine-tune X/Y frame alignment on the fly via keyboard controls or UI without modifying XML files.
- **Sequence Queueing:** Combine multiple animation states (e.g., *idle*, *singUP*, *singRIGHT*) into a custom playback order and preview or export them seamlessly.
- **Global Bounding Box Calculation:** Prevents sprite clipping and awkward frame jitter by automatically computing a unified canvas size across all frames.
- **High-Performance Caching:** Two-tier frame caching system ensures smooth previewing during zoom/pan operations and lag-free live offset tweaks.

---

## Run Python source

### Prerequisites

- **Python 3.8+**

### Install Dependencies

Install the required packages using `pip`:

```bash
pip install customtkinter pillow
```
or
```bash
py -m pip install customtkinter pillow
```

---

## Quick Start

1. Click **Browse...** next to **Atlas XML** and select your descriptor file (the matching `.png` and `.json` files are auto-detected if located in the same folder).
2. Select any animation in the **Available Animations** list on the left.
3. Click **Add ➔** (or double-click) to move animations into the **Export Queue**.
4. Arrange the playback sequence using the **Up ▲** and **Down ▼** buttons.
5. *(Optional)* Adjust offsets with the arrow keys and preview the loop using **Play Queue**. Use the mouse wheel to zoom and drag with the right mouse button to pan the preview viewport.
6. Set your desired **FPS** and **Scale** sliders.
7. Click **Export...** to open the **Export Settings** dialog window.
8. Choose your preferred **Mode** (Merge Queue, Batch Queue, or Batch All XML), **Format** (GIF or PNG Sequence), and **Loop** option, then click **Export ➔**.

---

## Keyboard & Mouse Controls

| Control / Shortcut | Action |
| :--- | :--- |
| `Scroll Wheel` | Zoom preview canvas in / out (15% to 600%) |
| `Right-Click` or `Middle-Click` + Drag | Pan preview viewport |
| `Double-Click` | Reset camera view position and zoom scale |
| `Delete` | Remove selected animation from export queue |
| `←` / `→` / `↑` / `↓` | Nudge active animation offset by **1 px** |
| `Shift` + `←` / `→` / `↑` / `↓` | Nudge active animation offset by **10 px** |

---
