"""Umgebungsprobe für die Kamera-Entwicklung (read-only, keine Seitenwirkungen)."""

import importlib
import sys

def main() -> None:
    print("python:", sys.version.split()[0])
    for name in ("fastapi", "uvicorn", "pytest", "httpx", "pydantic"):
        try:
            mod = importlib.import_module(name)
            print(f"{name}: OK", getattr(mod, "__version__", ""))
        except Exception as error:
            print(f"{name}: FEHLT ({type(error).__name__})")
    for tool in ("exiftool", "rsync", "ffmpeg", "sha256sum", "curl", "git"):
        import shutil
        print(f"tool {tool}:", shutil.which(tool) or "FEHLT")

if __name__ == "__main__":
    main()
