import json
import os
import re
import sys
import threading
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def resource_path(relative_path):
    """Accurately resolves asset paths for PyInstaller --onefile"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def natural_sort_key(s):
    """Sort strings containing numbers in natural order (idle1, idle2 ... idle10)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def clean_subtexture_name(full_name):
    """Removes trailing frame index digits from a SubTexture name"""
    base = re.sub(r"\d+$", "", full_name).strip()
    return base or full_name


class ExportDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_export_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_export_callback = on_export_callback

        self.title("Export Settings")
        self.geometry("460x510")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        has_queue = len(parent.selected_sequence) > 0
        default_mode = "merge_queue" if has_queue else "batch_all"

        self.mode_var = ctk.StringVar(value=default_mode)
        self.format_var = ctk.StringVar(value="GIF")
        self.loop_var = ctk.BooleanVar(value=True)

        self.setup_ui(has_queue)

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def setup_ui(self, has_queue):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=12)

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", pady=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=85,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=("#d0d0d0", "#454545"),
            text_color=("#333333", "#e0e0e0"),
            command=self.destroy,
        )
        btn_cancel.pack(side="left")

        btn_export = ctk.CTkButton(
            btn_row,
            text="Export ➔",
            height=32,
            font=ctk.CTkFont(weight="bold"),
            command=self._confirm,
        )
        btn_export.pack(side="right", fill="x", expand=True, padx=(8, 0))

        ctk.CTkLabel(
            container,
            text="Export Options",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=18, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        card_mode = ctk.CTkFrame(container, corner_radius=8)
        card_mode.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card_mode, text="Mode:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(6, 2))

        q_count = len(self.parent.selected_sequence)
        all_count = len(self.parent.available_names)

        self.rb_merge = ctk.CTkRadioButton(
            card_mode,
            text=f"Merge Queue into 1 file ({q_count} anims)",
            variable=self.mode_var,
            value="merge_queue",
            state="normal" if has_queue else "disabled",
            font=ctk.CTkFont(size=12),
        )
        self.rb_merge.pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(
            card_mode,
            text="Glues all queue animations in order into a single file",
            font=ctk.CTkFont(size=10),
            text_color=("#737373", "#8e8e8e"),
        ).pack(anchor="w", padx=36, pady=(0, 2))

        self.rb_batch_q = ctk.CTkRadioButton(
            card_mode,
            text=f"Separate file for each Queue anim ({q_count})",
            variable=self.mode_var,
            value="batch_queue",
            state="normal" if has_queue else "disabled",
            font=ctk.CTkFont(size=12),
        )
        self.rb_batch_q.pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(
            card_mode,
            text="Saves each queue animation as its own file in a folder",
            font=ctk.CTkFont(size=10),
            text_color=("#737373", "#8e8e8e"),
        ).pack(anchor="w", padx=36, pady=(0, 2))

        self.rb_batch_all = ctk.CTkRadioButton(
            card_mode,
            text=f"Separate file for ALL anims from XML ({all_count})",
            variable=self.mode_var,
            value="batch_all",
            font=ctk.CTkFont(size=12),
        )
        self.rb_batch_all.pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(
            card_mode,
            text="Exports every animation found in the XML into a folder",
            font=ctk.CTkFont(size=10),
            text_color=("#737373", "#8e8e8e"),
        ).pack(anchor="w", padx=36, pady=(0, 6))

        card_fmt = ctk.CTkFrame(container, corner_radius=8)
        card_fmt.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card_fmt, text="Format:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(6, 2))

        self.seg_fmt = ctk.CTkSegmentedButton(
            card_fmt,
            values=["GIF", "PNG Sequence"],
            variable=self.format_var,
            command=self._on_format_changed,
        )
        self.seg_fmt.pack(fill="x", padx=12, pady=(2, 4))

        self.lbl_fmt_desc = ctk.CTkLabel(
            card_fmt,
            text="Standard GIF animation (transparent background)",
            font=ctk.CTkFont(size=11),
            text_color=("#606060", "#9e9e9e"),
            wraplength=400,
            justify="left",
        )
        self.lbl_fmt_desc.pack(anchor="w", padx=14, pady=(2, 6))

        card_opts = ctk.CTkFrame(container, corner_radius=8)
        card_opts.pack(fill="x", pady=(0, 6))

        self.chk_loop = ctk.CTkCheckBox(
            card_opts,
            text="Infinite Loop (repeat animation)",
            variable=self.loop_var,
            font=ctk.CTkFont(size=12),
        )
        self.chk_loop.pack(anchor="w", padx=14, pady=6)

    def _on_format_changed(self, val):
        if val == "GIF":
            self.lbl_fmt_desc.configure(text="Standard GIF animation (transparent background)")
            self.chk_loop.configure(state="normal")
        elif val == "PNG Sequence":
            self.lbl_fmt_desc.configure(text="Folder with numbered frames (frame_0000.png) for Animate / Video Editors")
            self.chk_loop.configure(state="disabled")

    def _confirm(self):
        mode = self.mode_var.get()
        fmt = self.format_var.get()
        loop = self.loop_var.get()
        self.destroy()
        self.on_export_callback(mode, fmt, loop)


class AtlasToGifApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Atlas to GIF")

        self.PREVIEW_WIDTH = 320
        self.WIDTH_WITH_PREVIEW = 920
        self.WIDTH_WITHOUT_PREVIEW = 600
        self.BASE_HEIGHT = 770

        self.geometry(f"{self.WIDTH_WITH_PREVIEW}x{self.BASE_HEIGHT}")
        self.minsize(820, 720)
        self.configure(fg_color=("#f3f3f3", "#1a1a1a"))

        self.xml_path = ctk.StringVar()
        self.png_path = ctk.StringVar()
        self.fps_val = ctk.IntVar(value=24)
        self.scale_val = ctk.DoubleVar(value=1.0)
        self.preview_enabled = ctk.BooleanVar(value=True)

        # Offsets
        self.anim_offsets = {}
        self.cur_off_x = ctk.IntVar(value=0)
        self.cur_off_y = ctk.IntVar(value=0)
        self.active_anim_name = None
        self.is_playing_queue = False

        self.animations = {}
        self.available_names = []
        self.selected_sequence = []

        # Камера (Pan / Zoom)
        self.user_zoom = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._pan_start = None
        self._wheel_debounce_job = None
        self._last_canvas_size = (0, 0)

        # Двухуровневый кэш превью для быстрого зума
        self._raw_anim_cache = {}   # { anim_name: (list_of_pil_frames, min_x, min_y, bw, bh) }
        self._anim_cache = {}       # { (anim_name, ratio_key): (list_of_photo_images, min_x, min_y) }

        # Состояние отображения
        self.preview_photo_images = []
        self.preview_frame_meta = []
        self.preview_frame_idx = 0
        self.preview_loop_job = None
        self.canvas_resize_job = None
        self.loaded_atlas = None
        self.preview_canvas_img_id = None

        self.preview_scale_ratio = 1.0
        self.canvas_origin_x = 150.0
        self.canvas_origin_y = 150.0
        self.preview_anim_min_x = 0
        self.preview_anim_min_y = 0

        self.setup_ui()
        self.setup_keybindings()

    def _is_text_input_focused(self):
        focused = self.focus_get()
        if not focused:
            return False
        w_class = focused.winfo_class().lower()
        return "entry" in w_class or "text" in w_class

    def setup_keybindings(self):
        def on_delete(e):
            if not self._is_text_input_focused():
                self.remove_from_queue()

        self.bind("<Delete>", on_delete)

        # Мгновенные клавиши оффсета
        self.bind_all("<Left>", lambda e: self.adjust_offset(-1, 0))
        self.bind_all("<Right>", lambda e: self.adjust_offset(1, 0))
        self.bind_all("<Up>", lambda e: self.adjust_offset(0, -1))
        self.bind_all("<Down>", lambda e: self.adjust_offset(0, 1))

        self.bind_all("<Shift-Left>", lambda e: self.adjust_offset(-10, 0))
        self.bind_all("<Shift-Right>", lambda e: self.adjust_offset(10, 0))
        self.bind_all("<Shift-Up>", lambda e: self.adjust_offset(0, -10))
        self.bind_all("<Shift-Down>", lambda e: self.adjust_offset(0, 10))

    def setup_ui(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=16, pady=14)

        header_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Atlas to GIF",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=20, weight="bold"),
        )
        title_lbl.pack(side="left")

        self.chk_preview = ctk.CTkCheckBox(
            header_frame,
            text="Live Preview",
            variable=self.preview_enabled,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_preview_state,
        )
        self.chk_preview.pack(side="right", padx=(0, 4))

        # File Selection Card
        file_card = ctk.CTkFrame(
            main_container,
            corner_radius=10,
            fg_color=("#ffffff", "#252525"),
            border_width=1,
            border_color=("#e5e5e5", "#333333"),
        )
        file_card.pack(fill="x", pady=(0, 10))

        lbl_xml = ctk.CTkLabel(file_card, text="Atlas XML:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        lbl_xml.grid(row=0, column=0, padx=(14, 8), pady=(10, 4), sticky="w")

        self.entry_xml = ctk.CTkEntry(
            file_card,
            textvariable=self.xml_path,
            placeholder_text="Select Starling/Sparrow XML file...",
            state="readonly",
            height=30,
            corner_radius=6,
        )
        self.entry_xml.grid(row=0, column=1, padx=6, pady=(10, 4), sticky="ew")

        self.btn_browse_xml = ctk.CTkButton(
            file_card, text="Browse...", width=85, height=30, corner_radius=6, command=self.browse_xml
        )
        self.btn_browse_xml.grid(row=0, column=2, padx=(6, 14), pady=(10, 4))

        lbl_png = ctk.CTkLabel(file_card, text="Texture PNG:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        lbl_png.grid(row=1, column=0, padx=(14, 8), pady=(4, 10), sticky="w")

        self.entry_png = ctk.CTkEntry(
            file_card,
            textvariable=self.png_path,
            placeholder_text="Select PNG spritesheet image...",
            state="readonly",
            height=30,
            corner_radius=6,
        )
        self.entry_png.grid(row=1, column=1, padx=6, pady=(4, 10), sticky="ew")

        self.btn_browse_png = ctk.CTkButton(
            file_card, text="Browse...", width=85, height=30, corner_radius=6, command=self.browse_png
        )
        self.btn_browse_png.grid(row=1, column=2, padx=(6, 14), pady=(4, 10))
        file_card.grid_columnconfigure(1, weight=1)

        # Center Section
        self.center_split = ctk.CTkFrame(main_container, fg_color="transparent")
        self.center_split.pack(fill="both", expand=True, pady=(0, 10))

        anim_card = ctk.CTkFrame(
            self.center_split,
            corner_radius=10,
            fg_color=("#ffffff", "#252525"),
            border_width=1,
            border_color=("#e5e5e5", "#333333"),
        )
        anim_card.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # Left Column: Available Animations
        left_box = ctk.CTkFrame(anim_card, fg_color="transparent")
        left_box.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=10)

        lbl_avail = ctk.CTkLabel(left_box, text="Available Animations", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_avail.pack(anchor="w", pady=(0, 4))

        self.list_available = ctk.CTkScrollableFrame(
            left_box, corner_radius=8, fg_color=("#f9f9f9", "#1d1d1d"), border_width=1, border_color=("#e5e5e5", "#2e2e2e")
        )
        self.list_available.pack(fill="both", expand=True)

        # Center: Queue Controls (Ширина кнопок зафиксирована)
        btn_box = ctk.CTkFrame(anim_card, fg_color="transparent")
        btn_box.pack(side="left", padx=6, pady=10)

        self.btn_add = ctk.CTkButton(btn_box, text="Add ➔", width=90, height=30, corner_radius=6, command=self.add_to_queue)
        self.btn_add.pack(pady=4)

        self.btn_remove = ctk.CTkButton(
            btn_box,
            text="✕ Remove",
            width=90,
            height=30,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=("#d0d0d0", "#454545"),
            text_color=("#333333", "#e0e0e0"),
            hover_color=("#e8e8e8", "#383838"),
            command=self.remove_from_queue,
        )
        self.btn_remove.pack(pady=4)

        self.btn_clear = ctk.CTkButton(
            btn_box,
            text="Clear",
            width=90,
            height=30,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=("#d0d0d0", "#454545"),
            text_color=("#333333", "#e0e0e0"),
            hover_color=("#e8e8e8", "#383838"),
            command=self.clear_queue,
        )
        self.btn_clear.pack(pady=4)

        # Queue Order Controls
        self.btn_up = ctk.CTkButton(
            btn_box,
            text="Up ▲",
            width=90,
            height=28,
            corner_radius=6,
            fg_color=("#ebebeb", "#363636"),
            text_color=("#1f1f1f", "#ffffff"),
            hover_color=("#dcdcdc", "#454545"),
            command=self.move_up,
        )
        self.btn_up.pack(pady=4)

        self.btn_down = ctk.CTkButton(
            btn_box,
            text="Down ▼",
            width=90,
            height=28,
            corner_radius=6,
            fg_color=("#ebebeb", "#363636"),
            text_color=("#1f1f1f", "#ffffff"),
            hover_color=("#dcdcdc", "#454545"),
            command=self.move_down,
        )
        self.btn_down.pack(pady=4)

        # Кнопка Play Queue с оптимизированным шрифтом, чтобы не расширялась
        self.btn_play_queue = ctk.CTkButton(
            btn_box,
            text="Play Queue",
            width=90,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#0067c0", "#0078d4"),
            text_color="#ffffff",
            hover_color=("#00539a", "#005a9e"),
            command=self.toggle_play_queue,
        )
        self.btn_play_queue.pack(pady=(12, 4))

        # Right Column: Export Queue
        right_box = ctk.CTkFrame(anim_card, fg_color="transparent")
        right_box.pack(side="left", fill="both", expand=True, padx=(4, 10), pady=10)

        lbl_queue = ctk.CTkLabel(right_box, text="Export Queue", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_queue.pack(anchor="w", pady=(0, 4))

        self.list_queue = ctk.CTkScrollableFrame(
            right_box, corner_radius=8, fg_color=("#f9f9f9", "#1d1d1d"), border_width=1, border_color=("#e5e5e5", "#2e2e2e")
        )
        self.list_queue.pack(fill="both", expand=True)

        # Preview Sidebar
        self.preview_card = ctk.CTkFrame(
            self.center_split,
            width=self.PREVIEW_WIDTH,
            corner_radius=10,
            fg_color=("#ffffff", "#252525"),
            border_width=1,
            border_color=("#e5e5e5", "#333333"),
        )
        self.preview_card.pack(side="right", fill="y", padx=(4, 0))
        self.preview_card.pack_propagate(False)

        lbl_prev_title = ctk.CTkLabel(
            self.preview_card, text="Preview Display", font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_prev_title.pack(anchor="w", padx=12, pady=(10, 4))

        self.canvas_preview = ctk.CTkCanvas(
            self.preview_card,
            bg="#181818",
            highlightthickness=1,
            highlightbackground="#333333",
            relief="flat",
        )
        self.canvas_preview.pack(fill="both", expand=True, padx=12, pady=4)
        self.canvas_preview.bind("<Configure>", self._on_canvas_configure)

        # Бинды камеры (Zoom & Pan)
        self.canvas_preview.bind("<MouseWheel>", self._on_canvas_wheel)
        self.canvas_preview.bind("<Button-4>", lambda e: self._on_canvas_wheel_delta(1))
        self.canvas_preview.bind("<Button-5>", lambda e: self._on_canvas_wheel_delta(-1))

        self.canvas_preview.bind("<ButtonPress-3>", self._on_pan_start)
        self.canvas_preview.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas_preview.bind("<ButtonRelease-3>", self._on_pan_end)

        self.canvas_preview.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas_preview.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas_preview.bind("<ButtonRelease-2>", self._on_pan_end)

        self.canvas_preview.bind("<Double-Button-1>", self._reset_camera)
        self.canvas_preview.bind("<Double-Button-2>", self._reset_camera)
        self.canvas_preview.bind("<Double-Button-3>", self._reset_camera)

        self.lbl_preview_info = ctk.CTkLabel(
            self.preview_card, text="No frames", font=ctk.CTkFont(size=11), text_color=("#737373", "#999999")
        )
        self.lbl_preview_info.pack(pady=(0, 2))

        # Offset Panel
        self.offset_card = ctk.CTkFrame(self.preview_card, corner_radius=8, fg_color=("#f4f4f4", "#1e1e1e"))
        self.offset_card.pack(fill="x", padx=10, pady=(0, 8))

        lbl_off_title = ctk.CTkLabel(
            self.offset_card, text="Offset", font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_off_title.pack(anchor="w", padx=10, pady=(6, 2))

        coords_row = ctk.CTkFrame(self.offset_card, fg_color="transparent")
        coords_row.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(coords_row, text="X:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.lbl_x_val = ctk.CTkLabel(coords_row, textvariable=self.cur_off_x, width=36, font=ctk.CTkFont(size=11))
        self.lbl_x_val.pack(side="left", padx=(1, 6))

        ctk.CTkLabel(coords_row, text="Y:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.lbl_y_val = ctk.CTkLabel(coords_row, textvariable=self.cur_off_y, width=36, font=ctk.CTkFont(size=11))
        self.lbl_y_val.pack(side="left", padx=(1, 6))

        self.btn_reset_off = ctk.CTkButton(
            coords_row,
            text="Clear",
            width=54,
            height=22,
            font=ctk.CTkFont(size=10),
            command=self.reset_current_offset,
        )
        self.btn_reset_off.pack(side="right")

        lbl_hint = ctk.CTkLabel(
            self.offset_card,
            text="Arrows: Offset • Drag RMB: Pan • Wheel: Zoom",
            font=ctk.CTkFont(size=10),
            text_color=("#737373", "#888888"),
        )
        lbl_hint.pack(fill="x", padx=8, pady=(2, 6))

        # Options Panel
        opts_card = ctk.CTkFrame(
            main_container,
            corner_radius=10,
            fg_color=("#ffffff", "#252525"),
            border_width=1,
            border_color=("#e5e5e5", "#333333"),
            height=48,
        )
        opts_card.pack(fill="x", pady=(0, 10))

        lbl_fps = ctk.CTkLabel(opts_card, text="FPS:", font=ctk.CTkFont(size=12))
        lbl_fps.pack(side="left", padx=(14, 6), pady=8)

        self.fps_slider = ctk.CTkSlider(
            opts_card,
            from_=1,
            to=60,
            number_of_steps=59,
            variable=self.fps_val,
            width=90,
            command=self.on_fps_changed,
        )
        self.fps_slider.pack(side="left", padx=4, pady=8)

        self.lbl_fps_num = ctk.CTkLabel(
            opts_card, text=f"{self.fps_val.get()}", font=ctk.CTkFont(size=12, weight="bold"), width=24
        )
        self.lbl_fps_num.pack(side="left", padx=(2, 8), pady=8)

        lbl_scale = ctk.CTkLabel(opts_card, text="Scale:", font=ctk.CTkFont(size=12))
        lbl_scale.pack(side="left", padx=(6, 6), pady=8)

        self.scale_slider = ctk.CTkSlider(
            opts_card,
            from_=0.25,
            to=5.0,
            number_of_steps=19,
            variable=self.scale_val,
            width=90,
            command=self.on_scale_changed,
        )
        self.scale_slider.pack(side="left", padx=4, pady=8)

        self.lbl_scale_num = ctk.CTkLabel(
            opts_card, text=f"{self.scale_val.get():.2f}x", font=ctk.CTkFont(size=12, weight="bold"), width=42
        )
        self.lbl_scale_num.pack(side="left", padx=(2, 8), pady=8)

        self.progress_bar = ctk.CTkProgressBar(main_container, height=6, corner_radius=3)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 6))

        self.btn_convert = ctk.CTkButton(
            main_container,
            text="Export...",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled",
            command=self.open_export_dialog,
        )
        self.btn_convert.pack(fill="x", pady=(0, 4))

        self.lbl_status = ctk.CTkLabel(
            main_container,
            text="Please select XML and PNG files to begin",
            font=ctk.CTkFont(size=11),
            text_color=("#737373", "#a0a0a0"),
        )
        self.lbl_status.pack()

        self.selected_avail_idx = None
        self.selected_queue_idx = None

    # --- Mouse Pan & Zoom ---

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)

    def _on_pan_drag(self, event):
        if self._pan_start:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self._pan_start = (event.x, event.y)
            self.pan_offset_x += dx
            self.pan_offset_y += dy
            self._update_current_canvas_pos()

    def _on_pan_end(self, event):
        self._pan_start = None

    def _on_canvas_wheel(self, event):
        if not self.animations:
            return
        delta = 1 if event.delta > 0 else -1
        self._on_canvas_wheel_delta(delta)

    def _on_canvas_wheel_delta(self, direction):
        factor = 1.15 if direction > 0 else (1.0 / 1.15)
        new_zoom = max(0.15, min(6.0, self.user_zoom * factor))
        if abs(new_zoom - self.user_zoom) <= 0.001:
            return

        self.user_zoom = new_zoom

        zoom_pct = int(self.user_zoom * 100)
        total_f = len(self.preview_photo_images) if self.preview_photo_images else 0
        cur_f = (self.preview_frame_idx % total_f) + 1 if total_f > 0 else 0
        self.lbl_preview_info.configure(text=f"Frame: {cur_f} / {total_f}  ({zoom_pct}%)")

        if self._wheel_debounce_job:
            try:
                self.after_cancel(self._wheel_debounce_job)
            except Exception:
                pass
        self._wheel_debounce_job = self.after(50, self._apply_zoom_update)

    def _apply_zoom_update(self):
        self._wheel_debounce_job = None
        self._recalc_viewport_and_refresh()

    def _reset_camera(self, event=None):
        if self._wheel_debounce_job:
            try:
                self.after_cancel(self._wheel_debounce_job)
            except Exception:
                pass
            self._wheel_debounce_job = None

        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.user_zoom = 1.0
        self._recalc_viewport_and_refresh()

    # --- Offset Handling ---

    def get_anim_offset(self, anim_name):
        clean = anim_name.strip().lower()
        if clean in self.anim_offsets:
            return self.anim_offsets[clean]
        if anim_name in self.anim_offsets:
            return self.anim_offsets[anim_name]
        return [0, 0]

    def set_anim_offset(self, anim_name, off):
        clean = anim_name.strip().lower()
        self.anim_offsets[clean] = list(off)
        self.anim_offsets[anim_name] = list(off)

    def adjust_offset(self, dx, dy):
        if self._is_text_input_focused():
            return

        if not self.active_anim_name:
            if self.is_playing_queue and self.selected_sequence:
                self.active_anim_name = self.selected_sequence[0]
            else:
                return

        cur = list(self.get_anim_offset(self.active_anim_name))
        cur[0] += dx
        cur[1] += dy
        self.set_anim_offset(self.active_anim_name, cur)

        self.cur_off_x.set(cur[0])
        self.cur_off_y.set(cur[1])

        self._update_current_canvas_pos()

    def reset_current_offset(self):
        if not self.active_anim_name:
            return
        self.set_anim_offset(self.active_anim_name, [0, 0])
        self.cur_off_x.set(0)
        self.cur_off_y.set(0)
        self._update_current_canvas_pos()

    def sync_offset_display(self):
        if self.active_anim_name:
            off = self.get_anim_offset(self.active_anim_name)
            self.cur_off_x.set(off[0])
            self.cur_off_y.set(off[1])
        else:
            self.cur_off_x.set(0)
            self.cur_off_y.set(0)

    # --- Character Bounds & Calculations (Охватывает все позы) ---

    def get_character_bounds(self):
        """Гарантирует, что абсолютно все анимации влезут в экран и ни одна не улетит за край"""
        if not self.animations:
            return 0, 0, 300, 300

        if self.is_playing_queue and self.selected_sequence:
            anims_to_check = set(self.selected_sequence)
        elif self.active_anim_name:
            anims_to_check = {self.active_anim_name}
            base = self.get_base_animation_name()
            if base:
                anims_to_check.add(base)
        else:
            anims_to_check = set(self.animations.keys())

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        found = False

        for a in anims_to_check:
            if a not in self.animations:
                continue
            off_x, off_y = self.get_anim_offset(a)
            for st in self.animations[a]:
                w = int(st.get("width", 0))
                h = int(st.get("height", 0))
                if w <= 0 or h <= 0:
                    continue
                rotated = st.get("rotated", "false").lower() == "true"
                cw, ch = (h, w) if rotated else (w, h)
                fx = -int(st.get("frameX", 0)) + off_x
                fy = -int(st.get("frameY", 0)) + off_y
                min_x = min(min_x, fx)
                min_y = min(min_y, fy)
                max_x = max(max_x, fx + cw)
                max_y = max(max_y, fy + ch)
                found = True

        if not found or min_x == float("inf"):
            return 0, 0, 300, 300

        return int(min_x), int(min_y), int(max_x), int(max_y)

    def get_global_bbox(self, specific_anims=None):
        anims_to_check = set(specific_anims) if specific_anims else set(self.animations.keys())
        base_anim = self.get_base_animation_name()
        if base_anim:
            anims_to_check.add(base_anim)

        if not anims_to_check:
            return 0, 0, 100, 100

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        found = False

        for anim_name in anims_to_check:
            if anim_name not in self.animations:
                continue
            off_x, off_y = self.get_anim_offset(anim_name)
            for st in self.animations[anim_name]:
                found = True
                w = int(st.get("width", 0))
                h = int(st.get("height", 0))
                rotated = st.get("rotated", "false").lower() == "true"
                crop_w, crop_h = (h, w) if rotated else (w, h)

                fx = -int(st.get("frameX", 0)) + off_x
                fy = -int(st.get("frameY", 0)) + off_y

                min_x = min(min_x, fx)
                min_y = min(min_y, fy)
                max_x = max(max_x, fx + crop_w)
                max_y = max(max_y, fy + crop_h)

        if not found or min_x == float("inf"):
            return 0, 0, 100, 100

        return int(min_x), int(min_y), int(max_x), int(max_y)

    # --- Fast & Smooth Frame Pipeline with Zoom Caching ---

    def _prepare_animation_frames(self, anim_name):
        ratio_key = round(self.preview_scale_ratio, 3)
        cache_key = (anim_name, ratio_key)
        if cache_key in self._anim_cache:
            return self._anim_cache[cache_key]

        # 1. Сборка сырых мастер-кадров
        if anim_name not in self._raw_anim_cache:
            if not self.loaded_atlas:
                self.loaded_atlas = Image.open(self.png_path.get()).convert("RGBA")

            subtextures = self.get_sorted_subtextures([anim_name])
            if not subtextures:
                return [], 0, 0

            min_x, min_y = float("inf"), float("inf")
            max_x, max_y = float("-inf"), float("-inf")
            for st in subtextures:
                w = int(st.get("width", 0))
                h = int(st.get("height", 0))
                if w <= 0 or h <= 0:
                    continue
                rotated = st.get("rotated", "false").lower() == "true"
                cw, ch = (h, w) if rotated else (w, h)
                fx = -int(st.get("frameX", 0))
                fy = -int(st.get("frameY", 0))
                min_x = min(min_x, fx)
                min_y = min(min_y, fy)
                max_x = max(max_x, fx + cw)
                max_y = max(max_y, fy + ch)

            if min_x == float("inf"):
                return [], 0, 0

            bw = max(1, int(max_x - min_x))
            bh = max(1, int(max_y - min_y))

            raw_frames = []
            for st in subtextures:
                x, y = int(st.get("x", 0)), int(st.get("y", 0))
                w, h = int(st.get("width", 0)), int(st.get("height", 0))
                if w <= 0 or h <= 0:
                    continue
                rotated = st.get("rotated", "false").lower() == "true"
                fx = -int(st.get("frameX", 0))
                fy = -int(st.get("frameY", 0))

                cropped = self.loaded_atlas.crop((x, y, x + w, y + h))
                if rotated:
                    cropped = cropped.transpose(Image.Transpose.ROTATE_270)

                frame = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
                frame.paste(cropped, (fx - min_x, fy - min_y), cropped)
                raw_frames.append(frame)

            self._raw_anim_cache[anim_name] = (raw_frames, int(min_x), int(min_y), bw, bh)

        # 2. Быстрое масштабирование
        raw_frames, min_x, min_y, bw, bh = self._raw_anim_cache[anim_name]
        ratio = self.preview_scale_ratio
        tw = max(1, int(bw * ratio))
        th = max(1, int(bh * ratio))

        photos = []
        for rf in raw_frames:
            resized = rf.resize((tw, th), Image.Resampling.BILINEAR)
            photos.append(ImageTk.PhotoImage(resized))

        self._anim_cache[cache_key] = (photos, min_x, min_y)
        return photos, min_x, min_y

    def _draw_or_move(self, img, draw_x, draw_y):
        try:
            if self.preview_canvas_img_id is None or not self.canvas_preview.find_withtag(self.preview_canvas_img_id):
                self.canvas_preview.delete("all")
                self.preview_canvas_img_id = self.canvas_preview.create_image(draw_x, draw_y, image=img, anchor="nw")
            else:
                self.canvas_preview.coords(self.preview_canvas_img_id, draw_x, draw_y)
                self.canvas_preview.itemconfig(self.preview_canvas_img_id, image=img)
            # Защита от случайного удаления сборщиком мусора
            self.canvas_preview._current_img = img
        except Exception:
            pass

    def _update_current_canvas_pos(self):
        """Мгновенное обновление позиции при панорамировании ПКМ и стрелочках"""
        if not self.preview_photo_images or self.preview_canvas_img_id is None:
            return
        total_p = len(self.preview_photo_images)
        if total_p == 0:
            return
        idx = self.preview_frame_idx % total_p
        if self.is_playing_queue and self.preview_frame_meta:
            m_idx = idx % len(self.preview_frame_meta)
            anim_name, a_min_x, a_min_y = self.preview_frame_meta[m_idx]
        else:
            anim_name = self.active_anim_name or ""
            a_min_x = self.preview_anim_min_x
            a_min_y = self.preview_anim_min_y

        off = self.get_anim_offset(anim_name)
        draw_x = int(self.canvas_origin_x + self.pan_offset_x + (a_min_x + off[0]) * self.preview_scale_ratio)
        draw_y = int(self.canvas_origin_y + self.pan_offset_y + (a_min_y + off[1]) * self.preview_scale_ratio)
        self.canvas_preview.coords(self.preview_canvas_img_id, draw_x, draw_y)

    def _on_canvas_configure(self, event):
        if not self.preview_enabled.get():
            return
        # Игнорируем микро-сдвиги на 1-2 пикселя, чтобы не вызывать паразитные сбросы
        if hasattr(self, "_last_canvas_size"):
            if abs(event.width - self._last_canvas_size[0]) < 3 and abs(event.height - self._last_canvas_size[1]) < 3:
                return
        self._last_canvas_size = (event.width, event.height)

        if self.canvas_resize_job:
            try:
                self.after_cancel(self.canvas_resize_job)
            except Exception:
                pass
        self.canvas_resize_job = self.after(80, self._recalc_viewport_and_refresh)

    def _recalc_viewport_and_refresh(self):
        cw = self.canvas_preview.winfo_width()
        ch = self.canvas_preview.winfo_height()
        if cw < 50:
            cw = self.PREVIEW_WIDTH - 24
        if ch < 50:
            ch = 320

        bx1, by1, bx2, by2 = self.get_character_bounds()
        char_w = max(10, bx2 - bx1)
        char_h = max(10, by2 - by1)
        char_cx = (bx1 + bx2) / 2.0
        char_cy = (by1 + by2) / 2.0

        base_ratio = max(0.01, min((cw - 32) / char_w, (ch - 32) / char_h, 1.0))
        self.preview_scale_ratio = base_ratio * self.user_zoom

        self.canvas_origin_x = (cw / 2.0) - (char_cx * self.preview_scale_ratio)
        self.canvas_origin_y = (ch / 2.0) - (char_cy * self.preview_scale_ratio)

        self.refresh_current_preview(preserve_frame_idx=True)

    def toggle_preview_state(self):
        curr_height = self.winfo_height()
        curr_width = self.winfo_width()

        if not self.preview_enabled.get():
            self.stop_preview_loop()
            self.preview_card.pack_forget()

            new_width = max(self.WIDTH_WITHOUT_PREVIEW, curr_width - self.PREVIEW_WIDTH)
            self.minsize(580, 720)
            self.geometry(f"{new_width}x{curr_height}")
        else:
            self.preview_card.pack(side="right", fill="y", padx=(4, 0))

            new_width = curr_width + self.PREVIEW_WIDTH
            self.minsize(820, 720)
            self.geometry(f"{new_width}x{curr_height}")

            self.refresh_current_preview()

    def stop_preview_loop(self):
        if self.preview_loop_job:
            try:
                self.after_cancel(self.preview_loop_job)
            except Exception:
                pass
            self.preview_loop_job = None

    def clear_canvas(self, text="No Preview"):
        self.preview_photo_images.clear()
        self.preview_frame_meta.clear()
        self.preview_canvas_img_id = None
        self.canvas_preview.delete("all")
        w = max(10, self.canvas_preview.winfo_width())
        h = max(10, self.canvas_preview.winfo_height())
        self.canvas_preview.create_text(
            w // 2, h // 2, text=text, fill="#777777", font=("Segoe UI", 10), justify="center"
        )

    def on_fps_changed(self, val):
        self.lbl_fps_num.configure(text=f"{int(val)}")

    def on_scale_changed(self, val):
        self.lbl_scale_num.configure(text=f"{val:.2f}x")

    def refresh_current_preview(self, preserve_frame_idx=False):
        saved_idx = self.preview_frame_idx if preserve_frame_idx else 0
        if self.is_playing_queue:
            self.preview_full_queue(start_idx=saved_idx)
        elif self.active_anim_name:
            self.load_preview_for_anim(self.active_anim_name, start_idx=saved_idx)

    def get_base_animation_name(self):
        if not self.available_names:
            return None
        priorities = ["idle", "dance", "stand"]
        for p in priorities:
            found = next((name for name in self.available_names if p in name.lower()), None)
            if found:
                return found
        return self.available_names[0]

    def load_preview_for_anim(self, anim_name, start_idx=0):
        self.is_playing_queue = False
        self.stop_preview_loop()

        if not self.preview_enabled.get():
            return

        if not self.png_path.get() or not os.path.exists(self.png_path.get()):
            self.clear_canvas("PNG file not found")
            return

        try:
            photos, a_min_x, a_min_y = self._prepare_animation_frames(anim_name)
            if not photos:
                self.clear_canvas("No frames found")
                return

            self.preview_photo_images = photos
            self.preview_anim_min_x = a_min_x
            self.preview_anim_min_y = a_min_y
            self.preview_frame_meta = []

            self.preview_frame_idx = start_idx % len(self.preview_photo_images)
            zoom_pct = int(self.user_zoom * 100)
            self.lbl_preview_info.configure(
                text=f"Frame: {self.preview_frame_idx + 1} / {len(self.preview_photo_images)}  ({zoom_pct}%)"
            )

            off = self.get_anim_offset(anim_name)
            draw_x = int(self.canvas_origin_x + self.pan_offset_x + (a_min_x + off[0]) * self.preview_scale_ratio)
            draw_y = int(self.canvas_origin_y + self.pan_offset_y + (a_min_y + off[1]) * self.preview_scale_ratio)

            self._draw_or_move(self.preview_photo_images[self.preview_frame_idx], draw_x, draw_y)
            self.run_preview_loop()
        except Exception as e:
            self.clear_canvas(f"Preview error:\n{e}")

    def toggle_play_queue(self):
        if self.is_playing_queue:
            self.stop_queue_preview()
        else:
            self.preview_full_queue()

    def update_queue_btn_ui(self):
        if self.is_playing_queue:
            self.btn_play_queue.configure(
                text="Stop Queue",
                fg_color=("#a82323", "#c42b2b"),
                hover_color=("#8a1c1c", "#a82323"),
            )
        else:
            self.btn_play_queue.configure(
                text="Play Queue",
                fg_color=("#0067c0", "#0078d4"),
                hover_color=("#00539a", "#005a9e"),
            )

    def stop_queue_preview(self):
        self.is_playing_queue = False
        self.update_queue_btn_ui()
        if self.active_anim_name:
            self.load_preview_for_anim(self.active_anim_name)
        elif self.available_names:
            self.select_available(0)
        else:
            self.stop_preview_loop()
            self.clear_canvas("Playback stopped")

    def preview_full_queue(self, start_idx=0):
        if not self.selected_sequence:
            self.clear_canvas("Export Queue is empty")
            self.is_playing_queue = False
            self.update_queue_btn_ui()
            return

        if not self.png_path.get() or not os.path.exists(self.png_path.get()):
            self.clear_canvas("PNG file not found")
            self.is_playing_queue = False
            self.update_queue_btn_ui()
            return

        self.is_playing_queue = True
        self.update_queue_btn_ui()
        self.stop_preview_loop()

        if not self.preview_enabled.get():
            return

        try:
            full_photos = []
            full_meta = []
            for name in self.selected_sequence:
                photos, ax, ay = self._prepare_animation_frames(name)
                for p in photos:
                    full_photos.append(p)
                    full_meta.append((name, ax, ay))

            if not full_photos:
                self.clear_canvas("No frames in queue")
                return

            self.preview_photo_images = full_photos
            self.preview_frame_meta = full_meta

            self.preview_frame_idx = start_idx % len(self.preview_photo_images)
            zoom_pct = int(self.user_zoom * 100)

            anim_name, ax, ay = self.preview_frame_meta[self.preview_frame_idx]
            self.lbl_preview_info.configure(
                text=f"[{anim_name}] Frame: {self.preview_frame_idx + 1} / {len(self.preview_photo_images)}  ({zoom_pct}%)"
            )

            off = self.get_anim_offset(anim_name)
            draw_x = int(self.canvas_origin_x + self.pan_offset_x + (ax + off[0]) * self.preview_scale_ratio)
            draw_y = int(self.canvas_origin_y + self.pan_offset_y + (ay + off[1]) * self.preview_scale_ratio)

            self._draw_or_move(self.preview_photo_images[self.preview_frame_idx], draw_x, draw_y)
            self.run_preview_loop()
        except Exception as e:
            self.clear_canvas(f"Queue preview error:\n{e}")

    def run_preview_loop(self):
        if not self.preview_enabled.get() or not self.preview_photo_images:
            return

        try:
            total_f = len(self.preview_photo_images)
            if total_f == 0:
                return

            self.preview_frame_idx = self.preview_frame_idx % total_f
            img = self.preview_photo_images[self.preview_frame_idx]

            if self.is_playing_queue and self.preview_frame_meta:
                meta_idx = self.preview_frame_idx % len(self.preview_frame_meta)
                anim_name, ax, ay = self.preview_frame_meta[meta_idx]
            else:
                anim_name = self.active_anim_name or ""
                ax = self.preview_anim_min_x
                ay = self.preview_anim_min_y

            off = self.get_anim_offset(anim_name)
            draw_x = int(self.canvas_origin_x + self.pan_offset_x + (ax + off[0]) * self.preview_scale_ratio)
            draw_y = int(self.canvas_origin_y + self.pan_offset_y + (ay + off[1]) * self.preview_scale_ratio)

            self._draw_or_move(img, draw_x, draw_y)

            zoom_pct = int(self.user_zoom * 100)
            prefix = f"[{anim_name}] " if self.is_playing_queue else ""
            self.lbl_preview_info.configure(
                text=f"{prefix}Frame: {self.preview_frame_idx + 1} / {total_f}  ({zoom_pct}%)"
            )

            self.preview_frame_idx = (self.preview_frame_idx + 1) % total_f
            delay = max(15, int(1000 / max(1, self.fps_val.get())))
            self.preview_loop_job = self.after(delay, self.run_preview_loop)
        except Exception:
            pass

    # --- Lists and Selection ---

    def deselect_all_lists(self):
        self.selected_avail_idx = None
        self.selected_queue_idx = None
        if hasattr(self, "avail_buttons"):
            for btn in self.avail_buttons:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))
        if hasattr(self, "queue_buttons"):
            for btn in self.queue_buttons:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))

    def render_available_list(self):
        for widget in self.list_available.winfo_children():
            widget.destroy()

        self.avail_buttons = []
        for idx, name in enumerate(self.available_names):
            count = len(self.animations[name])
            btn = ctk.CTkButton(
                self.list_available,
                text=f"{name} ({count}f)",
                anchor="w",
                height=28,
                corner_radius=6,
                fg_color="transparent",
                text_color=("#1f1f1f", "#f3f3f3"),
                hover_color=("#e6f2ff", "#293d56"),
                command=lambda i=idx: self.select_available(i),
            )
            btn.bind("<Double-Button-1>", lambda e, i=idx: (self.select_available(i), self.add_to_queue()))
            btn.pack(fill="x", pady=1)
            self.avail_buttons.append(btn)

    def select_available(self, idx):
        self.is_playing_queue = False
        self.update_queue_btn_ui()

        self.selected_avail_idx = idx
        self.selected_queue_idx = None

        if hasattr(self, "queue_buttons"):
            for btn in self.queue_buttons:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))

        for i, btn in enumerate(self.avail_buttons):
            if i == idx:
                btn.configure(fg_color=("#0067c0", "#0078d4"), text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))

        if 0 <= idx < len(self.available_names):
            self.active_anim_name = self.available_names[idx]
            self.sync_offset_display()
            self.load_preview_for_anim(self.active_anim_name)

    def render_queue_list(self):
        for widget in self.list_queue.winfo_children():
            widget.destroy()

        self.queue_buttons = []
        for idx, name in enumerate(self.selected_sequence):
            btn = ctk.CTkButton(
                self.list_queue,
                text=f"{idx + 1}. {name}",
                anchor="w",
                height=28,
                corner_radius=6,
                fg_color="transparent",
                text_color=("#1f1f1f", "#f3f3f3"),
                hover_color=("#e6f2ff", "#293d56"),
                command=lambda i=idx: self.select_queue(i),
            )
            btn.pack(fill="x", pady=1)
            self.queue_buttons.append(btn)

    def select_queue(self, idx):
        self.selected_queue_idx = idx
        self.selected_avail_idx = None

        if hasattr(self, "avail_buttons"):
            for btn in self.avail_buttons:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))

        for i, btn in enumerate(self.queue_buttons):
            if i == idx:
                btn.configure(fg_color=("#0067c0", "#0078d4"), text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=("#1f1f1f", "#f3f3f3"))

        if 0 <= idx < len(self.selected_sequence):
            self.active_anim_name = self.selected_sequence[idx]
            self.sync_offset_display()
            if self.is_playing_queue:
                self.preview_full_queue()
            else:
                self.load_preview_for_anim(self.active_anim_name)

    def add_to_queue(self):
        if self.selected_avail_idx is not None and self.selected_avail_idx < len(self.available_names):
            anim_name = self.available_names[self.selected_avail_idx]
            self.selected_sequence.append(anim_name)
            self.render_queue_list()
            self.select_queue(len(self.selected_sequence) - 1)
            self.check_ready()

    def remove_from_queue(self):
        if self.selected_queue_idx is not None and 0 <= self.selected_queue_idx < len(self.selected_sequence):
            del self.selected_sequence[self.selected_queue_idx]
            self.selected_queue_idx = None
            self.render_queue_list()
            self.check_ready()
            if not self.selected_sequence:
                self.stop_queue_preview()
            else:
                self.select_queue(min(self.selected_queue_idx or 0, len(self.selected_sequence) - 1))

    def clear_queue(self):
        self.selected_sequence.clear()
        self.selected_queue_idx = None
        self.render_queue_list()
        self.check_ready()
        self.stop_queue_preview()
        self.clear_canvas("Queue is empty")

    def move_up(self):
        idx = self.selected_queue_idx
        if idx is not None and idx > 0:
            self.selected_sequence[idx - 1], self.selected_sequence[idx] = (
                self.selected_sequence[idx],
                self.selected_sequence[idx - 1],
            )
            self.render_queue_list()
            self.select_queue(idx - 1)

    def move_down(self):
        idx = self.selected_queue_idx
        if idx is not None and idx < len(self.selected_sequence) - 1:
            self.selected_sequence[idx + 1], self.selected_sequence[idx] = (
                self.selected_sequence[idx],
                self.selected_sequence[idx + 1],
            )
            self.render_queue_list()
            self.select_queue(idx + 1)

    # --- XML & JSON Parsing ---

    def browse_xml(self):
        file = filedialog.askopenfilename(filetypes=[("XML files", "*.xml")])
        if file:
            self.xml_path.set(file)
            auto_png = os.path.splitext(file)[0] + ".png"
            if os.path.exists(auto_png) and not self.png_path.get():
                self.png_path.set(auto_png)
                self.loaded_atlas = None
                self._raw_anim_cache.clear()
                self._anim_cache.clear()
            self.parse_xml()

    def browse_png(self):
        file = filedialog.askopenfilename(filetypes=[("PNG files", "*.png")])
        if file:
            self.png_path.set(file)
            self.loaded_atlas = None
            self._raw_anim_cache.clear()
            self._anim_cache.clear()
            self.check_ready()
            if self.active_anim_name:
                self.load_preview_for_anim(self.active_anim_name)

    def parse_xml(self):
        try:
            xml_file = self.xml_path.get()
            tree = ET.parse(xml_file)
            root = tree.getroot()
            self.animations.clear()
            self.anim_offsets.clear()
            self._raw_anim_cache.clear()
            self._anim_cache.clear()

            xml_dir = os.path.dirname(xml_file)
            clean_name = os.path.splitext(os.path.basename(xml_file))[0]
            candidates = [
                os.path.join(xml_dir, f"{clean_name}.json"),
                os.path.join(xml_dir, f"{clean_name.replace('_', '-')}.json"),
                os.path.join(xml_dir, f"{clean_name.replace('-', '_')}.json"),
            ]
            loaded_json_msg = ""
            for json_candidate in candidates:
                if os.path.exists(json_candidate):
                    try:
                        with open(json_candidate, "r", encoding="utf-8") as jf:
                            data = json.load(jf)
                            for anim in data.get("animations", []):
                                offs = anim.get("offsets", [0, 0])
                                shift = [-offs[0], -offs[1]]

                                raw_name = anim.get("name", "")
                                raw_anim = anim.get("anim", "")
                                b1 = clean_subtexture_name(raw_name)
                                b2 = clean_subtexture_name(raw_anim)

                                for k in [raw_name, raw_anim, b1, b2]:
                                    if k:
                                        self.set_anim_offset(k, shift)

                        loaded_json_msg = f" + JSON ({os.path.basename(json_candidate)})"
                        break
                    except Exception as je:
                        print(f"JSON Parse warning: {je}")

            for st in root.findall("SubTexture"):
                full_name = st.get("name", "")
                base_name = clean_subtexture_name(full_name)
                self.animations.setdefault(base_name, []).append(st)

            if not self.animations:
                messagebox.showwarning("Warning", "No <SubTexture> elements found in XML.")
                return

            self.available_names = sorted(list(self.animations.keys()), key=natural_sort_key)
            self.render_available_list()
            self.clear_queue()
            self.lbl_status.configure(
                text=f"Loaded {len(self.available_names)} animation(s){loaded_json_msg}"
            )
            self.check_ready()

            self._reset_camera()

            if self.available_names:
                self.select_available(0)
        except Exception as e:
            messagebox.showerror("XML Parse Error", f"Could not parse XML:\n{e}")

    def check_ready(self):
        can_export = bool(self.xml_path.get() and self.png_path.get() and (self.selected_sequence or self.available_names))
        self.btn_convert.configure(state="normal" if can_export else "disabled")

    def get_sorted_subtextures(self, sequence_names):
        all_subtextures = []
        for anim_name in sequence_names:
            if anim_name in self.animations:
                subs = list(self.animations[anim_name])
                subs.sort(key=lambda st: natural_sort_key(st.get("name", "")))
                all_subtextures.extend(subs)
        return all_subtextures

    # --- Full Quality Frame Slicing for Export ---

    def cut_frames(self, atlas_img, subtextures, scale=1.0, custom_bbox=None, progress_callback=None):
        if not subtextures:
            return []

        if custom_bbox is not None:
            min_x, min_y, max_x, max_y = custom_bbox
        else:
            min_x, min_y, max_x, max_y = self.get_global_bbox()

        canvas_w = max(1, int(max_x - min_x))
        canvas_h = max(1, int(max_y - min_y))

        frames = []
        total = len(subtextures)
        for idx, st in enumerate(subtextures):
            full_name = st.get("name", "")
            base_name = clean_subtexture_name(full_name)
            off_x, off_y = self.get_anim_offset(base_name)

            x, y = int(st.get("x", 0)), int(st.get("y", 0))
            w, h = int(st.get("width", 0)), int(st.get("height", 0))
            rotated = st.get("rotated", "false").lower() == "true"

            fx = -int(st.get("frameX", 0)) + off_x
            fy = -int(st.get("frameY", 0)) + off_y

            cropped = atlas_img.crop((x, y, x + w, y + h))
            if rotated:
                cropped = cropped.transpose(Image.Transpose.ROTATE_270)

            frame = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            dest_x = fx - min_x
            dest_y = fy - min_y
            frame.paste(cropped, (dest_x, dest_y), cropped)

            if scale != 1.0:
                nw = max(1, int(canvas_w * scale))
                nh = max(1, int(canvas_h * scale))
                frame = frame.resize((nw, nh), Image.Resampling.BILINEAR)

            frames.append(frame)

            if progress_callback:
                progress_callback(idx + 1, total)

        return frames

    # --- Export Management ---

    def open_export_dialog(self):
        if not self.xml_path.get() or not self.png_path.get():
            return
        ExportDialog(self, self.start_export_process)

    def start_export_process(self, mode, fmt, loop):
        if mode == "merge_queue" and fmt != "PNG Sequence":
            default_name = "_".join(self.selected_sequence)[:40] or "animation"
            safe_name = re.sub(r'[\\/*?:"<>|]', "", default_name).strip()

            target = filedialog.asksaveasfilename(
                defaultextension=".gif",
                initialfile=f"{safe_name}.gif",
                filetypes=[("GIF Image", "*.gif")],
            )
            if not target:
                return
        else:
            target = filedialog.askdirectory(title="Select Destination Folder")
            if not target:
                return

        self.btn_convert.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Processing export...")

        scale = round(self.scale_val.get(), 2)
        fps = max(1, self.fps_val.get())

        thread = threading.Thread(
            target=self._export_worker,
            args=(target, mode, fmt, loop, scale, fps),
            daemon=True,
        )
        thread.start()

    def _export_worker(self, target, mode, fmt, loop, scale, fps):
        try:
            atlas = Image.open(self.png_path.get()).convert("RGBA")
            duration = int(1000 / fps)
            loop_count = 0 if loop else 1

            if mode == "merge_queue":
                items = [("_".join(self.selected_sequence)[:40], self.selected_sequence)]
                export_bbox = self.get_global_bbox(self.selected_sequence)
            elif mode == "batch_queue":
                items = [(name, [name]) for name in self.selected_sequence]
                export_bbox = self.get_global_bbox(self.selected_sequence)
            else:  # batch_all
                items = [(name, [name]) for name in self.available_names]
                export_bbox = self.get_global_bbox(self.available_names)

            total_items = len(items)
            total_frames_saved = 0

            for item_idx, (anim_title, anim_seq) in enumerate(items):
                safe_title = re.sub(r'[\\/*?:"<>|]', "", anim_title).strip() or "animation"
                subtextures = self.get_sorted_subtextures(anim_seq)
                if not subtextures:
                    continue

                def on_progress(current, total, idx=item_idx):
                    step = (idx / total_items) + (current / total) * (0.7 / total_items)
                    self.after(0, lambda c=current, s=step: self._update_progress(s, f"[{idx+1}/{total_items}] Cutting {safe_title}: {c}/{total}"))

                frames = self.cut_frames(
                    atlas,
                    subtextures,
                    scale=scale,
                    custom_bbox=export_bbox,
                    progress_callback=on_progress,
                )
                if not frames:
                    continue

                if mode == "merge_queue" and fmt != "PNG Sequence":
                    out_path = target
                else:
                    out_path = os.path.join(target, f"{safe_title}.gif") if fmt != "PNG Sequence" else os.path.join(target, safe_title)

                if fmt == "PNG Sequence":
                    os.makedirs(out_path, exist_ok=True)
                    for f_i, frm in enumerate(frames):
                        frm.save(os.path.join(out_path, f"frame_{f_i:04d}.png"))
                else:  # GIF
                    self.after(0, lambda: self._update_progress(0.85, f"Optimizing and encoding GIF: {safe_title}..."))
                    processed_frames = []
                    for f in frames:
                        if f.mode != "RGBA":
                            f = f.convert("RGBA")

                        r, g, b, a = f.split()
                        rgb_f = Image.merge("RGB", (r, g, b))

                        p_frame = rgb_f.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
                        mask = Image.eval(a, lambda val: 255 if val <= 128 else 0)

                        p_frame.paste(255, mask)
                        p_frame.info["transparency"] = 255
                        p_frame.info["duration"] = duration
                        p_frame.info["disposal"] = 2
                        processed_frames.append(p_frame)

                    processed_frames[0].save(
                        out_path,
                        save_all=True,
                        append_images=processed_frames[1:],
                        duration=duration,
                        loop=loop_count,
                        disposal=2,
                        transparency=255,
                    )

                total_frames_saved += len(frames)

            self.after(0, lambda: self._on_export_complete(target, total_frames_saved))
        except Exception as e:
            self.after(0, lambda: self._on_export_error(str(e)))

    def _update_progress(self, val, status_text):
        self.progress_bar.set(val)
        self.lbl_status.configure(text=status_text)

    def _on_export_complete(self, save_path, total_frames):
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"Export finished successfully ({total_frames} frames)!")
        self.btn_convert.configure(state="normal")
        messagebox.showinfo(
            "Success",
            f"Export completed!\n"
            f"Total frames processed: {total_frames}\n"
            f"Destination:\n{save_path}",
        )

    def _on_export_error(self, err_msg):
        self.progress_bar.set(0)
        self.btn_convert.configure(state="normal")
        self.lbl_status.configure(text="Export failed")
        messagebox.showerror("Export Error", f"An error occurred during export:\n{err_msg}")


if __name__ == "__main__":
    app = AtlasToGifApp()
    app.mainloop()
