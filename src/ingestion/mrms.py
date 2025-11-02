# src/ingestion/mrms.py
from __future__ import annotations
from pathlib import Path
import re, numpy as np, xarray as xr, pygrib
import csv

# Minimal mapping from filename token → canonical name + attrs
_CANON = {
    "MultiSensor_QPE_01H_Pass2_00.00": {
        "name": "QPE_01H_Pass2",
        "units": "mm",
        "long_name": "MRMS MultiSensor QPE 1h (Pass2)",
        "expected_stepType": "accum",
    }
}

_NAME_RE = re.compile(r"MRMS_(.+?)_\d{8}-\d{6}\.grib2$")

def _token_for(path: Path) -> str | None:
    m = _NAME_RE.match(path.name)
    return m.group(1) if m else None

def _load_user_table(csv_path: str | Path) -> dict[str, dict]:
    # MRMS v12.2 user table CSV columns include: Discipline,Category,Parameter,Name,Unit,...
    out = {}
    with open(csv_path, newline="") as fp:
        for row in csv.DictReader(fp):
            out[row["Name"]] = {
                "discipline": row.get("Discipline"),
                "category": row.get("Category"),
                "parameter": row.get("Parameter"),
                "unit": row.get("Unit"),
            }
    return out

def open_mrms_qpe(path: str | Path, user_table_csv: str | Path | None = None) -> xr.DataArray:
    f = Path(path)
    token = _token_for(f)
    canon = _CANON.get(token or "", {"name": "qpe", "units": "mm", "long_name": "MRMS QPE"})

    # Try cfgrib first; fall back to pygrib
    try:
        ds = xr.open_dataset(f, engine="cfgrib", backend_kwargs={"indexpath": ""})
        first = list(ds.data_vars)[0]  # often 'unknown'
        da = ds[first].astype("float32")
    except Exception:
        # pygrib may not have typed stubs; silence attribute warning for the call
        with pygrib.open(str(f)) as g: # type: ignore[attr-defined]
            msg = next(iter(g))
            data, lats, lons = msg.data()
        da = xr.DataArray(
            data.astype("float32"),
            coords={"lat": lats[:,0], "lon": lons[0,:]},
            dims=("lat","lon")
        )

    # Clean
    da = xr.where(~np.isfinite(da), 0, da)
    da = xr.where(da < 0, 0, da)

    # Attach canonical attrs; optionally enrich from user table
    attrs = {"long_name": canon["long_name"], "units": canon["units"], "product_token": token or "unknown"}
    if user_table_csv and token:
        tbl = _load_user_table(user_table_csv)
        if token in tbl:
            meta = tbl[token]
            attrs.update({
                "GRIB_discipline": meta["discipline"],
                "GRIB_category": meta["category"],
                "GRIB_parameter": meta["parameter"],
                "units": meta["unit"] or canon["units"],
            })
    return da.rename(canon["name"]).assign_attrs(attrs)
