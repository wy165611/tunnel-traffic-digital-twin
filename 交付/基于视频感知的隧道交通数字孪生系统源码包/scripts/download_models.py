"""Download existing pretrained weights and verify pinned SHA-256; never train."""
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.settings import DATA
from backend.vision.weights import sha256_file


def download_file(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "TunnelTrafficTwin/1.0"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def main() -> int:
    destination = DATA / "models"
    destination.mkdir(parents=True, exist_ok=True)
    models = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    for model in models:
        path = destination / model["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        expected = model["sha256"]
        if path.exists() and sha256_file(path) == expected:
            print("Verified:", model["name"])
            continue

        temporary = path.with_suffix(path.suffix + ".download")
        last_error = None
        for attempt in range(3):
            try:
                temporary.unlink(missing_ok=True)
                download_file(model["url"], temporary)
                actual = sha256_file(temporary)
                if actual != expected:
                    raise ValueError(f"SHA-256 mismatch: expected {expected}, got {actual}")
                temporary.replace(path)
                print("Downloaded and verified:", model["name"])
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                temporary.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if last_error is not None:
            print(f"Failed to download or verify {model['name']}: {last_error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
