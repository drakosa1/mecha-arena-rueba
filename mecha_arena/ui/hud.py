"""
MECHA ARENA - ui/hud.py
===============================================================
Interfaz de combate: barras de vida, energia, marcador de rondas, reloj y
mensajes de estado (presentacion, K.O., victoria y derrota).

El HUD solo lee datos del dominio; nunca modifica el estado del combate.
"""

from __future__ import annotations

from typing import Tuple

import pygame

from mecha_arena.settings import (
    COLOR_ACCENT,
    COLOR_DANGER,
    COLOR_HP_BACK,
    COLOR_HP_ENEMY,
    COLOR_HP_PLAYER,
    COLOR_HUD_BG,
    COLOR_HUD_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    SCREEN_WIDTH,
)
from mecha_arena.ui.fonts import render_text
from mecha_arena.ui.palette import mix, shade

Color = Tuple[int, int, int]

#: Geometria de las barras de vida.
BAR_WIDTH = 380
BAR_HEIGHT = 26
BAR_MARGIN = 34
BAR_TOP = 26


class HUD:
    """
    Dibujo de la interfaz de combate.

    Se construye una sola vez y reutiliza las mismas cajas en cada fotograma.
    """

    def __init__(self, width: int = SCREEN_WIDTH) -> None:
        self.width = width
        self._panel = self._build_panel()
        #: Creditos ganados en el combate que acaba de terminar.
        self.reward = 0

    def set_result(self, reward: int) -> None:
        """Registra la recompensa del combate para mostrarla en el resumen."""
        self.reward = reward

    # ------------------------------------------------------------------
    # Elementos estaticos
    # ------------------------------------------------------------------
    def _build_panel(self) -> pygame.Surface:
        """Panel translucido que contiene las barras superiores."""
        panel = pygame.Surface((self.width, 96), pygame.SRCALPHA)
        panel.fill((*COLOR_HUD_BG, 190))
        pygame.draw.line(panel, (*COLOR_HUD_BORDER, 255), (0, 0), (self.width, 0), 2)
        pygame.draw.line(panel, (*COLOR_HUD_BORDER, 90), (0, 94), (self.width, 94), 1)
        return panel

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, player, enemy, combat) -> None:
        """
        Dibuja el HUD completo.

        :param player: Mecha del jugador.
        :param enemy: Mecha enemigo.
        :param combat: sistema de combate (reloj y marcador de rondas).
        """
        surface.blit(self._panel, (0, 0))

        self._draw_mecha_bar(surface, player, BAR_MARGIN, BAR_TOP, COLOR_HP_PLAYER, align_left=True)
        self._draw_mecha_bar(surface, enemy, self.width - BAR_MARGIN, BAR_TOP, COLOR_HP_ENEMY, align_left=False)
        self._draw_round_info(surface, combat)
        self._draw_weapon_info(surface, player)
        self._draw_status_messages(surface, combat)

    # -- Barras ----------------------------------------------------------
    def _draw_mecha_bar(
        self, surface: pygame.Surface, mecha, x: int, y: int, color: Color, align_left: bool
    ) -> None:
        """Barra de vida de un Mecha con nombre y valor numerico."""
        bar_left = x if align_left else x - BAR_WIDTH
        bar = pygame.Rect(bar_left, y, BAR_WIDTH, BAR_HEIGHT)

        # Marco
        pygame.draw.rect(surface, COLOR_HUD_BG, bar.inflate(8, 8), border_radius=6)
        pygame.draw.rect(surface, COLOR_HUD_BORDER, bar.inflate(8, 8), width=2, border_radius=6)

        # Fondo
        pygame.draw.rect(surface, COLOR_HP_BACK, bar, border_radius=4)

        # Relleno proporcional a la vida actual.
        fill = pygame.Rect(bar)
        fill.width = int(bar.width * mecha.health_ratio)

        if mecha.health_ratio < 0.3:
            fill_color = COLOR_DANGER
        else:
            fill_color = color
        pygame.draw.rect(surface, fill_color, fill, border_radius=4)
        # Brillo superior
        pygame.draw.rect(
            surface, mix(fill_color, (255, 255, 255), 0.35), pygame.Rect(fill.x, fill.y, fill.width, 6),
            border_radius=3,
        )

        # Marco interior
        pygame.draw.rect(surface, shade(fill_color, 0.6), bar, width=1, border_radius=4)

        # Nombre y vida
        name_x = bar_left + 8 if align_left else bar.right - 8
        anchor = "topleft" if align_left else "topright"
        render_text(surface, mecha.name, 20, (name_x, y - 24), COLOR_TEXT, anchor=anchor)
        render_text(
            surface,
            f"{int(mecha.health)}/{int(mecha.stats.max_health)}",
            15,
            (name_x, y + BAR_HEIGHT + 4),
            COLOR_TEXT_DIM,
            anchor=anchor,
        )
        # Arma equipada: indica si el rival esta con hoja o a distancia.
        weapon_label = mecha.weapon.spec.name.upper()
        weapon_color = mecha.weapon.spec.glow if mecha.is_alive else COLOR_TEXT_DIM
        render_text(
            surface,
            weapon_label,
            13,
            (name_x, y + BAR_HEIGHT + 20),
            weapon_color,
            anchor=anchor,
        )

        if not mecha.is_alive:
            center = bar.center
            render_text(surface, "K.O.", 30, center, COLOR_DANGER, anchor="center")

    def _draw_round_info(self, surface: pygame.Surface, combat) -> None:
        """Reloj, numero de ronda y marcadores de victoria."""
        center_x = self.width // 2

        render_text(
            surface, f"RONDA {combat.round.number}", 20, (center_x, 18), COLOR_TEXT, anchor="center"
        )
        time_left = int(combat.round.time_left)
        time_color = COLOR_DANGER if time_left <= 10 else COLOR_TEXT
        render_text(
            surface,
            f"{time_left:02d}",
            46,
            (center_x, 38),
            time_color,
            anchor="center",
        )

        self._draw_score_pips(surface, combat, center_x - 78, 92)
        self._draw_score_pips(surface, combat, center_x + 78, 92, enemy=True)

    def _draw_score_pips(
        self, surface: pygame.Surface, combat, x: int, y: int, enemy: bool = False
    ) -> None:
        """Marcadores redondos: rondas ganadas por cada combatiente."""
        score = combat.round.enemy_score if enemy else combat.round.player_score
        for index in range(combat.rounds_to_win):
            color = COLOR_HP_ENEMY if enemy else COLOR_HP_PLAYER
            center = (x + index * 24, y)
            if index < score:
                pygame.draw.circle(surface, color, center, 8)
            else:
                pygame.draw.circle(surface, shade(color, 0.35), center, 8, width=2)

    def _draw_weapon_info(self, surface: pygame.Surface, player) -> None:
        """Arma equipada y barra de energia del jugador."""
        x = BAR_MARGIN
        y = 96
        energy = getattr(player, "energy_ratio", None)
        if energy is None:
            return

        bar = pygame.Rect(x, y + 18, 220, 10)
        pygame.draw.rect(surface, (24, 28, 54), bar, border_radius=5)
        fill = pygame.Rect(bar)
        fill.width = int(bar.width * energy)
        ready = energy >= 1.0 and player.can_fire_energy
        color = COLOR_ACCENT if ready else shade(COLOR_ACCENT, 0.55)
        pygame.draw.rect(surface, color, fill, border_radius=5)

        label = "ENERGIA [K]" if ready else "ENERGIA"
        render_text(surface, label, 15, (x, y), COLOR_TEXT_DIM)

    def _draw_status_messages(self, surface: pygame.Surface, combat) -> None:
        """Avisos centrados: resultado de ronda y fin de combate."""
        state = combat.round.state.value
        center = (self.width // 2, 260)

        if combat.match_over:
            winner = combat.winner_name or ""
            player_won = combat.round.player_score > combat.round.enemy_score
            message = "VICTORIA" if player_won else "DERROTA"
            color = COLOR_HP_PLAYER if player_won else COLOR_HP_ENEMY
            render_text(surface, message, 76, center, color, anchor="center")
            render_text(
                surface,
                f"{winner} DOMINA LA ARENA",
                26,
                (center[0], center[1] + 60),
                COLOR_TEXT,
                anchor="center",
            )
            render_text(
                surface,
                f"+{self.reward} CREDITOS",
                30,
                (center[0], center[1] + 104),
                COLOR_ACCENT,
                anchor="center",
            )
            render_text(
                surface,
                "PULSA J PARA VOLVER AL MENU",
                20,
                (center[0], center[1] + 150),
                COLOR_TEXT_DIM,
                anchor="center",
            )
        elif state == "player_wins":
            self._draw_round_banner(surface, "K.O.  -  RONDA PARA TI", COLOR_HP_PLAYER, center)
        elif state == "enemy_wins":
            self._draw_round_banner(
                surface, f"K.O.  -  RONDA PARA {combat.enemy.name.upper()}", COLOR_HP_ENEMY, center
            )

    def _draw_round_banner(
        self, surface: pygame.Surface, message: str, color: Color, center: Tuple[int, int]
    ) -> None:
        """Banner de fin de ronda."""
        render_text(surface, message, 48, center, color, anchor="center")
