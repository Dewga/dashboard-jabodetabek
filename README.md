# Potret Harga Rumah Jabodetabek

Dashboard Streamlit untuk membandingkan pilihan rumah dan menguji estimasi harga penawaran di lima wilayah Jabodetabek.

## Menjalankan di Windows

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Jika `.venv` sudah ada, gunakan lingkungan tersebut. Buka http://localhost:8501.

## Cara membaca dashboard

- **Ringkasan** menjelaskan tujuan proyek, cakupan data, dan komposisi listing per wilayah.
- **Eksplorasi** memuat grafik dan pembanding anggaran, ranking, serta rentang luas bangunan. Heatmap kamar, perbandingan luas serupa, dan tabel listing dengan CSV tersedia di panel detail. Anggaran awal Rp1 miliar, batasnya inklusif dan berlaku pada kedua tampilan eksplorasi.
- **Metode dan Model** menjelaskan aturan kelayakan, pemisahan berdasarkan kelompok lokasi, MAE validasi dan uji, serta simulasi harga penawaran. Model dilatih saat pertama dibutuhkan dan disimpan dalam cache berdasarkan data yang digunakan.
- **Temuan** merangkum hasil eksplorasi dan evaluasi model menggunakan cakupan workbook, terpisah dari filter pengguna.

Sumber data adalah `data/Data_Rumah_Jabodetabek.xlsx`, sheet `Data`. Angka menunjukkan harga penawaran rumah sekunder. Workbook tidak memuat periode pengumpulan. Setiap baris dihitung sebagai satu listing.

Untuk deployment, sertakan `housing_model.py` bersama `app.py`, komponen dashboard, CSS, konfigurasi Streamlit, workbook, dan `requirements.txt`.

Jalankan pengujian dengan `.\.venv\Scripts\python.exe -m unittest -v`.
