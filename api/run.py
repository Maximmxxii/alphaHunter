"""
api/run.py — Script para levantar la API de AlphaHunter
"""

import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--reload",
        "--port", "8000",
        "--host", "0.0.0.0",
    ])
