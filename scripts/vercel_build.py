"""Copy only public UI assets into Vercel's CDN directory; no credentials or DB access."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    public = root / "public"
    for source_name, target_name in (("static", "static"), ("insights_ui", "insights-assets")):
        source = root / source_name
        destination = public / target_name
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for path in source.rglob("*"):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".css", ".js"}:
                target = destination / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    print("Vercel public assets prepared. No webhook or database changes performed.")


if __name__ == "__main__":
    build()
