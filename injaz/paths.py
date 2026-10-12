"""
Path and asset resolution utilities for INJAZ (إنجاز).
Provides reliable location of runtime assets in development, testing,
and frozen PyInstaller standalone distributions.
"""
import os
import sys


def get_assets_dir() -> str:
    """
    Returns the absolute path to the assets directory,
    handling both source development and frozen PyInstaller executables.
    """
    # 1. PyInstaller _MEIPASS extraction directory
    if hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, "assets")
        if os.path.exists(candidate):
            return candidate

    # 2. Frozen onedir distribution beside executable
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        for rel in ["assets", os.path.join("_internal", "assets")]:
            candidate = os.path.join(exe_dir, rel)
            if os.path.exists(candidate):
                return candidate

    # 3. Development root relative to this module (injaz/paths.py -> root/assets)
    dev_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(dev_root, "assets")
    if os.path.exists(candidate):
        return candidate

    # 4. Fallback to current working directory
    return os.path.join(os.getcwd(), "assets")


def get_asset_path(filename: str) -> str:
    """
    Returns the absolute path to a specific asset filename.
    """
    return os.path.join(get_assets_dir(), filename)
