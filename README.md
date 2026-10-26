# 🎮 FitGirl Part Extractor & Browser Downloader

Aplikasi desktop berbasis Python & CustomTkinter modern untuk mengekstrak, mendekripsi tautan part dari landing page atau PrivateBin FitGirl, serta mengotomasikan proses pengunduhan via browser Google Chrome dengan dukungan ekstensi download manager (seperti **IDM** / **ABDM**).

---

## ✨ Fitur Utama

- 🔓 **Dekripsi Otomatis Pastebin FitGirl**: Mendekripsi tautan terenkripsi AES-256-GCM (PrivateBin) secara langsung tanpa perlu membuka browser secara manual.
- 🎯 **Filter Cerdas Part**: Otomatis mengenali dan memisahkan part wajib dari file bahasa opsional (*selective/optional*).
- 🖱️ **Navigasi Ala Windows Explorer**: Mendukung seleksi rentang (`Shift + Klik`), toggle mandiri (`Ctrl + Klik`), tombol `Spasi` untuk centang, tombol panah navigasi, `Ctrl + A` (pilih semua), dan `Ctrl + I` (balik pilihan).
- 🔢 **Seleksi Rentang Angka**: Input praktis untuk memilih rentang part tertentu (misal part 1 s/d 15).
- 🚀 **Otomasi Selenium & Anti-Iklan**: Membuka tautan part satu per satu secara otomatis di Google Chrome, mendeteksi dan menutup tab pop-up iklan, serta memicu tombol unduh agar ditangkap oleh download manager Anda.
- 📋 **Tab Log Viewer**: Riwayat aktivitas terstruktur dengan fitur salin log (*clipboard*), pencarian, dan simpan log ke file `.txt`.

---

## 📦 Bahan-Bahan yang Diperlukan (Di Luar Repo)

Beberapa komponen binary dan aplikasi pihak ketiga sengaja tidak disertakan di dalam repositori Git ini demi efisiensi dan kompabilitas versi. Berikut adalah bahan yang perlu Anda siapkan:

### 1. Python 3.10+
Pastikan Python sudah terinstal di komputer Anda dan opsi **"Add Python to PATH"** dicentang saat instalasi.
- Unduh di: [python.org/downloads](https://www.python.org/downloads/)

### 2. Google Chrome Browser
Aplikasi membutuhkan Google Chrome untuk proses otomasi pengunduhan.
- Unduh di: [google.com/chrome](https://www.google.com/chrome/)
- *Default path* yang dicari aplikasi: `C:\Program Files\Google\Chrome\Application\chrome.exe`

### 3. ChromeDriver (`chromedriver.exe`)
File driver ini wajib diletakkan di dalam folder proyek ini (sejajar dengan `FitGirl_Browser_Downloader.py`). Versi ChromeDriver **harus sama dengan versi Google Chrome** yang terpasang di komputer Anda.

#### 📌 Cara Download ChromeDriver:
1. **Cek versi Google Chrome Anda**:
   - Buka Google Chrome.
   - Ketikkan `chrome://settings/help` di address bar (atau klik menu titik tiga di kanan atas > **Help** > **About Google Chrome**).
   - Catat nomor versi Chrome Anda (misalnya: `131.0.6778.86`).
2. **Unduh ChromeDriver yang cocok**:
   - **Untuk Chrome versi 115 ke atas**:
     - Buka situs resmi [Chrome for Testing Availability](https://googlechromelabs.github.io/chrome-for-testing/).
     - Temukan versi yang sama dengan Chrome Anda di bagian *Stable* atau daftar versi.
     - Pada baris **chromedriver** untuk platform **win64**, salin tautan URL-nya dan unduh file `.zip` tersebut.
   - **Untuk Chrome versi 114 ke bawah**:
     - Unduh dari [ChromeDriver Legacy Downloads](https://chromedriver.chromium.org/downloads).
3. **Ekstrak File**:
   - Ekstrak file zip hasil unduhan.
   - Salin file `chromedriver.exe` dan letakkan langsung di dalam folder proyek ini:
     ```
     FitGirl_Browser_Downloader/
     ├── FitGirl_Browser_Downloader.py
     ├── chromedriver.exe   <-- (Letakkan di sini)
     ├── requirements.txt
     └── README.md
     ```

### 4. Ekstensi Download Manager (IDM / ABDM)
Agar unduhan langsung ditangkap secara otomatis saat tombol download diklik oleh bot:
- **Internet Download Manager (IDM)**: Pastikan aplikasi IDM terinstal dan ekstensi browser **IDM Integration Module** sudah aktif di Chrome Anda.
- **ABDM (Automated Browser Download Manager)**: Atau ekstensi download manager favorit Anda lainnya yang aktif di browser.

---

## 🛠️ Panduan Instalasi & Menjalankan

### 1. Clone Repositori
```bash
git clone https://github.com/studentawangihti/FitGirl_Browser_Downloader.git
cd FitGirl_Browser_Downloader
```

### 2. Install Dependensi Python
Jalankan perintah berikut di Terminal / PowerShell pada folder proyek:
```bash
pip install -r requirements.txt
```

*(Dependensi meliputi: `customtkinter`, `selenium`, `requests`, `beautifulsoup4`, `cryptography`)*

### 3. Pasang `chromedriver.exe`
Pastikan Anda sudah mengunduh `chromedriver.exe` yang sesuai versi Chrome Anda dan meletakkannya di folder root proyek seperti panduan di atas.

### 4. Jalankan Aplikasi
```bash
python FitGirl_Browser_Downloader.py
```

---

## 📖 Cara Penggunaan

1. **Input Link**: Masukkan URL landing page atau tautan Pastebin FitGirl (contoh: `https://paste.fitgirl-repacks.site/?...#...`) pada kolom yang tersedia.
2. **Ekstrak Part**: Klik tombol **🔍 Ekstrak Part**. Daftar part akan dimuat dan otomatis memisahkan part wajib dan part opsional.
3. **Pilih Part**: Centang part yang ingin diunduh menggunakan mouse, tombol cepat, atau shortcut keyboard.
4. **Mulai Unduh**: Klik tombol **🚀 Mulai Download via Browser Extension**.
5. Browser Chrome akan terbuka otomatis, membuka tautan part terpilih satu per satu, mengklik tombol unduh, menutup pop-up iklan, dan meneruskan link ke IDM/Download Manager Anda.

---

## ⌨️ Daftar Tombol Pintasan (Keyboard Shortcuts)

| Tombol / Kombinasi | Fungsi |
| :--- | :--- |
| `Spasi` | Toggle (centang / lepas centang) part yang sedang aktif |
| `↑` / `↓` | Navigasi kursor ke part atas / bawah |
| `Shift + ↑` / `Shift + ↓` | Seleksi bertingkat part ke atas / bawah |
| `Shift + Klik` | Seleksi rentang part (dari titik awal hingga baris yang diklik) |
| `Ctrl + Klik` | Memilih/membatalkan satu part tanpa merubah pilihan lain |
| `Ctrl + A` | Memilih seluruh part (*Select All*) |
| `Ctrl + I` | Membalikkan pilihan (*Invert Selection*) |
| `Home` / `End` | Loncat langsung ke part pertama / terakhir |
| `Esc` | Membatalkan / melepas semua pilihan centang |

---

## ❓ Troubleshooting

- **Error: `Gagal menghubungkan Chrome: ... Pastikan chromedriver.exe tersedia`**
  - Pastikan file `chromedriver.exe` berada tepat di folder yang sama dengan `FitGirl_Browser_Downloader.py`.
  - Pastikan versi `chromedriver.exe` sama persis dengan versi browser Google Chrome Anda.
- **Chrome tidak terbuka atau path berbeda**:
  - Jika Google Chrome Anda terpasang di lokasi berbeda, sesuaikan variabel `CHROME_PATH` pada baris 31 di file `FitGirl_Browser_Downloader.py`.
- **Port 9222 sedang digunakan**:
  - Tutup instance Chrome lama yang berjalan di latar belakang melalui Task Manager, atau ubah nilai `DEBUG_PORT` di script.

---

## 📜 Lisensi
Proyek ini dibuat untuk tujuan edukasi dan kemudahan manajemen unduhan pribadi.
