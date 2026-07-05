import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
