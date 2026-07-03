import os
import sys

# Project root on sys.path and as cwd (loads .env via pydantic-settings).
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

from app import create_app

app = create_app()
application = app  # PythonAnywhere expects this name
