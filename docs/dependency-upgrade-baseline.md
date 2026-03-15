# Dependency Upgrade Baseline (Phase 0)

Captured on: 2026-03-07 (Australia/Sydney)

## Environment
- Python: `3.12.10`
- Pip: `25.0.1`

## Baseline Commands
- `python --version`
- `python -m pip freeze > docs/baseline-freeze.txt`
- `python -m pip check`
- `python -m unittest -q`
- Streamlit smoke startup command:
  - `streamlit run streamlit_app.py --server.headless true --server.port 8509`

## Baseline Results
- `pip check`: passed (no broken requirements)
- `unittest`: passed (`Ran 16 tests`)
- Streamlit smoke: startup command available only after dependency upgrade in this shell.
  The `streamlit.exe` command launched and served until timeout (headless smoke).

## Interaction Baseline Notes
Observed user-facing bottlenecks before optimizations:
- Full rerun latency when switching chart scope widgets.
- DWR-heavy summary rendering for wide/long datasets.

These are addressed in subsequent implementation:
- Render caching in Streamlit view flow
- Endpoint-only DWR for summary tables
- Workload-aware auto resampling for DWR
