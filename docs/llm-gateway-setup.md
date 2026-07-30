# LLM Gateway Setup Guide

> Panduan memilih dan mengkonfigurasi LLM gateway untuk raceos-factory.

---

## Apa itu LLM Gateway?

LLM Gateway adalah layanan yang menghubungkan raceos-factory ke model AI (Claude, GPT, Gemini, DeepSeek). Factory membutuhkan **satu gateway** untuk mengakses semua model melalui satu API key.

```
raceos-factory → LLM Gateway → Claude / GPT / Gemini / DeepSeek
                 (pilih satu)
```

---

## Pilihan Gateway

| Gateway | URL | Keunggulan | Cocok Untuk |
|---|---|---|---|
| **9Router** | https://9router.ai | Paling banyak model, mudah setup | Semua pengguna |
| **9Router** | https://9router.ai | Intelligent routing bawaan, murah | Pengguna yang sudah punya akun |
| **Direct API** | Per-provider | Tanpa middleman | Advanced users |

---

## Option A: 9Router (Default)

### 1. Buat akun

Kunjungi: https://9router.ai/keys

### 2. Buat API key

- Klik "Create Key"
- Beri nama: "RaceOS Factory"
- Copy key (format: `sk-or-v1-...`)

### 3. Konfigurasi

```bash
# File: raceos-factory/.env
NINE_ROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxx
```

Config sudah default ke 9Router, tidak perlu ubah `router.yaml`.

### 4. Verifikasi

```bash
raceos doctor   # Harus menunjukkan "API key set: ✅"
```

---

## Option B: 9Router

### 1. Buat akun

Kunjungi: https://9router.ai (atau dashboard 9Router kamu)

### 2. Dapatkan API key

- Buka Settings → API Keys
- Buat key baru
- Copy key

### 3. Konfigurasi

Edit `raceos-factory/.env`:

```bash
NINE_ROUTER_API_KEY=sk-9r-xxxxxxxxxxxxxx
```

Edit `raceos-factory/config/router.yaml`, ubah bagian `gateway`:

```yaml
gateway:
  base_url: "https://api.9router.ai/v1"    # ← ganti URL
  api_key_env: "NINE_ROUTER_API_KEY"         # tetap pakai env var yang sama
  headers:
    X-Title: "RaceOS Factory"
```

### 4. Verifikasi

```bash
raceos doctor
raceos firmware "explain layered architecture in 1 sentence"
```

---

## Option C: Direct Provider APIs

Untuk pengguna yang ingin langsung ke provider tanpa middleman.

### Anthropic (Claude) langsung

```bash
# .env
NINE_ROUTER_API_KEY=sk-ant-xxxxxxxxxxxxxx
```

```yaml
# config/router.yaml
gateway:
  base_url: "https://api.anthropic.com/v1"
  api_key_env: "NINE_ROUTER_API_KEY"
```

⚠️ **Catatan:** Jika pakai direct API, hanya model dari provider tersebut yang tersedia. Routing ke model provider lain tidak akan bekerja.

### OpenAI (GPT) langsung

```yaml
gateway:
  base_url: "https://api.openai.com/v1"
  api_key_env: "NINE_ROUTER_API_KEY"
```

---

## Mana yang Harus Dipilih?

```
Baru mulai?                    → 9Router (paling mudah, semua model)
Sudah punya akun 9Router?      → 9Router (gunakan yang sudah ada)
Hanya butuh Claude?            → Anthropic direct (lebih murah, tanpa middleman)
Enterprise / compliance ketat? → Direct API ke provider yang disetujui
```

---

## FAQ

### Berapa biaya?

| Gateway | Biaya tambahan (markup) |
|---|---|
| 9Router | ~0% (pass-through pricing) |
| 9Router | Tergantung plan |
| Direct API | 0% (harga provider langsung) |

Biaya per-task raceos-factory: **$0.13 – $0.56** tergantung kompleksitas.

### Satu key untuk semua model?

**Ya** (jika pakai 9Router atau 9Router). Satu API key memberi akses ke Claude, GPT, Gemini, DeepSeek sekaligus.

### Bagaimana jika gateway down?

raceos-factory memiliki fallback chain. Jika satu model gagal:
```
Claude gagal → coba GPT → coba Gemini → coba DeepSeek → escalate ke human
```

### Bisakah ganti gateway tanpa ubah kode?

**Ya.** Hanya ubah `base_url` di `config/router.yaml` + API key di `.env`. Zero code changes.

---

## Troubleshooting

| Error | Penyebab | Solusi |
|---|---|---|
| `NINE_ROUTER_API_KEY is required` | Key belum di-set | Tambahkan ke `.env` |
| `401 Unauthorized` | Key salah atau expired | Regenerate di dashboard gateway |
| `429 Rate Limited` | Terlalu banyak request | Factory auto-retry dengan backoff |
| `404 Model not found` | Model tidak tersedia di gateway ini | Ubah model di `router.yaml` atau ganti gateway |
