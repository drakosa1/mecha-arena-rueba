"""
MECHA ARENA - ui/fonts.py
===============================================================
Fabrica de fuentes de pygame con cache.

Centralizar las fuentes evita crear objetos ``Font`` en cada fotograma
(recurso caro) y garantiza el mismo estilo tipografico en toda la interfaz.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pygame

#: Familias preferidas, de la mas tecnologia a la mas legible.
FONT_STACKS: Tuple[Tuple[str, ...], ...] = (
    ("consolas", "couriernew", "monospace"),
    ("arial", "helvetica", "dejavusans"),
)

_CACHE: Dict[Tuple[int, bool], pygame.font.Font] = {}


def get_font(size: int, bold: bool = True) -> pygame.font.Font:
    """
    Devuelve una fuente cacheada de tamano ``size``.

    :param bold: usa la variante en negrita.
    """
    if not pygame.font.get_init():
        # pygame.quit() invalida las fuentes existentes: se regeneran.
        _CACHE.clear()
        pygame.font.init()

    key = (size, bold)
    if key in _CACHE:
        return _CACHE[key]

    font = None
    for stack in FONT_STACKS:
        try:
            font = pygame.font.SysFont(stack, size, bold=bold)
            break
        except Exception:  # pragma: no cover - depende del sistema
            font = None
    if font is None:  # ultimo recurso: fuente por defecto de pygame
        font = pygame.font.Font(None, size)

    _CACHE[key] = font
    return font


def render_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    position: Tuple[int, int],
    color: Tuple[int, int, int],
    bold: bool = True,
    anchor: str = "topleft",
) -> pygame.Rect:
    """
    Dibuja texto y devuelve el rectángulo ocupado.

    :param anchor: ``topleft``, ``center``, ``midtop``, ``midright``, etc.
    """
    font = get_font(size, bold)
    try:
        image = font.render(text, True, color)
    except pygame.error:
        # Si pygame se reinicio (pygame.quit) las fuentes cacheadas quedan
        # invalidas: se regeneran y se reintenta una unica vez.
        _CACHE.clear()
        image = get_font(size, bold).render(text, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, position)
    surface.blit(image, rect)
    return rect
