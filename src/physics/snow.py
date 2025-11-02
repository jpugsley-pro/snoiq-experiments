# src/physics/snow.py
from __future__ import annotations
import xarray as xr

def slr_temp_ramp(t2m_c: xr.DataArray | float) -> xr.DataArray:
    t = xr.DataArray(t2m_c) if not isinstance(t2m_c, xr.DataArray) else t2m_c
    slr = xr.where(t >= 0.0, 8.0, 8.0 + (-(t) / 12.0) * (18.0 - 8.0))
    slr = xr.where(t <= -18.0, 22.0, slr)
    return slr

def snowfall_depth_mm(qpe_mm: xr.DataArray, t2m_c: xr.DataArray | float) -> xr.DataArray:
    return qpe_mm * slr_temp_ramp(t2m_c)

def to_inches(mm: xr.DataArray | float) -> xr.DataArray:
    a = xr.DataArray(mm) if not isinstance(mm, xr.DataArray) else mm
    return a / 25.4
