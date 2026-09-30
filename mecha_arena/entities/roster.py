"""
MECHA ARENA - entities/roster.py
===============================================================
Catalogo de Mecha del juego.

Reune las fichas de los Mecha jugables y las funciones que las convierten en
entidades reales. Anadir un Mecha nuevo (para el menu de seleccion o para un
rival futuro) es anadir una entrada a :data:`ROSTER`: el menu, la pantalla de
mejoras y el combate leen de aqui, no de codigo disperso.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional

from mecha_arena.domain.mecha import MechaPalette, MechaSpec, MechaStats
from mecha_arena.domain.upgrade import UpgradeKind, apply_upgrades
from mecha_arena.domain.weapon import (
    FUSION_BLADE,
    HEAVY_CANNON,
    NEEDLE_RIFLE,
    PLASMA_RIFLE,
    PULSE_CANNON,
    SHOCK_CANNON,
    TWIN_LANCE,
)
from mecha_arena.entities.enemy import Enemy
from mecha_arena.entities.player import Player

# ---------------------------------------------------------------------------
# Mecha jugables
# ---------------------------------------------------------------------------

TITAN_X = MechaSpec(
    key="titan-x",
    name="TITAN-X",
    tagline="Equilibrado. El caballo de batalla de la arena.",
    stats=MechaStats(
        max_health=120.0,
        attack=12.0,
        defense=5.0,
        move_speed=340.0,
        jump_force=800.0,
        move_accel=2900.0,
        body_width=48,
        body_height=90,
    ),
    palette=MechaPalette(
        primary=(58, 122, 196),
        secondary=(30, 62, 118),
        metal=(176, 190, 214),
        visor=(120, 245, 255),
        accent=(240, 196, 84),
        glow=(108, 208, 255),
    ),
    weapon_spec=FUSION_BLADE,
    secondary_spec=PULSE_CANNON,
    price=0,
    difficulty=2,
)

NIMBO_X = MechaSpec(
    key="nimbo-x",
    name="NIMBO-X",
    tagline="Rapidisimo y fragil. Gana antes de que te toquen.",
    stats=MechaStats(
        max_health=96.0,
        attack=11.0,
        defense=3.0,
        move_speed=430.0,
        jump_force=880.0,
        move_accel=3600.0,
        body_width=42,
        body_height=84,
    ),
    palette=MechaPalette(
        primary=(60, 186, 168),
        secondary=(24, 96, 96),
        metal=(198, 226, 224),
        visor=(160, 255, 230),
        accent=(226, 255, 120),
        glow=(120, 240, 210),
    ),
    weapon_spec=TWIN_LANCE,
    secondary_spec=PLASMA_RIFLE,
    price=400,
    difficulty=3,
)

VULCANO_9 = MechaSpec(
    key="vulcano-9",
    name="VULCANO-9",
    tagline="Tanque lento. Cada golpe suyo se nota en el suelo.",
    stats=MechaStats(
        max_health=165.0,
        attack=14.0,
        defense=8.0,
        move_speed=265.0,
        jump_force=720.0,
        move_accel=2100.0,
        body_width=60,
        body_height=104,
    ),
    palette=MechaPalette(
        primary=(206, 96, 40),
        secondary=(112, 44, 24),
        metal=(178, 158, 140),
        visor=(255, 176, 72),
        accent=(255, 214, 96),
        glow=(255, 140, 60),
    ),
    weapon_spec=HEAVY_CANNON,
    secondary_spec=SHOCK_CANNON,
    price=750,
    difficulty=3,
)

FENIX_01 = MechaSpec(
    key="fenix-01",
    name="FENIX-01",
    tagline="Control total del campo. Artilleria de precision.",
    stats=MechaStats(
        max_health=108.0,
        attack=13.0,
        defense=4.0,
        move_speed=360.0,
        jump_force=840.0,
        move_accel=3200.0,
        body_width=46,
        body_height=94,
    ),
    palette=MechaPalette(
        primary=(186, 62, 132),
        secondary=(96, 28, 78),
        metal=(214, 196, 220),
        visor=(255, 214, 240),
        accent=(255, 240, 120),
        glow=(255, 130, 210),
    ),
    weapon_spec=PULSE_CANNON,
    secondary_spec=NEEDLE_RIFLE,
    price=1100,
    difficulty=4,
)

#: Todos los Mecha jugables, en el orden en que aparecen en el menu.
ROSTER: Dict[str, MechaSpec] = {
    spec.key: spec for spec in (TITAN_X, NIMBO_X, VULCANO_9, FENIX_01)
}

#: Orden de presentacion del menu de seleccion.
ROSTER_ORDER: List[str] = list(ROSTER.keys())

#: Mecha gratuito de partida: siempre disponible, incluso sin perfil guardado.
DEFAULT_MECHA = TITAN_X.key


# ---------------------------------------------------------------------------
# Rival
# ---------------------------------------------------------------------------

OMEGA_7 = MechaSpec(
    key="omega-7",
    name="OMEGA-7",
    tagline="Rival de la arena.",
    stats=MechaStats(
        max_health=110.0,
        attack=12.0,
        defense=3.0,
        move_speed=300.0,
        jump_force=760.0,
        move_accel=2400.0,
        body_width=52,
        body_height=96,
    ),
    palette=MechaPalette(
        primary=(168, 62, 74),
        secondary=(92, 30, 48),
        metal=(150, 146, 162),
        visor=(255, 196, 90),
        accent=(255, 132, 96),
        glow=(255, 120, 90),
    ),
    weapon_spec=HEAVY_CANNON,
    secondary_spec=PLASMA_RIFLE,
    difficulty=3,
)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


def get_spec(key: str) -> MechaSpec:
    """
    Devuelve la ficha de un Mecha jugable.

    :raises KeyError: si la clave no existe en el catalogo.
    """
    return ROSTER[key]


def neighbor(key: str, direction: int) -> str:
    """Clave del Mecha anterior o siguiente en el menu (con vuelta)."""
    index = ROSTER_ORDER.index(key)
    return ROSTER_ORDER[(index + direction) % len(ROSTER_ORDER)]


# ---------------------------------------------------------------------------
# Fabricas
# ---------------------------------------------------------------------------


def build_player(
    key: str,
    x: float,
    y: float,
    upgrades: Optional[Mapping[UpgradeKind, int]] = None,
) -> Player:
    """
    Crea el Mecha del jugador a partir de su ficha y sus mejoras.

    Las estadisticas del catalogo no se modifican: se parte de una copia con
    las mejoras ya aplicadas.
    """
    spec = get_spec(key)
    stats = apply_upgrades(spec.stats, upgrades)
    return Player(
        x=x,
        y=y,
        name=spec.name,
        stats=stats,
        weapon_spec=spec.weapon_spec,
        energy_weapon=spec.secondary_spec or spec.weapon_spec,
    )


def build_enemy(
    x: float,
    y: float,
    key: str = OMEGA_7.key,
    health_scale: float = 1.0,
) -> Enemy:
    """
    Crea al rival. ``health_scale`` permite rounds mas duros en el futuro
    sin duplicar fichas de Mecha.
    """
    spec = OMEGA_7 if key == OMEGA_7.key else get_spec(key)
    stats = spec.stats
    if health_scale != 1.0:
        from dataclasses import replace

        stats = replace(stats, max_health=stats.max_health * health_scale)
    return Enemy(
        x=x,
        y=y,
        name=spec.name,
        stats=stats,
        weapon_spec=spec.weapon_spec,
        ranged_weapon=spec.secondary_spec or spec.weapon_spec,
    )
