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

        # Offsets and alignment
        self.anim_offsets = {}  # { 'anim_name': [shift_x, shift_y] }
        self.cur_off_x = ctk.IntVar(value=0)
        self.cur_off_y = ctk.IntVar(value=0)
        self.active_anim_name = None
        self.is_playing_queue = False

        self.animations = {}
        self.available_names = []
        self.selected_sequence = []

        # Preview and frame caching
        self.preview_raw_frames = []
        self.preview_photo_images = []
        self.preview_frame_idx = 0
        self.preview_loop_job = None
        self.canvas_resize_job = None
        self.loaded_atlas = None

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

        # Keyboard offset adjustments
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

        # Center Section: Lists + Preview
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

        # Center: Queue Controls
        btn_box = ctk.CTkFrame(anim_card, fg_color="transparent")
        btn_box.pack(side="left", padx=4, pady=10)

        self.btn_add = ctk.CTkButton(btn_box, text="Add ➔", width=95, height=30, corner_radius=6, command=self.add_to_queue)
        self.btn_add.pack(pady=4)

        self.btn_remove = ctk.CTkButton(
            btn_box,
            text="✕ Remove",
            width=95,
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
            width=95,
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
            width=95,
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
            width=95,
            height=28,
            corner_radius=6,
            fg_color=("#ebebeb", "#363636"),
            text_color=("#1f1f1f", "#ffffff"),
            hover_color=("#dcdcdc", "#454545"),
            command=self.move_down,
        )
        self.btn_down.pack(pady=4)

        self.btn_play_queue = ctk.CTkButton(
            btn_box,
            text="▶ Play Queue",
            width=95,
            height=30,
            corner_radius=6,
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

        self.lbl_preview_info = ctk.CTkLabel(
            self.preview_card, text="No frames", font=ctk.CTkFont(size=11), text_color=("#737373", "#999999")
        )
        self.lbl_preview_info.pack(pady=(0, 4))

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
            text="Arrow keys for x1 (Hold Shift for x10)",
            font=ctk.CTkFont(size=10),
            text_color=("#737373", "#888888"),
        )
        lbl_hint.pack(fill="x", padx=8, pady=(2, 6))

        # Options Panel (FPS, Scale)
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
            width=110,
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
            width=110,
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
            text="Export GIF",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled",
            command=self.start_export_thread,
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
        self.refresh_current_preview(preserve_frame_idx=True)

    def reset_current_offset(self):
        if not self.active_anim_name:
            return
        self.set_anim_offset(self.active_anim_name, [0, 0])
        self.cur_off_x.set(0)
        self.cur_off_y.set(0)
        self.refresh_current_preview(preserve_frame_idx=True)

    def sync_offset_display(self):
        if self.active_anim_name:
            off = self.get_anim_offset(self.active_anim_name)
            self.cur_off_x.set(off[0])
            self.cur_off_y.set(off[1])
        else:
            self.cur_off_x.set(0)
            self.cur_off_y.set(0)

    # --- Global Canvas Bounding Box ---

    def get_global_bbox(self, specific_anims=None):
        """Calculates a unified Bounding Box relative to origin (0, 0)"""
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

    # --- Preview System ---

    def _on_canvas_configure(self, event):
        if not self.preview_enabled.get() or not self.preview_raw_frames:
            return
        if self.canvas_resize_job:
            try:
                self.after_cancel(self.canvas_resize_job)
            except Exception:
                pass
        self.canvas_resize_job = self.after(100, self._rebuild_preview_from_raw)

    def _rebuild_preview_from_raw(self):
        if not self.preview_raw_frames:
            return
        c_width = max(120, self.canvas_preview.winfo_width() - 8)
        c_height = max(120, self.canvas_preview.winfo_height() - 8)

        new_photos = []
        for rf in self.preview_raw_frames:
            ratio = min(c_width / rf.width, c_height / rf.height, 1.0)
            tw, th = max(1, int(rf.width * ratio)), max(1, int(rf.height * ratio))
            resized = rf.resize((tw, th), Image.Resampling.BILINEAR)
            new_photos.append(ImageTk.PhotoImage(resized))

        self.preview_photo_images = new_photos
        if not self.preview_loop_job and self.preview_photo_images:
            self.run_preview_loop()

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
        self.preview_raw_frames.clear()
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
        self.preview_photo_images.clear()

        if not self.preview_enabled.get():
            return

        if not self.png_path.get() or not os.path.exists(self.png_path.get()):
            self.clear_canvas("PNG file not found")
            return

        subtextures = self.get_sorted_subtextures([anim_name])
        if not subtextures:
            self.clear_canvas("No frames found")
            return

        base_anim = self.get_base_animation_name()
        bbox = self.get_global_bbox([anim_name, base_anim] if base_anim else [anim_name])
        self._render_and_start_preview(subtextures, custom_bbox=bbox, start_idx=start_idx)

    # --- Queue Playback Toggle ---

    def toggle_play_queue(self):
        if self.is_playing_queue:
            self.stop_queue_preview()
        else:
            self.preview_full_queue()

    def update_queue_btn_ui(self):
        if self.is_playing_queue:
            self.btn_play_queue.configure(
                text="⏹ Stop Queue",
                fg_color=("#a82323", "#c42b2b"),
                hover_color=("#8a1c1c", "#a82323"),
            )
        else:
            self.btn_play_queue.configure(
                text="▶ Play Queue",
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
        self.preview_photo_images.clear()

        if not self.preview_enabled.get():
            return

        if not self.active_anim_name or self.active_anim_name not in self.selected_sequence:
            self.active_anim_name = self.selected_sequence[0]
            self.sync_offset_display()

        subtextures = self.get_sorted_subtextures(self.selected_sequence)
        if not subtextures:
            self.clear_canvas("No frames in queue")
            return

        bbox = self.get_global_bbox(self.selected_sequence)
        self._render_and_start_preview(subtextures, custom_bbox=bbox, start_idx=start_idx)

    def _render_and_start_preview(self, subtextures, custom_bbox=None, start_idx=0):
        try:
            if not self.loaded_atlas:
                self.loaded_atlas = Image.open(self.png_path.get()).convert("RGBA")

            self.preview_raw_frames = self.cut_frames(
                self.loaded_atlas,
                subtextures,
                scale=1.0,
                custom_bbox=custom_bbox,
            )
            if not self.preview_raw_frames:
                self.clear_canvas("Empty frames")
                return

            self.update_idletasks()
            c_width = max(120, self.canvas_preview.winfo_width() - 8)
            c_height = max(120, self.canvas_preview.winfo_height() - 8)

            self.preview_photo_images = []
            for rf in self.preview_raw_frames:
                ratio = min(c_width / rf.width, c_height / rf.height, 1.0)
                tw, th = max(1, int(rf.width * ratio)), max(1, int(rf.height * ratio))
                resized = rf.resize((tw, th), Image.Resampling.BILINEAR)
                self.preview_photo_images.append(ImageTk.PhotoImage(resized))

            self.preview_frame_idx = start_idx % len(self.preview_photo_images)
            self.lbl_preview_info.configure(text=f"Total: {len(self.preview_photo_images)} frames")
            self.run_preview_loop()
        except Exception as e:
            self.clear_canvas(f"Preview error:\n{e}")

    def run_preview_loop(self):
        if not self.preview_enabled.get() or not self.preview_photo_images:
            return

        self.preview_frame_idx = self.preview_frame_idx % len(self.preview_photo_images)
        img = self.preview_photo_images[self.preview_frame_idx]
        self.canvas_preview.delete("all")

        w = self.canvas_preview.winfo_width()
        h = self.canvas_preview.winfo_height()
        self.canvas_preview.create_image(w // 2, h // 2, image=img, anchor="center")

        self.lbl_preview_info.configure(
            text=f"Frame: {self.preview_frame_idx + 1} / {len(self.preview_photo_images)}"
        )

        self.preview_frame_idx = (self.preview_frame_idx + 1) % len(self.preview_photo_images)
        delay = max(15, int(1000 / max(1, self.fps_val.get())))
        self.preview_loop_job = self.after(delay, self.run_preview_loop)

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
            self.parse_xml()

    def browse_png(self):
        file = filedialog.askopenfilename(filetypes=[("PNG files", "*.png")])
        if file:
            self.png_path.set(file)
            self.loaded_atlas = None
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

            # Automatic search for associated FNF .json file
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

            if self.available_names:
                self.select_available(0)
        except Exception as e:
            messagebox.showerror("XML Parse Error", f"Could not parse XML:\n{e}")

    def check_ready(self):
        if self.xml_path.get() and self.png_path.get() and self.selected_sequence:
            self.btn_convert.configure(state="normal")
        else:
            self.btn_convert.configure(state="disabled")

    def get_sorted_subtextures(self, sequence_names):
        all_subtextures = []
        for anim_name in sequence_names:
            if anim_name in self.animations:
                subs = list(self.animations[anim_name])
                subs.sort(key=lambda st: natural_sort_key(st.get("name", "")))
                all_subtextures.extend(subs)
        return all_subtextures

    # --- Frame Slicing with Strict Bounding Box ---

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

    # --- Export to GIF ---

    def start_export_thread(self):
        if not self.selected_sequence:
            return

        default_name = "_".join(self.selected_sequence)[:40]
        safe_name = re.sub(r'[\\/*?:"<>|]', "", default_name).strip()

        save_path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            initialfile=f"{safe_name}.gif",
            filetypes=[("GIF Image", "*.gif")],
        )
        if not save_path:
            return

        self.btn_convert.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Processing frames...")

        scale = round(self.scale_val.get(), 2)
        fps = max(1, self.fps_val.get())

        thread = threading.Thread(
            target=self._export_worker,
            args=(save_path, scale, fps),
            daemon=True,
        )
        thread.start()

    def _export_worker(self, save_path, scale, fps):
        try:
            atlas = Image.open(self.png_path.get()).convert("RGBA")
            subtextures = self.get_sorted_subtextures(self.selected_sequence)

            def on_progress(current, total):
                if current % 4 == 0 or current == total:
                    prog = (current / total) * 0.7
                    self.after(0, lambda c=current: self._update_progress(prog, f"Cutting frames: {c}/{total}"))

            export_bbox = self.get_global_bbox(self.selected_sequence)

            frames = self.cut_frames(
                atlas,
                subtextures,
                scale=scale,
                custom_bbox=export_bbox,
                progress_callback=on_progress,
            )
            if not frames:
                raise ValueError("No valid frames could be generated.")

            self.after(0, lambda: self._update_progress(0.75, "Optimizing and encoding GIF..."))

            processed_frames = []
            duration = int(1000 / fps)

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
                save_path,
                save_all=True,
                append_images=processed_frames[1:],
                duration=duration,
                loop=0,
                disposal=2,
                transparency=255,
            )

            self.after(0, lambda: self._on_export_complete(save_path, len(frames)))
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
            f"Animations: {len(self.selected_sequence)}\n"
            f"Total frames: {total_frames}\n"
            f"Saved to:\n{save_path}",
        )

    def _on_export_error(self, err_msg):
        self.progress_bar.set(0)
        self.btn_convert.configure(state="normal")
        self.lbl_status.configure(text="Export failed")
        messagebox.showerror("Export Error", f"An error occurred during export:\n{err_msg}")


if __name__ == "__main__":
    app = AtlasToGifApp()
    app.mainloop()