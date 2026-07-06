#!/usr/bin/env python3
"""
Manhwa Panel Editor GUI — Smooth version with AI Refine
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
from pathlib import Path
import sys, os, base64, json

sys.path.insert(0, str(Path(__file__).resolve().parent))

class PanelEditor:
    PANEL_COLOR = "#00ff00"
    SELECTED_COLOR = "#ff4444"
    
    def __init__(self, root):
        self.root = root
        self.root.title("Manhwa Panel Editor")
        self.root.geometry("1200x800")
        
        self.img_path = None
        self.original = None
        self.gray = None
        self.panels = []
        self.selected_idx = -1
        self.drag_mode = None
        self.drag_start_y = 0
        self.drag_start_panel = None
        self.scale = 1.0
        self.img_display_w = 0
        self.img_display_h = 0
        self.add_mode = False
        self.add_start_y = None
        self.history = []
        self.right_click_start = None
        self.bg_image_id = None
        self.panel_rects = []
        self.handle_items = []
        
        self._build_ui()
    
    def _build_ui(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="📁 Merge Folder", command=self.merge_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📂 Open Folder", command=self.open_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Auto Detect", command=self.auto_detect).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Sel", command=self.delete_panel).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Add Panel ➕", command=self.enter_add_mode).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Undo ↩", command=self.undo_last).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Layout", command=self.save_panels).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PNGs", command=self.export_crops).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="AI Refine ✨", command=self.ai_refine).pack(side=tk.LEFT, padx=2)
        
        self.status_var = tk.StringVar(value="Open a manhwa image")
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        
        frame = ttk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        
        self.canvas = tk.Canvas(frame, bg="#222222", xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set, highlightthickness=0)
        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))
        self.canvas.bind("<Configure>", self.on_resize)
        
        self.info_var = tk.StringVar(value="")
        info = ttk.Label(self.root, textvariable=self.info_var, font=("TkDefaultFont", 9))
        info.pack(side=tk.BOTTOM, fill=tk.X, padx=5)
    
    def merge_folder(self):
        """Select folder -> stitch all images vertically -> auto-detect."""
        folder = filedialog.askdirectory(title="Select Folder with Manga Pages")
        if not folder: return
        paths = sorted([p for p in os.listdir(folder) if p.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))])
        if not paths: messagebox.showerror("Error", "No images found in folder"); return
        self.status_var.set(f"Merging {len(paths)} images..."); self.root.update()
        images = []
        for name in paths:
            img = cv2.imread(os.path.join(folder, name))
            if img is not None: images.append(img)
        if not images: messagebox.showerror("Error", "Could not read any images"); return
        min_w = min(img.shape[1] for img in images)
        resized = []
        for img in images:
            r = min_w / img.shape[1]
            h = int(img.shape[0] * r)
            resized.append(cv2.resize(img, (min_w, h)))
        self.original = np.vstack(resized)
        self.gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
        h, w = self.original.shape[:2]
        self.img_path = folder
        self.panels = []; self.selected_idx = -1
        self.status_var.set(f"Merged {len(paths)} images -> {w}x{h}px")
        self.render_background()
        self.auto_detect()

    def open_folder(self):
        """Select folder -> load first image."""
        folder = filedialog.askdirectory(title="Select Image Folder")
        if not folder: return
        files = sorted([p for p in os.listdir(folder) if p.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))])
        if not files: messagebox.showerror("Error", "No images found"); return
        path = os.path.join(folder, files[0])
        self.img_path = path
        self.original = cv2.imread(path)
        if self.original is None: messagebox.showerror("Error", "Cannot read image"); return
        self.gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
        h, w = self.original.shape[:2]
        self.panels = []; self.selected_idx = -1
        self.status_var.set(f"Loaded: {files[0]} ({w}x{h}) - {len(files)} files in folder")
        self.render_background()
        self.auto_detect()
    
    def render_background(self):
        if self.original is None: return
        h, w = self.original.shape[:2]
        cw = max(100, self.canvas.winfo_width() - 20)
        self.scale = min(cw / w, 1.0)
        self.scale = max(0.05, self.scale)
        self.img_display_w = int(w * self.scale)
        self.img_display_h = int(h * self.scale)
        
        display = cv2.resize(self.original, (self.img_display_w, self.img_display_h))
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.canvas.delete("all")
        self.bg_image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=(0, 0, self.img_display_w, self.img_display_h))
        self.redraw_panels()
    
    def redraw_panels(self):
        for rect_id, text_id in self.panel_rects:
            self.canvas.delete(rect_id); self.canvas.delete(text_id)
        for item in self.handle_items: self.canvas.delete(item)
        self.canvas.delete("marker")
        self.panel_rects = []; self.handle_items = []
        if not self.panels: return
        s = self.scale
        for i, (px, py, pw, ph) in enumerate(self.panels):
            sx, sy = int(px*s), int(py*s); sw, sh = int(pw*s), int(ph*s)
            is_sel = (i == self.selected_idx)
            color = self.SELECTED_COLOR if is_sel else self.PANEL_COLOR
            w = 3 if is_sel else 2
            rect = self.canvas.create_rectangle(sx, sy, sx+sw, sy+sh, outline=color, width=w)
            text = self.canvas.create_text(sx+5, sy+18, anchor=tk.W, text=str(i+1), fill=color, font=("TkDefaultFont", 10, "bold"))
            self.panel_rects.append((rect, text))
            if is_sel:
                self.handle_items = [
                    self.canvas.create_rectangle(sx, sy-3, sx+sw, sy+3, fill=self.SELECTED_COLOR, outline=""),
                    self.canvas.create_rectangle(sx, sy+sh-3, sx+sw, sy+sh+3, fill=self.SELECTED_COLOR, outline="")]
    
    # --- Mouse handlers ---
    def on_click(self, event):
        if self.original is None: return
        sx, sy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        ix, iy = sx/self.scale, sy/self.scale
        if self.add_mode:
            on_panel = any(px <= ix <= px+pw and py <= iy <= py+ph for px,py,pw,ph in self.panels)
            if not on_panel:
                self.add_start_y = iy; self.drag_mode = 'add_panel'
                self.status_var.set("Drag to set height, release to place"); return
            else: self.add_mode = False; self.status_var.set("Add mode OFF")
        if self.selected_idx >= 0:
            px, py, pw, ph = self.panels[self.selected_idx]; m = 8/self.scale
            if abs(iy-py) < m and ix >= px and ix <= px+pw:
                self.drag_mode = 'top_edge'; self.drag_start_y = iy; self.drag_start_panel = self.panels[self.selected_idx]; return
            if abs(iy-(py+ph)) < m and ix >= px and ix <= px+pw:
                self.drag_mode = 'bot_edge'; self.drag_start_y = iy; self.drag_start_panel = self.panels[self.selected_idx]; return
        for i in range(len(self.panels)-1, -1, -1):
            px, py, pw, ph = self.panels[i]
            if px <= ix <= px+pw and py <= iy <= py+ph:
                old = self.selected_idx; self.selected_idx = i
                self.drag_mode = 'move'; self.drag_start_y = iy; self.drag_start_panel = self.panels[i]
                if old != i: self.redraw_panels(); return
                return
        if self.selected_idx != -1: self.selected_idx = -1; self.drag_mode = None; self.redraw_panels()

    def on_drag(self, event):
        if self.drag_mode is None: return
        sx, sy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        iy = sy/self.scale
        if self.drag_mode == 'add_panel' and self.add_start_y is not None:
            h = max(20, int(abs(iy-self.add_start_y))); top = int(min(self.add_start_y, iy))
            self.redraw_panels(); s = self.scale
            self.canvas.create_rectangle(int(5*s), int(top*s), int((self.original.shape[1]-5)*s), int((top+h)*s), outline="#ffaa00", width=2, dash=(4,4), tags="ghost"); return
        if self.selected_idx < 0: return
        idx = self.selected_idx; px, py, pw, ph = self.panels[idx]
        if self.drag_mode == 'top_edge':
            ny = max(0, int(iy)); nh = max(20, int(py+ph-ny))
            if ny+nh <= py+ph: self.panels[idx] = (px, ny, pw, nh)
        elif self.drag_mode == 'bot_edge':
            nh = max(20, int(iy-py)); self.panels[idx] = (px, py, pw, nh)
        elif self.drag_mode == 'move':
            dy = int(iy-self.drag_start_y); ny = max(0, self.drag_start_panel[1]+dy)
            if idx > 0: ny = max(ny, self.panels[idx-1][1]+self.panels[idx-1][3]+5)
            if idx < len(self.panels)-1: ny = min(ny, self.panels[idx+1][1]-ph-5)
            self.panels[idx] = (px, ny, pw, ph)
        self.info_var.set(f"Panels: {len(self.panels)} | #{idx+1} selected"); self.redraw_panels()

    def on_release(self, event):
        if self.drag_mode == 'add_panel' and self.add_start_y is not None:
            sx, sy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            iy = sy/self.scale; h = max(20, int(abs(iy-self.add_start_y)))
            if h >= 20:
                self.save_state(); top = int(min(self.add_start_y, iy)); w = self.original.shape[1]
                self.panels.append((0, top, w, h)); self.panels.sort(key=lambda p: p[1])
                self.selected_idx = -1; self.add_mode = False
                self.status_var.set(f"Added panel at y={top}, h={h}px"); self.info_var.set(f"Panels: {len(self.panels)}"); self.redraw_panels()
        self.drag_mode = None; self.drag_start_panel = None; self.add_start_y = None
    
    def on_double_click(self, event):
        if self.original is None: return
        sx, sy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        ix, iy = sx/self.scale, sy/self.scale
        for i in range(len(self.panels)-1, -1, -1):
            px, py, pw, ph = self.panels[i]
            if px <= ix <= px+pw and py <= iy <= py+ph:
                self.save_state()
                del self.panels[i]
                self.selected_idx = -1
                self.info_var.set(f"Panels: {len(self.panels)}")
                self.redraw_panels()
                return
        if self.right_click_start is None:
            self.right_click_start = iy
            self.status_var.set(f"Point A: y={int(iy)}. Double-click below for Point B")
            self.redraw_panels()
            s = self.scale
            self.canvas.create_line(0, int(iy*s), self.img_display_w, int(iy*s),
                                   fill="#ffaa00", width=2, dash=(4,4), tags="marker")
        else:
            y1 = int(min(self.right_click_start, iy))
            y2 = int(max(self.right_click_start, iy))
            if y2 - y1 >= 15:
                self.save_state()
                self.panels.append((0, y1, self.original.shape[1], y2 - y1))
                self.panels.sort(key=lambda p: p[1])
                self.status_var.set(f"Panel created y={y1}-{y2}")
                self.info_var.set(f"Panels: {len(self.panels)}")
            else:
                self.status_var.set("Too small, try again")
            self.right_click_start = None
            self.redraw_panels()

    def on_right_click(self, event):
        if self.original is None: return
        sx, sy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        iy = sy / self.scale
        if self.selected_idx >= 0:
            px, py, pw, ph = self.panels[self.selected_idx]
            self.save_state()
            dist_top = abs(iy - py)
            dist_bot = abs(iy - (py + ph))
            if dist_top <= dist_bot:
                new_y = max(0, int(iy))
                new_h = max(20, ph + (py - new_y))
                self.panels[self.selected_idx] = (px, new_y, pw, new_h)
                self.status_var.set(f"Top -> y={new_y}")
            else:
                new_h = max(20, int(iy - py))
                self.panels[self.selected_idx] = (px, py, pw, new_h)
                self.status_var.set(f"Bottom -> y={int(iy)}")
            self.info_var.set(f"Panels: {len(self.panels)}")
            self.redraw_panels()

    def on_resize(self, event):
        if self.original is not None: self.render_background()

    def delete_panel(self):
        if self.selected_idx < 0: return
        self.save_state(); del self.panels[self.selected_idx]; self.selected_idx = -1
        self.info_var.set(f"Panels: {len(self.panels)}"); self.redraw_panels()

    def enter_add_mode(self):
        if self.original is None: return
        self.add_mode = True; self.selected_idx = -1
        self.status_var.set("ADD: click-drag empty space to create panel"); self.redraw_panels()

    def save_state(self):
        self.history.append([p for p in self.panels])
        if len(self.history) > 20: self.history.pop(0)

    def undo_last(self):
        if not self.history: return
        self.panels = self.history.pop(); self.selected_idx = -1
        self.info_var.set(f"Panels: {len(self.panels)}"); self.status_var.set("Undone"); self.redraw_panels()

    def auto_detect(self):
        if self.original is None: return
        self.save_state(); self.status_var.set("Detecting..."); self.root.update()
        from extractor import extract_manhwa_panels
        self.panels = extract_manhwa_panels(self.original); self.selected_idx = -1
        h, w = self.original.shape[:2]
        self.status_var.set(f"Detected: {len(self.panels)} panels"); self.info_var.set(f"Panels: {len(self.panels)}"); self.redraw_panels()

    def ai_refine(self):
        if self.original is None or not self.panels: messagebox.showinfo("Info", "Detect panels first"); return
        self.status_var.set("AI Refining..."); self.root.update()
        try:
            from google import genai
            n = len(self.panels); cols = min(5, n); rows = (n+cols-1)//cols
            montage = np.ones((rows*120, cols*200, 3), dtype=np.uint8)*30
            for i, (x, y, pw, ph) in enumerate(self.panels):
                crop = self.original[y:y+ph, x:x+pw]
                if crop.size == 0: continue
                th = cv2.resize(crop, (190, 90)); r, c = i//cols, i%cols
                th = th[:montage.shape[0]-(r*120+5), :montage.shape[1]-(c*200+5)]
                montage[r*120+5:r*120+5+th.shape[0], c*200+5:c*200+5+th.shape[1]] = th
                cv2.putText(montage, f'#{i+1}', (c*200+5, r*120+112), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,0), 1)
            _, buf = cv2.imencode('.jpg', montage, [cv2.IMWRITE_JPEG_QUALITY, 85])
            img_b64 = base64.b64encode(buf).decode()
            panels_info = '\n'.join([f'Panel {i+1}: y={y}-{y+ph}, h={ph}px' for i,(x,y,pw,ph) in enumerate(self.panels)])
            import os
            api_key = os.environ.get("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY"
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[
                'You are a manhwa panel expert. Review thumbnails numbered 1-N. RULES: 1) Merge mostly-white speech bubble panels into parent 2) Merge tiny panels <40px 3) Merge adjacent panels that clearly belong together 4) If ONE panel has 2 scenes suggest split y. Return JSON ONLY: {"merges":[[src,dst],...], "splits":[[num,y],...], "deletes":[num,...], "summary":"text"}',
                f'Image: {self.original.shape[1]}x{self.original.shape[0]}. Panels ({n}):\n{panels_info}',
                genai.types.Part.from_bytes(data=base64.b64decode(img_b64), mime_type='image/jpeg')])
            text = response.text.strip()
            import json
            if '```json' in text: text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text: text = text.split('```')[1].split('```')[0].strip()
            result = json.loads(text); changes = []
            for d in sorted(result.get('deletes', []), reverse=True):
                if 1 <= d <= len(self.panels): del self.panels[d-1]; changes.append(f"Deleted #{d}")
            for src, dst in sorted(result.get('merges', []), key=lambda x: -max(x)):
                if 1 <= src <= len(self.panels) and 1 <= dst <= len(self.panels) and self.panels[src-1] is not None and self.panels[dst-1] is not None:
                    sx,sy,sw,sh = self.panels[src-1]; dx,dy,dw,dh = self.panels[dst-1]
                    self.panels[dst-1] = (dx, min(dy,sy), dw, max(dy+dh,sy+sh)-min(dy,sy))
                    self.panels[src-1] = None; changes.append(f"Merged #{src}->#{dst}")
            self.panels = [p for p in self.panels if p is not None]
            for pnum, split_y in result.get('splits', []):
                if 1 <= pnum <= len(self.panels):
                    px,py,pw,ph = self.panels[pnum-1]
                    if py < split_y < py+ph and split_y-py >= 30 and (py+ph)-split_y >= 30:
                        self.panels[pnum-1] = (px,py,pw,split_y-py)
                        self.panels.insert(pnum, (px,split_y,pw,(py+ph)-split_y))
                        changes.append(f"Split #{pnum}")
            self.selected_idx = -1; self.redraw_panels()
            self.status_var.set(f"AI: {result.get('summary','Done')}")
            self.info_var.set(f"Panels: {len(self.panels)} | {' | '.join(changes[:3]) or 'No changes'}")
        except Exception as e: messagebox.showerror("AI Error", str(e)[:300]); self.status_var.set("AI Refine failed")

    def save_panels(self):
        if not self.panels: return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path: return
        with open(path, 'w') as f:
            f.write(f"# Source: {self.img_path}\n# Panels: {len(self.panels)}\n\n")
            for i, (x, y, w, h) in enumerate(self.panels): f.write(f"panel_{i+1:04d} {x} {y} {w} {h}\n")
        self.status_var.set(f"Saved: {Path(path).name}")

    def export_crops(self):
        if self.original is None or not self.panels: return
        out_dir = filedialog.askdirectory(title="Select Output Folder")
        if not out_dir: return
        p = Path(out_dir); p.mkdir(parents=True, exist_ok=True)
        for i, (x, y, w, h) in enumerate(self.panels):
            cv2.imwrite(str(p / f"panel_{i+1:04d}.png"), self.original[y:y+h, x:x+w])
        self.status_var.set(f"Exported {len(self.panels)} panels to {out_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PanelEditor(root)
    root.mainloop()
