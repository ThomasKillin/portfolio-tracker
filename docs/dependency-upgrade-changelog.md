# Dependency Upgrade Changelog (Python 3.12 Modernization)

Date: 2026-03-07

## Runtime Target
- Primary runtime standardized on Python 3.12.

## Dependency Management
- Added `requirements.in` (direct dependency spec with guardrails).
- Recompiled `requirements.txt` as a full pinned transitive set via `pip-tools`.
- Added `scripts/deps.ps1` for install/compile/sync/check workflows.

## Key Library Changes
- `streamlit` -> `1.55.0`
- `pandas` -> `2.3.3`
- `numpy` -> `2.4.2`
- `scipy` -> `1.17.1`
- `matplotlib` -> `3.10.8`
- `seaborn` -> `0.13.2`
- `plotly` -> `6.6.0`
- `finnhub-python` -> `2.4.27`
- `python-dotenv` -> `1.2.2`
- `requests` -> `2.32.5`
- `yfinance` remains pinned at `1.2.0` (compatibility with current provider path)

## Validation Summary
- `pip check`: passed
- `python -m unittest -q`: passed
- `python -m py_compile streamlit.py share_tracking.py graphs.py performance_calcs.py`: passed
- `asx_data_probe.py`: Yahoo long-history access validated for major ASX tickers
  - `BHP.AX`, `CBA.AX`, `WES.AX` met 20y target
  - `STW.AX`, `VAS.AX` did not meet 20y because listing history is < 20 years

## Notable Compatibility Notes
- `streamlit.py` filename can shadow package import in some `python -m ...` invocation paths.
  Prefer launching via `streamlit run streamlit.py` (CLI executable) in practice.
