from pathlib import Path

root = Path(__file__).resolve().parents[1]
count = 0
for directory in ("backend", "frontend/src", "scripts", "tests", "pitch"):
    for path in (root / directory).rglob("*"):
        if path.suffix in {".py", ".ts", ".tsx", ".css"}:
            count += sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())
print(f"Project-specific nonblank source lines (excluding locks/vendor/builds): {count}")
