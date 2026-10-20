"""Locate the bundled SDFormat schemas before loading native bindings."""

import os
import sys
from pathlib import Path


schemas = Path(sys._MEIPASS) / 'share/sdformat15'
existing = os.environ.get('SDF_PATH', '')
os.environ['SDF_PATH'] = str(schemas) + (os.pathsep + existing if existing else '')
