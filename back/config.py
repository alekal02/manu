import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

DATABASE_PATH = os.environ.get(
    "DATABASE_PATH", os.path.join(DATA_DIR, "manu.db")
)
SECRET_KEY = os.environ.get("SECRET_KEY", "manu-dev-key-altere-em-producao")
