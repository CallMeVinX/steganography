# StegoLab

Aplikasi kecil untuk demonstrasi steganografi citra digital berbasis LSB dengan lapisan XOR sederhana.

## Cara Menjalankan

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Jalankan Streamlit
python -m streamlit run app.py
```

Browser akan otomatis membuka `http://localhost:8501`.

---
## Link Video Penjelasan Aplikasi

### `https://mikroskilacid-my.sharepoint.com/:f:/g/personal/alvin_dinata_students_mikroskil_ac_id/IgBpDEEnrE-hRZxPDO8v5ZrHAYVdnCxodRIgeJdl2CzDrHw?e=whpEld`

## Arsitektur & Design Decisions

### Layer Stack

```text
Plaintext
  → xor_encrypt()          # Cipher: c = ord(m) ^ 42
  → + DELIMITER            # Sentinel: "<<<END>>>"
  → text_to_bits()         # MSB-first per byte
  → LSB Write (RGB flat)   # flat[i] = (pixel & 0xFE) | bit
  → PNG save               # Lossless — wajib
```

### Catatan Singkat

- `app.py` menjalankan UI Streamlit untuk memasukkan pesan ke gambar dan mengekstrak kembali.
- Format output yang disarankan adalah `PNG` karena sifat lossless-nya.
- `DELIMITER` digunakan untuk menandai akhir payload yang disisipkan.
- `Video Penjelasan` merupakan video yang menjelaskan cara kerja aplikasi.

