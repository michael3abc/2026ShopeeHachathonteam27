"""Add the static keynote to the existing Explorer Pages artifact."""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "presentation" / "dist"
TARGET.mkdir(parents=True, exist_ok=True)
for name in ("presentation.html", "index.html", "css", "js", "assets"):
    source = HERE / name
    destination = TARGET / "slide" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
(TARGET / "presentation.html").write_text(
    (HERE / "index.html").read_text(encoding="utf-8").replace(
        "presentation.html", "slide/presentation.html"
    ), encoding="utf-8"
)
print("Keynote ready: presentation/dist/slide/presentation.html")
