"""Local checkout import helper for tests before editable installation."""

from pathlib import Path
import os
import sys

# Third-party pytest plugins in the execution environment can monkey-patch subprocess
# handling and make CLI subprocess tests hang. The repository test suite has no plugin
# dependency, so disable autoload when tests run from this checkout.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

src = Path(__file__).resolve().parent / "src"
if src.exists() and str(src) not in sys.path:
    sys.path.insert(0, str(src))
