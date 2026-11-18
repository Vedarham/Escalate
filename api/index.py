"""Vercel Serverless Function entry point for Escalate FastAPI backend."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app

# Export ASGI app for Vercel Python runtime
handler = app
