"""Ponto de entrada WSGI para produção (Gunicorn, Waitress, uWSGI)."""
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

from app import app as application  # noqa: E402
