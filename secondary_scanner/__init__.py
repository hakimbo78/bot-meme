"""
Scanner package
"""
import sys
import os

# Add parent directory to path so we can import from scanner.py
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import BaseScanner from the scanner.py file in parent directory
try:
    from scanner import BaseScanner
    __all__ = ['BaseScanner']
except ImportError:
    __all__ = []