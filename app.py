"""
Steganografi LSB Termodifikasi dengan Enkripsi XOR
====================================================
Metode  : LSB (Least Significant Bit) + XOR Cipher + Delimiter
Platform: Streamlit Web UI
Author  : Alvin Dinata
"""

import io
import math
import numpy as np
import streamlit as st
from PIL import Image

# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────
DELIMITER       = "<<<END>>>"   # sentinel akhir pesan
XOR_KEY         = 42            # kunci XOR (0–255)
MIN_RESOLUTION  = (250, 250)    # resolusi minimum yang diterima

# ─────────────────────────────────────────────────────────────
# LAPISAN ENKRIPSI / DEKRIPSI
# ─────────────────────────────────────────────────────────────

def xor_encrypt(message: str, key: int = XOR_KEY) -> str:
    """
    Enkripsi / dekripsi XOR sederhana.
    XOR bersifat involutory: encrypt(encrypt(m)) == m,
    sehingga fungsi yang sama dipakai untuk keduanya.

    Output  : string di mana setiap karakter di-XOR-kan dengan `key`.
    Catatan : menggunakan chr/ord agar tetap bekerja pada ASCII printable.
    """
    return "".join(chr(ord(c) ^ key) for c in message)


def xor_decrypt(cipher: str, key: int = XOR_KEY) -> str:
    """Dekripsi — identik dengan encrypt karena sifat involutory XOR."""
    return xor_encrypt(cipher, key)


# ─────────────────────────────────────────────────────────────
# UTILITAS BIT
# ─────────────────────────────────────────────────────────────

def text_to_bits(text: str) -> list[int]:
    """Ubah string ke daftar bit (MSB-first per byte)."""
    bits = []
    for char in text:
        byte = ord(char)
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_text(bits: list[int]) -> str:
    """Kembalikan daftar bit menjadi string."""
    chars = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i + 8]
        if len(byte_bits) < 8:
            break
        byte = 0
        for b in byte_bits:
            byte = (byte << 1) | b
        chars.append(chr(byte))
    return "".join(chars)


# ─────────────────────────────────────────────────────────────
# KALKULASI PSNR
# ─────────────────────────────────────────────────────────────

def calculate_psnr(original: np.ndarray, stego: np.ndarray) -> float:
    """
    Hitung Peak Signal-to-Noise Ratio (PSNR) antara dua citra.

    Rumus:
        MSE  = (1 / MN) * Σ Σ [I(i,j) - K(i,j)]²
        PSNR = 10 * log10(MAX_I² / MSE)

    di mana:
        MAX_I = nilai piksel maksimum (255 untuk 8-bit)
        M, N  = dimensi citra (tinggi, lebar)
        I     = cover image (asli)
        K     = stego image

    Nilai PSNR yang baik untuk steganografi: > 40 dB
    Nilai ≥ 50 dB dianggap sangat tidak terdeteksi secara visual.
    """
    original_f = original.astype(np.float64)
    stego_f    = stego.astype(np.float64)

    mse = np.mean((original_f - stego_f) ** 2)

    if mse == 0:
        # Tidak ada distorsi sama sekali
        return float("inf")

    max_pixel = 255.0
    psnr = 10.0 * math.log10((max_pixel ** 2) / mse)
    return round(psnr, 4)


# ─────────────────────────────────────────────────────────────
# CORE: EMBED
# ─────────────────────────────────────────────────────────────

def embed_message(image: Image.Image, secret_message: str) -> Image.Image:
    """
    Sisipkan pesan rahasia ke dalam citra menggunakan metode LSB termodifikasi.

    Pipeline:
        1. Enkripsi pesan dengan XOR cipher.
        2. Tambahkan delimiter di akhir ciphertext.
        3. Ubah ciphertext+delimiter ke bit stream.
        4. Tulis satu bit per channel LSB secara sekuensial
           (R→G→B per piksel, baris demi baris).

    Args:
        image          : PIL Image (akan dikonversi ke RGB).
        secret_message : plaintext yang akan disembunyikan.

    Returns:
        stego_image    : PIL Image dengan pesan tersembunyi.

    Raises:
        ValueError jika kapasitas piksel tidak mencukupi.
    """
    img = image.convert("RGB")
    pixels = np.array(img, dtype=np.uint8)

    # Enkripsi + tambah delimiter
    cipher_text   = xor_encrypt(secret_message)
    payload       = cipher_text + DELIMITER

    bits          = text_to_bits(payload)
    total_bits    = len(bits)
    capacity_bits = pixels.size  # H × W × 3 channel

    if total_bits > capacity_bits:
        raise ValueError(
            f"Kapasitas tidak mencukupi. "
            f"Dibutuhkan {total_bits} bit, tersedia {capacity_bits} bit "
            f"({capacity_bits // 8} byte)."
        )

    # Tulis bit ke LSB secara flat
    flat = pixels.flatten()
    for idx, bit in enumerate(bits):
        # Bersihkan LSB lalu set dengan bit pesan
        flat[idx] = (flat[idx] & 0xFE) | bit

    stego_pixels = flat.reshape(pixels.shape)
    return Image.fromarray(stego_pixels, "RGB")


# ─────────────────────────────────────────────────────────────
# CORE: EXTRACT
# ─────────────────────────────────────────────────────────────

def extract_message(stego_image: Image.Image) -> str:
    """
    Ekstrak pesan tersembunyi dari stego image.

    Pipeline (kebalikan embed):
        1. Baca LSB setiap channel secara sekuensial.
        2. Susun ulang bit menjadi string karakter.
        3. Cari delimiter untuk menentukan batas pesan.
        4. Dekripsi XOR untuk mendapatkan plaintext.

    Args:
        stego_image : PIL Image yang mengandung pesan tersembunyi.

    Returns:
        Plaintext pesan rahasia.

    Raises:
        ValueError jika delimiter tidak ditemukan (bukan stego image valid).
    """
    img    = stego_image.convert("RGB")
    pixels = np.array(img, dtype=np.uint8)
    flat   = pixels.flatten()

    # Kumpulkan LSB
    bits = [int(flat[i]) & 1 for i in range(len(flat))]

    # Konversi bit → karakter, cari delimiter secara inkremental
    extracted = ""
    for i in range(0, len(bits) - 7, 8):
        byte_bits = bits[i:i + 8]
        byte      = 0
        for b in byte_bits:
            byte = (byte << 1) | b
        extracted += chr(byte)

        if extracted.endswith(DELIMITER):
            # Temukan delimiter — potong dan dekripsi
            cipher_text   = extracted[: -len(DELIMITER)]
            plaintext     = xor_decrypt(cipher_text)
            return plaintext

    raise ValueError(
        "Delimiter tidak ditemukan. "
        "Pastikan gambar adalah stego image yang valid dan belum dikompresi ulang."
    )


# ─────────────────────────────────────────────────────────────
# UTILITAS UI
# ─────────────────────────────────────────────────────────────

def image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    """Serialisasi PIL Image ke bytes untuk download/display."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def validate_image(image: Image.Image) -> tuple[bool, str]:
    """
    Validasi resolusi minimum 250×250.

    Returns:
        (True, "") jika valid, (False, pesan_error) jika tidak.
    """
    w, h = image.size
    if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
        return False, (
            f"Resolusi gambar terlalu kecil: {w}×{h} px. "
            f"Minimum yang dibutuhkan: {MIN_RESOLUTION[0]}×{MIN_RESOLUTION[1]} px."
        )
    return True, ""


def capacity_info(image: Image.Image) -> dict:
    """Hitung kapasitas maksimum pesan yang dapat disisipkan."""
    w, h     = image.size
    channels = 3  # RGB
    max_bits  = w * h * channels
    # Kurangi kapasitas delimiter dan overhead enkripsi (konservatif)
    usable_bytes = (max_bits // 8) - len(DELIMITER) - 4
    return {
        "pixels"       : w * h,
        "max_bits"     : max_bits,
        "usable_chars" : max(0, usable_bytes),
    }


# ─────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────

def setup_page():
    st.set_page_config(
        page_title  = "StegoLab",
        page_icon   = "🔐",
        layout      = "wide",
        initial_sidebar_state = "collapsed",
    )
    # Injeksi CSS — desain monospace/terminal dengan aksen biru dingin
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Inter:wght@300;400;500;600&display=swap');

        :root {
            --bg-primary   : #0d1117;
            --bg-card      : #161b22;
            --bg-card2     : #1c2128;
            --border       : #30363d;
            --accent-blue  : #58a6ff;
            --accent-cyan  : #39d353;
            --accent-amber : #e3b341;
            --accent-red   : #f85149;
            --text-primary : #e6edf3;
            --text-muted   : #8b949e;
            --text-dim     : #484f58;
            --mono         : 'JetBrains Mono', monospace;
            --sans         : 'Inter', sans-serif;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background-color: var(--bg-primary) !important;
            color: var(--text-primary) !important;
            font-family: var(--sans) !important;
        }

        /* Header utama */
        .main-header {
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }
        .main-title {
            font-family: var(--mono);
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--accent-blue);
            letter-spacing: -0.5px;
            margin: 0;
        }
        .main-subtitle {
            font-family: var(--mono);
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.35rem;
            letter-spacing: 0.05em;
        }
        .badge {
            display: inline-block;
            background: #1f3149;
            color: var(--accent-blue);
            border: 1px solid #1f6feb;
            border-radius: 4px;
            font-family: var(--mono);
            font-size: 0.65rem;
            padding: 2px 8px;
            margin-right: 6px;
            letter-spacing: 0.05em;
        }

        /* Kartu section */
        .section-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.25rem;
        }
        .section-label {
            font-family: var(--mono);
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-label::after {
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }

        /* Metrik PSNR */
        .metric-block {
            background: var(--bg-card2);
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent-blue);
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-family: var(--mono);
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .metric-value {
            font-family: var(--mono);
            font-size: 2.2rem;
            font-weight: 700;
            color: var(--accent-blue);
            line-height: 1.1;
        }
        .metric-unit {
            font-size: 0.9rem;
            color: var(--text-muted);
        }
        .metric-interp {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }
        .metric-good  { border-left-color: var(--accent-cyan) !important; }
        .metric-good .metric-value { color: var(--accent-cyan) !important; }
        .metric-warn  { border-left-color: var(--accent-amber) !important; }
        .metric-warn .metric-value { color: var(--accent-amber) !important; }
        .metric-bad   { border-left-color: var(--accent-red) !important; }
        .metric-bad .metric-value  { color: var(--accent-red) !important; }

        /* Info box */
        .info-box {
            background: #1f3149;
            border: 1px solid #1f6feb;
            border-radius: 6px;
            padding: 0.85rem 1.1rem;
            font-size: 0.82rem;
            color: #79c0ff;
            font-family: var(--mono);
            margin: 0.75rem 0;
        }
        .info-box code {
            color: var(--accent-cyan);
            background: transparent;
            font-size: 0.78rem;
        }

        /* Status hasil ekstraksi */
        .extract-result {
            background: #0d2119;
            border: 1px solid #238636;
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin-top: 0.75rem;
        }
        .extract-label {
            font-family: var(--mono);
            font-size: 0.65rem;
            color: #3fb950;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.5rem;
        }
        .extract-text {
            font-family: var(--mono);
            font-size: 0.9rem;
            color: var(--text-primary);
            word-break: break-word;
            white-space: pre-wrap;
        }

        /* Override Streamlit komponen */
        .stTextArea textarea, .stTextInput input {
            background-color: var(--bg-card2) !important;
            border: 1px solid var(--border) !important;
            color: var(--text-primary) !important;
            font-family: var(--mono) !important;
            font-size: 0.85rem !important;
            border-radius: 6px !important;
        }
        .stTextArea textarea:focus, .stTextInput input:focus {
            border-color: var(--accent-blue) !important;
            box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
        }

        .stButton > button {
            background: var(--accent-blue) !important;
            color: #0d1117 !important;
            border: none !important;
            border-radius: 6px !important;
            font-family: var(--mono) !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            letter-spacing: 0.05em !important;
            padding: 0.55rem 1.5rem !important;
            transition: opacity 0.15s !important;
        }
        .stButton > button:hover { opacity: 0.85 !important; }

        .stDownloadButton > button {
            background: transparent !important;
            color: var(--accent-cyan) !important;
            border: 1px solid var(--accent-cyan) !important;
            border-radius: 6px !important;
            font-family: var(--mono) !important;
            font-size: 0.78rem !important;
        }

        /* File uploader */
        [data-testid="stFileUploaderDropzone"] {
            background: var(--bg-card2) !important;
            border: 1px dashed var(--border) !important;
            border-radius: 8px !important;
        }

        /* Tab */
        .stTabs [data-baseweb="tab-list"] {
            background: var(--bg-card) !important;
            border-bottom: 1px solid var(--border) !important;
            gap: 0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            color: var(--text-muted) !important;
            font-family: var(--mono) !important;
            font-size: 0.78rem !important;
            font-weight: 400 !important;
            border-radius: 0 !important;
            padding: 0.65rem 1.25rem !important;
            border-bottom: 2px solid transparent !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent-blue) !important;
            border-bottom-color: var(--accent-blue) !important;
        }

        /* Alert */
        .stAlert { border-radius: 6px !important; font-family: var(--mono) !important; font-size: 0.82rem !important; }

        /* Caption gambar */
        .img-caption {
            font-family: var(--mono);
            font-size: 0.7rem;
            color: var(--text-muted);
            text-align: center;
            margin-top: 0.4rem;
            letter-spacing: 0.04em;
        }

        div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }
        .stMarkdown p { margin: 0 !important; }
        footer { display: none !important; }
    </style>
    """, unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div class="main-header">
        <p class="main-title">🔐 StegoLab</p>
        <p class="main-subtitle">
            <span class="badge">LSB Modified</span>
            <span class="badge">XOR Cipher</span>
            <span class="badge">PSNR Analysis</span>
            &nbsp;· Steganografi Citra Digital · Akademik
        </p>
    </div>
    """, unsafe_allow_html=True)


def psnr_class(psnr: float) -> str:
    """Pilih kelas CSS berdasarkan kualitas PSNR."""
    if psnr >= 50:
        return "metric-good"
    if psnr >= 40:
        return "metric-warn"
    return "metric-bad"


def psnr_interpretation(psnr: float) -> str:
    if psnr == float("inf"):
        return "Tidak ada modifikasi (pesan kosong / identik)"
    if psnr >= 50:
        return "Sangat tidak terdeteksi secara visual (imperceptible)"
    if psnr >= 40:
        return "Distorsi minimal — masih dalam threshold steganografi aman"
    return "Distorsi terdeteksi — ukuran pesan mendekati kapasitas maksimum"


def render_embed_tab():
    st.markdown('<div class="section-label">01 &nbsp; Upload Cover Image</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Pilih file gambar (PNG / JPG / BMP / WEBP)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        key="embed_upload",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.markdown("""
        <div class="info-box">
        Gambar akan dikonversi otomatis ke <code>PNG</code> sebelum penyisipan untuk
        menghindari kerusakan data akibat kompresi lossy (JPEG, WEBP).
        </div>
        """, unsafe_allow_html=True)
        return

    original_img = Image.open(uploaded)

    # Validasi resolusi
    valid, err_msg = validate_image(original_img)
    if not valid:
        st.error(f"⚠ {err_msg}")
        return

    # Informasi kapasitas
    cap = capacity_info(original_img)
    w, h = original_img.size

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(f"""
        <div class="metric-block">
            <div class="metric-label">Resolusi</div>
            <div class="metric-value" style="font-size:1.4rem">{w} × {h}</div>
            <div class="metric-interp">piksel</div>
        </div>""", unsafe_allow_html=True)
    with col_info2:
        st.markdown(f"""
        <div class="metric-block">
            <div class="metric-label">Kapasitas LSB</div>
            <div class="metric-value" style="font-size:1.4rem">{cap['usable_chars']:,}</div>
            <div class="metric-interp">karakter maksimum</div>
        </div>""", unsafe_allow_html=True)
    with col_info3:
        st.markdown(f"""
        <div class="metric-block">
            <div class="metric-label">Total Bit Tersedia</div>
            <div class="metric-value" style="font-size:1.4rem">{cap['max_bits']:,}</div>
            <div class="metric-interp">bit (3 channel RGB)</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">02 &nbsp; Pesan Rahasia</div>', unsafe_allow_html=True)

    secret = st.text_area(
        "Masukkan pesan rahasia",
        placeholder="Ketik pesan yang akan disembunyikan di sini...",
        height=120,
        label_visibility="collapsed",
    )

    char_count = len(secret) if secret else 0
    if char_count > 0:
        usage_pct = (char_count / cap['usable_chars']) * 100 if cap['usable_chars'] > 0 else 0
        color = "#39d353" if usage_pct < 70 else "#e3b341" if usage_pct < 90 else "#f85149"
        st.markdown(
            f'<p style="font-family:\'JetBrains Mono\',monospace; font-size:0.7rem; '
            f'color:{color}; margin-top:4px;">'
            f'{char_count} / {cap["usable_chars"]:,} karakter ({usage_pct:.1f}% kapasitas)</p>',
            unsafe_allow_html=True,
        )

    st.markdown('<br>', unsafe_allow_html=True)

    if st.button("⬛  Jalankan Embedding", use_container_width=True):
        if not secret or not secret.strip():
            st.error("Pesan tidak boleh kosong.")
            return

        if char_count > cap["usable_chars"]:
            st.error(f"Pesan terlalu panjang ({char_count} kar). Maksimum: {cap['usable_chars']:,} karakter.")
            return

        with st.spinner("Menyisipkan pesan ke piksel..."):
            try:
                stego_img    = embed_message(original_img, secret)
                orig_arr     = np.array(original_img.convert("RGB"))
                stego_arr    = np.array(stego_img)
                psnr_value   = calculate_psnr(orig_arr, stego_arr)
                stego_bytes  = image_to_bytes(stego_img, "PNG")
            except ValueError as e:
                st.error(str(e))
                return

        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">03 &nbsp; Hasil Perbandingan</div>', unsafe_allow_html=True)

        col_orig, col_stego = st.columns(2)
        with col_orig:
            st.image(original_img, use_container_width=True)
            st.markdown('<p class="img-caption">COVER IMAGE (original)</p>', unsafe_allow_html=True)
        with col_stego:
            st.image(stego_img, use_container_width=True)
            st.markdown('<p class="img-caption">STEGO IMAGE (modified LSB)</p>', unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">04 &nbsp; Analisis PSNR</div>', unsafe_allow_html=True)

        psnr_str  = f"{psnr_value:.2f}" if psnr_value != float("inf") else "∞"
        css_class = psnr_class(psnr_value)
        interp    = psnr_interpretation(psnr_value)

        col_psnr, col_formula = st.columns([1, 1])
        with col_psnr:
            st.markdown(f"""
            <div class="metric-block {css_class}">
                <div class="metric-label">Peak Signal-to-Noise Ratio</div>
                <div class="metric-value">{psnr_str} <span class="metric-unit">dB</span></div>
                <div class="metric-interp">{interp}</div>
            </div>""", unsafe_allow_html=True)
        with col_formula:
            st.markdown("""
            <div class="info-box" style="height:100%;box-sizing:border-box;">
                <b style="color:#e6edf3">Rumus PSNR:</b><br><br>
                <code>MSE  = (1/MN) · Σ[I(i,j) − K(i,j)]²</code><br>
                <code>PSNR = 10 · log₁₀(255² / MSE)</code><br><br>
                Threshold aman steganografi: <code>> 40 dB</code>
            </div>""", unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)
        st.download_button(
            label="⬇  Unduh Stego Image (PNG)",
            data=stego_bytes,
            file_name="stego_output.png",
            mime="image/png",
            use_container_width=True,
        )


def render_extract_tab():
    st.markdown('<div class="section-label">01 &nbsp; Upload Stego Image</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Pilih stego image hasil embedding",
        type=["png"],
        key="extract_upload",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.markdown("""
        <div class="info-box">
        Pastikan file yang diunggah adalah <code>PNG</code> asli dari proses embedding —
        bukan hasil screenshot atau konversi ulang yang merusak bit LSB.
        </div>
        """, unsafe_allow_html=True)
        return

    stego_img = Image.open(uploaded)
    w, h      = stego_img.size
    st.image(stego_img, caption=f"Stego Image · {w}×{h} px · PNG", use_container_width=True)

    st.markdown('<br>', unsafe_allow_html=True)

    if st.button("🔍  Ekstrak Pesan", use_container_width=True):
        with st.spinner("Membaca bit LSB dan mendekripsi..."):
            try:
                plaintext = extract_message(stego_img)
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Terjadi kesalahan tak terduga: {e}")
                return

        st.markdown('<div class="section-label" style="margin-top:1.5rem;">02 &nbsp; Pesan Berhasil Diekstrak</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="extract-result">
            <div class="extract-label">✓ Plaintext (setelah dekripsi XOR)</div>
            <div class="extract-text">{plaintext}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)
        st.download_button(
            label="⬇  Unduh Pesan sebagai .txt",
            data=plaintext.encode("utf-8"),
            file_name="extracted_message.txt",
            mime="text/plain",
            use_container_width=True,
        )


def render_about_tab():
    st.markdown("""
    <div class="section-card">
        <div class="section-label">Metode</div>
        <div style="font-family:'Inter',sans-serif; font-size:0.88rem; color:#c9d1d9; line-height:1.7;">
            Steganografi ini menggunakan <strong style="color:#58a6ff">LSB Termodifikasi</strong>
            dengan dua lapisan modifikasi:
            <br><br>
            <span style="color:#39d353; font-family:'JetBrains Mono',monospace; font-size:0.8rem;">
            [1] XOR Cipher</span> — Setiap karakter pesan di-XOR dengan kunci 42 sebelum
            disisipkan, sehingga bit stream yang tertanam bukan representasi langsung dari teks asli.<br><br>
            <span style="color:#39d353; font-family:'JetBrains Mono',monospace; font-size:0.8rem;">
            [2] Delimiter</span> — String <code style="color:#e3b341"><<<END>>></code>
            ditambahkan di akhir ciphertext sebagai penanda batas pesan,
            menggantikan kebutuhan menyimpan panjang pesan secara eksplisit.
        </div>
    </div>

    <div class="section-card">
        <div class="section-label">Pipeline Embedding</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#8b949e; line-height:2;">
            Plaintext<br>
            &nbsp;&nbsp;→ <span style="color:#58a6ff">XOR Encrypt</span> (key=42) → Ciphertext<br>
            &nbsp;&nbsp;→ <span style="color:#58a6ff">Append Delimiter</span> → Payload String<br>
            &nbsp;&nbsp;→ <span style="color:#58a6ff">text_to_bits()</span> → Bit Stream [0,1,1,0,...]<br>
            &nbsp;&nbsp;→ <span style="color:#58a6ff">LSB Write</span> per channel RGB → Stego Image
        </div>
    </div>

    <div class="section-card">
        <div class="section-label">Kapasitas Formula</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#8b949e; line-height:2;">
            Max bits  = Width × Height × 3<br>
            Max chars = (Max bits / 8) − len(DELIMITER) − overhead<br><br>
            <span style="color:#58a6ff">Contoh:</span> 512×512 PNG → 786,432 bit → ~98,297 karakter
        </div>
    </div>

    <div class="section-card">
        <div class="section-label">Batasan & Catatan</div>
        <div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:#c9d1d9; line-height:1.7;">
            • Gunakan hanya format <strong>PNG</strong> untuk stego image — format lossy (JPEG, WEBP)
              merusak bit LSB sehingga ekstraksi akan gagal.<br>
            • XOR key bersifat shared-secret — dalam implementasi nyata, gunakan key derivation
              function (PBKDF2 / Argon2) dengan password berbasis user input.<br>
            • PSNR mengukur distorsi, bukan keamanan. Untuk ketahanan terhadap steganalisis,
              pertimbangkan distribusi bit yang lebih acak (LSBM, PVD, dll).
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    setup_page()
    render_header()

    tab_embed, tab_extract = st.tabs([
        "⬛  Embedding",
        "🔍  Extraction",
    ])

    with tab_embed:
        st.markdown('<br>', unsafe_allow_html=True)
        render_embed_tab()

    with tab_extract:
        st.markdown('<br>', unsafe_allow_html=True)
        render_extract_tab()


if __name__ == "__main__":
    main()