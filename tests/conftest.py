import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)
