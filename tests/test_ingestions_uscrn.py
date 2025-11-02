# tests/test_ingestions_uscrn.py
from pathlib import Path
from src.ingestion.uscrn import open_uscrn_hourly

def test_uscrn_parses_fixture():
    p = Path("data/golden/uscrn_hourly_sample.txt")
    df = open_uscrn_hourly(p)
    assert df.shape[0] >= 3
    assert {"wban","timestamp_utc","t_air_c","precip_mm","qc_flags"} <= set(df.columns)
    # each row matches the pattern exactly once
    assert (df["timestamp_utc"].str.count_matches(r"T\d{2}:00:00Z") == 1).all()
