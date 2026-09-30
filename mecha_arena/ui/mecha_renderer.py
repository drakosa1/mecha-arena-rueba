"""
MECHA ARENA - ui/mecha_renderer.py
===============================================================
Dibujado procedural de los Mecha. No se usa ninguna imagen externa.

Cada robot se construye pieza a pieza (piernas, cadera, torso, brazos, cabeza,
visor y arma) sobre un lienzo propio. Trabajar sobre un lienzo permite
aplicar volteo horizontal, rotacion de caida y destello de impacto en una
sola pasada, sin duplicar la logica de dibujo.

Convencion de coordenadas locales del esqueleto:
    - Origen en el centro de los pies.
    - Eje X local hacia el frente del robot.
    - Eje Y local hacia arriba.
La clase :class:`Painter` traduce esas coordenadas a pixeles del lienzo.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import pygame

from mecha_arena.domain.weapon import WeaponKind
from mecha_arena.settings import HIT_FLASH_TIME, MUZZLE_FLASH_TIME
from mecha_arena.ui.palette import mix, shade

Color = Tuple[int, int, int]

#: Lienzo de trabajo por Mecha: margen para el arma y la rotacion de caida.
CANVAS_SIZE = (240, 240)
#: Altura nominal del esqueleto usada como referencia de escala.
SKELETON_HEIGHT = 86.0
#: Margen inferior del lienzo reservado para los pies.
FOOT_MARGIN = 14.0


# ---------------------------------------------------------------------------
# Traduccion de coordenadas
# ---------------------------------------------------------------------------


class Painter:
    """
    Convierte coordenadas locales del esqueleto a pixeles de un lienzo.

    Se pasa a todas las funciones de dibujo para que cada pieza se describa
    en "unidades de Mecha" y no en pixeles, de modo que el mismo codigo
    sirve para TITAN-X y para OMEGA-7 aunque tengan tallas distintas.
    """

    def __init__(self, canvas: pygame.Surface, unit: float, offset_y: float = 0.0) -> None:
        self.canvas = canvas
        self.unit = unit
        self.origin_x = canvas.get_width() / 2.0
        self.origin_y = canvas.get_height() - FOOT_MARGIN + offset_y

    def point(self, x: float, y: float) -> Tuple[int, int]:
        """Punto local -> pixeles del lienzo."""
        return (
            int(self.origin_x + x * self.unit),
            int(self.origin_y - y * self.unit),
        )

    def box(self, x: float, y: float, width: float, height: float) -> pygame.Rect:
        """
        Rectangulo local definido por su esquina inferior izquierda.

        En coordenadas locales Y crece hacia arriba, mientras que en pixeles
        crece hacia abajo: por eso el alto se resta desde el borde inferior.
        """
        px, py = self.point(x, y)
        return pygame.Rect(px, py - int(height * self.unit), int(width * self.unit), int(height * self.unit))


# ---------------------------------------------------------------------------
# Renderizador
# ---------------------------------------------------------------------------


class MechaRenderer:
    """
    Dibuja Mecha completos a partir de su estado de dominio.

    Es un servicio sin estado entre partidas: solo conserva los lienzos
    cacheados por Mecha para no recrearlos en cada fotograma.
    """

    def __init__(self) -> None:
        self._canvases: Dict[int, pygame.Surface] = {}

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, mecha, time: float) -> None:
        """Dibuja ``mecha`` sobre ``surface`` en su posicion actual."""
        canvas = self._get_canvas(mecha)
        canvas.fill((0, 0, 0, 0))

        painter = Painter(
            canvas,
            unit=mecha.body_height / SKELETON_HEIGHT,
            offset_y=self._idle_bob(mecha, time),
        )
        self._draw_robot(painter, mecha, time)

        if mecha.facing < 0:
            canvas.blit(pygame.transform.flip(canvas, True, False), (0, 0))

        if mecha.hit_flash > 0.0 and mecha.is_alive:
            self._composite_flash(canvas, min(1.0, mecha.hit_flash / HIT_FLASH_TIME))

        if not mecha.is_alive:
            self._composite_wreck(canvas, mecha)

        surface.blit(
            canvas,
            (mecha.x - canvas.get_width() // 2, mecha.y - canvas.get_height() + FOOT_MARGIN),
        )

    def draw_shadow(self, surface: pygame.Surface, mecha, floor_y: float) -> None:
        """Sombra elliptica bajo el Mecha: ancla la figura al suelo."""
        if not mecha.is_alive:
            return
        lift = max(0.0, min(1.0, (floor_y - mecha.y) / 200.0))
        width = int(mecha.body_width * (1.1 - 0.4 * lift))
        height = max(4, int(10 * (1.0 - 0.55 * lift)))
        alpha = int(130 * (1.0 - lift * 0.7))
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (8, 10, 22, alpha), pygame.Rect(0, 0, width, height))
        surface.blit(shadow, (mecha.x - width // 2, int(mecha.y) - height // 2))

    # ------------------------------------------------------------------
    # Composicion del lienzo
    # ------------------------------------------------------------------
    def _get_canvas(self, mecha) -> pygame.Surface:
        """Devuelve (o crea) el lienzo de trabajo asociado al Mecha."""
        key = id(mecha)
        if key not in self._canvases:
            self._canvases[key] = pygame.Surface(CANVAS_SIZE, pygame.SRCALPHA)
        return self._canvases[key]

    def _composite_flash(self, canvas: pygame.Surface, ratio: float) -> None:
        """Superpone un destello blanco proporcional al impacto recibido."""
        flash = canvas.copy()
        flash.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGBA_MAX)
        flash.set_alpha(int(220 * ratio))
        canvas.blit(flash, (0, 0))

    def _composite_wreck(self, canvas: pygame.Surface, mecha) -> None:
        """Tumba el Mecha derrotado: lo gira, lo oscurece y lo desvanece."""
        rotated = pygame.transform.rotate(canvas, 78 * mecha.facing)
        tinted = rotated.copy()
        tinted.fill((52, 56, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
        tinted.set_alpha(150)
        canvas.fill((0, 0, 0, 0))
        canvas.blit(tinted, (0, 0))

    # ------------------------------------------------------------------
    # Animacion
    # ------------------------------------------------------------------
    def _idle_bob(self, mecha, time: float) -> float:
        """Respiracion sutil en reposo: da sensacion de peso al robot."""
        if abs(mecha.vx) > 12.0 or not mecha.on_ground:
            return 0.0
        return math.sin(time * 2.6) * 1.5

    def _walk_phase(self, mecha, time: float) -> float:
        """Fase del ciclo de caminado segun la velocidad horizontal."""
        if not mecha.on_ground or abs(mecha.vx) < 8.0:
            return 0.0
        return time * (6.0 + abs(mecha.vx) * 0.014)

    # ------------------------------------------------------------------
    # Construccion del esqueleto
    # ------------------------------------------------------------------
    def _draw_robot(self, painter: Painter, mecha, time: float) -> None:
        """Dibuja todas las piezas del Mecha, de atras hacia delante."""
        canvas = painter.canvas
        palette = mecha.palette
        walk = self._walk_phase(mecha, time)
        attack = mecha.weapon.swing_ratio if mecha.weapon.spec.is_melee else 0.0

        self._draw_back_thruster(painter, mecha, time)
        self._draw_legs(painter, mecha, walk)
        self._draw_hips(painter, mecha)
        self._draw_torso(painter, mecha, time)
        self._draw_back_arm(painter, mecha, walk)
        self._draw_head(painter, mecha, time)
        self._draw_weapon(painter, mecha, attack)
        # Brillo superior: simula la iluminacion cenital de la arena.
        highlight = painter.box(-13, 58, 24, 3)
        pygame.draw.rect(canvas, (*mix(palette.metal, (255, 255, 255), 0.4), 120), highlight, border_radius=1)

    # -- Piezas ----------------------------------------------------------
    def _draw_back_thruster(self, painter: Painter, mecha, time: float) -> None:
        """Propulsor trasero: brilla mas cuanto mas desplazamiento tiene."""
        canvas = painter.canvas
        palette = mecha.palette
        heat = min(1.0, abs(mecha.vx) / max(1.0, mecha.stats.move_speed))
        housing = painter.box(-25, 40, 13, 20)
        pygame.draw.rect(canvas, shade(palette.secondary, 0.8), housing, border_radius=3)
        flame = painter.box(-26, 34 - 7 * heat, 11, 6 + 9 * heat)
        color = mix(palette.glow, (255, 255, 255), 0.4 * heat)
        pygame.draw.rect(canvas, color, flame, border_radius=3)

    def _draw_legs(self, painter: Painter, mecha, walk_phase: float) -> None:
        """Piernas con ciclo de marcha y postura de salto."""
        canvas = painter.canvas
        palette = mecha.palette
        swing = math.sin(walk_phase) * 7.0
        airborne = not mecha.on_ground
        tuck = 6.0 if airborne else 0.0

        # (desplazamiento de marcha, altura extra, x base)
        legs = ((swing, tuck, 4.0), (-swing, tuck * 0.4, -12.0))
        for step, lift, base_x in legs:
            thigh = painter.box(base_x, 18 + lift, 11, 16)
            shin = painter.box(base_x + step * 0.25, 4 + lift, 9, 15)
            pygame.draw.rect(canvas, shade(palette.secondary, 0.95), thigh, border_radius=3)
            pygame.draw.rect(canvas, palette.metal, shin, border_radius=3)
            foot = painter.box(base_x + step * 0.2, lift, 15, 5)
            pygame.draw.rect(canvas, shade(palette.metal, 0.75), foot, border_radius=2)
            joint = painter.box(base_x + 2, 31 + lift, 7, 6)
            pygame.draw.rect(canvas, shade(palette.accent, 0.9), joint, border_radius=2)

    def _draw_hips(self, painter: Painter, mecha) -> None:
        """Cintura pelviana: union entre piernas y torso."""
        canvas = painter.canvas
        palette = mecha.palette
        rect = painter.box(-13, 28, 28, 12)
        pygame.draw.rect(canvas, shade(palette.secondary, 0.85), rect, border_radius=4)
        pygame.draw.rect(
            canvas, palette.accent, rect.inflate(4, 4), width=2, border_radius=5
        )

    def _draw_torso(self, painter: Painter, mecha, time: float) -> None:
        """Torso con placa pectoral, nucleo energetico y paneles."""
        canvas = painter.canvas
        palette = mecha.palette

        torso = painter.box(-15, 28, 30, 32)
        pygame.draw.rect(canvas, palette.primary, torso, border_radius=6)
        pygame.draw.rect(
            canvas, shade(palette.primary, 0.6), torso.inflate(2, 2), width=2, border_radius=7
        )

        chest = painter.box(-10, 34, 20, 20)
        pygame.draw.rect(canvas, shade(palette.secondary, 1.15), chest, border_radius=4)

        # Nucleo: late suavemente, es el foco visual del personaje.
        pulse = 0.5 + 0.5 * math.sin(time * 5.0)
        core = painter.box(-3, 42, 7, 7)
        pygame.draw.rect(
            canvas, mix(palette.glow, (255, 255, 255), 0.45 * pulse), core, border_radius=2
        )

        for index in range(3):
            panel = painter.box(-9, 52 - index * 5, 16, 2)
            pygame.draw.rect(canvas, shade(palette.metal, 0.85), panel, border_radius=1)

    def _draw_back_arm(self, painter: Painter, mecha, walk_phase: float) -> None:
        """Brazo trasero: contrapeso que se balancea al caminar."""
        canvas = painter.canvas
        palette = mecha.palette
        swing = math.sin(walk_phase + math.pi) * 6.0
        upper = painter.box(-19, 40, 10, 18)
        fore = painter.box(-21 + swing * 0.2, 24, 8, 18)
        pygame.draw.rect(canvas, shade(palette.primary, 0.8), upper, border_radius=3)
        pygame.draw.rect(canvas, shade(palette.metal, 0.85), fore, border_radius=3)

    def _draw_head(self, painter: Painter, mecha, time: float) -> None:
        """Cabeza con visor luminoso, antena y proteccion de nuca."""
        canvas = painter.canvas
        palette = mecha.palette

        head = painter.box(-10, 58, 22, 16)
        pygame.draw.rect(canvas, shade(palette.primary, 1.12), head, border_radius=5)

        visor = painter.box(4, 66, 9, 6)
        pygame.draw.rect(canvas, shade(palette.visor, 0.75), visor, border_radius=2)
        glow = painter.box(5, 67, 7, 4)
        pygame.draw.rect(
            canvas, mix(palette.visor, (255, 255, 255), 0.55), glow, border_radius=1
        )

        antenna = painter.box(-6, 74, 3, 9)
        pygame.draw.rect(canvas, palette.metal, antenna, border_radius=1)
        tip = painter.box(-7, 82, 5, 4)
        pygame.draw.rect(canvas, palette.accent, tip, border_radius=1)

        crest = painter.box(-13, 60, 5, 12)
        pygame.draw.rect(canvas, shade(palette.secondary, 0.9), crest, border_radius=2)

    def _draw_weapon(self, painter: Painter, mecha, attack: float) -> None:
        """Brazo delantero y arma equipada."""
        palette = mecha.palette
        spec = mecha.weapon.spec

        # El brazo se extiende a medida que avanza el golpe.
        extension = 6.0 + attack * 14.0 if spec.is_melee else 4.0 + attack * 6.0
        upper = painter.box(11, 42, 10, 18)
        fore = painter.box(13 + extension * 0.3, 26, 9, 18)
        hand = painter.box(15 + extension * 0.3, 24, 7, 6)
        pygame.draw.rect(painter.canvas, shade(palette.primary, 1.05), upper, border_radius=3)
        pygame.draw.rect(painter.canvas, palette.metal, fore, border_radius=3)
        pygame.draw.rect(painter.canvas, shade(palette.metal, 0.8), hand, border_radius=2)

        if spec.kind is WeaponKind.MELEE:
            self._draw_blade(painter, mecha, attack, extension)
        else:
            self._draw_cannon(painter, mecha, extension)

    def _draw_blade(self, painter: Painter, mecha, attack: float, extension: float) -> None:
        """Hoja de energia: barre de arriba abajo y deja estela."""
        canvas = painter.canvas
        palette = mecha.palette

        grip = (19.0 + extension * 0.3, 27.0)
        angle = math.radians(-58.0 + attack * 100.0)
        length = 30.0 + attack * 14.0
        tip = (grip[0] + math.cos(angle) * length, grip[1] + math.sin(angle) * length)

        pygame.draw.rect(
            canvas, shade(palette.metal, 0.75), painter.box(grip[0] - 2, grip[1] - 1, 9, 6),
            border_radius=2,
        )
        pygame.draw.line(
            canvas, shade(palette.metal, 0.9), painter.point(*grip), painter.point(*tip), 5
        )
        pygame.draw.line(
            canvas,
            mix(palette.glow, (255, 255, 255), 0.35 + 0.45 * attack),
            painter.point(*grip),
            painter.point(*tip),
            2,
        )

        if attack > 0.15:
            trail_angle = angle - 0.55
            trail = (
                grip[0] + math.cos(trail_angle) * length,
                grip[1] + math.sin(trail_angle) * length,
            )
            pygame.draw.line(
                canvas, shade(palette.glow, 0.6), painter.point(*grip), painter.point(*trail), 2
            )

    def _draw_cannon(self, painter: Painter, mecha, extension: float) -> None:
        """Cannon de energia: cuerpo, barrel y fogonazo al disparar."""
        canvas = painter.canvas
        palette = mecha.palette
        offset = extension * 0.3

        body = painter.box(18 + offset, 22, 22, 12)
        pygame.draw.rect(canvas, shade(palette.secondary, 1.1), body, border_radius=4)
        barrel = painter.box(37 + offset, 25, 16, 7)
        pygame.draw.rect(canvas, palette.metal, barrel, border_radius=3)
        muzzle = painter.box(51 + offset, 26, 4, 5)
        pygame.draw.rect(canvas, shade(palette.accent, 1.1), muzzle, border_radius=1)

        if mecha.muzzle_flash > 0.0:
            intensity = min(1.0, mecha.muzzle_flash / MUZZLE_FLASH_TIME)
            flash = painter.box(50 + offset, 17, 15, 22)
            color = mix(palette.glow, (255, 255, 255), 0.6 * intensity)
            pygame.draw.rect(canvas, color, flash, border_radius=6)
