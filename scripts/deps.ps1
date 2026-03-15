param(
    [ValidateSet("install", "compile", "sync", "check")]
    [string]$Task = "check"
)

$ErrorActionPreference = "Stop"

switch ($Task) {
    "install" {
        python -m pip install --upgrade pip
        python -m pip install --upgrade pip-tools
        python -m pip install -r requirements.txt
    }
    "compile" {
        python -m pip install --upgrade pip-tools
        python -m piptools compile --upgrade --resolver=backtracking --output-file requirements.txt requirements.in
    }
    "sync" {
        python -m pip install --upgrade pip-tools
        python -m piptools sync requirements.txt
    }
    "check" {
        python -m pip check
        python -m unittest -q
        python -m py_compile streamlit_app.py share_tracking.py graphs.py performance_calcs.py
    }
}
