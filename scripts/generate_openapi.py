"""Generate openapi-spec.json from the FastAPI app.

Usage: uv run python -m scripts.generate_openapi
"""

import json
from pathlib import Path

from src.main import app

spec = app.openapi()
out = Path(__file__).resolve().parent.parent / "openapi-spec.json"
out.write_text(json.dumps(spec, indent=2) + "\n")
print(f"Wrote {out} ({len(spec['paths'])} paths)")
