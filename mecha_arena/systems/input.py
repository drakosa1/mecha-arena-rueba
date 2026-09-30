"""
MECHA ARENA - systems/input.py
===============================================================
Sistema de entrada de teclado.

Responsabilidades:
    - Traducir eventos de pygame en un estado de entrada consultable.
    - Detectar pulsaciones (accion) frente a teclas mantenidas (estado).
    - Exponer una interfaz simple que las entidades no puedan usar directamente
      pygame, manteniendo el dominio y las entidades libres de la libreria.
"""

from __future__ import annotations

from typing import Iterable, Set

import pygame

from mecha_arena.settings import CONTROLS, PlayerControls


class InputState:
    """
    Estado de entrada de un fotograma.

    ``held``      -> teclas mantenidas en este momento.
    ``pressed``   -> teclas pulsadas en este fotograma (flanco de subida).

    Las entidades consultan metodos semanticos (``move_axis``, ``jump_pressed``)
    en lugar de teclas concretas: asi los controles se pueden remapear en un
    unico sitio y la logica de juego no cambia.

    Compatibilidad con pygame-ce
    -----------------------------
    El estado se mantiene a partir de los eventos ``KEYDOWN`` / ``KEYUP``, no
    consultando ``pygame.key.get_pressed()``. En pygame-ce ese metodo devuelve
    un ``ScancodeWrapper`` que no se puede recorrer
    (``TypeError: Iterating over key states is not supported``) y que ademas
    indexa por *scancode*, no por constante de tecla, de modo que
    ``get_pressed()[pygame.K_a]`` consultaria la tecla equivocada. Mantener el
    estado por eventos evita ambas cosas y funciona igual en cualquier version
    de pygame.
    """

    def __init__(self, controls: PlayerControls = CONTROLS) -> None:
        self.controls = controls
        self.held: Set[int] = set()
        self.pressed: Set[int] = set()
        #: Se ha cerrado la ventana: hay que terminar el proceso.
        self.quit_requested = False
        #: Se ha pulsado la tecla de pausa (ESC): atras en menus, salir en combate.
        self.pause_pressed = False
        self.any_key_pressed = False

    # ------------------------------------------------------------------
    # Actualizacion
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Registra un evento de pygame en el estado de entrada.

        ``KEYDOWN`` anade la tecla al conjunto de mantenidas (la repeticion del
        sistema es idempotente) y registra el flanco de pulsacion; ``KEYUP`` la
        retira. Si la ventana pierde el foco se vacia el conjunto, porque
        entonces nunca llegara el ``KEYUP`` y la tecla se quedaria pegada.

        Ojo: en pygame-ce cada evento de ventana tiene su propio tipo
        (``pygame.WINDOWFOCUSLOST``, ``pygame.WINDOWMINIMIZED``...) y no existe
        una constante ``pygame.WINDOWEVENT`` que los agrupe.
        """
        if event.type == pygame.KEYDOWN:
            if event.key:
                self.held.add(event.key)
            self.pressed.add(event.key)
            self.any_key_pressed = True
            if event.key == self.controls.pause:
                self.pause_pressed = True
        elif event.type == pygame.KEYUP:
            self.held.discard(event.key)
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.clear_held()
        elif event.type == pygame.QUIT:
            self.quit_requested = True

    def begin_frame(self) -> None:
        """
        Prepara el estado de entrada del fotograma.

        Las teclas mantenidas ya se conocen por los eventos recibidos, asi que
        aqui solo se actualiza el indicador de "hay algo pulsado".
        """
        self.any_key_pressed = bool(self.held)

    def end_frame(self) -> None:
        """Limpia los pulsos de un solo fotograma."""
        self.pressed.clear()
        self.pause_pressed = False

    def clear_held(self) -> None:
        """
        Olvida todas las teclas mantenidas.

        Se invoca al perder el foco de la ventana: en ese caso nunca llega el
        ``KEYUP`` correspondiente y, si no se limpiara, el Mecha seguiria
        avanzando despues de volver a la ventana.
        """
        self.held.clear()

    # ------------------------------------------------------------------
    # Consultas semanticas
    # ------------------------------------------------------------------
    def _any_held(self, keys: Iterable[int]) -> bool:
        return any(key in self.held for key in keys)

    def _any_pressed(self, keys: Iterable[int]) -> bool:
        return any(key in self.pressed for key in keys)

    def move_axis(self) -> float:
        """Eje horizontal: -1.0 a la izquierda, 1.0 a la derecha, 0.0 quieto."""
        left_keys = (self.controls.left, self.controls.alt_left)
        right_keys = (self.controls.right, self.controls.alt_right)
        left = self._any_held(left_keys)
        right = self._any_held(right_keys)
        if left and right:
            return 0.0
        return -1.0 if left else (1.0 if right else 0.0)

    def jump_pressed(self) -> bool:
        return self._any_pressed(self.controls.jump_keys())

    def jump_held(self) -> bool:
        return self._any_held(self.controls.jump_keys())

    def melee_pressed(self) -> bool:
        return self._any_pressed(self.controls.melee_keys())

    def energy_pressed(self) -> bool:
        return self._any_pressed(self.controls.energy_keys())

    def melee_held(self) -> bool:
        return self._any_held(self.controls.melee_keys())

    def energy_held(self) -> bool:
        return self._any_held(self.controls.energy_keys())
