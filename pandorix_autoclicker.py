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
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from pynput.mouse import Controller as MouseController, Button as MouseButton, Listener as MouseListener
    from pynput import keyboard
except ImportError:
    MouseController = None
    MouseButton = None
    MouseListener = None
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
        self.keyboard_ctrl = keyboard.Controller() if keyboard else None

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

    def _mouse_button_from_value(self, value):
        mapping = {"left": MouseButton.left, "right": MouseButton.right, "middle": MouseButton.middle}
        if value == "x1" and hasattr(MouseButton, "x1"):
            return MouseButton.x1
        if value == "x2" and hasattr(MouseButton, "x2"):
            return MouseButton.x2
        return mapping.get(value, MouseButton.left)

    def _string_to_key(self, name):
        """Pretvara sacuvani naziv tipke (npr. 'ESC', 'F6', 'A') nazad u pynput objekat."""
        if keyboard is None:
            return name
        special = getattr(keyboard.Key, name.lower(), None)
        if special is not None:
            return special
        return name.lower()

    def _get_target_hwnd(self):
        """Vraca HWND odabranog prozora, bez oslanjanja na fokus."""
        if not HAS_WIN32:
            return None
        return self.app.get_selected_hwnd()

    def _background_mouse_click(self, hwnd, button_name, double=False):
        """Salje Windows mouse poruku direktno ciljanom prozoru.
        Ne pomjera fizicki mis i korisnik moze normalno koristiti druge aplikacije.
        """
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False

        point = self.app.get_background_point()
        if point is None:
            return False

        x, y = point
        lparam = (int(y) << 16) | (int(x) & 0xFFFF)

        down_up = {
            "left": (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP),
            "right": (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP),
            "middle": (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP),
        }
        if button_name not in down_up:
            return False

        down, up = down_up[button_name]
        wparam = {
            "left": win32con.MK_LBUTTON,
            "right": win32con.MK_RBUTTON,
            "middle": win32con.MK_MBUTTON,
        }[button_name]

        try:
            win32gui.PostMessage(hwnd, down, wparam, lparam)
            win32gui.PostMessage(hwnd, up, 0, lparam)
            if double:
                time.sleep(0.01)
                win32gui.PostMessage(hwnd, down, wparam, lparam)
                win32gui.PostMessage(hwnd, up, 0, lparam)
            return True
        except Exception:
            return False

    def _perform_action(self):
        kind = self.app.click_keybind_type.get()
        value = self.app.click_keybind_value.get()
        double = self.app.double_click.get()

        # Background Window mode: mouse clicks go directly to the selected HWND.
        if self.app.background_mode.get() and kind == "mouse":
            hwnd = self._get_target_hwnd()
            if hwnd:
                return self._background_mouse_click(hwnd, value, double)
            return False

        if kind == "keyboard":
            if self.keyboard_ctrl is None:
                return False
            key_obj = self._string_to_key(value)
            try:
                self.keyboard_ctrl.press(key_obj)
                self.keyboard_ctrl.release(key_obj)
                if double:
                    self.keyboard_ctrl.press(key_obj)
                    self.keyboard_ctrl.release(key_obj)
                return True
            except Exception:
                return False
        else:
            button = self._mouse_button_from_value(value)
            self.mouse.click(button, 2 if double else 1)
            return True

    def _target_window_active(self):
        """U starom modu provjerava fokus; background modu fokus nije potreban."""
        if self.app.background_mode.get():
            hwnd = self._get_target_hwnd()
            return bool(hwnd and win32gui.IsWindow(hwnd))

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

            if self._target_window_active():
                if self._perform_action():
                    self.app.increment_click_count()
                    self.app.set_waiting_for_window(False)
                else:
                    self.app.set_waiting_for_window(True)
            else:
                self.app.set_waiting_for_window(True)

            time.sleep(interval if interval > 0 else 0.01)


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

        self.click_keybind_type = tk.StringVar(value="mouse")   # "mouse" ili "keyboard"
        self.click_keybind_value = tk.StringVar(value="left")   # npr. "left"/"right"/"middle" ili "ESC"
        self.keybind_display_var = tk.StringVar(value="Lijevi klik")
        self._capturing_keybind = False
        self.cps_var = tk.StringVar(value="10")
        self.double_click = tk.BooleanVar(value=False)
        self.restrict_to_window = tk.BooleanVar(value=False)
        self.selected_window = tk.StringVar(value="(nije odabran)")
        self.selected_hwnd = None
        self.background_mode = tk.BooleanVar(value=False)
        self.background_x = tk.StringVar(value="0")
        self.background_y = tk.StringVar(value="0")
        self.hotkey_var = tk.StringVar(value="F6")

        self._load_settings()
        self._build_ui()
        self._update_keybind_display()
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

        keybind_row = tk.Frame(settings_panel, bg=BG_PANEL)
        keybind_row.pack(fill="x", padx=15, pady=6)
        tk.Label(keybind_row, text="Keybind:", fg=TEXT_MAIN, bg=BG_PANEL,
                 font=("Segoe UI", 10)).pack(side="left")
        self.keybind_btn_text = tk.StringVar(value="Klikni")
        self.keybind_btn = tk.Button(
            keybind_row, textvariable=self.keybind_btn_text, command=self._start_keybind_capture,
            bg=BG_INPUT, fg=ACCENT, relief="flat", width=12, cursor="hand2",
            activebackground=ACCENT, activeforeground="white", font=("Segoe UI", 10, "bold")
        )
        self.keybind_btn.pack(side="right", ipady=3)

        self.keybind_current_label = tk.Label(
            keybind_row, textvariable=self.keybind_display_var, fg=TEXT_MUTED, bg=BG_PANEL,
            font=("Segoe UI", 9)
        )
        self.keybind_current_label.pack(side="right", padx=(0, 8))

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
            window_panel, "Ograniči na odabrani prozor (samo kad je aktivan)",
            self.restrict_to_window
        )

        self._row_checkbox(
            window_panel, "BACKGROUND MODE — radi i kad prozor nije aktivan",
            self.background_mode
        )

        picker_row = tk.Frame(window_panel, bg=BG_PANEL)
        picker_row.pack(fill="x", padx=15, pady=(0, 6))

        self.window_combo = ttk.Combobox(
            picker_row, textvariable=self.selected_window, state="readonly", width=24
        )
        self.window_combo.pack(side="left", fill="x", expand=True, ipady=3)
        self.window_combo.bind("<<ComboboxSelected>>", lambda e: self._remember_selected_window())

        refresh_btn = tk.Button(
            picker_row, text="⟳", command=self._refresh_window_list,
            bg=BG_INPUT, fg=TEXT_MAIN, relief="flat", width=3,
            activebackground=ACCENT
        )
        refresh_btn.pack(side="right", padx=(8, 0))

        pos_row = tk.Frame(window_panel, bg=BG_PANEL)
        pos_row.pack(fill="x", padx=15, pady=(2, 6))

        tk.Label(pos_row, text="Pozicija unutar prozora:", fg=TEXT_MAIN, bg=BG_PANEL,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Label(pos_row, text="X", fg=TEXT_MUTED, bg=BG_PANEL).pack(side="left", padx=(10, 2))
        tk.Entry(pos_row, textvariable=self.background_x, width=6, bg=BG_INPUT,
                 fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat",
                 justify="center").pack(side="left")
        tk.Label(pos_row, text="Y", fg=TEXT_MUTED, bg=BG_PANEL).pack(side="left", padx=(8, 2))
        tk.Entry(pos_row, textvariable=self.background_y, width=6, bg=BG_INPUT,
                 fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat",
                 justify="center").pack(side="left")

        set_pos_btn = tk.Button(
            pos_row, text="Postavi poziciju mišem", command=self._capture_background_position,
            bg=BG_INPUT, fg=ACCENT, relief="flat", cursor="hand2",
            activebackground=ACCENT, activeforeground="white"
        )
        set_pos_btn.pack(side="right")

        self.window_hint = tk.Label(
            window_panel,
            text="Background: odaberi prozor, klikni 'Postavi poziciju mišem', pa START. "
                 "Pandorix tada šalje klikove direktno prozoru bez pomjeranja miša.",
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
        self._window_map = {title: hwnd for hwnd, title in windows}
        titles = list(self._window_map.keys())
        if not titles:
            titles = ["(Windows funkcija - nedostupno van Windows-a)"]
        current = self.selected_window.get()
        self.window_combo["values"] = titles
        if current not in titles and titles:
            self.selected_window.set(titles[0])
        self._remember_selected_window()

    def _remember_selected_window(self):
        self.selected_hwnd = getattr(self, "_window_map", {}).get(
            self.selected_window.get()
        )

    def get_selected_hwnd(self):
        self._remember_selected_window()
        return self.selected_hwnd

    def get_background_point(self):
        try:
            return int(float(self.background_x.get())), int(float(self.background_y.get()))
        except (ValueError, TypeError):
            return None

    def _capture_background_position(self):
        """Snima trenutnu poziciju misa kao koordinatu unutar odabranog prozora."""
        if not HAS_WIN32:
            messagebox.showerror(APP_NAME, "Background mode zahtijeva Windows + pywin32.")
            return

        hwnd = self.get_selected_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            messagebox.showwarning(APP_NAME, "Prvo odaberi ciljani prozor.")
            return

        try:
            import pyautogui
            screen_x, screen_y = pyautogui.position()
        except ImportError:
            # Bez dodatne biblioteke koristimo Win32 API za poziciju kursora.
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            screen_x, screen_y = pt.x, pt.y

        try:
            client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
            self.background_x.set(str(client_x))
            self.background_y.set(str(client_y))
            self.background_mode.set(True)
            self.window_hint.config(
                text=f"Background pozicija postavljena: X={client_x}, Y={client_y}. "
                     "Možeš sada koristiti druge aplikacije i pokrenuti START."
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Ne mogu postaviti poziciju.\n\n{exc}")

    def _on_toggle(self):
        if not self.engine.running and self.background_mode.get():
            if not HAS_WIN32:
                messagebox.showerror(APP_NAME, "Background mode radi samo na Windowsu.")
                return
            if not self.get_selected_hwnd():
                messagebox.showwarning(APP_NAME, "Odaberi ciljani prozor prije START-a.")
                return
            if self.click_keybind_type.get() != "mouse":
                messagebox.showwarning(
                    APP_NAME,
                    "Background mode trenutno podržava mouse klikove. "
                    "Za tastaturu koristi normalni način rada."
                )
                return
            if self.get_background_point() is None:
                messagebox.showwarning(APP_NAME, "Unesi ispravne X/Y koordinate.")
                return
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
            if self._capturing_hotkey or self._capturing_keybind:
                return  # dok snimamo, ne pokrecemo/pauziramo klikanje
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

    def _mouse_label(self, value):
        mapping = {
            "left": "Lijevi klik", "right": "Desni klik", "middle": "Srednji klik",
            "x1": "Bočno dugme 1", "x2": "Bočno dugme 2",
        }
        return mapping.get(value, value)

    def _update_keybind_display(self):
        kind = self.click_keybind_type.get()
        value = self.click_keybind_value.get()
        if kind == "mouse":
            self.keybind_display_var.set(self._mouse_label(value))
        else:
            self.keybind_display_var.set(value)

    def _start_keybind_capture(self):
        """Ceka SLEDECI unos - bilo tipku na tastaturi ili klik misem - i vezuje ga kao keybind."""
        if self._capturing_keybind or self._capturing_hotkey:
            return
        if keyboard is None or MouseListener is None:
            messagebox.showerror(
                APP_NAME,
                "Nedostaje 'pynput' biblioteka. Instaliraj je sa: pip install pynput"
            )
            return

        self._capturing_keybind = True
        self.keybind_btn_text.set("Pritisni...")
        self.keybind_btn.config(bg=ACCENT, fg="white")

        captured = {"done": False}

        def stop_all():
            try:
                kb_listener.stop()
            except Exception:
                pass
            try:
                ms_listener.stop()
            except Exception:
                pass

        def on_key_press(key):
            if captured["done"]:
                return False
            captured["done"] = True
            key_name = self._key_to_name(key)
            self.root.after(0, lambda: self._finish_keybind_capture("keyboard", key_name))
            stop_all()
            return False

        def on_mouse_click(x, y, button, pressed):
            if captured["done"]:
                return False
            if not pressed:
                return True  # cekamo pritisak (press), ne otpustanje (release)
            captured["done"] = True
            btn_name = str(button).replace("Button.", "")
            self.root.after(0, lambda: self._finish_keybind_capture("mouse", btn_name))
            stop_all()
            return False

        try:
            kb_listener = keyboard.Listener(on_press=on_key_press)
            ms_listener = MouseListener(on_click=on_mouse_click)
            kb_listener.daemon = True
            ms_listener.daemon = True
            kb_listener.start()
            ms_listener.start()
        except Exception:
            self._capturing_keybind = False
            self.keybind_btn_text.set("Klikni")

    def _finish_keybind_capture(self, kind, value):
        self.click_keybind_type.set(kind)
        self.click_keybind_value.set(value)
        self._update_keybind_display()
        self.keybind_btn_text.set("Klikni")
        self.keybind_btn.config(bg=BG_INPUT, fg=ACCENT)
        self._capturing_keybind = False

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.click_keybind_type.set(data.get("click_keybind_type", "mouse"))
                self.click_keybind_value.set(data.get("click_keybind_value", "left"))
                self.cps_var.set(str(data.get("cps", "10")))
                self.double_click.set(data.get("double_click", False))
                self.restrict_to_window.set(data.get("restrict_to_window", False))
                self.selected_window.set(data.get("selected_window", "(nije odabran)"))
                self.background_mode.set(data.get("background_mode", False))
                self.background_x.set(str(data.get("background_x", "0")))
                self.background_y.set(str(data.get("background_y", "0")))
                self.hotkey_var.set(data.get("hotkey", "F6"))
            except Exception:
                pass

    def _save_settings(self):
        data = {
            "click_keybind_type": self.click_keybind_type.get(),
            "click_keybind_value": self.click_keybind_value.get(),
            "cps": self.cps_var.get(),
            "double_click": self.double_click.get(),
            "restrict_to_window": self.restrict_to_window.get(),
            "selected_window": self.selected_window.get(),
            "background_mode": self.background_mode.get(),
            "background_x": self.background_x.get(),
            "background_y": self.background_y.get(),
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

    try:
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT, background=BG_INPUT, foreground=TEXT_MAIN,
            arrowcolor=ACCENT, bordercolor=BG_PANEL, lightcolor=BG_INPUT, darkcolor=BG_INPUT,
            selectbackground=BG_INPUT, selectforeground=TEXT_MAIN, relief="flat",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT), ("!disabled", BG_INPUT)],
            foreground=[("readonly", TEXT_MAIN)],
            background=[("readonly", BG_INPUT)],
            bordercolor=[("focus", ACCENT)],
        )
        root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        root.option_add("*TCombobox*Listbox.foreground", TEXT_MAIN)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", "white")
        root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")
    except Exception:
        pass

    app = PandorixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
