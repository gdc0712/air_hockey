"""
Air Hockey Game - UI: Menus, HUD, Buttons
"""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    WHITE, BLACK, GRAY, DARK_GRAY, LIGHT_GRAY,
    RED, BLUE, YELLOW, GREEN, ORANGE, CYAN,
    PLAYER1_COLOR, PLAYER2_COLOR,
    BOOST_MAX_ENERGY,
    POWERUP_COLORS, POWERUP_DURATION,
    PU_BIGGER, PU_SMALLER, PU_SPEED, PU_MAGNET, PU_FREEZE,
    ARENAS,
)


class Button:
    """A clickable UI button."""

    def __init__(self, x, y, width, height, text, color=DARK_GRAY,
                 hover_color=GRAY, text_color=WHITE, font_size=24):
        self.rect = pygame.Rect(x - width // 2, y - height // 2, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font = pygame.font.SysFont(None, font_size)
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface):
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=6)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos, mouse_pressed):
        return self.hovered and mouse_pressed


class Selector:
    """A left/right selector for choosing options."""

    def __init__(self, x, y, label, options, default_index=0, width=260):
        self.x = x
        self.y = y
        self.label = label
        self.options = options
        self.index = default_index
        self.width = width
        self.font = pygame.font.SysFont(None, 24)
        self.small_font = pygame.font.SysFont(None, 22)
        # Arrow buttons
        arrow_size = 30
        self.left_rect = pygame.Rect(x - width // 2, y - arrow_size // 2,
                                     arrow_size, arrow_size)
        self.right_rect = pygame.Rect(x + width // 2 - arrow_size, y - arrow_size // 2,
                                      arrow_size, arrow_size)

    @property
    def value(self):
        return self.options[self.index]

    def handle_click(self, mouse_pos):
        if self.left_rect.collidepoint(mouse_pos):
            self.index = (self.index - 1) % len(self.options)
            return True
        if self.right_rect.collidepoint(mouse_pos):
            self.index = (self.index + 1) % len(self.options)
            return True
        return False

    def draw(self, surface):
        # Label
        label_surf = self.font.render(self.label, True, LIGHT_GRAY)
        surface.blit(label_surf, (self.x - label_surf.get_width() // 2, self.y - 30))

        # Arrows
        pygame.draw.rect(surface, GRAY, self.left_rect, border_radius=4)
        pygame.draw.rect(surface, GRAY, self.right_rect, border_radius=4)
        left_text = self.small_font.render("<", True, WHITE)
        right_text = self.small_font.render(">", True, WHITE)
        surface.blit(left_text, left_text.get_rect(center=self.left_rect.center))
        surface.blit(right_text, right_text.get_rect(center=self.right_rect.center))

        # Current value
        val_text = self.font.render(str(self.value), True, WHITE)
        surface.blit(val_text, (self.x - val_text.get_width() // 2, self.y - 8))


class MainMenu:
    """Main menu screen."""

    def __init__(self):
        cx = SCREEN_WIDTH // 2
        self.title_font = pygame.font.SysFont(None, 64)
        self.sub_font = pygame.font.SysFont(None, 28)

        self.buttons = {
            "local_1v1": Button(cx, 200, 260, 44, "Local 1v1"),
            "vs_ai": Button(cx, 260, 260, 44, "Player vs AI"),
            "practice": Button(cx, 320, 260, 44, "Practice"),
            "quit": Button(cx, 520, 200, 40, "Quit", color=(100, 30, 30)),
        }

        # Settings selectors
        self.difficulty_sel = Selector(cx, 400, "AI Difficulty",
                                       ["Easy", "Medium", "Hard"], default_index=1)
        self.arena_sel = Selector(cx, 460, "Arena",
                                   list(ARENAS.keys()), default_index=0)
        self.rules_sel = Selector(cx - 150, 400, "Match Rules",
                                   ["First to 5", "First to 7", "First to 10",
                                    "Timed 60s", "Timed 90s", "Timed 120s"],
                                   default_index=1, width=200)
        self.mouse_toggle = Button(cx + 180, 400, 160, 30, "Mouse: OFF",
                                   font_size=20)
        self.mouse_mode = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            for name, btn in self.buttons.items():
                if btn.is_clicked(pos, True):
                    return name

            self.difficulty_sel.handle_click(pos)
            self.arena_sel.handle_click(pos)
            self.rules_sel.handle_click(pos)

            if self.mouse_toggle.is_clicked(pos, True):
                self.mouse_mode = not self.mouse_mode
                self.mouse_toggle.text = f"Mouse: {'ON' if self.mouse_mode else 'OFF'}"

        return None

    def get_settings(self):
        """Return current menu selections as a dict."""
        rules_val = self.rules_sel.value
        if rules_val.startswith("First"):
            n = int(rules_val.split()[-1])
            mode = "first_to"
            match_param = n
        else:
            t = int(rules_val.split()[1].rstrip("s"))
            mode = "timed"
            match_param = t

        return {
            "difficulty": self.difficulty_sel.value.lower(),
            "arena": self.arena_sel.value,
            "match_mode": mode,
            "match_param": match_param,
            "mouse_mode": self.mouse_mode,
        }

    def update(self, mouse_pos):
        for btn in self.buttons.values():
            btn.update(mouse_pos)
        self.mouse_toggle.update(mouse_pos)

    def draw(self, surface):
        surface.fill((20, 20, 30))

        # Title
        title = self.title_font.render("AIR HOCKEY", True, WHITE)
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        sub = self.sub_font.render("Select a game mode", True, GRAY)
        surface.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 130))

        for btn in self.buttons.values():
            btn.draw(surface)

        self.difficulty_sel.draw(surface)
        self.arena_sel.draw(surface)
        self.rules_sel.draw(surface)
        self.mouse_toggle.draw(surface)

        # Arena description
        arena_key = self.arena_sel.value
        if arena_key in ARENAS:
            desc = ARENAS[arena_key].get("description", "")
            desc_surf = self.sub_font.render(desc, True, LIGHT_GRAY)
            surface.blit(desc_surf, (SCREEN_WIDTH // 2 - desc_surf.get_width() // 2, 490))


class PauseMenu:
    """Overlay pause menu."""

    def __init__(self):
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        self.buttons = {
            "resume": Button(cx, cy - 50, 220, 44, "Resume"),
            "restart": Button(cx, cy + 10, 220, 44, "Restart"),
            "quit": Button(cx, cy + 70, 220, 44, "Quit to Menu"),
        }
        self.font = pygame.font.SysFont(None, 48)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, btn in self.buttons.items():
                if btn.is_clicked(event.pos, True):
                    return name
        return None

    def update(self, mouse_pos):
        for btn in self.buttons.values():
            btn.update(mouse_pos)

    def draw(self, surface):
        # Dim overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        title = self.font.render("PAUSED", True, WHITE)
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2,
                             SCREEN_HEIGHT // 2 - 120))

        for btn in self.buttons.values():
            btn.draw(surface)


class EndScreen:
    """End of match screen."""

    def __init__(self):
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        self.buttons = {
            "replay": Button(cx, cy + 40, 220, 44, "Play Again"),
            "menu": Button(cx, cy + 100, 220, 44, "Main Menu"),
        }
        self.title_font = pygame.font.SysFont(None, 56)
        self.sub_font = pygame.font.SysFont(None, 32)
        self.winner_text = ""
        self.score_text = ""

    def set_result(self, winner, score_p1, score_p2):
        self.winner_text = f"{winner} WINS!" if winner != "Draw" else "DRAW!"
        self.score_text = f"{score_p1} - {score_p2}"

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, btn in self.buttons.items():
                if btn.is_clicked(event.pos, True):
                    return name
        return None

    def update(self, mouse_pos):
        for btn in self.buttons.values():
            btn.update(mouse_pos)

    def draw(self, surface):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        title = self.title_font.render(self.winner_text, True, YELLOW)
        surface.blit(title, (cx - title.get_width() // 2, cy - 100))

        score = self.sub_font.render(self.score_text, True, WHITE)
        surface.blit(score, (cx - score.get_width() // 2, cy - 40))

        for btn in self.buttons.values():
            btn.draw(surface)


class HUD:
    """Heads-up display: scores, timer, boost meters, active power-ups."""

    def __init__(self):
        self.score_font = pygame.font.SysFont(None, 48)
        self.info_font = pygame.font.SysFont(None, 24)
        self.small_font = pygame.font.SysFont(None, 20)
        self.countdown_font = pygame.font.SysFont(None, 80)

    def draw(self, surface, game_state):
        """game_state is a dict with keys: score_p1, score_p2, match_mode, match_param,
        timer, boost_p1, boost_p2, effects_p1, effects_p2, countdown, labels."""
        s = game_state

        # Scores
        p1_score = self.score_font.render(str(s["score_p2"]), True, PLAYER2_COLOR)
        p2_score = self.score_font.render(str(s["score_p1"]), True, PLAYER1_COLOR)

        # P2 (top) score on left side of top
        surface.blit(p1_score, (20, 5))
        # P1 (bottom) score on left side of bottom
        surface.blit(p2_score, (20, SCREEN_HEIGHT - 40))

        # Match info (center top)
        if s["match_mode"] == "first_to":
            info_text = f"First to {s['match_param']}"
        else:
            minutes = int(s["timer"]) // 60
            seconds = int(s["timer"]) % 60
            info_text = f"Time: {minutes}:{seconds:02d}"

        info = self.info_font.render(info_text, True, LIGHT_GRAY)
        surface.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2, 8))

        # Labels
        if s.get("labels"):
            p1_label = self.small_font.render(s["labels"][0], True, PLAYER1_COLOR)
            p2_label = self.small_font.render(s["labels"][1], True, PLAYER2_COLOR)
            surface.blit(p2_label, (60, 12))
            surface.blit(p1_label, (60, SCREEN_HEIGHT - 30))

        # Boost meters
        self._draw_boost_meter(surface, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 30,
                               s["boost_p1"], PLAYER1_COLOR)
        self._draw_boost_meter(surface, SCREEN_WIDTH - 120, 15,
                               s["boost_p2"], PLAYER2_COLOR)

        # Active effects
        self._draw_effects(surface, SCREEN_WIDTH - 30, SCREEN_HEIGHT - 50,
                           s.get("effects_p1", {}), going_up=True)
        self._draw_effects(surface, SCREEN_WIDTH - 30, 40,
                           s.get("effects_p2", {}), going_up=False)

        # Countdown
        if s.get("countdown") and s["countdown"] > 0:
            num = max(1, int(s["countdown"] + 0.99))
            cd_text = self.countdown_font.render(str(num), True, YELLOW)
            surface.blit(cd_text, (SCREEN_WIDTH // 2 - cd_text.get_width() // 2,
                                   SCREEN_HEIGHT // 2 - cd_text.get_height() // 2))

    def _draw_boost_meter(self, surface, x, y, energy, color):
        bar_w = 80
        bar_h = 10
        bg_rect = pygame.Rect(x, y, bar_w, bar_h)
        fill_w = int(bar_w * energy / BOOST_MAX_ENERGY)
        fill_rect = pygame.Rect(x, y, fill_w, bar_h)
        pygame.draw.rect(surface, DARK_GRAY, bg_rect)
        pygame.draw.rect(surface, color, fill_rect)
        pygame.draw.rect(surface, WHITE, bg_rect, 1)
        label = self.small_font.render("BOOST", True, LIGHT_GRAY)
        surface.blit(label, (x - 45, y - 2))

    def _draw_effects(self, surface, x, y, effects, going_up=True):
        """Draw active power-up icons as small colored squares with timer."""
        effect_names = {
            PU_BIGGER: "BIG", PU_SMALLER: "SML", PU_SPEED: "SPD",
            PU_MAGNET: "MAG", PU_FREEZE: "FRZ",
        }
        offset = 0
        for eff, remaining in effects.items():
            color = POWERUP_COLORS.get(eff, WHITE)
            ey = y + (offset * (-20 if going_up else 20))
            pygame.draw.rect(surface, color, (x - 16, ey, 16, 16))
            text = self.small_font.render(
                f"{effect_names.get(eff, '?')} {remaining:.1f}s", True, color)
            surface.blit(text, (x - 16 - text.get_width() - 4, ey))
            offset += 1
