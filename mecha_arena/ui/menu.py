"""
MECHA ARENA - ui/menu.py
===============================================================
Interfaz de los menus: portada, seleccion de Mecha, taller de mejoras y
ayuda de controles.

La clase ``Menu`` no decide nada del combate: se limita a traducir la entrada
en ordenes ("jugar", "salir") y a dibujar. El progreso vive en ``profile`` y el
catalogo de Mecha en ``roster``, de modo que la interfaz es solo una vista.

Estructura de cada pagina:

    MAIN       -> portada con las opciones principales
    SELECT     -> catalogo de Mecha, con vista previa y compra
    UPGRADES   -> taller: cuatro lineas de mejora por Mecha
    HELP       -> tabla de controles
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pygame

from mecha_arena import settings
from mecha_arena.domain.upgrade import UPGRADES, UPGRADE_ORDER, UpgradeKind, apply_upgrades
from mecha_arena.entities.roster import ROSTER, ROSTER_ORDER, build_player
from mecha_arena.profile import PlayerProfile
from mecha_arena.ui.fonts import render_text
from mecha_arena.ui.mecha_renderer import MechaRenderer
from mecha_arena.ui.palette import mix, with_alpha

#: Teclas de repeticion al mantener la direccion en un menu.
REPEAT_DELAY = 0.34
REPEAT_RATE = 0.11
#: Tiempo que permanece un aviso en pantalla (compra fallida, etc.).
MESSAGE_TIME = 1.8


class MenuPage(Enum):
    """Paginas del menu principal."""

    MAIN = "main"
    SELECT = "select"
    UPGRADES = "upgrades"
    HELP = "help"


#: Etiquetas de las lineas del taller, en el orden de ``UPGRADE_ORDER``.
UPGRADE_TAGS = {
    UpgradeKind.ATTACK: "ATQ",
    UpgradeKind.ARMOR: "DEF",
    UpgradeKind.HULL: "VIDA",
    UpgradeKind.ENGINE: "VEL",
}


class Menu:
    """
    Maquina de estados de los menus.

    ``update`` consume el estado de entrada y devuelve una orden para el
    orquestador (``"play"``, ``"quit"`` o ``None``); ``draw`` pinta la pagina
    activa usando el fondo de la arena como ambientacion comun.
    """

    def __init__(self, profile: PlayerProfile, arena=None) -> None:
        self.profile = profile
        self.arena = arena
        self.renderer = MechaRenderer()
        #: Estado de entrada del fotograma en curso (lo inyecta ``update``).
        self.input = None
        self.page = MenuPage.MAIN

        # --- Estado de navegacion -----------------------------------------
        self.option_index = 0
        self.mecha_index = ROSTER_ORDER.index(profile.selected) if profile.selected in ROSTER_ORDER else 0
        self.upgrade_index = 0
        self._repeat_timer = 0.0
        self._repeat_dir = 0
        self._time = 0.0

        # --- Avisos -------------------------------------------------------
        self.message = ""
        self._message_timer = 0.0

        # --- Vista previa del Mecha ---------------------------------------
        self._preview_key: Optional[str] = None
        self._preview = None

        #: Opciones de la portada, en orden de navegacion.
        self.main_options: List[str] = ["COMBATIR", "MEZCLA", "CONTROLES", "SALIR"]

        #: Referencias de escala para las barras de estadisticas.
        self._stat_maxima = self._compute_stat_maxima()

    # ------------------------------------------------------------------
    # Utilidades de estado
    # ------------------------------------------------------------------
    @property
    def mecha_key(self) -> str:
        """Clave del Mecha resaltado en la pagina de seleccion."""
        return ROSTER_ORDER[self.mecha_index]

    def _compute_stat_maxima(self) -> Dict[str, float]:
        """
        Mayor valor de cada estadistica en el catalogo.

        Sirve para normalizar las barras: asi se ve de un vistazo que
        VULCANO-9 es mas duro, aunque sus numeros sean absolutos.
        """
        maxima = {"max_health": 0.0, "attack": 0.0, "defense": 0.0, "move_speed": 0.0}
        for spec in ROSTER.values():
            for key in maxima:
                maxima[key] = max(maxima[key], getattr(spec.stats, key))
        return {key: value * 1.05 for key, value in maxima.items()}

    def _nav(self, delta_time: float) -> int:
        """
        Lee el eje horizontal con repeticion y devuelve -1, 0 o 1.

        La primera pulsacion responde al instante y las siguientes se repiten
        mientras la tecla este mantenida, como en un menu de consola.
        """
        axis = self.input.move_axis()
        if axis == 0.0:
            self._repeat_timer = 0.0
            self._repeat_dir = 0
            return 0

        if axis != self._repeat_dir:
            self._repeat_dir = int(axis)
            self._repeat_timer = REPEAT_DELAY
            return int(axis)

        self._repeat_timer -= delta_time
        if self._repeat_timer <= 0.0:
            self._repeat_timer = REPEAT_RATE
            return int(axis)
        return 0

    def _notify(self, text: str) -> None:
        """Muestra un aviso breve (compra imposible, Mecha nuevo, etc.)."""
        self.message = text
        self._message_timer = MESSAGE_TIME

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def update(self, input_state, delta_time: float) -> Optional[str]:
        """
        Procesa la entrada del fotograma.

        :return: ``"play"``, ``"quit"`` o ``None`` si no hay orden.
        """
        self.input = input_state
        self._time += delta_time
        if self._message_timer > 0.0:
            self._message_timer -= delta_time

        if self.page is MenuPage.MAIN:
            return self._update_main(delta_time)
        if self.page is MenuPage.SELECT:
            return self._update_select(delta_time)
        if self.page is MenuPage.UPGRADES:
            return self._update_upgrades(delta_time)
        return self._update_help()

    def _update_main(self, delta_time: float) -> Optional[str]:
        """Portada: navegacion vertical simulada con el eje horizontal."""
        step = self._nav(delta_time)
        if step:
            self.option_index = (self.option_index + step) % len(self.main_options)

        if not self.input.melee_pressed():
            return None

        option = self.main_options[self.option_index]
        if option == "COMBATIR":
            return "play"
        if option == "MEZCLA":
            self.page = MenuPage.UPGRADES
            self.upgrade_index = 0
        elif option == "CONTROLES":
            self.page = MenuPage.HELP
        elif option == "SALIR":
            return "quit"
        return None

    def _update_select(self, delta_time: float) -> Optional[str]:
        """Catalogo: recorrer Mecha, equipar o comprar."""
        if self.input.pause_pressed:
            self.page = MenuPage.MAIN
            return None

        step = self._nav(delta_time)
        if step:
            self.mecha_index = (self.mecha_index + step) % len(ROSTER_ORDER)

        key = self.mecha_key
        if self.input.melee_pressed():
            self._select_mecha(key)
        elif self.input.energy_pressed():
            # K entra directamente al combate con el Mecha resaltado.
            if self.profile.owns(key) or self.profile.purchase(key):
                self.profile.select(key)
                self.profile.save()
                return "play"
            self._notify("CREDITOS INSUFICIENTES")
        return None

    def _select_mecha(self, key: str) -> None:
        """Equipa un Mecha propio o lo compra si hay creditos."""
        if self.profile.owns(key):
            self.profile.select(key)
            self._notify(f"{ROSTER[key].name} EQUIPADO")
        elif self.profile.purchase(key):
            self.profile.select(key)
            self._notify(f"{ROSTER[key].name} ADQUIRIDO")
        else:
            self._notify("CREDITOS INSUFICIENTES")
        self.profile.save()

    def _update_upgrades(self, delta_time: float) -> Optional[str]:
        """Taller: navegar lineas, comprar niveles y cambiar de Mecha."""
        if self.input.pause_pressed:
            self.page = MenuPage.MAIN
            return None

        step = self._nav(delta_time)
        if step:
            self.upgrade_index = (self.upgrade_index + step) % len(UPGRADE_ORDER)

        kind = UPGRADE_ORDER[self.upgrade_index]
        key = self.profile.selected

        if self.input.melee_pressed():
            if self.profile.upgrade_maxed(kind, key):
                self._notify("NIVEL MAXIMO")
            elif self.profile.buy_upgrade(kind, key):
                self.profile.save()
                self._notify(f"{UPGRADES[kind].name} NIVEL {self.profile.upgrade_level(kind, key)}")
            else:
                self._notify("CREDITOS INSUFICIENTES")
        elif self.input.energy_pressed():
            # K recorre los Mecha propios sin salir del taller.
            propias = [key for key in ROSTER_ORDER if self.profile.owns(key)]
            actual = propias.index(key) if key in propias else 0
            self.profile.select(propias[(actual + 1) % len(propias)])
            self._notify(f"TALLER: {ROSTER[key].name}")
        return None

    def _update_help(self) -> Optional[str]:
        """Ayuda: cualquier tecla vuelve a la portada."""
        if self.input.melee_pressed() or self.input.pause_pressed:
            self.page = MenuPage.MAIN
        return None

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Pinta la pagina activa."""
        if self.arena is not None:
            self.arena.draw_backdrop(surface, dim=150)
        else:
            surface.fill(settings.COLOR_BACKGROUND_TOP)

        if self.page is MenuPage.MAIN:
            self._draw_main(surface)
        elif self.page is MenuPage.SELECT:
            self._draw_select(surface)
        elif self.page is MenuPage.UPGRADES:
            self._draw_upgrades(surface)
        else:
            self._draw_help(surface)

        self._draw_header(surface)
        if self._message_timer > 0.0:
            self._draw_message(surface)

    # ------------------------------------------------------------------
    # Cabecera comun
    # ------------------------------------------------------------------
    def _draw_header(self, surface: pygame.Surface) -> None:
        """Titulo, creditos y record siempre visibles."""
        rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, 64)
        bar = pygame.Surface(rect.size, pygame.SRCALPHA)
        bar.fill((*settings.COLOR_HUD_BG, 220))
        surface.blit(bar, rect.topleft)
        pygame.draw.line(
            surface, settings.COLOR_ACCENT, (0, 64), (settings.SCREEN_WIDTH, 64), 2
        )

        render_text(
            surface, settings.GAME_TITLE, 26, (24, 18), settings.COLOR_ACCENT, anchor="midleft"
        )
        record = f"{self.profile.wins}V / {self.profile.losses}D"
        if self.profile.streak > 1:
            record += f"   RACHA x{self.profile.streak}"
        render_text(
            surface, record, 16, (settings.SCREEN_WIDTH - 210, 20), settings.COLOR_TEXT_DIM,
            anchor="midleft",
        )
        render_text(
            surface, f"{self.profile.credits} CR", 22, (settings.SCREEN_WIDTH - 24, 32),
            settings.COLOR_ACCENT, anchor="midright",
        )
        render_text(
            surface, "CREDITOS", 13, (settings.SCREEN_WIDTH - 24, 14), settings.COLOR_TEXT_DIM,
            anchor="midright",
        )

    def _draw_message(self, surface: pygame.Surface) -> None:
        """Aviso central que se desvanece."""
        alpha = min(1.0, self._message_timer / 0.5)
        color = mix(settings.COLOR_BACKGROUND_TOP, settings.COLOR_TEXT, alpha)
        text_rect = render_text(
            surface, self.message, 22, (settings.SCREEN_WIDTH // 2, 118), color, anchor="center"
        )
        pygame.draw.rect(
            surface, with_alpha(settings.COLOR_ACCENT, 0.4 * alpha), text_rect.inflate(28, 16), 2
        )

    # ------------------------------------------------------------------
    # Pagina: portada
    # ------------------------------------------------------------------
    def _draw_main(self, surface: pygame.Surface) -> None:
        """Portada con las opciones principales y la ficha del Mecha actual."""
        center_x = settings.SCREEN_WIDTH // 2
        render_text(
            surface, settings.GAME_TITLE, 78, (center_x, 168), settings.COLOR_TEXT, anchor="center"
        )
        render_text(
            surface, "COMBATE DE MECHA 2D  -  GANADOR A 2 RONDAS", 20, (center_x, 218),
            settings.COLOR_TEXT_DIM, bold=False, anchor="center",
        )

        self._draw_equipped_card(surface)

        top = 300
        for index, option in enumerate(self.main_options):
            activo = index == self.option_index
            y = top + index * 62
            if activo:
                box = pygame.Rect(center_x - 190, y - 26, 380, 52)
                self._panel(surface, box, highlight=True)
                # pequena marca que respira cuando la opcion esta activa
                pulse = 0.55 + 0.45 * math.sin(self._time * 6.0)
                pygame.draw.polygon(
                    surface,
                    mix(settings.COLOR_ACCENT, (255, 255, 255), pulse * 0.5),
                    [(box.left - 30, y - 10), (box.left - 18, y), (box.left - 30, y + 10)],
                )
            render_text(
                surface, option, 28,
                (center_x, y), settings.COLOR_TEXT if activo else settings.COLOR_TEXT_DIM,
                anchor="center",
            )

        self._draw_hint(surface, "A / D  ELEGIR        J  ACEPTAR")

    def _draw_equipped_card(self, surface: pygame.Surface) -> None:
        """Ficha resumida del Mecha equipado, arriba a la derecha."""
        spec = ROSTER[self.profile.selected]
        box = pygame.Rect(settings.SCREEN_WIDTH - 350, 96, 326, 168)
        self._panel(surface, box)

        render_text(surface, "EQUIPADO", 14, (box.x + 16, box.y + 12), settings.COLOR_TEXT_DIM)
        render_text(surface, spec.name, 30, (box.x + 16, box.y + 32), spec.palette.accent)
        render_text(
            surface, f"PRIMARIA  {spec.weapon_spec.name}", 15, (box.x + 16, box.y + 74),
            settings.COLOR_TEXT_DIM, bold=False,
        )
        render_text(
            surface, f"SECUNDARIA  {spec.secondary_spec.name}", 15, (box.x + 16, box.y + 94),
            settings.COLOR_TEXT_DIM, bold=False,
        )
        self._preview_mecha(surface, spec.key, (box.x + 250, box.bottom - 62))

    # ------------------------------------------------------------------
    # Pagina: seleccion de Mecha
    # ------------------------------------------------------------------
    def _draw_select(self, surface: pygame.Surface) -> None:
        """Catalogo: lista a la izquierda, detalle y vista previa a la derecha."""
        box = pygame.Rect(0, 80, 470, settings.SCREEN_HEIGHT - 80)
        self._panel(surface, box)
        render_text(
            surface, "SELECCION DE MECHA", 24, (24, 94), settings.COLOR_TEXT, anchor="midleft"
        )

        for index, key in enumerate(ROSTER_ORDER):
            spec = ROSTER[key]
            y = 140 + index * 108
            fila = pygame.Rect(16, y - 44, 438, 92)
            activo = index == self.mecha_index
            if activo:
                self._panel(surface, fila, color=settings.COLOR_HUD_BORDER, alpha=60, highlight=True)

            color = spec.palette.primary if self.profile.owns(key) else settings.COLOR_TEXT_DIM
            pygame.draw.rect(surface, color, (28, y - 34, 6, 72), border_radius=3)
            render_text(surface, spec.name, 26, (46, y - 20), color)
            render_text(
                surface, spec.tagline, 14, (46, y + 12), settings.COLOR_TEXT_DIM, bold=False
            )
            self._draw_stat_row(surface, fila, spec.stats)
            self._draw_ownership_tag(surface, fila, spec)

        self._draw_detail(surface)
        self._draw_hint(surface, "A / D  RECORRER        J  COMPRAR / EQUIPAR        K  JUGAR        ESC  VOLVER")

    def _draw_ownership_tag(self, surface: pygame.Surface, fila: pygame.Rect, spec) -> None:
        """Etiqueta de estado: en posesion, precio o bloqueado."""
        if self.profile.owns(spec.key):
            if self.profile.selected == spec.key:
                text, color = "EQUIPADO", settings.COLOR_HP_PLAYER
            else:
                text, color = "EN USO", settings.COLOR_TEXT_DIM
        elif self.profile.can_afford(spec.price):
            text, color = f"{spec.price} CR", settings.COLOR_ACCENT
        else:
            text, color = f"{spec.price} CR", settings.COLOR_DANGER
        render_text(
            surface, text, 17, (fila.right - 16, fila.y + 14), color, anchor="topright"
        )

    def _draw_stat_row(self, surface: pygame.Surface, fila: pygame.Rect, stats) -> None:
        """Barras de vida, dano, defensa y velocidad."""
        etiquetas = (
            ("VIDA", "max_health"),
            ("ATQ", "attack"),
            ("DEF", "defense"),
            ("VEL", "move_speed"),
        )
        for index, (etiqueta, key) in enumerate(etiquetas):
            x = fila.x + 46 + index * 96
            y = fila.bottom - 16
            render_text(
                surface, etiqueta, 12, (x, y - 12), settings.COLOR_TEXT_DIM, bold=False
            )
            self._stat_bar(surface, x, y, 84, stats, key)

    def _draw_detail(self, surface: pygame.Surface) -> None:
        """Panel derecho: vista previa animada y numeros del Mecha resaltado."""
        spec = ROSTER[self.mecha_key]
        box = pygame.Rect(490, 96, 766, 476)
        self._panel(surface, box)

        render_text(surface, spec.name, 40, (box.x + 28, box.y + 22), spec.palette.accent)
        render_text(
            surface, spec.tagline, 17, (box.x + 28, box.y + 68), settings.COLOR_TEXT_DIM,
            bold=False,
        )
        self._draw_difficulty(surface, (box.x + 28, box.y + 96), spec.difficulty)

        self._preview_mecha(surface, spec.key, (box.right - 190, box.bottom - 150))

        # Armas: son la identidad del Mecha, se muestran siempre.
        armas_y = box.y + 140
        for etiqueta, weapon in (("PRIMARIA", spec.weapon_spec), ("SECUNDARIA", spec.secondary_spec)):
            if weapon is None:
                continue
            render_text(surface, etiqueta, 13, (box.x + 28, armas_y), settings.COLOR_TEXT_DIM)
            render_text(surface, weapon.name, 22, (box.x + 28, armas_y + 16), weapon.glow)
            render_text(
                surface,
                f"danio {weapon.damage:.0f}   enfriamiento {weapon.cooldown:.2f}s",
                14, (box.x + 28, armas_y + 44), settings.COLOR_TEXT_DIM, bold=False,
            )
            armas_y += 78

        niveles = self.profile.upgrade_levels(spec.key)
        if any(niveles.values()):
            mejoras = "  ".join(
                f"{UPGRADE_TAGS[kind]} {niveles.get(kind, 0)}" for kind in UPGRADE_ORDER
            )
            render_text(
                surface, f"MEJORAS  {mejoras}", 15, (box.x + 28, box.bottom - 24),
                settings.COLOR_HP_PLAYER, bold=False,
            )
        elif not self.profile.owns(spec.key):
            render_text(
                surface, f"BLOQUEADO  -  {spec.price} CREDITOS", 18, (box.x + 28, box.bottom - 28),
                settings.COLOR_DANGER,
            )

    def _draw_difficulty(self, surface: pygame.Surface, position: Tuple[int, int], nivel: int) -> None:
        """Cinco puntos que indican la dificultad de manejo del Mecha."""
        x, y = position
        render_text(surface, "DIFICULTAD", 13, (x, y), settings.COLOR_TEXT_DIM)
        for index in range(5):
            color = settings.COLOR_ACCENT if index < nivel else settings.COLOR_HUD_BORDER
            pygame.draw.circle(surface, color, (x + 100 + index * 18, y + 6), 5)

    # ------------------------------------------------------------------
    # Pagina: taller
    # ------------------------------------------------------------------
    def _draw_upgrades(self, surface: pygame.Surface) -> None:
        """Taller de mejoras del Mecha equipado."""
        key = self.profile.selected
        spec = ROSTER[key]
        niveles = self.profile.upgrade_levels(key)
        finales = apply_upgrades(spec.stats, niveles)

        render_text(
            surface, "TALLER DE MEJORAS", 34, (settings.SCREEN_WIDTH // 2, 96),
            settings.COLOR_TEXT, anchor="center",
        )
        render_text(
            surface, f"{spec.name}   -   {self.profile.credits} CREDITOS DISPONIBLES", 18,
            (settings.SCREEN_WIDTH // 2, 130), spec.palette.accent, anchor="center",
        )

        # --- Lineas de mejora ---------------------------------------------
        top = 178
        for index, kind in enumerate(UPGRADE_ORDER):
            upgrade = UPGRADES[kind]
            nivel = niveles.get(kind, 0)
            activo = index == self.upgrade_index
            box = pygame.Rect(70, top + index * 88, 700, 76)
            if activo:
                self._panel(surface, box, highlight=True)

            coste = self.profile.next_upgrade_cost(kind, key)
            if coste is None:
                etiqueta, color = "AL MAXIMO", settings.COLOR_HP_PLAYER
            elif self.profile.can_afford(coste):
                etiqueta, color = f"{coste} CR", settings.COLOR_ACCENT
            else:
                etiqueta, color = f"{coste} CR", settings.COLOR_DANGER

            render_text(
                surface, upgrade.name, 24, (box.x + 24, box.y + 14),
                settings.COLOR_TEXT if activo else settings.COLOR_TEXT_DIM,
            )
            render_text(
                surface, upgrade.description, 15, (box.x + 24, box.y + 44),
                settings.COLOR_TEXT_DIM, bold=False,
            )
            self._draw_level_pips(surface, (box.x + 340, box.y + 26), nivel, upgrade.max_level)
            render_text(
                surface, f"{getattr(spec.stats, upgrade.stat):.0f} -> "
                         f"{getattr(finales, upgrade.stat):.0f}",
                18, (box.x + 430, box.y + 16), settings.COLOR_HP_PLAYER, anchor="topright",
            )
            render_text(
                surface, etiqueta, 20, (box.right - 24, box.centery), color, anchor="midright"
            )

        # --- Panel derecho: resultado final --------------------------------
        self._draw_upgrade_summary(surface, spec, finales, key)
        self._draw_hint(
            surface, "A / D  LINEA        J  COMPRAR        K  CAMBIAR DE MECHA        ESC  VOLVER"
        )

    def _draw_upgrade_summary(
        self, surface: pygame.Surface, spec, finales, key: str
    ) -> None:
        """Comparativa base / mejorada y vista previa del Mecha."""
        box = pygame.Rect(800, 178, 456, 400)
        self._panel(surface, box)
        render_text(surface, "RESULTADO", 18, (box.x + 24, box.y + 16), settings.COLOR_ACCENT)

        filas = (("VIDA", "max_health"), ("DANO", "attack"), ("DEFENSA", "defense"),
                 ("VELOCIDAD", "move_speed"))
        for index, (etiqueta, atributo) in enumerate(filas):
            y = box.y + 56 + index * 30
            base = getattr(spec.stats, atributo)
            valor = getattr(finales, atributo)
            render_text(surface, etiqueta, 15, (box.x + 24, y), settings.COLOR_TEXT_DIM, bold=False)
            render_text(
                surface, f"{base:.0f}", 17, (box.x + 260, y), settings.COLOR_TEXT_DIM,
                anchor="topright",
            )
            flecha = "+" if valor > base else ""
            render_text(
                surface, f"{flecha}{valor:.0f}", 19, (box.right - 24, y),
                settings.COLOR_HP_PLAYER if valor > base else settings.COLOR_TEXT, anchor="topright",
            )

        self._preview_mecha(surface, key, (box.centerx, box.bottom - 96))

    def _draw_level_pips(self, surface: pygame.Surface, position: Tuple[int, int], nivel: int, maximo: int) -> None:
        """Cuadraditos que indican los niveles comprados."""
        x, y = position
        for index in range(maximo):
            color = settings.COLOR_HP_PLAYER if index < nivel else settings.COLOR_HUD_BORDER
            rect = pygame.Rect(x + index * 26, y, 20, 20)
            pygame.draw.rect(surface, color, rect, border_radius=3)

    # ------------------------------------------------------------------
    # Pagina: ayuda
    # ------------------------------------------------------------------
    def _draw_help(self, surface: pygame.Surface) -> None:
        """Tabla de controles y reglas basicas."""
        box = pygame.Rect(220, 120, 840, 500)
        self._panel(surface, box)
        render_text(
            surface, "CONTROLES", 34, (box.centerx, box.y + 24), settings.COLOR_ACCENT, anchor="center"
        )

        controles = (
            ("A / D  o  <- ->", "Mover y elegir en los menus"),
            ("W  o  ARRIBA", "Saltar"),
            ("J  o  ESPACIO", "Cuerpo a cuerpo"),
            ("K  o  MAYUS", "Arma de energia (consume barra)"),
            ("ESC", "Salir del combate / volver atras"),
        )
        for index, (tecla, accion) in enumerate(controles):
            y = box.y + 90 + index * 40
            render_text(surface, tecla, 20, (box.x + 40, y), settings.COLOR_TEXT, anchor="midleft")
            render_text(
                surface, accion, 18, (box.x + 320, y), settings.COLOR_TEXT_DIM, bold=False,
                anchor="midleft",
            )

        pygame.draw.line(
            surface, settings.COLOR_HUD_BORDER, (box.x + 40, box.y + 310), (box.right - 40, box.y + 310), 1
        )
        reglas = (
            "Gana 2 rondas para llevarte el combate.",
            "El arma secundaria se recarga sola, pero la barra de energia no.",
            "OMEGA-7 cambia de tactic a segun su vida y la ronda.",
            "Ganas creditos jugando: sirven en el TALLER para mejorar tu Mecha.",
        )
        for index, regla in enumerate(reglas):
            render_text(
                surface, f"-  {regla}", 17, (box.x + 40, box.y + 336 + index * 30),
                settings.COLOR_TEXT_DIM, bold=False,
            )

        self._draw_hint(surface, "J  o  ESC  VOLVER")

    # ------------------------------------------------------------------
    # Piezas reutilizables
    # ------------------------------------------------------------------
    def _panel(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        color=settings.COLOR_HUD_BG,
        alpha: int = 210,
        highlight: bool = False,
    ) -> None:
        """Panel translucido con borde, el contenedor basico de la interfaz."""
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((*color, alpha))
        border = settings.COLOR_ACCENT if highlight else settings.COLOR_HUD_BORDER
        pygame.draw.rect(panel, (*border, 255), panel.get_rect(), 2)
        surface.blit(panel, rect.topleft)

        if highlight:
            # Filo luminoso en el lado izquierdo: marca la seleccion sin ruido.
            pygame.draw.rect(
                surface, settings.COLOR_ACCENT, (rect.x, rect.y, 4, rect.height), border_radius=2
            )

    def _stat_bar(self, surface: pygame.Surface, x: int, y: int, width: int, stats, key: str) -> None:
        """Barra de estadistica normalizada contra el maximo del catalogo."""
        ratio = max(0.0, min(1.0, getattr(stats, key) / self._stat_maxima[key]))
        fondo = pygame.Rect(x, y, width, 8)
        pygame.draw.rect(surface, settings.COLOR_HUD_BG, fondo, border_radius=4)
        relleno = pygame.Rect(x, y, int(width * ratio), 8)
        color = mix(settings.COLOR_ACCENT, settings.COLOR_HP_PLAYER, ratio)
        pygame.draw.rect(surface, color, relleno, border_radius=4)

    def _preview_mecha(self, surface: pygame.Surface, key: str, position: Tuple[int, int]) -> None:
        """
        Dibuja el Mecha real de la ficha, con sus mejoras aplicadas.

        Reutiliza el renderizador del combate: la vista previa del menu muestra
        exactamente el Mecha que se va a usar, sin duplicar arte. El tamano sale
        de la propia ficha, asi que un Mecha pesado se ve mas grande.
        """
        if self._preview is None or self._preview_key != key:
            self._preview = build_player(key, position[0], settings.FLOOR_Y,
                                         self.profile.upgrade_levels(key))
            self._preview.on_ground = True
            self._preview.facing = 1
            self._preview_key = key

        antes = self._preview.x, self._preview.y
        self._preview.x, self._preview.y = position
        self.renderer.draw(surface, self._preview, self._time)
        self._preview.x, self._preview.y = antes

    def _draw_hint(self, surface: pygame.Surface, text: str) -> None:
        """Recordatorio de teclas al pie de la pantalla."""
        render_text(
            surface, text, 16, (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT - 22),
            settings.COLOR_TEXT_DIM, bold=False, anchor="center",
        )
