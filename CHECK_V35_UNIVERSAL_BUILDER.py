# Compatibility launcher: V35.1 supersedes the original 10-check V35 suite.
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().with_name('CHECK_V351_UNIVERSAL_BUILDER.py')), run_name='__main__')
