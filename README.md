# Potret Harga Rumah Jabodetabek

Dashboard Streamlit untuk membandingkan pilihan rumah berdasarkan anggaran di lima wilayah Jabodetabek.

## Menjalankan di Windows

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Jika `.venv` sudah ada, gunakan lingkungan tersebut. Buka http://localhost:8501.

## Cara membaca dashboard

- **Pilihan menurut anggaran** menunjukkan jumlah kumulatif listing dan ranking persentase per wilayah. Penyebut ranking mencakup seluruh listing dengan harga valid di tiap wilayah. Batas anggaran bersifat inklusif.
- **Spesifikasi rumah** merangkum luas bangunan tengah per wilayah dan kombinasi kamar untuk listing yang masuk anggaran. Tabel listing, pencarian, dan unduhan CSV ada di bawah grafik.
- Pilihan anggaran dan wilayah berlaku di kedua halaman. Nilai awal anggaran Rp1 miliar.

Sumber data adalah `data/Data_Rumah_Jabodetabek.xlsx`, sheet `Data`. Angka menunjukkan harga penawaran rumah sekunder. Workbook tidak memuat periode pengumpulan. Setiap baris dihitung sebagai satu listing.

## Deploy di Streamlit Community Cloud

Unggah isi folder ini ke lokasi `app.py` pada repo GitHub. Pertahankan folder `data/` dan `.streamlit/`.

Untuk deploy baru, pilih repository dan branch di Streamlit Community Cloud. Jika file berada di root repo, isi **Main file path** dengan `app.py`. Untuk memperbarui app yang sudah terhubung, commit file ke branch dan lokasi yang dipakai app tersebut.
