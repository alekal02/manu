"""Inicia o servidor a partir da pasta back."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACK = os.path.join(ROOT, "back")

sys.path.insert(0, BACK)
os.chdir(BACK)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from app import app  # noqa: E402

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=debug, host="0.0.0.0", port=port)
