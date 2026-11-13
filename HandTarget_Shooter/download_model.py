"""Download official Google MediaPipe Hand Landmarker model one time."""
from __future__ import annotations
import shutil
from pathlib import Path
from urllib.request import urlopen

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"


def main():
    MODEL_PATH.parent.mkdir(exist_ok=True)
    if MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 1_000_000:
        print("Hand model found:", MODEL_PATH)
        return
    temporary = MODEL_PATH.with_suffix(".download")
    try:
        print("Downloading official model (first launch only):", MODEL_URL)
        with urlopen(MODEL_URL, timeout=45) as src, temporary.open("wb") as out:
            shutil.copyfileobj(src, out)
        if temporary.stat().st_size < 1_000_000:
            raise RuntimeError("Download incomplete")
        temporary.replace(MODEL_PATH)
        print("Model ready:", MODEL_PATH)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
