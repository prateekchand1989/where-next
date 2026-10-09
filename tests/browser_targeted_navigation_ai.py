"""Compatibility entry point for navigation and mocked AI browser regressions.

The former main-content navigation was intentionally replaced by persistent
sidebar buttons. The interaction suite checks the replacement plus reactive AI
at all five viewport widths in both themes.
"""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('browser_interaction_improvements.py')),
                   run_name='__main__')
