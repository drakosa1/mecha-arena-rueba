"""
MECHA ARENA - systems/collision.py
===============================================================
Deteccion de colisiones ligadas al combate.

Responsabilidades:
    - Test AABB generico entre dos cajas.
    - Construir la caja de golpe de un Mecha a partir de su arma y su orientacion.
    - Resolver el impacto cuerpo a cuerpo (un solo golpe por animacion).
    - Resolver los impactos de los proyectiles contra los Mecha y el escenario.

No dibuja nada: devuelve datos que la UI convierte en efectos.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from mecha_arena.domain.mecha import DamageReport
from mecha_arena.settings import ARENA_LEFT, ARENA_RIGHT, FLOOR_Y, PLATFORM_RECTS
from mecha_arena.systems import physics

#: Caja de colision: (izquierda, arriba, derecha, abajo).
Bounds = Tuple[float, float, float, float]


def overlaps(first: Bounds, second: Bounds) -> bool:
    """True si dos cajas se solapan (test AABB, sin fases solapadas)."""
    return (
        first[0] < second[2]
        and first[2] > second[0]
        and first[1] < second[3]
        and first[3] > second[1]
    )


def center_of(bounds: Bounds) -> Tuple[float, float]:
    """Centro de una caja, usado para colocar el destello de impacto."""
    return ((bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0)


# ---------------------------------------------------------------------------
# Cuerpo a cuerpo
# ---------------------------------------------------------------------------


def melee_hitbox(mecha) -> Bounds:
    """
    Caja activa del golpe, situada delante del Mecha segun su orientacion.

    Solo se construye si el arma es cuerpo a cuerpo y esta en animacion de
    golpe: en cualquier otro momento la caja esta vacia (nunca impacta).
    """
    if not mecha.weapon.spec.is_melee or not mecha.weapon.is_swinging:
        return (0.0, 0.0, 0.0, 0.0)

    left, top, right, _bottom = mecha.bounds
    reach = mecha.weapon.spec.reach
    # Altura parcial: los golpes pasan por el torso, no por los pies.
    height = mecha.body_height * 0.62
    strike_y = mecha.y - mecha.body_height * 0.72

    if mecha.facing > 0:
        return (right - 10.0, strike_y, right + reach, strike_y + height)
    return (left - reach, strike_y, left + 10.0, strike_y + height)


def resolve_melee_hit(attacker, defender) -> Optional[DamageReport]:
    """
    Aplica el golpe cuerpo a cuerpo de ``attacker`` sobre ``defender``.

    Cada animacion de golpe solo puede conectar una vez: si ya habia
    impactado, no se vuelve a aplicar dano aunque la caja siga solapandose.

    :return: informe del impacto o ``None`` si no hubo golpe.
    """
    if attacker.swing_connected or not attacker.weapon.spec.is_melee:
        return None
    if not attacker.weapon.is_swinging or not defender.is_vulnerable:
        return None

    if not overlaps(melee_hitbox(attacker), defender.bounds):
        return None

    attacker.swing_connected = True
    # El dano escala con la estadistica de ataque del atacante.
    raw_damage = attacker.weapon.spec.damage * (attacker.stats.attack / 10.0)
    return defender.take_damage(
        raw_damage,
        attacker_x=attacker.x,
        knockback=attacker.weapon.spec.knockback,
    )


# ---------------------------------------------------------------------------
# Proyectiles
# ---------------------------------------------------------------------------


def hits_static_world(projectile) -> bool:
    """True si el proyectil toca el suelo, una plataforma o el borde de la arena."""
    left, top, right, bottom = projectile.rect

    if top > FLOOR_Y:
        return True
    if left < ARENA_LEFT - 30 or right > ARENA_RIGHT + 30:
        return True
    for px, py, pw, ph in PLATFORM_RECTS:
        if overlaps((left, top, right, bottom), (px, py, px + pw, py + ph)):
            return True
    return False


def resolve_projectile_hits(
    projectiles: Sequence,
    candidates: Iterable,
) -> List[Tuple[object, DamageReport]]:
    """
    Busca impactos de proyectil contra los Mecha indicados.

    Un proyectil solo puede golpear a un rival (nunca a su propio dueno) y
    desaparece en el impacto.

    :return: lista de tuplas ``(proyectil, informe_de_dano)``.
    """
    results: List[Tuple[object, DamageReport]] = []
    mechas = list(candidates)

    for projectile in projectiles:
        if not projectile.alive:
            continue
        target = projectile.target(mechas)
        if target is None:
            continue
        report = target.take_damage(
            projectile.damage,
            attacker_x=projectile.x - projectile.direction * projectile.radius,
            knockback=projectile.knockback,
        )
        projectile.kill()
        if report.hit_landed:
            results.append((projectile, report))
    return results


def resolve_body_separation(first, second, delta_time: float = 0.0) -> None:
    """
    Evita que dos Mecha se atraviesen.

    Delegado en ``physics`` para que la regla de separacion tenga un unico
    Dueeno; este envoltorio mantiene la API del sistema de colisiones.
    """
    physics.separate_bodies(first, second, delta_time)
