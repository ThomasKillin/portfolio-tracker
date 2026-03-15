# Dependency Upgrade Validation (Phases 2–4)

Date: 2026-03-07

## Installed Key Versions (Python 3.12)
- streamlit: 1.55.0
- pandas: 2.3.3
- numpy: 2.4.2
- scipy: 1.17.1
- yfinance: 1.2.0
- plotly: 6.6.0
- matplotlib: 3.10.8
- seaborn: 0.13.2
- requests: 2.32.5

## Validation Commands
- `python -m pip check`
- `python -m unittest -q`
- `python -m py_compile streamlit_app.py share_tracking.py graphs.py performance_calcs.py`
- `python asx_data_probe.py --tickers BHP.AX CBA.AX WES.AX STW.AX VAS.AX`

## Validation Results
- `pip check`: passed
- unit tests: passed (`Ran 16 tests`)
- py_compile: passed
- Streamlit smoke startup (`streamlit.exe run streamlit_app.py --server.headless true`): process started successfully (terminated via timeout in automated check)
- ASX probe:
  - `BHP.AX`, `CBA.AX`, `WES.AX` meet 20y target
  - `STW.AX`, `VAS.AX` do not meet 20y target due listing age

## Notes
- yfinance fallback/soft-fail behavior remains intact in tests and runtime.
- Existing benchmark/summary rendering semantics (blank benchmark TWR/DWR cells, style gradients) remain functional after upgrades.
