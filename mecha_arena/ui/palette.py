"""
MECHA ARENA - ui/palette.py
===============================================================
Utilidades de color compartidas por la capa de presentacion.

Centralizarlas evita repetir la misma funcion en el escenario y en el
renderizador de Mecha, y deja un unico sitio donde ajustar la paleta.
"""

from __future__ import annotations

from typing import Tuple

Color = Tuple[int, int, int]


def shade(color: Color, factor: float) -> Color:
    """Aclara (factor > 1.0) u oscurece (factor < 1.0) un color."""
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


def mix(first: Color, second: Color, amount: float) -> Color:
    """Interpola linealmente entre dos colores (0 = primero, 1 = segundo)."""
    amount = max(0.0, min(1.0, amount))
    return (
        int(first[0] + (second[0] - first[0]) * amount),
        int(first[1] + (second[1] - first[1]) * amount),
        int(first[2] + (second[2] - first[2]) * amount),
    )


def with_alpha(color: Color, alpha: float) -> Tuple[int, int, int, int]:
    """Anade canal alfa a un color RGB (0.0 - 1.0)."""
    return (color[0], color[1], color[2], max(0, min(255, int(alpha * 255))))
