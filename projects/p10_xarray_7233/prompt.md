# p10_xarray_7233

## Task

`Dataset.coarsen(...).construct(...)` demotes non-dimension coordinates to data variables. A
coordinate that is not among the dimensions being reshaped must come back as a coordinate.

## Reproduction

```python
import numpy as np
import xarray as xr

da = xr.DataArray(np.arange(24), dims=["time"]).assign_coords(day=lambda d: 365 * d)
ds = da.to_dataset(name="T")

result = ds.coarsen(time=12).construct(time=("year", "month"))

list(result.coords)     # []                 -- expected ['day']
list(result.data_vars)  # ['day', 'T']       -- 'day' should not be here
```

The `DataArray` path already keeps `day`; the `Dataset` path loses it. Both must agree with the
coordinates of the object the call started from.

## Files

The fix belongs in `xarray/core/rolling.py`, in `Coarsen.construct`. `test_coarsen_construct.py`
in the repository root is the visible suite and `xarray/tests/test_coarsen.py` holds the tests it
selects; read them, and do not modify either.

Do not install the package. `import xarray` resolves against the source tree in the working
directory, which is how the suite is run.

## Verification

Run `python -m pytest -q test_coarsen_construct.py` before you finish; the harness runs the full
tier afterwards.
