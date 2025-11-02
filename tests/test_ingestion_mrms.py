# tests/test_ingestion_mrms.py
from pathlib import Path

from src.ingestion.mrms import open_mrms_qpe


def test_mrms_qpe_contract():
    f = next(Path("data/raw/mrms").rglob("*.grib2"))
    da = open_mrms_qpe(f, user_table_csv="data/refs/UserTable_MRMS_v12.2.csv")
    assert da.name == "QPE_01H_Pass2"
    assert da.dims == ("latitude", "longitude")
    assert da.attrs.get("units") == "mm"
    assert (da >= 0).all().item()
