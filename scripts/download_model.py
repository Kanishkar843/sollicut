"""Public model download at build/setup time; never blocks HTTP startup."""
import os
from pathlib import Path
from faster_whisper.utils import download_model

if __name__ == "__main__":
    model = os.getenv("SOLLICUT_ASR_MODEL", "base")
    target = Path(os.getenv("SOLLICUT_MODEL_DIR", "models")) / model
    target.mkdir(parents=True, exist_ok=True)
    download_model(model, output_dir=str(target))
    print(f"Public {model} model downloaded to {target}")
