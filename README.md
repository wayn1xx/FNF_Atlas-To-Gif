# Atlas to GIF

A lightweight desktop tool built with CustomTkinter to convert Sparrow / Starling XML sprite sheets and PNG textures into animated GIFs, featuring full character offset alignment support.

## Features

- **Live Animation Preview**: real-time frame preview with playback controls.
- **FNF Offset Support**: automatically imports character offsets from adjacent `.json` files.
- **Manual Offset Adjustments**: fine-tune frame positioning using arrow keys (`Shift` for x10 speed).
- **Export Queue**: stitch multiple animations into a single sequence.
- **Customizable Output**: adjust playback FPS and scaling before export.

## Requirements

```bash
pip install customtkinter pillow
