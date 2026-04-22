"""
conftest.py (ROOT) — agrega la raíz del proyecto al sys.path
para que todos los imports absolutos funcionen sin instalar el paquete.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
