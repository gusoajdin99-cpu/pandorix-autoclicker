"""
Pandorix AutoClicker
---------------------
Windows autoclicker sa mogucnoscu ogranicavanja rada na odabrani prozor
(npr. samo dok je Roblox aktivan prozor).

Autor build-a: generisano za korisnika.
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from pynput.mouse import Controller as MouseController, Button as MouseButton
    from pynput import keyboard
except ImportError:
    MouseController = None
    MouseButton = None
    keyboard = None

# win32gui / win32process su Windows-only (dio pywin32 paketa).
try:
    import win32gui
    import win32con
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Sistemske/pomocne klase prozora koje ne predstavljaju stvarne pokrenute
# aplikacije - filtriramo ih da lista bude cista.
_SYSTEM_WINDOW_CLASSES = {
    "Progman", "Button", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "MultitaskingViewFrame",
    "TopLevelWindowForOverflowXamlIsland", "XamlExplorerHostIslandWindow",
    "SysShadow", "tooltips_class32", "NotifyIconOverflowWindow",
    "DesktopWindowXamlSource", "ForegroundStaging", "MSCTFIME UI", "IME",
}

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

APP_NAME = "Pandorix AutoClicker"
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "pandorix_settings.json")

# ---- Boje / tema (tamna tema sa ljubicasto-plavim akcentom) ----
BG_MAIN = "#12121c"
BG_PANEL = "#1b1b2b"
BG_INPUT = "#242438"
ACCENT = "#8b5cf6"
ACCENT_HOVER = "#a78bfa"
TEXT_MAIN = "#f2f2f7"
TEXT_MUTED = "#9a9ab0"
GREEN = "#4ade80"
RED = "#f87171"


class WindowPicker:
    """Pomocna klasa za listanje otvorenih prozora na Windowsu."""

    @staticmethod
    def _is_real_app_window(hwnd):
        """Filtrira sistemske/pozadinske prozore koji nisu stvarno pokrenute aplikacije."""
        if not win32gui.IsWindowVisible(hwnd):
            return False

        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return False

        class_name = win32gui.GetClassName(hwnd)
        if class_name in _SYSTEM_WINDOW_CLASSES:
            return False

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        is_tool_window = bool(ex_style & win32con.WS_EX_TOOLWINDOW)
        is_app_window = bool(ex_style & win32con.WS_EX_APPWINDOW)

        # Tool-window prozori se obicno ne pojavljuju na taskbaru - preskoci ih
        # osim ako su eksplicitno oznaceni kao app-window.
        if is_tool_window and not is_app_window:
            return False

        # Prozori koji imaju "vlasnika" (owner) obicno su popup/dijaloski
        # prozori nekog drugog prozora, ne samostalne pokrenute aplikacije.
        owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
        if owner != 0 and not is_app_window:
            return False

        # Minimizirani/skriveni (cloaked) UWP prozori - preskoci ako mozemo provjeriti.
        try:
            import ctypes
            DWMWA_CLOAKED = 14
            cloaked = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            if cloaked.value != 0:
                return False
        except Exception:
            pass

        return True

    @staticmethod
    def list_windows():
        results = []
        if not HAS_WIN32:
            return results

        def callback(hwnd, extra):
            if WindowPicker._is_real_app_window(hwnd):
                title = win32gui.GetWindowText(hwnd)
                results.append((hwnd, title))
            return True

        win32gui.EnumWindows(callback, None)
        return results

    @staticmethod
    def get_foreground_title():
        if not HAS_WIN32:
            return None
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except Exception:
            return None


class AutoClickerEngine:
    """Logika klikanja - radi u posebnom threadu."""

    def __init__(self, app):
        self.app = app
        self.running = False
        self.thread = None
        self.mouse = MouseController() if MouseController else None

    def start(self):
        if self.running:
            return
        if self.mouse is None:
            messagebox.showerror(
                APP_NAME,
                "Nedostaje 'pynput' biblioteka. Instaliraj je sa: pip install pynput"
            )
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.app.set_status(True)

    def stop(self):
        self.running = False
        self.app.set_status(False)

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def _get_button(self):
        mapping = {
            "Lijevi klik": MouseButton.left,
            "Desni klik": MouseButton.right,
            "Srednji klik": MouseButton.middle,
        }
        return mapping.get(self.app.click_type.get(), MouseButton.left)

    def _target_window_active(self):
        """Provjerava da li je odabrani prozor trenutno aktivan (fokusiran)."""
        if not self.app.restrict_to_window.get():
            return True
        target = self.app.selected_window.get()
        if not target or target == "(nije odabran)":
            return True
        if not HAS_WIN32:
            return True
        current = WindowPicker.get_foreground_title()
        if current is None:
            return False
        # Poredimo dio naziva (contains) da bi radilo i ako se naslov malo mijenja
        return target.lower() in current.lower()

    def _loop(self):
        while self.running:
            try:
                cps = float(self.app.cps_var.get())
                if cps <= 0:
                    cps = 1
            except ValueError:
                cps = 1

            interval = 1.0 / cps
            double_click = self.app.double_click.get()

            if self._target_window_active():
                button = self._get_button()
                self.mouse.click(button, 2 if double_click else 1)
                self.app.increment_click_count()
            else:
                # Prozor nije aktivan - pauziramo klikanje ali ostajemo "running"
                self.app.set_waiting_for_window(True)
                time.sleep(0.15)
                continue

            self.app.set_waiting_for_window(False)
            time.sleep(interval)


class PandorixApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.configure(bg=BG_MAIN)
        self.root.geometry("440x600")
        self.root.minsize(400, 560)

        self.click_count = 0
        self.engine = AutoClickerEngine(self)
        self._capturing_hotkey = False

        self.click_type = tk.StringVar(value="Lijevi klik")
        self.cps_var = tk.StringVar(value="10")
        self.double_click = tk.BooleanVar(value=False)
        self.restrict_to_window = tk.BooleanVar(value=False)
        self.selected_window = tk.StringVar(value="(nije odabran)")
        self.hotkey_var = tk.StringVar(value="F6")

        self._load_settings()
        self._build_ui()
        self._setup_hotkey_listener()
        self._refresh_window_list()

    # ---------------- UI ----------------

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG_MAIN)
        header.pack(fill="x", padx=20, pady=(20, 10))

        logo_img = self._load_logo_image()
        if logo_img is not None:
            logo_label = tk.Label(header, image=logo_img, bg=BG_MAIN)
            logo_label.image = logo_img  # referenca da GC ne obrise sliku
            logo_label.pack(side="left", padx=(0, 12))

        title_box = tk.Frame(header, bg=BG_MAIN)
        title_box.pack(side="left", anchor="w")

        title = tk.Label(
            title_box, text="PANDORIX", font=("Segoe UI", 22, "bold"),
            fg=ACCENT, bg=BG_MAIN
        )
        title.pack(anchor="w")
        subtitle = tk.Label(
            title_box, text="AutoClicker", font=("Segoe UI", 12),
            fg=TEXT_MUTED, bg=BG_MAIN
        )
        subtitle.pack(anchor="w")

        # ---- Status kartica ----
        status_panel = tk.Frame(self.root, bg=BG_PANEL)
        status_panel.pack(fill="x", padx=20, pady=10)

        self.status_dot = tk.Label(status_panel, text="●", font=("Segoe UI", 16), fg=RED, bg=BG_PANEL)
        self.status_dot.pack(side="left", padx=(15, 5), pady=15)

        self.status_label = tk.Label(
            status_panel, text="Zaustavljen", font=("Segoe UI", 12, "bold"),
            fg=TEXT_MAIN, bg=BG_PANEL
        )
        self.status_label.pack(side="left", pady=15)

        self.count_label = tk.Label(
            status_panel, text="Klikova: 0", font=("Segoe UI", 10),
            fg=TEXT_MUTED, bg=BG_PANEL
        )
        self.count_label.pack(side="right", padx=15, pady=15)

        # ---- Podesavanja ----
        settings_panel = tk.Frame(self.root, bg=BG_PANEL)
        settings_panel.pack(fill="x", padx=20, pady=10)
        self._section_label(settings_panel, "Podešavanja klika")

        self._row_dropdown(
            settings_panel, "Dugme miša:", self.click_type,
            ["Lijevi klik", "Desni klik", "Srednji klik"]
        )

        self._row_checkbox(settings_panel, "Dupli klik", self.double_click)

        cps_row = tk.Frame(settings_panel, bg=BG_PANEL)
        cps_row.pack(fill="x", padx=15, pady=6)
        tk.Label(cps_row, text="Klikova u sekundi (CPS):", fg=TEXT_MAIN, bg=BG_PANEL,
                 font=("Segoe UI", 10)).pack(side="left")
        cps_entry = tk.Entry(cps_row, textvariable=self.cps_var, width=8, bg=BG_INPUT,
                              fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat",
                              justify="center")
        cps_entry.pack(side="right", ipady=4)

        hotkey_row = tk.Frame(settings_panel, bg=BG_PANEL)
        hotkey_row.pack(fill="x", padx=15, pady=(6, 15))
        tk.Label(hotkey_row, text="Prečica za Start/Pauza:", fg=TEXT_MAIN, bg=BG_PANEL,
                 font=("Segoe UI", 10)).pack(side="left")
        self.hotkey_btn_text = tk.StringVar(value="Klikni")
        self.hotkey_btn = tk.Button(
            hotkey_row, textvariable=self.hotkey_btn_text, command=self._start_hotkey_capture,
            bg=BG_INPUT, fg=ACCENT, relief="flat", width=12, cursor="hand2",
            activebackground=ACCENT, activeforeground="white", font=("Segoe UI", 10, "bold")
        )
        self.hotkey_btn.pack(side="right", ipady=3)

        self.hotkey_current_label = tk.Label(
            hotkey_row, textvariable=self.hotkey_var, fg=TEXT_MUTED, bg=BG_PANEL,
            font=("Segoe UI", 9)
        )
        self.hotkey_current_label.pack(side="right", padx=(0, 8))

        # ---- Ciljani prozor (posebna Pandorix funkcija) ----
        window_panel = tk.Frame(self.root, bg=BG_PANEL)
        window_panel.pack(fill="x", padx=20, pady=10)
        self._section_label(window_panel, "Ciljani prozor")

        self._row_checkbox(
            window_panel, "Radi samo kada je odabrani prozor aktivan",
            self.restrict_to_window
        )

        picker_row = tk.Frame(window_panel, bg=BG_PANEL)
        picker_row.pack(fill="x", padx=15, pady=(0, 10))

        self.window_combo = ttk.Combobox(
            picker_row, textvariable=self.selected_window, state="readonly", width=24
        )
        self.window_combo.pack(side="left", fill="x", expand=True, ipady=3)

        refresh_btn = tk.Button(
            picker_row, text="⟳", command=self._refresh_window_list,
            bg=BG_INPUT, fg=TEXT_MAIN, relief="flat", width=3,
            activebackground=ACCENT
        )
        refresh_btn.pack(side="right", padx=(8, 0))

        self.window_hint = tk.Label(
            window_panel,
            text="Otvori Roblox (ili bilo koji program), klikni ⟳, pa ga odaberi sa liste.",
            fg=TEXT_MUTED, bg=BG_PANEL, font=("Segoe UI", 8), wraplength=380, justify="left"
        )
        self.window_hint.pack(anchor="w", padx=15, pady=(0, 15))

        # ---- Start/Pause dugme ----
        control_panel = tk.Frame(self.root, bg=BG_MAIN)
        control_panel.pack(fill="x", padx=20, pady=15)

        self.toggle_btn = tk.Button(
            control_panel, text="▶  START", command=self._on_toggle,
            font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
            activebackground=ACCENT_HOVER, relief="flat", pady=12, cursor="hand2"
        )
        self.toggle_btn.pack(fill="x")

        footer = tk.Label(
            self.root, text=f"Prečica: {self.hotkey_var.get()}  |  Pandorix © 2026",
            fg=TEXT_MUTED, bg=BG_MAIN, font=("Segoe UI", 8)
        )
        footer.pack(pady=(0, 10))
        self.footer_label = footer
        self.hotkey_var.trace_add("write", lambda *args: self._update_footer())

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_logo_image(self):
        """Ucitava logo.png (ako postoji) kao malu sliku za zaglavlje prozora."""
        if not HAS_PIL:
            return None
        logo_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logo.png")
        if not os.path.exists(logo_path):
            return None
        try:
            img = Image.open(logo_path).convert("RGBA")
            size = 56
            img = img.resize((size, size), Image.LANCZOS)

            # Napravi kruznu masku da logo lijepo izgleda u zaglavlju
            mask = Image.new("L", (size, size), 0)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)

            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _section_label(self, parent, text):
        lbl = tk.Label(parent, text=text, fg=ACCENT, bg=BG_PANEL, font=("Segoe UI", 10, "bold"))
        lbl.pack(anchor="w", padx=15, pady=(15, 5))

    def _row_dropdown(self, parent, label, variable, options):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=15, pady=6)
        tk.Label(row, text=label, fg=TEXT_MAIN, bg=BG_PANEL, font=("Segoe UI", 10)).pack(side="left")
        combo = ttk.Combobox(row, textvariable=variable, values=options, state="readonly", width=14)
        combo.pack(side="right")
        return combo

    def _row_checkbox(self, parent, label, variable):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=15, pady=6)
        chk = tk.Checkbutton(
            row, text=label, variable=variable, fg=TEXT_MAIN, bg=BG_PANEL,
            selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=TEXT_MAIN,
            font=("Segoe UI", 10), anchor="w"
        )
        chk.pack(side="left", fill="x")
        return chk

    # ---------------- Logika ----------------

    def _refresh_window_list(self):
        windows = WindowPicker.list_windows()
        titles = [w[1] for w in windows]
        if not titles:
            titles = ["(Windows funkcija - nedostupno van Windows-a)"]
        current = self.selected_window.get()
        self.window_combo["values"] = titles
        if current not in titles and titles:
            self.selected_window.set(titles[0])

    def _on_toggle(self):
        self.engine.toggle()

    def set_status(self, running):
        if running:
            self.status_dot.config(fg=GREEN)
            self.status_label.config(text="Aktivan")
            self.toggle_btn.config(text="⏸  PAUZA", bg=RED, activebackground="#fca5a5")
        else:
            self.status_dot.config(fg=RED)
            self.status_label.config(text="Zaustavljen")
            self.toggle_btn.config(text="▶  START", bg=ACCENT, activebackground=ACCENT_HOVER)

    def set_waiting_for_window(self, waiting):
        if waiting:
            self.status_label.config(text="Čeka ciljani prozor...")
        elif self.engine.running:
            self.status_label.config(text="Aktivan")

    def _update_footer(self):
        self.footer_label.config(text=f"Prečica: {self.hotkey_var.get()}  |  Pandorix © 2026")

    def increment_click_count(self):
        self.click_count += 1
        # UI update sa glavnog threada preko 'after' zbog thread-safety
        self.root.after(0, lambda: self.count_label.config(text=f"Klikova: {self.click_count}"))

    def _key_to_name(self, key):
        try:
            if hasattr(key, "char") and key.char:
                return key.char.upper()
            return str(key).replace("Key.", "").upper()
        except Exception:
            return str(key)

    def _setup_hotkey_listener(self):
        if keyboard is None:
            return

        def on_press(key):
            if self._capturing_hotkey:
                return  # dok snimamo novu precicu, ne pokrecemo/pauziramo klikanje
            key_name = self._key_to_name(key)
            if key_name == self.hotkey_var.get().upper():
                self.root.after(0, self._on_toggle)

        try:
            listener = keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except Exception:
            pass

    def _start_hotkey_capture(self):
        """Cim korisnik klikne dugme, cekamo sledeci pritisak tipke i vezujemo ga kao precicu."""
        if self._capturing_hotkey:
            return
        if keyboard is None:
            messagebox.showerror(
                APP_NAME,
                "Nedostaje 'pynput' biblioteka. Instaliraj je sa: pip install pynput"
            )
            return

        self._capturing_hotkey = True
        self.hotkey_btn_text.set("Pritisni tipku...")
        self.hotkey_btn.config(bg=ACCENT, fg="white")

        def on_capture(key):
            key_name = self._key_to_name(key)
            self.root.after(0, lambda: self._finish_hotkey_capture(key_name))
            return False  # zaustavlja ovaj (jednokratni) listener

        try:
            capture_listener = keyboard.Listener(on_press=on_capture)
            capture_listener.daemon = True
            capture_listener.start()
        except Exception:
            self._capturing_hotkey = False
            self.hotkey_btn_text.set("Klikni")

    def _finish_hotkey_capture(self, key_name):
        self.hotkey_var.set(key_name)
        self.hotkey_btn_text.set("Klikni")
        self.hotkey_btn.config(bg=BG_INPUT, fg=ACCENT)
        self._capturing_hotkey = False

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.click_type.set(data.get("click_type", "Lijevi klik"))
                self.cps_var.set(str(data.get("cps", "10")))
                self.double_click.set(data.get("double_click", False))
                self.restrict_to_window.set(data.get("restrict_to_window", False))
                self.selected_window.set(data.get("selected_window", "(nije odabran)"))
                self.hotkey_var.set(data.get("hotkey", "F6"))
            except Exception:
                pass

    def _save_settings(self):
        data = {
            "click_type": self.click_type.get(),
            "cps": self.cps_var.get(),
            "double_click": self.double_click.get(),
            "restrict_to_window": self.restrict_to_window.get(),
            "selected_window": self.selected_window.get(),
            "hotkey": self.hotkey_var.get(),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _on_close(self):
        self.engine.stop()
        self._save_settings()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        # Ako postoji logo.ico u istom folderu, koristi ga kao ikonu aplikacije/prozora
        icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    app = PandorixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
