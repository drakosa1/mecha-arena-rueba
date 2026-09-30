"""
MECHA ARENA - systems/physics.py
===============================================================
Sistema de fisica de la arena.

Responsabilidades:
    - Integrar gravedad y desplazamiento de los Mecha.
    - Resolver la velocidad horizontal a partir de la intencion de movimiento
      (aceleracion y frenado), de forma independiente del framerate.
    - Resolver colisiones con el suelo y las plataformas.
    - Mantener a los combatientes dentro de los limites de la arena.
    - Evitar que dos Mecha se solapen.

Este modulo no sabe nada de DIBUJO: solo mueve cajas.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from mecha_arena.settings import (
    AIR_CONTROL,
    ARENA_LEFT,
    ARENA_RIGHT,
    BODY_PUSH_STRENGTH,
    FLOOR_Y,
    GRAVITY,
    GROUND_FRICTION,
    MAX_FALL_SPEED,
    PLATFORM_RECTS,
)

#: Tipo de una superficie solida: (izquierda, arriba, derecha, abajo).
Surface = Tuple[float, float, float, float]

#: Limite de velocidad impuesto por el empuje entre cuerpos.
MAX_SEPARATION_SPEED = 900.0


def approach(current: float, target: float, max_delta: float) -> float:
    """
    Acerca ``current`` a ``target`` como maximo ``max_delta``.

    Es la primitiva base de la aceleracion: garantiza que ningun Mecha
    cambie su velocidad de golpe, ni dependa de los fotogramas por segundo.
    """
    if current < target:
        return min(current + max_delta, target)
    if current > target:
        return max(current - max_delta, target)
    return target


# ---------------------------------------------------------------------------
# Movimiento
# ---------------------------------------------------------------------------


def resolve_horizontal(mecha, delta_time: float) -> None:
    """
    Acerca la velocidad real del Mecha a su intencion de movimiento.

    En el suelo frena con ``GROUND_FRICTION``; en el aire la aceleracion se
    reduce (control aéreo) para que los saltos sean menos flotantes.
    """
    accel = mecha.stats.move_accel * delta_time
    if mecha.on_ground:
        if mecha.move_intent is None:
            mecha.vx = approach(mecha.vx, 0.0, GROUND_FRICTION * delta_time)
            return
    else:
        accel *= AIR_CONTROL
        if mecha.move_intent is None:
            # Frenado en el aire muy suave: se conserva la inercia del salto.
            mecha.vx = approach(mecha.vx, 0.0, accel * 0.35)
            return

    mecha.vx = approach(mecha.vx, mecha.move_intent, accel)


def apply_gravity(mecha, delta_time: float) -> None:
    """Suma la gravedad a la velocidad vertical, con limite de caida."""
    mecha.vy += GRAVITY * delta_time
    if mecha.vy > MAX_FALL_SPEED:
        mecha.vy = MAX_FALL_SPEED


def integrate_position(mecha, delta_time: float) -> None:
    """Desplaza el Mecha segun su velocidad actual."""
    mecha.x += mecha.vx * delta_time
    mecha.y += mecha.vy * delta_time


# ---------------------------------------------------------------------------
# Colisiones con el escenario
# ---------------------------------------------------------------------------


def arena_surfaces() -> Sequence[Surface]:
    """Devuelve las superficies solidas de la arena (suelo y plataformas)."""
    surfaces: list[Surface] = [
        (ARENA_LEFT - 40, FLOOR_Y, ARENA_RIGHT + 40, FLOOR_Y + 400),
    ]
    for px, py, pw, ph in PLATFORM_RECTS:
        surfaces.append((px, py, px + pw, py + ph))
    return surfaces


def resolve_vertical(mecha, surfaces: Optional[Sequence[Surface]] = None) -> None:
    """
    Detecta el suelo bajo los pies del Mecha y lo coloca encima.

    Se usa el borde inferior de los pies: basta con comprobar que se ha
    atravesado la superficie durante este fotograma.
    """
    surfaces = arena_surfaces() if surfaces is None else surfaces
    feet_x_left, _, feet_x_right, _ = mecha.bounds

    mecha.on_ground = False
    for left, top, right, _bottom in surfaces:
        # La horizontal del Mecha solapa la superficie...
        if feet_x_right <= left or feet_x_left >= right:
            continue
        # ...y se ha cruzado la superficie de arriba hacia abajo.
        if mecha.y >= top - 1.0 and mecha.vy >= 0.0:
            mecha.y = top
            mecha.vy = 0.0
            mecha.on_ground = True
            return


def clamp_to_arena(mecha) -> None:
    """Impide que un Mecha salga de los limites horizontales de la arena."""
    half = mecha.body_width / 2.0
    if mecha.x - half < ARENA_LEFT:
        mecha.x = ARENA_LEFT + half
        mecha.vx = max(0.0, mecha.vx)
    elif mecha.x + half > ARENA_RIGHT:
        mecha.x = ARENA_RIGHT - half
        mecha.vx = min(0.0, mecha.vx)


# ---------------------------------------------------------------------------
# Interaccion entre cuerpos
# ---------------------------------------------------------------------------


def separate_bodies(first, second, delta_time: float = 0.0) -> None:
    """
    Empuja dos Mecha que se solapan para que no se atraviesen.

    Cada uno retrocede la mitad de la separacion, en la direccion que ya
    tenga, y frena un poco para que el empuje sea visible.
    """
    left_a, _, right_a, _ = first.bounds
    left_b, _, right_b, _ = second.bounds
    if right_a <= left_b or right_b <= left_a:
        return

    overlap = min(right_a, right_b) - max(left_a, left_b)
    push = overlap / 2.0 + 0.5
    direction = 1 if first.x <= second.x else -1
    first.x -= push * direction
    second.x += push * direction

    # Impulso de rechazo: el contacto se nota, no solo se corrige la posicion.
    # Se limita con BODY_PUSH_STRENGTH para que un choque no lance a nadie.
    shove = min(BODY_PUSH_STRENGTH, overlap * 8.0) * direction
    first.vx -= shove
    second.vx += shove
    first.vx = max(-MAX_SEPARATION_SPEED, min(MAX_SEPARATION_SPEED, first.vx))
    second.vx = max(-MAX_SEPARATION_SPEED, min(MAX_SEPARATION_SPEED, second.vx))


def update_mecha(mecha, delta_time: float, surfaces: Optional[Sequence[Surface]] = None) -> None:
    """
    Ciclo fisico completo de un Mecha.

    Orden importante: intencion -> gravedad -> desplazamiento -> suelo ->
    limites. Separar estos pasos mantiene el comportamiento predecible.
    """
    resolve_horizontal(mecha, delta_time)
    apply_gravity(mecha, delta_time)
    integrate_position(mecha, delta_time)
    resolve_vertical(mecha, surfaces)
    clamp_to_arena(mecha)
