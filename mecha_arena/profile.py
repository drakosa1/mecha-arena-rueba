"""
MECHA ARENA - profile.py
===============================================================
Perfil del jugador: creditos, Mecha en posesion, mejoras compradas y
historial de combates.

Es la capa de persistencia del juego. Guarda en ``assets/profile.json`` con un
formato versionado y tolera siempre los archivos corruptos o de una version
distinta: en ese caso vuelve a los valores por defecto en lugar de fallar al
arrancar.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping, Optional

from mecha_arena.domain.upgrade import UPGRADES, UpgradeKind, upgrade_cost
from mecha_arena.entities.roster import DEFAULT_MECHA, ROSTER
from mecha_arena.settings import SAVE_FILE

#: Version del formato de guardado.
SAVE_VERSION = 1

#: Creditos que se ganan al ganar y al perder un combate.
REWARD_WIN = 200
REWARD_LOSS = 70
#: Bonus por vida restante al ganar (1 punto de vida = 1 credito).
REWARD_HP_FACTOR = 0.8

#: Creditos con los que empieza una partida nueva.
STARTING_CREDITS = 450


def default_data() -> Dict[str, Any]:
    """Perfil de partida nueva."""
    return {
        "version": SAVE_VERSION,
        "credits": STARTING_CREDITS,
        "selected": DEFAULT_MECHA,
        "owned": [DEFAULT_MECHA],
        "upgrades": {DEFAULT_MECHA: {}},
        "wins": 0,
        "losses": 0,
        "best_streak": 0,
        "current_streak": 0,
    }


class PlayerProfile:
    """
    Estado persistente de la persona jugadora.

    Encapsula el acceso al disco: el resto del juego solo usa los metodos
    (``add_credits``, ``purchase``, ``buy_upgrade``) y nunca toca el JSON.
    """

    def __init__(self, path: str = SAVE_FILE) -> None:
        self.path = path
        self.data: Dict[str, Any] = default_data()
        self.load()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def load(self) -> None:
        """
        Lee el perfil del disco.

        Cualquier problema (archivo ausente, JSON invalido, version distinta o
        claves desconocidas) se resuelve volviendo al perfil por defecto.
        """
        if not os.path.exists(self.path):
            self.data = default_data()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.data = self._sanitize(raw)
        except (OSError, ValueError, TypeError):
            self.data = default_data()

    def save(self) -> None:
        """Escribe el perfil en disco, creando la carpeta si hace falta."""
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
        except OSError:
            # Perder la partida es malo; no poder guardar, no debe romperla.
            pass

    def _sanitize(self, raw: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los datos leidos: descarta claves invalidas y valores
        fuera de rango, de modo que un guardado manipulado no rompa el juego.
        """
        clean = default_data()

        try:
            version = int(raw.get("version", 0))
        except (TypeError, ValueError):
            version = 0
        if version > SAVE_VERSION:
            # Guardado de una version futura: se ignora en lugar de malinterpretarlo.
            return clean

        clean["credits"] = max(0, int(raw.get("credits", STARTING_CREDITS)))
        clean["wins"] = max(0, int(raw.get("wins", 0)))
        clean["losses"] = max(0, int(raw.get("losses", 0)))
        clean["best_streak"] = max(0, int(raw.get("best_streak", 0)))
        clean["current_streak"] = max(0, int(raw.get("current_streak", 0)))

        # Mecha en posesion: solo los que existen en el catalogo, sin repetir.
        owned: list = []
        for key in raw.get("owned", []):
            if key in ROSTER and key not in owned:
                owned.append(key)
        if DEFAULT_MECHA not in owned:
            owned.insert(0, DEFAULT_MECHA)
        clean["owned"] = owned

        selected = raw.get("selected")
        clean["selected"] = selected if selected in owned else owned[0]

        # Mejoras: se recorren las lineas conocidas del taller, de modo que un
        # nombre antiguo o desconocido en el guardado se ignora en lugar de
        # invalidar el perfil completo.
        upgrades: Dict[str, Dict[str, int]] = {}
        for mecha_key, levels in (raw.get("upgrades") or {}).items():
            if mecha_key not in ROSTER or not isinstance(levels, dict):
                continue
            valid = {}
            for kind, spec in UPGRADES.items():
                if kind.value not in levels:
                    continue
                try:
                    valid[kind.value] = max(0, min(spec.max_level, int(levels[kind.value])))
                except (TypeError, ValueError):
                    continue
            upgrades[mecha_key] = valid
        clean["upgrades"] = {key: upgrades.get(key, {}) for key in owned}
        return clean

    # ------------------------------------------------------------------
    # Creditos
    # ------------------------------------------------------------------
    @property
    def credits(self) -> int:
        return int(self.data["credits"])

    def add_credits(self, amount: int) -> None:
        """Suma creditos (nunca negativos)."""
        self.data["credits"] = max(0, self.credits + int(amount))

    def can_afford(self, amount: int) -> bool:
        return self.credits >= amount

    def spend(self, amount: int) -> bool:
        """Gasta creditos si reaching. :return: True si se pudo pagar."""
        if not self.can_afford(amount):
            return False
        self.data["credits"] = self.credits - int(amount)
        return True

    # ------------------------------------------------------------------
    # Mecha
    # ------------------------------------------------------------------
    @property
    def selected(self) -> str:
        """Clave del Mecha equipado."""
        return str(self.data["selected"])

    @property
    def owned(self) -> list:
        """Claves de los Mecha en posesion."""
        return list(self.data["owned"])

    def owns(self, key: str) -> bool:
        return key in self.data["owned"]

    def select(self, key: str) -> bool:
        """Equipa un Mecha que ya se posee."""
        if not self.owns(key):
            return False
        self.data["selected"] = key
        return True

    def purchase(self, key: str) -> bool:
        """
        Compra un Mecha con los creditos disponibles.

        :return: True si la compra se realizo.
        """
        if key not in ROSTER or self.owns(key):
            return False
        price = ROSTER[key].price
        if not self.spend(price):
            return False
        self.data["owned"].append(key)
        self.data["upgrades"][key] = {}
        return True

    # ------------------------------------------------------------------
    # Mejoras
    # ------------------------------------------------------------------
    def upgrade_levels(self, key: Optional[str] = None) -> Dict[str, int]:
        """Niveles comprados de un Mecha, indexados por ``UpgradeKind``."""
        levels = self.data["upgrades"].get(key or self.selected, {})
        return {UpgradeKind(name): level for name, level in levels.items()}

    def upgrade_level(self, kind: UpgradeKind, key: Optional[str] = None) -> int:
        return self.upgrade_levels(key).get(kind, 0)

    def upgrade_maxed(self, kind: UpgradeKind, key: Optional[str] = None) -> bool:
        spec = UPGRADES[kind]
        return self.upgrade_level(kind, key) >= spec.max_level

    def next_upgrade_cost(self, kind: UpgradeKind, key: Optional[str] = None) -> Optional[int]:
        """Coste del siguiente nivel, o ``None`` si ya esta al maximo."""
        if self.upgrade_maxed(kind, key):
            return None
        return upgrade_cost(UPGRADES[kind], self.upgrade_level(kind, key))

    def buy_upgrade(self, kind: UpgradeKind, key: Optional[str] = None) -> bool:
        """
        Compra un nivel de mejora para un Mecha.

        :return: True si la compra se realizo.
        """
        target = key or self.selected
        cost = self.next_upgrade_cost(kind, target)
        if cost is None or not self.spend(cost):
            return False
        levels = self.data["upgrades"].setdefault(target, {})
        name = kind.value
        levels[name] = int(levels.get(name, 0)) + 1
        return True

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    @property
    def wins(self) -> int:
        return int(self.data["wins"])

    @property
    def losses(self) -> int:
        return int(self.data["losses"])

    @property
    def streak(self) -> int:
        return int(self.data["current_streak"])

    @property
    def best_streak(self) -> int:
        return int(self.data["best_streak"])

    def record_result(self, won: bool, health_ratio: float = 0.0) -> int:
        """
        Registra el resultado de un combate y devuelve los creditos ganados.

        Ganar da mas creditos, con un extra por vida restante: premia jugar
        bien en vez de limitarse a sobrevivir.
        """
        if won:
            self.data["wins"] = int(self.data["wins"]) + 1
            self.data["current_streak"] = self.streak + 1
            self.data["best_streak"] = max(self.best_streak, self.streak)
            reward = REWARD_WIN + int(health_ratio * 100 * REWARD_HP_FACTOR)
        else:
            self.data["losses"] = int(self.data["losses"]) + 1
            self.data["current_streak"] = 0
            reward = REWARD_LOSS

        self.add_credits(reward)
        return reward
