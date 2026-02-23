"""
Air Hockey Game - AI Controller
Handles Easy / Medium / Hard difficulty computer opponents.
"""
import math
import random
from settings import (
    AI_DIFFICULTY,
    RINK_LEFT, RINK_RIGHT, RINK_TOP, RINK_BOTTOM,
    RINK_CENTER_X, CENTER_LINE_Y,
    PADDLE_RADIUS, PUCK_RADIUS,
    GOAL_LEFT_X, GOAL_RIGHT_X,
)


class AIController:
    """Controls a paddle using AI logic. Always controls the 'top' half paddle."""

    def __init__(self, difficulty="medium"):
        self.set_difficulty(difficulty)
        self.target_x = RINK_CENTER_X
        self.target_y = RINK_TOP + (CENTER_LINE_Y - RINK_TOP) * 0.35
        self.reaction_timer = 0.0
        self.cached_target = (self.target_x, self.target_y)
        self._noise_x = 0.0
        self._noise_y = 0.0

    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        cfg = AI_DIFFICULTY.get(difficulty, AI_DIFFICULTY["medium"])
        self.reaction_delay = cfg["reaction_delay"]
        self.max_speed_mult = cfg["max_speed_mult"]
        self.prediction_mode = cfg["prediction"]
        self.overshoot = cfg["overshoot"]
        self.boost_chance = cfg["boost_chance"]

    def update(self, dt, paddle, puck):
        """Returns (ax, ay, boost) - acceleration inputs and whether to boost."""
        self.reaction_timer += dt

        # Only update target on reaction intervals
        if self.reaction_timer >= self.reaction_delay:
            self.reaction_timer = 0.0
            self._noise_x = random.uniform(-self.overshoot, self.overshoot)
            self._noise_y = random.uniform(-self.overshoot, self.overshoot)
            self.cached_target = self._compute_target(paddle, puck)

        tx, ty = self.cached_target
        tx += self._noise_x
        ty += self._noise_y

        # Compute direction to target
        dx = tx - paddle.x
        dy = ty - paddle.y
        dist = math.hypot(dx, dy)

        if dist < 3:
            return 0.0, 0.0, False

        ax = dx / dist
        ay = dy / dist

        # Scale down acceleration based on difficulty
        ax *= self.max_speed_mult
        ay *= self.max_speed_mult

        # Decide on boost
        boost = False
        if puck.active and puck.vy < -50:  # puck heading toward AI
            if dist > 100 and random.random() < self.boost_chance * dt * 10:
                boost = True

        return ax, ay, boost

    def _compute_target(self, paddle, puck):
        """Compute where the AI wants to move based on prediction mode."""
        home_x = RINK_CENTER_X
        home_y = RINK_TOP + (CENTER_LINE_Y - RINK_TOP) * 0.35
        defense_y = RINK_TOP + (CENTER_LINE_Y - RINK_TOP) * 0.25

        if not puck.active:
            return home_x, home_y

        # If puck is moving away from AI (toward bottom), go to defensive position
        if puck.vy > 20:
            # Puck heading away - drift toward home/defense
            target_x = _clamp(puck.x, RINK_LEFT + PADDLE_RADIUS + 10,
                              RINK_RIGHT - PADDLE_RADIUS - 10)
            return target_x, home_y

        # Puck is heading toward AI (vy < 0) or roughly horizontal
        if self.prediction_mode == "none":
            return self._predict_none(puck, defense_y)
        elif self.prediction_mode == "linear":
            return self._predict_linear(puck, paddle, defense_y)
        else:  # "bounce"
            return self._predict_bounce(puck, paddle, defense_y)

    def _predict_none(self, puck, defense_y):
        """Easy: just follow the puck's current x position."""
        target_x = _clamp(puck.x, RINK_LEFT + PADDLE_RADIUS,
                          RINK_RIGHT - PADDLE_RADIUS)
        # Stay at defense line
        return target_x, defense_y

    def _predict_linear(self, puck, paddle, defense_y):
        """Medium: predict where puck crosses the defense line (no wall bounces)."""
        if abs(puck.vy) < 10:
            return puck.x, defense_y

        # Time for puck to reach defense_y
        t = (defense_y - puck.y) / puck.vy if puck.vy != 0 else 999
        if t < 0:
            t = 0

        predicted_x = puck.x + puck.vx * t
        predicted_x = _clamp(predicted_x, RINK_LEFT + PADDLE_RADIUS,
                             RINK_RIGHT - PADDLE_RADIUS)

        # If puck is close, move aggressively toward it
        dist_to_puck = math.hypot(puck.x - paddle.x, puck.y - paddle.y)
        if dist_to_puck < 150 and puck.y < CENTER_LINE_Y:
            return puck.x, puck.y

        return predicted_x, defense_y

    def _predict_bounce(self, puck, paddle, defense_y):
        """Hard: simulate puck path with wall reflections."""
        if abs(puck.vy) < 10 and abs(puck.vx) < 10:
            return puck.x, defense_y

        # Simulate puck trajectory
        sim_x = puck.x
        sim_y = puck.y
        sim_vx = puck.vx
        sim_vy = puck.vy
        sim_dt = 1.0 / 60.0
        max_steps = 180  # simulate up to 3 seconds

        for _ in range(max_steps):
            sim_x += sim_vx * sim_dt
            sim_y += sim_vy * sim_dt

            # Wall bounces (left/right)
            if sim_x - PUCK_RADIUS < RINK_LEFT:
                sim_x = RINK_LEFT + PUCK_RADIUS
                sim_vx = abs(sim_vx)
            elif sim_x + PUCK_RADIUS > RINK_RIGHT:
                sim_x = RINK_RIGHT - PUCK_RADIUS
                sim_vx = -abs(sim_vx)

            # Top wall bounce
            if sim_y - PUCK_RADIUS < RINK_TOP:
                # Check if it's a goal
                if GOAL_LEFT_X < sim_x < GOAL_RIGHT_X:
                    break  # puck would score
                sim_y = RINK_TOP + PUCK_RADIUS
                sim_vy = abs(sim_vy)

            # Bottom wall bounce
            if sim_y + PUCK_RADIUS > RINK_BOTTOM:
                if GOAL_LEFT_X < sim_x < GOAL_RIGHT_X:
                    break
                sim_y = RINK_BOTTOM - PUCK_RADIUS
                sim_vy = -abs(sim_vy)

            # Check if simulation reached AI's defense zone
            if sim_y <= defense_y + 20:
                predicted_x = _clamp(sim_x, RINK_LEFT + PADDLE_RADIUS,
                                     RINK_RIGHT - PADDLE_RADIUS)
                # Aggressive: if puck is in AI half and close, go to it directly
                dist_to_puck = math.hypot(puck.x - paddle.x, puck.y - paddle.y)
                if dist_to_puck < 120 and puck.y < CENTER_LINE_Y:
                    return puck.x, puck.y
                return predicted_x, defense_y

        # Fallback: just go toward puck x
        return _clamp(sim_x, RINK_LEFT + PADDLE_RADIUS,
                      RINK_RIGHT - PADDLE_RADIUS), defense_y


def _clamp(val, mn, mx):
    return max(mn, min(mx, val))
