import os
import re
import json
import base64
import zlib
import urllib.parse
import threading
import time
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from bs4 import BeautifulSoup
import customtkinter as ctk

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


# ============================================================
# KONFIGURASI PATH CHROME & PROFIL PENGGUNA
# ============================================================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Menggunakan profil Chrome default agar ekstensi ABDM/IDM langsung aktif
USER_PROFILE_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
CHROME_DRIVER_PATH = os.path.join(os.getcwd(), "chromedriver.exe")
DEBUG_PORT = "9222"

driver = None
is_running = False
found_links_data = []  # List of PartRowItem (kompatibel sebagai tuple: clean_name, link_url, tk_boolean_var)
focused_index = None   # Index part yang sedang aktif/fokus (kursor)
anchor_index = None    # Index acuan titik awal saat seleksi rentang (Shift + Klik)

log_textbox = None
autoscroll_var = None
selection_counter_label = None
range_from_entry = None
range_to_entry = None


class PartRowItem:
    """Representasi satu baris part dengan kompatibilitas tuple (name, url, var) dan widget UI."""
    def __init__(self, index, name, link, var, frame, checkbox, label, badge, is_optional):
        self.index = index
        self.name = name
        self.link = link
        self.var = var
        self.frame = frame
        self.checkbox = checkbox
        self.label = label
        self.badge = badge
        self.is_optional = is_optional

    def __getitem__(self, idx):
        if idx == 0:
            return self.name
        elif idx == 1:
            return self.link
        elif idx == 2:
            return self.var
        raise IndexError("PartRowItem index out of range")

    def __iter__(self):
        yield self.name
        yield self.link
        yield self.var


def scroll_to_item(index):
    """Memastikan part yang sedang aktif/fokus selalu tampak di viewport CTkScrollableFrame."""
    if not found_links_data or len(found_links_data) <= 1:
        return
    try:
        top, btm = scrollable_frame._parent_canvas.yview()
        h = btm - top
        total = len(found_links_data)
        pos = index / max(1, total)
        if pos < top or pos > (btm - (1.0 / total)):
            target = max(0.0, min(1.0, pos - (h / 3)))
            scrollable_frame._parent_canvas.yview_moveto(target)
    except Exception:
        pass


def update_row_style(index):
    """Memperbarui gaya visual baris (fokus, centang, atau uncheck)."""
    if not (0 <= index < len(found_links_data)):
        return
    item = found_links_data[index]
    is_focused = (index == focused_index)
    is_checked = item.var.get()

    if is_focused:
        # Highlight fokus aktif (border aksen biru cerah + background biru lembut)
        item.frame.configure(
            fg_color=("#dbeafe", "#1e3a8a"),
            border_width=1,
            border_color=("#3b82f6", "#60a5fa")
        )
    elif is_checked:
        # Part terpilih/dicentang (background abu-abu lembut / slate gelap)
        item.frame.configure(
            fg_color=("#f1f5f9", "#1e293b"),
            border_width=0
        )
    else:
        # Part tidak dipilih (transparan)
        item.frame.configure(
            fg_color="transparent",
            border_width=0
        )


def update_all_row_styles():
    """Memperbarui gaya seluruh baris part yang ada."""
    for i in range(len(found_links_data)):
        update_row_style(i)


def update_selection_counter():
    """Memperbarui label jumlah part terpilih secara real-time."""
    if not selection_counter_label:
        return
    total = len(found_links_data)
    if total == 0:
        selection_counter_label.configure(text="📌 Terpilih: 0 / 0 Part (0%)")
        return
    selected = sum(1 for item in found_links_data if item.var.get())
    percent = int((selected / total) * 100)
    selection_counter_label.configure(text=f"📌 Terpilih: {selected} / {total} Part ({percent}%)")


def on_row_enter(index, event=None):
    """Efek hover halus saat kursor mouse melintas di atas baris."""
    if index != focused_index and 0 <= index < len(found_links_data):
        item = found_links_data[index]
        is_checked = item.var.get()
        hover_bg = ("#e2e8f0", "#334155") if is_checked else ("#f8fafc", "#1f2937")
        try:
            item.frame.configure(fg_color=hover_bg)
        except Exception:
            pass


def on_row_leave(index, event=None):
    """Mengembalikan warna baris saat kursor mouse keluar."""
    if index != focused_index and 0 <= index < len(found_links_data):
        frame = found_links_data[index].frame
        try:
            x, y = frame.winfo_pointerxy()
            rx, ry = frame.winfo_rootx(), frame.winfo_rooty()
            rw, rh = frame.winfo_width(), frame.winfo_height()
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return  # Pointer masih berada di dalam area frame
        except Exception:
            pass
        update_row_style(index)


def on_item_click(index, event=None):
    """
    Handler klik part mirip Windows File Explorer:
    - Shift + Klik : Memilih seluruh rentang dari anchor ke item ini
    - Ctrl + Klik  : Membalik (toggle) centang item ini tanpa mengubah part lainnya
    - Klik biasa   : Membalik (toggle) centang dan menetapkan fokus & anchor
    """
    global focused_index, anchor_index

    if not (0 <= index < len(found_links_data)):
        return

    # Ambil fokus jendela utama agar shortcut keyboard (Spasi, Panah, dll.) langsung siap
    try:
        root.focus_set()
    except Exception:
        pass

    state = getattr(event, "state", 0) if event else 0
    is_shift = bool(state & 0x0001)
    is_ctrl = bool(state & 0x0004)

    target_item = found_links_data[index]

    if is_shift:
        # Shift + Klik: Seleksi rentang
        if anchor_index is None:
            anchor_index = 0
            target_state = True
        else:
            target_state = found_links_data[anchor_index].var.get()

        start = min(anchor_index, index)
        end = max(anchor_index, index)
        for i in range(start, end + 1):
            found_links_data[i].var.set(target_state)

        focused_index = index
        action_str = "Dicentang" if target_state else "Dibatalkan"
        log_message(f"Seleksi Rentang (Shift+Klik): Part {start + 1} s/d {end + 1} -> {action_str}", "INFO")

    elif is_ctrl:
        # Ctrl + Klik: Toggle mandiri
        new_val = not target_item.var.get()
        target_item.var.set(new_val)
        anchor_index = index
        focused_index = index
        action_str = "Dicentang" if new_val else "Dibatalkan"
        log_message(f"Seleksi Satuan (Ctrl+Klik): Part {index + 1} -> {action_str}", "INFO")

    else:
        # Klik biasa: Toggle centang dan jadikan anchor
        new_val = not target_item.var.get()
        target_item.var.set(new_val)
        anchor_index = index
        focused_index = index

    update_all_row_styles()
    update_selection_counter()
    scroll_to_item(index)


def bind_row_events(widget, click_cb, enter_cb, leave_cb):
    """Menghubungkan event klik & hover ke seluruh sub-elemen widget CustomTkinter."""
    try:
        widget.bind("<Button-1>", click_cb)
        widget.bind("<Enter>", enter_cb)
        widget.bind("<Leave>", leave_cb)
    except Exception:
        pass
    for attr in ("_canvas", "_label", "_text_label"):
        if hasattr(widget, attr):
            inner = getattr(widget, attr)
            if inner:
                try:
                    inner.bind("<Button-1>", click_cb)
                    inner.bind("<Enter>", enter_cb)
                    inner.bind("<Leave>", leave_cb)
                except Exception:
                    pass


def invert_selection():
    """Membalikkan seluruh pilihan part (yang dicentang jadi lepas, yang lepas jadi dicentang)."""
    if not found_links_data:
        return
    for item in found_links_data:
        item.var.set(not item.var.get())
    update_all_row_styles()
    update_selection_counter()
    log_message("Aksi seleksi: 'Balik Pilihan' (Invert) diterapkan ke seluruh part.", "INFO")
    set_status("Pilihan part berhasil dibalik (Invert).", "#38bdf8", "INFO")


def select_main_parts_only():
    """Hanya memilih part utama dan mengabaikan file bahasa opsional / selective."""
    if not found_links_data:
        return
    main_count = 0
    for item in found_links_data:
        if item.is_optional:
            item.var.set(False)
        else:
            item.var.set(True)
            main_count += 1
    update_all_row_styles()
    update_selection_counter()
    log_message(f"Aksi seleksi: 'Part Utama Saja' diterapkan ({main_count} part dicentang).", "INFO")
    set_status(f"{main_count} part utama berhasil dipilih.", "green", "SUCCESS")


def apply_range_selection(state=True):
    """Memilih atau membatalkan pilihan part berdasarkan rentang nomor (misal 1 s/d 15)."""
    if not range_from_entry or not range_to_entry:
        return
    from_val = range_from_entry.get().strip()
    to_val = range_to_entry.get().strip()

    if not from_val or not to_val:
        set_status("Masukkan nomor part awal dan akhir untuk memilih rentang!", "orange", "WARNING")
        return

    try:
        start_num = int(from_val)
        end_num = int(to_val)
    except ValueError:
        set_status("Nomor rentang part harus berupa angka integer!", "red", "ERROR")
        return

    total = len(found_links_data)
    if total == 0:
        set_status("Daftar part masih kosong!", "orange", "WARNING")
        return

    if start_num > end_num:
        start_num, end_num = end_num, start_num

    start_num = max(1, min(start_num, total))
    end_num = max(1, min(end_num, total))

    for idx in range(start_num - 1, end_num):
        found_links_data[idx].var.set(state)

    update_all_row_styles()
    update_selection_counter()
    action = "dicentang" if state else "dibatalkan"
    log_message(f"Rentang part {start_num} s/d {end_num} berhasil {action}.", "INFO")
    set_status(f"Part {start_num} s/d {end_num} berhasil {action}.", "green", "SUCCESS")


def is_text_input_focused():
    """Memeriksa apakah fokus sedang berada di kolom ketik agar shortcut tidak mengganggu pengetikan."""
    try:
        focused = root.focus_get()
        if not focused:
            return False
        if focused.winfo_class() in ("Entry", "Text", "TEntry"):
            return True
    except Exception:
        pass
    return False


def on_key_space(event):
    """Menekan Spasi akan membalik (toggle) centang pada part yang sedang aktif."""
    global anchor_index, focused_index
    if is_text_input_focused() or not found_links_data:
        return
    if focused_index is None or not (0 <= focused_index < len(found_links_data)):
        focused_index = 0
    item = found_links_data[focused_index]
    new_val = not item.var.get()
    item.var.set(new_val)
    anchor_index = focused_index
    update_all_row_styles()
    update_selection_counter()
    return "break"


def on_key_down(event):
    """Menekan Panah Bawah (atau Shift + Panah Bawah) untuk navigasi dan seleksi bertahap."""
    global focused_index, anchor_index
    if is_text_input_focused() or not found_links_data:
        return
    is_shift = bool(getattr(event, "state", 0) & 0x0001)

    if focused_index is None:
        new_idx = 0
    else:
        new_idx = min(len(found_links_data) - 1, focused_index + 1)

    if is_shift:
        if anchor_index is None:
            anchor_index = focused_index if focused_index is not None else 0
        start = min(anchor_index, new_idx)
        end = max(anchor_index, new_idx)
        target_state = found_links_data[anchor_index].var.get()
        for i in range(start, end + 1):
            found_links_data[i].var.set(target_state)
        update_selection_counter()
    else:
        anchor_index = new_idx

    focused_index = new_idx
    scroll_to_item(new_idx)
    update_all_row_styles()
    return "break"


def on_key_up(event):
    """Menekan Panah Atas (atau Shift + Panah Atas) untuk navigasi dan seleksi bertahap."""
    global focused_index, anchor_index
    if is_text_input_focused() or not found_links_data:
        return
    is_shift = bool(getattr(event, "state", 0) & 0x0001)

    if focused_index is None:
        new_idx = len(found_links_data) - 1
    else:
        new_idx = max(0, focused_index - 1)

    if is_shift:
        if anchor_index is None:
            anchor_index = focused_index if focused_index is not None else len(found_links_data) - 1
        start = min(anchor_index, new_idx)
        end = max(anchor_index, new_idx)
        target_state = found_links_data[anchor_index].var.get()
        for i in range(start, end + 1):
            found_links_data[i].var.set(target_state)
        update_selection_counter()
    else:
        anchor_index = new_idx

    focused_index = new_idx
    scroll_to_item(new_idx)
    update_all_row_styles()
    return "break"


def on_key_select_all(event):
    """Shortcut Ctrl + A: Memilih semua part."""
    if is_text_input_focused():
        return
    toggle_all(True)
    return "break"


def on_key_invert(event):
    """Shortcut Ctrl + I: Membalikkan pilihan."""
    if is_text_input_focused():
        return
    invert_selection()
    return "break"


def on_key_escape(event):
    """Shortcut Escape: Menghapus semua pilihan."""
    if is_text_input_focused():
        return
    toggle_all(False)
    return "break"


def on_key_home(event):
    """Shortcut Home: Loncat ke part pertama."""
    global focused_index, anchor_index
    if is_text_input_focused() or not found_links_data:
        return
    is_shift = bool(getattr(event, "state", 0) & 0x0001)
    new_idx = 0
    if is_shift:
        if anchor_index is None:
            anchor_index = focused_index if focused_index is not None else 0
        start = min(anchor_index, new_idx)
        end = max(anchor_index, new_idx)
        target_state = found_links_data[anchor_index].var.get()
        for i in range(start, end + 1):
            found_links_data[i].var.set(target_state)
        update_selection_counter()
    else:
        anchor_index = new_idx
    focused_index = new_idx
    scroll_to_item(new_idx)
    update_all_row_styles()
    return "break"


def on_key_end(event):
    """Shortcut End: Loncat ke part terakhir."""
    global focused_index, anchor_index
    if is_text_input_focused() or not found_links_data:
        return
    is_shift = bool(getattr(event, "state", 0) & 0x0001)
    new_idx = len(found_links_data) - 1
    if is_shift:
        if anchor_index is None:
            anchor_index = focused_index if focused_index is not None else new_idx
        start = min(anchor_index, new_idx)
        end = max(anchor_index, new_idx)
        target_state = found_links_data[anchor_index].var.get()
        for i in range(start, end + 1):
            found_links_data[i].var.set(target_state)
        update_selection_counter()
    else:
        anchor_index = new_idx
    focused_index = new_idx
    scroll_to_item(new_idx)
    update_all_row_styles()
    return "break"

LEVEL_ICONS = {
    "INFO": "ℹ️ [INFO]",
    "SUCCESS": "✅ [SUCCESS]",
    "WARNING": "⚠️ [WARNING]",
    "ERROR": "❌ [ERROR]"
}


def log_message(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    icon_tag = LEVEL_ICONS.get(level, f"[{level}]")
    formatted = f"[{timestamp}] {icon_tag} {msg}\n"
    try:
        print(formatted.strip())
    except UnicodeEncodeError:
        try:
            print(f"[{timestamp}] [{level}] {msg.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass

    if log_textbox:
        def _update():
            try:
                log_textbox.configure(state="normal")
                log_textbox.insert("end", formatted)
                if autoscroll_var and autoscroll_var.get():
                    log_textbox.see("end")
                log_textbox.configure(state="disabled")
            except Exception:
                pass
        try:
            root.after(0, _update)
        except Exception:
            pass


def set_status(text, color=None, log_level=None):
    def _update():
        if color:
            status_label.configure(text=text, text_color=color)
        else:
            status_label.configure(text=text)
    try:
        root.after(0, _update)
    except Exception:
        pass
    if log_level:
        log_message(text, log_level)


# ============================================================
# 1. DECRYPTOR PASTEBIN FITGIRL (LAPIS PERTAMA)
# ============================================================
def b58decode(v):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = 0
    for char in v:
        num = num * 58 + alphabet.index(char)
    n_bytes = (num.bit_length() + 7) // 8
    res = num.to_bytes(n_bytes, byteorder="big")
    pad = 0
    for c in v:
        if c == '1':
            pad += 1
        else:
            break
    return (b'\x00' * pad) + res


def extract_pastebin_links(paste_url):
    """Mendekripsi PrivateBin FitGirl langsung lewat API tanpa browser."""
    parsed = urllib.parse.urlparse(paste_url)
    paste_id = parsed.query.strip()
    key_b58 = parsed.fragment.strip()

    if not paste_id or not key_b58:
        raise ValueError("URL harus menyertakan tanda '#' dan kuncinya!")

    api_url = f"{parsed.scheme}://{parsed.netloc}/?{paste_id}"
    resp = requests.get(api_url, headers={"X-Requested-With": "JSONHttpRequest"}, timeout=15)
    
    if resp.status_code != 200:
        raise ValueError(f"Gagal mengambil Pastebin (HTTP {resp.status_code})")

    res_data = resp.json()
    if res_data.get("status") != 0:
        raise ValueError(f"Server error: {res_data.get('message', 'Unknown')}")

    key_bytes = b58decode(key_b58)
    key_bytes = key_bytes.rjust(32, b'\x00') if len(key_bytes) < 32 else key_bytes[:32]

    adata = res_data["adata"]
    ct = base64.b64decode(res_data["ct"])
    spec = adata[0]
    iv = base64.b64decode(spec[0])
    salt = base64.b64decode(spec[1])
    iterations = spec[2]
    keysize = spec[3]
    tag_size = spec[4] // 8
    compression = spec[7]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=keysize // 8,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    derived_key = kdf.derive(key_bytes)

    decryptor = Cipher(
        algorithms.AES(derived_key),
        modes.GCM(iv, ct[-tag_size:]),
        backend=default_backend()
    ).decryptor()
    decryptor.authenticate_additional_data(json.dumps(adata, separators=(',', ':')).encode('utf-8'))
    decrypted = decryptor.update(ct[:-tag_size]) + decryptor.finalize()

    if compression == "zlib":
        try:
            decrypted = zlib.decompress(decrypted, -zlib.MAX_WBITS)
        except zlib.error:
            decrypted = zlib.decompress(decrypted)

    payload = json.loads(decrypted.decode("utf-8"))
    raw_text = payload.get("paste", "")
    return re.findall(r'https?://[^\s<>"]+', raw_text)


# ============================================================
# 2. PROSES SCAN & TAMPILKAN CHECKLIST SELEKTIF
# ============================================================
def start_scan():
    raw_url = url_entry.get().strip()
    if not raw_url:
        set_status("Masukkan link landing page/pastebin!", "red", "WARNING")
        return

    set_status("Mengekstrak daftar part...", "orange", "INFO")
    scan_btn.configure(state="disabled")
    log_message(f"Memulai pemindaian URL: {raw_url}", "INFO")

    def task():
        try:
            urls = []
            if "paste.fitgirl" in raw_url:
                log_message("Mendekripsi data FitGirl PrivateBin via AES-256-GCM...", "INFO")
                urls = extract_pastebin_links(raw_url)
                log_message(f"Berhasil membaca {len(urls)} link dari Pastebin.", "SUCCESS")
            else:
                log_message("Mengunduh landing page...", "INFO")
                resp = requests.get(raw_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                urls = [a.get("href") for a in soup.find_all("a") if a.get("href")]
                log_message(f"Ditemukan {len(urls)} link pada halaman HTML.", "INFO")

            # Filter hanya hoster (misal: fuckingfast) atau file part
            clean_links = [u for u in urls if "fuckingfast" in u.lower() or any(ext in u.lower() for ext in [".rar", ".bin"])]
            unique_links = list(dict.fromkeys(clean_links))

            if not unique_links:
                set_status("Tidak ditemukan pecahan link yang sesuai.", "red", "WARNING")
                return

            def render_ui():
                global focused_index, anchor_index
                focused_index = None
                anchor_index = None

                # Bersihkan checklist lama
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                found_links_data.clear()

                for i, link in enumerate(unique_links, 1):
                    part_name = link.split('#')[-1] if '#' in link else os.path.basename(link) or f"Part {i}"
                    
                    # Default: Part utama dicentang, file bahasa opsional tidak dicentang
                    is_opt = any(x in part_name.lower() for x in ["optional", "selective"])
                    chk_var = ctk.BooleanVar(value=(not is_opt))

                    # Row Container Frame
                    row_frame = ctk.CTkFrame(
                        scrollable_frame,
                        corner_radius=6,
                        fg_color=("#f1f5f9", "#1e293b") if (not is_opt) else "transparent",
                        border_width=0,
                        cursor="hand2"
                    )
                    row_frame.pack(fill="x", padx=4, pady=2)

                    # CheckBox widget
                    chk = ctk.CTkCheckBox(
                        row_frame,
                        text="",
                        variable=chk_var,
                        width=22,
                        checkbox_width=18,
                        checkbox_height=18,
                        corner_radius=4,
                        cursor="hand2"
                    )
                    chk.pack(side="left", padx=(8, 0), pady=4)

                    # Label nama part
                    lbl = ctk.CTkLabel(
                        row_frame,
                        text=f"{i}.  {part_name}",
                        font=("Segoe UI", 11),
                        anchor="w",
                        cursor="hand2"
                    )
                    lbl.pack(side="left", fill="x", expand=True, padx=(8, 8), pady=4)

                    # Badge Kategori
                    if is_opt:
                        badge = ctk.CTkLabel(
                            row_frame,
                            text="Opsional",
                            font=("Segoe UI", 9, "bold"),
                            text_color=("#b45309", "#fbbf24"),
                            fg_color=("#fef3c7", "#451a03"),
                            corner_radius=6,
                            width=60,
                            height=20,
                            cursor="hand2"
                        )
                    else:
                        badge = ctk.CTkLabel(
                            row_frame,
                            text="Wajib",
                            font=("Segoe UI", 9, "bold"),
                            text_color=("#1d4ed8", "#93c5fd"),
                            fg_color=("#dbeafe", "#1e3a8a"),
                            corner_radius=6,
                            width=50,
                            height=20,
                            cursor="hand2"
                        )
                    badge.pack(side="right", padx=(4, 8), pady=4)

                    item = PartRowItem(
                        index=i - 1,
                        name=part_name,
                        link=link,
                        var=chk_var,
                        frame=row_frame,
                        checkbox=chk,
                        label=lbl,
                        badge=badge,
                        is_optional=is_opt
                    )
                    found_links_data.append(item)

                    # Event bindings for row, checkbox, label, and badge
                    idx = i - 1
                    def make_click_handler(cur_idx):
                        return lambda e: on_item_click(cur_idx, e)

                    def make_enter_handler(cur_idx):
                        return lambda e: on_row_enter(cur_idx, e)

                    def make_leave_handler(cur_idx):
                        return lambda e: on_row_leave(cur_idx, e)

                    click_cb = make_click_handler(idx)
                    enter_cb = make_enter_handler(idx)
                    leave_cb = make_leave_handler(idx)

                    # Bind click & hover across all components of the row
                    bind_row_events(row_frame, click_cb, enter_cb, leave_cb)
                    bind_row_events(lbl, click_cb, enter_cb, leave_cb)
                    bind_row_events(badge, click_cb, enter_cb, leave_cb)
                    bind_row_events(chk, click_cb, enter_cb, leave_cb)

                update_all_row_styles()
                update_selection_counter()
                set_status(f"Ditemukan {len(found_links_data)} part! Silakan pilih part yang ingin di-download.", "green", "SUCCESS")
                download_btn.configure(state="normal")

            root.after(0, render_ui)

        except Exception as e:
            set_status(f"Gagal ekstrak link: {e}", "red", "ERROR")
        finally:
            root.after(0, lambda: scan_btn.configure(state="normal"))

    threading.Thread(target=task, daemon=True).start()


# ============================================================
# 3. OTOMASI CHROME & INTEGRASI EXTENSION (ABDM / IDM)
# ============================================================
def close_browser():
    """Menutup browser Chrome secara bersih jika sedang aktif."""
    global driver
    if driver:
        log_message("Menutup browser Chrome...", "INFO")
        try:
            driver.execute_cdp_cmd("Browser.close", {})
        except Exception:
            try:
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.close()
            except Exception:
                pass
        try:
            driver.quit()
        except Exception:
            pass
        driver = None
        log_message("Browser Chrome berhasil ditutup.", "SUCCESS")


def start_browser_download():
    global is_running
    is_running = True
    threading.Thread(target=process_download_queue, daemon=True).start()


def process_download_queue():
    global driver, is_running
    selected_parts = [(name, url) for name, url, var in found_links_data if var.get()]

    if not selected_parts:
        set_status("Pilih minimal satu part di daftar checklist!", "red", "WARNING")
        return

    root.after(0, lambda: download_btn.configure(state="disabled"))
    total = len(selected_parts)

    set_status("Membuka Chrome dengan ekstensi downloader...", "orange", "INFO")
    log_message(f"Memulai proses download untuk {total} part terpilih...", "INFO")

    try:
        chrome_cmd = f'"{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT} --user-data-dir="C:\\chrome_downloader_profile"'
        subprocess.Popen(chrome_cmd, shell=True)
        time.sleep(2)

        options = Options()
        options.add_experimental_option("debuggerAddress", f"localhost:{DEBUG_PORT}")
        service = Service(CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        log_message(f"Berhasil tersambung ke Chrome (port {DEBUG_PORT}).", "SUCCESS")

    except Exception as e:
        set_status(f"Gagal menghubungkan Chrome: {e}. Pastikan chromedriver.exe tersedia.", "red", "ERROR")
        root.after(0, lambda: download_btn.configure(state="normal"))
        return

    selectors = [
        "//a[contains(@class,'link-button') and contains(@class,'gay-button')]",
        "//a[contains(text(),'DOWNLOAD')]",
        "//button[contains(@class,'link-button')]",
        "//button[contains(text(),'DOWNLOAD')]"
    ]

    completed_all = True
    for idx, (name, link) in enumerate(selected_parts, 1):
        if not is_running:
            set_status("Download dibatalkan.", "orange", "WARNING")
            completed_all = False
            break

        set_status(f"[{idx}/{total}] Membuka halaman part: {name}...", "#38bdf8", "INFO")
        log_message(f"[{idx}/{total}] Membuka halaman part: {name} ({link})", "INFO")
        try:
            driver.get(link)
            time.sleep(3)

            # Cari tombol Download besar
            btn = None
            for sel in selectors:
                try:
                    btn = driver.find_element(By.XPATH, sel)
                    break
                except Exception:
                    continue

            if btn:
                log_message(f"[{idx}/{total}] Tombol download ditemukan, mengklik...", "INFO")
                # Klik pertama
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)

                # Jika muncul popup tab iklan, tutup tab tersebut
                if len(driver.window_handles) > 1:
                    log_message(f"[{idx}/{total}] Tab popup iklan terdeteksi, menutup tab iklan...", "WARNING")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)

                    # Klik kedua untuk memicu unduhan riil
                    for sel in selectors:
                        try:
                            btn = driver.find_element(By.XPATH, sel)
                            driver.execute_script("arguments[0].click();", btn)
                            log_message(f"[{idx}/{total}] Tombol download diklik ulang untuk memicu unduhan riil.", "INFO")
                            break
                        except Exception:
                            continue

                # Beri jeda 3-4 detik agar ekstensi ABDM atau IDM menangkap download-nya
                log_message(f"[{idx}/{total}] Menunggu ekstensi menangkap link download...", "INFO")
                time.sleep(4)
                log_message(f"[{idx}/{total}] Part {name} berhasil dipicu ke Download Manager.", "SUCCESS")
            else:
                log_message(f"[{idx}/{total}] Peringatan: Tombol download tidak ditemukan pada halaman.", "WARNING")

        except Exception as e:
            log_message(f"[{idx}/{total}] Error saat memproses part {name}: {e}", "ERROR")

    if completed_all and is_running:
        if autoclose_var.get():
            set_status(f"Selesai! Seluruh {len(selected_parts)} part berhasil dipicu. Menutup browser...", "green", "INFO")
            time.sleep(2)
            close_browser()
            set_status(f"Selesai! Seluruh {len(selected_parts)} part berhasil dipicu & browser telah ditutup.", "green", "SUCCESS")
        else:
            set_status(f"Selesai! Seluruh {len(selected_parts)} part berhasil dipicu ke Download Manager.", "green", "SUCCESS")

    is_running = False
    root.after(0, lambda: download_btn.configure(state="normal"))


def toggle_all(state):
    for item in found_links_data:
        item.var.set(state)
    update_all_row_styles()
    update_selection_counter()
    action_label = "Pilih Semua" if state else "Hapus Pilihan"
    log_message(f"Aksi seleksi: '{action_label}' diterapkan ke seluruh part.", "INFO")


def stop_download():
    global is_running
    is_running = False
    set_status("Menghentikan proses...", "orange", "WARNING")


def clear_log():
    if log_textbox:
        log_textbox.configure(state="normal")
        log_textbox.delete("1.0", "end")
        log_textbox.configure(state="disabled")
        log_message("Log telah dibersihkan.", "INFO")


def copy_log():
    if log_textbox:
        try:
            content = log_textbox.get("1.0", "end-1c")
            root.clipboard_clear()
            root.clipboard_append(content)
            set_status("Seluruh log berhasil disalin ke clipboard!", "#38bdf8", "INFO")
        except Exception as e:
            log_message(f"Gagal menyalin log: {e}", "ERROR")


def save_log():
    if log_textbox:
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                title="Simpan Log Aktivitas",
                initialfile="fitgirl_downloader_log.txt"
            )
            if filepath:
                content = log_textbox.get("1.0", "end-1c")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                set_status(f"Log berhasil disimpan ke {os.path.basename(filepath)}", "green", "SUCCESS")
                log_message(f"Log berhasil disimpan ke file: {filepath}", "SUCCESS")
        except Exception as e:
            log_message(f"Gagal menyimpan log: {e}", "ERROR")


# ============================================================
# 4. GUI TAMPILAN CUSTOMTKINTER
# ============================================================
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("FitGirl Part Extractor & Browser Downloader")
root.geometry("780x680")
root.minsize(700, 560)

# Tabview Utama
tabview = ctk.CTkTabview(root)
tabview.pack(fill="both", expand=True, padx=20, pady=(15, 5))

tab_downloader = tabview.add("📥 Downloader")
tab_logviewer = tabview.add("📋 Log Viewer")

# ----------------- TAB DOWNLOADER -----------------
# Input URL
url_frame = ctk.CTkFrame(tab_downloader, fg_color="transparent")
url_frame.pack(fill="x", padx=10, pady=(10, 5))

url_entry = ctk.CTkEntry(url_frame, placeholder_text="Masukkan Link Landing Page / Pastebin...", height=34)
url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

scan_btn = ctk.CTkButton(url_frame, text="🔍 Ekstrak Part", command=start_scan, width=130, height=34)
scan_btn.pack(side="right")

# Toolbar Baris 1: Aksi Cepat Seleksi & Opsi Browser
actions_frame = ctk.CTkFrame(tab_downloader, fg_color="transparent")
actions_frame.pack(fill="x", padx=10, pady=(4, 2))

ctk.CTkButton(
    actions_frame, 
    text="✓ Pilih Semua (Ctrl+A)", 
    width=135, 
    height=28, 
    font=("Segoe UI", 11),
    command=lambda: toggle_all(True)
).pack(side="left", padx=(0, 5))

ctk.CTkButton(
    actions_frame, 
    text="✗ Hapus Pilihan (Esc)", 
    width=135, 
    height=28, 
    font=("Segoe UI", 11),
    command=lambda: toggle_all(False)
).pack(side="left", padx=(0, 5))

ctk.CTkButton(
    actions_frame, 
    text="⇄ Balik (Ctrl+I)", 
    width=105, 
    height=28, 
    font=("Segoe UI", 11),
    command=invert_selection
).pack(side="left", padx=(0, 5))

ctk.CTkButton(
    actions_frame, 
    text="⭐ Part Utama Saja", 
    width=120, 
    height=28, 
    font=("Segoe UI", 11),
    command=select_main_parts_only
).pack(side="left")

autoclose_var = ctk.BooleanVar(value=True)
autoclose_chk = ctk.CTkCheckBox(
    actions_frame, 
    text="Auto-close browser setelah selesai", 
    variable=autoclose_var, 
    font=("Segoe UI", 11)
)
autoclose_chk.pack(side="right")

# Toolbar Baris 2: Seleksi Rentang & Counter Part Terpilih
range_frame = ctk.CTkFrame(tab_downloader, fg_color="transparent")
range_frame.pack(fill="x", padx=10, pady=(2, 4))

ctk.CTkLabel(range_frame, text="🔢 Rentang Part:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 4))
ctk.CTkLabel(range_frame, text="Dari", font=("Segoe UI", 11)).pack(side="left", padx=(0, 3))
range_from_entry = ctk.CTkEntry(range_frame, width=45, height=26, justify="center", font=("Segoe UI", 11))
range_from_entry.pack(side="left", padx=(0, 4))
range_from_entry.bind("<Return>", lambda e: apply_range_selection(True))

ctk.CTkLabel(range_frame, text="s/d", font=("Segoe UI", 11)).pack(side="left", padx=(0, 3))
range_to_entry = ctk.CTkEntry(range_frame, width=45, height=26, justify="center", font=("Segoe UI", 11))
range_to_entry.pack(side="left", padx=(0, 6))
range_to_entry.bind("<Return>", lambda e: apply_range_selection(True))

ctk.CTkButton(
    range_frame, 
    text="Pilih Rentang", 
    width=90, 
    height=26, 
    font=("Segoe UI", 11),
    command=lambda: apply_range_selection(True)
).pack(side="left", padx=(0, 4))

ctk.CTkButton(
    range_frame, 
    text="Batal Rentang", 
    width=90, 
    height=26, 
    font=("Segoe UI", 11),
    fg_color=("gray75", "gray30"),
    hover_color=("gray65", "gray25"),
    command=lambda: apply_range_selection(False)
).pack(side="left")

selection_counter_label = ctk.CTkLabel(
    range_frame, 
    text="📌 Terpilih: 0 / 0 Part (0%)", 
    font=("Segoe UI", 11, "bold"), 
    text_color=("#2563eb", "#60a5fa")
)
selection_counter_label.pack(side="right")

# Daftar Checklist Part
scrollable_frame = ctk.CTkScrollableFrame(tab_downloader, label_text="Daftar Part (Centang part yang ingin kamu unduh)")
scrollable_frame.pack(fill="both", expand=True, padx=10, pady=(4, 2))

# Hint Bar Seleksi Windows Explorer
hint_label = ctk.CTkLabel(
    tab_downloader, 
    text="💡 Tips Explorer: Shift+Klik (Rentang) • Ctrl+Klik (Pilih Satuan) • Spasi (Centang/Batal) • ↑/↓ (Navigasi) • Ctrl+A (Semua) • Ctrl+I (Invert)", 
    font=("Segoe UI", 10), 
    text_color=("gray50", "gray40"),
    anchor="w"
)
hint_label.pack(fill="x", padx=12, pady=(0, 4))

# ----------------- TAB LOG VIEWER -----------------
log_toolbar = ctk.CTkFrame(tab_logviewer, fg_color="transparent")
log_toolbar.pack(fill="x", padx=10, pady=(5, 5))

ctk.CTkButton(log_toolbar, text="🗑️ Bersihkan Log", command=clear_log, width=120, height=30).pack(side="left", padx=(0, 8))
ctk.CTkButton(log_toolbar, text="📋 Salin Semua", command=copy_log, width=110, height=30).pack(side="left", padx=(0, 8))
ctk.CTkButton(log_toolbar, text="💾 Simpan ke File", command=save_log, width=125, height=30).pack(side="left")

autoscroll_var = ctk.BooleanVar(value=True)
autoscroll_chk = ctk.CTkCheckBox(log_toolbar, text="Auto-scroll", variable=autoscroll_var, font=("Segoe UI", 11))
autoscroll_chk.pack(side="right")

log_textbox = ctk.CTkTextbox(
    tab_logviewer, 
    font=("Consolas", 11), 
    wrap="word", 
    activate_scrollbars=True
)
log_textbox.pack(fill="both", expand=True, padx=10, pady=(5, 10))
log_textbox.configure(state="disabled")

# ----------------- BOTTOM STATUS & ACTIONS -----------------
bottom_frame = ctk.CTkFrame(root, fg_color="transparent")
bottom_frame.pack(fill="x", padx=20, pady=(0, 15))

status_label = ctk.CTkLabel(bottom_frame, text="Masukkan link di atas untuk mengekstrak pecahan part.", anchor="w")
status_label.pack(fill="x", pady=(0, 8))

download_btn = ctk.CTkButton(
    bottom_frame, 
    text="🚀 Mulai Download via Browser Extension", 
    command=start_browser_download, 
    state="disabled", 
    height=38, 
    fg_color="#2563eb", 
    hover_color="#1d4ed8", 
    font=("Segoe UI", 12, "bold")
)
download_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

stop_btn = ctk.CTkButton(
    bottom_frame, 
    text="Stop", 
    command=stop_download, 
    width=90, 
    height=38, 
    fg_color="#dc2626", 
    hover_color="#b91c1c"
)
stop_btn.pack(side="right")

# ----------------- SHORTCUT KEYBOARD WINDOWS EXPLORER -----------------
root.bind("<space>", on_key_space)
root.bind("<Down>", on_key_down)
root.bind("<Up>", on_key_up)
root.bind("<Shift-Down>", on_key_down)
root.bind("<Shift-Up>", on_key_up)
root.bind("<Control-a>", on_key_select_all)
root.bind("<Control-A>", on_key_select_all)
root.bind("<Control-i>", on_key_invert)
root.bind("<Control-I>", on_key_invert)
root.bind("<Escape>", on_key_escape)
root.bind("<Home>", on_key_home)
root.bind("<End>", on_key_end)
root.bind("<Shift-Home>", on_key_home)
root.bind("<Shift-End>", on_key_end)

# Pesan sambutan di log
log_message("Aplikasi FitGirl Part Extractor & Browser Downloader berhasil dimuat.", "INFO")
log_message("Silakan masukkan URL landing page atau link Pastebin FitGirl pada tab Downloader.", "INFO")

if __name__ == "__main__":
    root.mainloop()