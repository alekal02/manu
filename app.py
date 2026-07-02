"""Inicia o servidor a partir da pasta back."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACK = os.path.join(ROOT, "back")

sys.path.insert(0, BACK)
os.chdir(BACK)

from app import app  # noqa: E402

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
