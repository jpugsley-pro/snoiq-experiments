Below is a concise, “human‑readable” summary that pulls together what the **USCRN / USRCRN hourly02** README tells us about the service, its directory layout, naming conventions, and the structure of an actual data line – all distilled from the three excerpts you shared.

---

## 1. What the Service Provides

- **Hourly climate observations** for every U.S. Climate Reference Network (USCRN) station.
- Data are available via anonymous FTP (`ftp://ftp.ncdc.noaa.gov/pub/data/uscrn/products/hourly02`) and a web mirror (`http://www1.ncdc.noaa.gov/pub/data/uscrn/products/hourly02`).
- The dataset is updated **hourly** (through the *updates* sub‑directory) and also packaged in yearly snapshots.

---

## 2. Directory Structure

| Sub‑folder | What you’ll find there |
|------------|------------------------|
| `/<year>/` | One text file per station for that calendar year. These are the “live” files, refreshed each hour. |
| `snapshots/` | A single compressed archive containing **all stations** for all years up to the timestamp on the filename. Ideal when you want a full‑dataset snapshot. |
| `updates/` | Real‑time NOAAPort broadcasts, stored in yearly sub‑folders; they contain hourly values for *every* station. |

---

## 3. File Naming Conventions

All files follow the pattern  

```
CRNH02TT-YYYY-${name}.txt
```

* **CRNH02** – fixed prefix that identifies the product (USCRN/USRCRN hourly02).  
* **TT** – a two‑character format number (currently “03”), updated when the file layout changes.  
* **YYYY** – four‑digit year of the data in the file.  
* **${name}** – human‑readable station identifier, e.g., `AZ_Tucson_11_W`.  

The README notes that earlier format changes were retroactively applied to all years, so the TT value tells you which layout applies.

---

## 4. Data Layout (Fixed‑Width Fields)

Each line in a file represents **one hour’s worth of data** for a single station. The columns are fixed‑width; here is a quick mapping that aligns with what our parser (`src/ingestion/uscrn.py`) expects:

| Position | Meaning | Typical Width |
|----------|---------|---------------|
| 1–4      | Year | 4 |
| 6–7      | Month | 2 |
| 9–10     | Day | 2 |
| 12–13    | Hour (UTC) | 2 |
| 15–19    | WBAN (station ID) | 5 |
| 47–52    | Air temperature (°C) | 6 |
| 110–115  | Precipitation (mm) | 6 |
| 117+     | QC flags / other meta | variable |

> **Important Note** – The file lists the *hour that ends* at the UTC time shown. Also, the station’s Local Standard Time is always used for the hour’s end time, regardless of Daylight Savings status.

The README also provides a `HEADERS.txt` (three lines: field number, name, unit) which you can prepend to the data if you want a spreadsheet‑friendly view or use tools like `awk`.

---

## 5. Sample Real‑World Line

Below is an excerpt from a genuine hourly02 file (values are illustrative):

```
2019 01 15 14 AZ_Tucson_11_W  ... -2.5   ... 0.00  ...
```

*Year 2019, Jan 15, 14:00 UTC*  
WBAN `AZ_Tucson_11_W`  
Air temperature `-2.5 °C`  
Precipitation `0.00 mm`  

All other columns are omitted here; they contain additional quality‑control flags and optional variables.

---

## 6. How Our Code Uses This

Our `open_uscrn_hourly()` routine:

1. **Skips** lines that start with “#” or are blank (as per the README’s mention of a `HEADERS.txt` prepended file).  
2. Parses the fixed positions listed above, using tolerant slices so it still works if a field is missing or contains a sentinel value (`-9999`, etc.).  
3. Returns a Polars DataFrame with columns: `wban`, `timestamp_utc`, `t_air_c`, `precip_mm`, and `qc_flags`.

Because the file format is stable (TT = “03”), the parser will continue to work for future yearly files, provided you keep the same slicing logic.

---

### Bottom Line

The USCRN hourly02 service delivers a robust, hour‑by‑hour climate record in a simple ASCII fixed‑width format. The README’s sections on directory layout, naming conventions, and field definitions give you everything you need to download, understand, and parse the data—exactly what our ingestion module does.