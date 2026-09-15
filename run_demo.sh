#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -x .venv/bin/python ]]; then
  demo_python=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  demo_python=python3
elif command -v python >/dev/null 2>&1; then
  demo_python=python
else
  echo "Python 3.12+ is required. See README.md for installation." >&2
  exit 1
fi
"$demo_python" - <<'PYTHON'
import importlib.util
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12+ is required. Create a .venv using Python 3.12 (see README.md).")
missing = [name for name in ("maniloop", "mujoco", "numpy", "PIL", "openai") if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("Missing dependencies: " + ", ".join(missing) +
                     ". Run: python -m pip install -r requirements.txt in your .venv.")
PYTHON
exec "$demo_python" -m arx5_demo.app "$@"
