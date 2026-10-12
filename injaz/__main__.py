"""
Module entry point allowing execution via `python -m injaz` and standalone PyInstaller executable.
"""
import sys
import os
import traceback

log_file = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "injaz_debug.log")
try:
    log_fp = open(log_file, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_fp
    if sys.stderr is None:
        sys.stderr = log_fp
except Exception:
    log_fp = None


def run():
    try:
        if log_fp:
            log_fp.write(f"STARTUP: argv={sys.argv}\n")

        # Windows DLL discovery for frozen PyInstaller environment
        if sys.platform == "win32":
            meipass = getattr(sys, "_MEIPASS", None)
            if not meipass:
                meipass = os.path.dirname(sys.executable)
            for sub in ["PySide6", "shiboken6", ""]:
                p = os.path.join(meipass, sub)
                if os.path.isdir(p):
                    try:
                        os.add_dll_directory(p)
                    except Exception:
                        pass
                    os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

            # Ensure Windows System32 is registered for native OS ICU libraries
            system32 = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
            if os.path.isdir(system32):
                try:
                    os.add_dll_directory(system32)
                except Exception:
                    pass
                os.environ["PATH"] = system32 + os.pathsep + os.environ.get("PATH", "")

        from injaz.main import main
        code = main()
        if log_fp:
            log_fp.write(f"MAIN_RETURNED: {code}\n")
        sys.exit(code)
    except Exception as e:
        if log_fp:
            log_fp.write(f"CRASH: {e}\n{traceback.format_exc()}\n")
        sys.exit(1)


if __name__ == "__main__":
    run()
