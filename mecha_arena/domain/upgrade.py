"""
MECHA ARENA - domain/upgrade.py
===============================================================
Reglas del taller de mejoras.

Una mejora es una modificacion permanente de las estadisticas de un Mecha que
se compra con creditos ganados en combate. Este modulo solo define las reglas
(coste, niveles y efecto); el dinero y el progreso viven en ``profile.py``.

La aplicacion es siempre proporcional al nivel comprado y nunca supera el
maximo, de modo que el balance se puede ajustar cambiando un solo numero.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Mapping, Optional

from mecha_arena.domain.mecha import MechaStats


class UpgradeKind(str, Enum):
    """Lineas de mejora del taller."""

    ATTACK = "attack"    # mas daño
    ARMOR = "armor"      # mas defensa
    ENGINE = "engine"    # mas velocidad y salto
    HULL = "hull"        # mas vida maxima


@dataclass(frozen=True)
class UpgradeSpec:
    """Definicion de una linea de mejora."""

    kind: UpgradeKind
    name: str
    description: str
    max_level: int = 3
    base_cost: int = 120
    #: Estadistica afectada.
    stat: str = "attack"
    #: Valor anadido por nivel (absoluto o porcentual).
    step: float = 0.0
    #: True si ``step`` es un porcentaje del valor base.
    percent: bool = False


#: Catalogo del taller. El orden es el orden en que se muestra en pantalla.
UPGRADES: Dict[UpgradeKind, UpgradeSpec] = {
    UpgradeKind.ATTACK: UpgradeSpec(
        kind=UpgradeKind.ATTACK,
        name="NUCLEO",
        description="Aumenta el dano de todas las armas",
        max_level=3,
        base_cost=150,
        stat="attack",
        step=2.0,
    ),
    UpgradeKind.ARMOR: UpgradeSpec(
        kind=UpgradeKind.ARMOR,
        name="BLINDAJE",
        description="Reduce el dano recibido",
        max_level=3,
        base_cost=130,
        stat="defense",
        step=1.5,
    ),
    UpgradeKind.HULL: UpgradeSpec(
        kind=UpgradeKind.HULL,
        name="CASCO",
        description="Aumenta la vida maxima",
        max_level=3,
        base_cost=140,
        stat="max_health",
        step=12.0,
    ),
    UpgradeKind.ENGINE: UpgradeSpec(
        kind=UpgradeKind.ENGINE,
        name="PROPULSION",
        description="Mas velocidad de movimiento",
        max_level=3,
        base_cost=120,
        stat="move_speed",
        step=30.0,
    ),
}

#: Orden estable para menus.
UPGRADE_ORDER = [
    UpgradeKind.ATTACK,
    UpgradeKind.ARMOR,
    UpgradeKind.HULL,
    UpgradeKind.ENGINE,
]


def upgrade_cost(spec: UpgradeSpec, current_level: int) -> int:
    """
    Coste del siguiente nivel de una mejora.

    Sube de forma escalonada: el primer nivel es barato y el tercero encarece,
    de modo que la decision de invertir tenga peso.
    """
    return int(spec.base_cost * (1.0 + 0.75 * current_level))


def apply_upgrades(
    stats: MechaStats,
    levels: Optional[Mapping[UpgradeKind, int]] = None,
) -> MechaStats:
    """
    Devuelve unas estadisticas nuevas con las mejoras ya aplicadas.

    Se trabaja sobre una copia: las estadisticas originales del Mecha no se
    tocan, de modo que un guardado corrupto nunca deja a un Mecha invalido.
    """
    if not levels:
        return stats

    # Se acumulan los cambios y se aplican de una sola vez: MechaStats es
    # inmutable, de modo que cada mejora genera una copia nueva completa.
    changes: Dict[str, float] = {}
    for kind, level in levels.items():
        spec = UPGRADES.get(kind)
        if spec is None or level <= 0:
            continue
        level = min(level, spec.max_level)
        current = getattr(stats, spec.stat)
        if spec.percent:
            changes[spec.stat] = current * (1.0 + spec.step * level)
        else:
            changes[spec.stat] = current + spec.step * level

    if not changes:
        return stats
    return replace(stats, **changes)


def total_invested(levels: Mapping[UpgradeKind, int]) -> int:
    """Cuanto credito se ha gastado en las mejoras indicadas."""
    total = 0
    for kind, level in levels.items():
        spec = UPGRADES.get(kind)
        if spec is None:
            continue
        for bought in range(min(level, spec.max_level)):
            total += upgrade_cost(spec, bought)
    return total
