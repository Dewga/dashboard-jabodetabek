# Potret Harga Rumah Jabodetabek

Dashboard Streamlit untuk PSD Kelompok 3 dengan dua menu: **Harga Antarwilayah**
dan **Harga & Spesifikasi Rumah**. Filter wilayah dan harga tetap tersimpan
ketika berpindah menu.

## Menjalankan di Windows

Buka terminal PowerShell di folder proyek ini:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Jika virtual environment belum ada, buat dengan `py -m venv .venv` terlebih dahulu.
Buka URL yang ditampilkan terminal, biasanya http://localhost:8501.
Hentikan aplikasi dengan Ctrl+C pada terminal tersebut.
Jalankan dari folder proyek agar `.streamlit/config.toml` terbaca.

## Fitur tahap ini

- Sidebar dengan dua menu, multiselect wilayah, harga minimum–maksimum dalam rupiah,
  dan Reset filter. Batas harga inklusif dan dapat diketik.
- Tiga KPI: jumlah listing, median harga, dan rentang tengah Q1–Q3.
- Grafik batang median dari tertinggi, sumbu mulai nol, dengan jumlah listing
  per wilayah dan tooltip harga rupiah lengkap.
- Temuan utama mengikuti filter, termasuk satu wilayah dan median tertinggi seri.
- Box plot dengan sumbu logaritmik, Q1/median/Q3, whisker 1,5 × IQR,
  jumlah valid per wilayah, dan titik ekstrem. Kuartil dihitung dari rupiah asli
  memakai interpolasi linear; tidak ada pemangkasan harga ekstrem.
- Pesan hasil kosong, KPI 0/—/—, dan reset. Harga minimum melebihi maksimum
  menghasilkan peringatan yang jelas.

Menu Harga & Spesifikasi Rumah:

- Tiga KPI: median luas tanah, median luas bangunan (masing-masing hanya nilai
  positif dan terhingga, disertai jumlah observasi), serta kombinasi kamar teratas.
  Kombinasi seri ditandai dan seluruh pasangannya dirinci di panel heatmap.
- Scatter lebar dengan pilihan Luas Bangunan (default) atau Luas Tanah.
  Kedua sumbu logaritmik memakai satuan asli. Tooltip berisi nama, wilayah,
  lokasi, harga, kedua luas, kamar tidur, dan kamar mandi. Warna wilayah sama
  dengan menu pertama. Tidak ada sampling atau penghapusan titik ekstrem.
- Pearson log-log luas bangunan–harga mulai 10 pasangan valid, dengan variasi
  pada kedua variabel. Kondisi yang tidak memenuhi syarat diberi penjelasan.
- Heatmap grid 1–6 × 1–6 berisi jumlah dan persentase dari seluruh hasil filter;
  cakupan grid ditampilkan. Grafik median luas berpasangan berada di sebelahnya,
  dengan jumlah observasi positif tiap ukuran di tooltip.
- Bagian Lihat Tabel Listing dengan pencarian nama/lokasi tanpa membedakan
  kapitalisasi dan CSV UTF-8 dengan BOM. Tabel dan CSV memakai baris yang sama;
  pencarian tidak mengubah KPI atau grafik.

Komposisi segmen harga pada menu pertama belum termasuk tahap ini.

## Sumber dan rekonsiliasi

Satu-satunya sumber adalah `data/Data_Rumah_Jabodetabek.xlsx`, sheet `Data`.
File dibaca menggunakan pandas/openpyxl tanpa menulis kembali ke workbook.
Cache pembacaan diperbarui ketika waktu modifikasi file berubah. Setiap baris
tetap dihitung sebagai listing; tidak ada penghapusan duplikat otomatis.

| Wilayah | Listing | Median harga | Pasangan harga–luas bangunan positif |
| --- | ---: | ---: | ---: |
| Bekasi | 535 | Rp620.000.000 | 534 |
| Bogor | 1.105 | Rp630.000.000 | 1.101 |
| Depok | 353 | Rp1.100.000.000 | 351 |
| Jakarta | 149 | Rp3.770.000.000 | 145 |
| Tangerang | 162 | Rp1.260.000.000 | 161 |
| Total | 2.304 | Rp690.000.000 | 2.292 |

Seluruh harga positif. Dua belas listing memiliki luas bangunan nol. Listing
tersebut tetap masuk analisis harga pada menu pertama. Angka 2.304 dan 2.292
cocok dengan blueprint, tetapi memakai cakupan yang berbeda.

Q1 harga penuh = **Rp540.000.000**, Q3 = **Rp1.280.000.000**. Q3 berbeda dari
patokan awal Rp1,26 miliar pada blueprint/mockup; aplikasi menggunakan hasil Excel.
Harga adalah harga penawaran, bukan harga transaksi.

Angka acuan spesifikasi pada seluruh data juga cocok dengan blueprint:
**2.292** pasangan harga–luas bangunan positif, **2.301** pasangan harga–luas
tanah positif, dan **1.167** listing berkombinasi 2 kamar tidur–1 kamar mandi
(50,7% dari 2.304). Pearson log-log bangunan–harga **0,7632687107**.
Median luas tanah positif **79 m²** (2.301 observasi), median luas bangunan
positif **60 m²** (2.292 observasi).

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p test_app.py -v
```

Pengujian menggunakan Streamlit AppTest terhadap Excel asli: semua wilayah,
satu wilayah, perubahan rentang harga, grafik dan kuartil, navigasi dengan
filter yang bertahan, reset, pilihan wilayah kosong, rentang tanpa listing,
dan batas harga terbalik. SHA-256 workbook dibandingkan sebelum dan sesudah
pengujian untuk memastikan sumber tidak berubah.

Pengujian menu spesifikasi juga memeriksa tiga angka acuan, jumlah titik saat
berganti jenis luas, nilai setiap median luas per wilayah, heatmap, wilayah
tunggal, anggaran inklusif, filter yang bertahan saat berpindah menu, pencarian,
kesamaan baris tabel dengan CSV yang benar-benar dikirim ke widget unduhan,
kondisi hasil kosong, serta hasil filter yang memiliki luas bangunan nol
sehingga scatter tidak tersedia tetapi visual lain tetap berfungsi.
