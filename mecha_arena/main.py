"""
MECHA ARENA - main.py (punto de entrada del paquete).
===============================================================
Uso alternativo:  python mecha_arena/main.py

La raiz del repositorio se anade al path para que los imports absolutos
(``mecha_arena.*``) funcionen tanto si se ejecuta este archivo como si se
importa el paquete con ``python -m mecha_arena.main``.
"""

from __future__ import annotations

import os
import sys


def _bootstrap_path() -> None:
    """Anade la carpeta padre del paquete al path de busqueda."""
    package_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(package_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def main() -> None:
    """Arranca el juego."""
    _bootstrap_path()
    from mecha_arena.app import Game

    try:
        Game().run()
    except KeyboardInterrupt:
        print("\nMECHA ARENA cerrado.")


if __name__ == "__main__":
    main()
