import os
import sys

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_app = os.path.join(_root, "app")
if _app not in sys.path:
    sys.path.insert(0, _app)
