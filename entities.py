"""
Air Hockey Game - Entity classes: Paddle, Puck, PowerUp, Particle
"""
import math
import random
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    RINK_LEFT, RINK_RIGHT, RINK_TOP, RINK_BOTTOM,
    RINK_CENTER_X, RINK_CENTER_Y, CENTER_LINE_Y,
    GOAL_LEFT_X, GOAL_RIGHT_X,
    PADDLE_RADIUS, PADDLE_MAX_SPEED, PADDLE_ACCELERATION, PADDLE_FRICTION, PADDLE_MASS,
    BOOST_MULTIPLIER, BOOST_MAX_ENERGY, BOOST_DRAIN_RATE, BOOST_REGEN_RATE,
    PUCK_RADIUS, PUCK_MAX_SPEED, PUCK_FRICTION, PUCK_MASS,
    PUCK_WALL_RESTITUTION, PUCK_PADDLE_RESTITUTION,
    RALLY_SPEED_INCREMENT, RALLY_MAX_EXTRA_SPEED, SPIN_FACTOR,
    TRAIL_MIN_SPEED, TRAIL_LENGTH, TRAIL_ALPHA_START,
    POWERUP_RADIUS, POWERUP_DURATION, POWERUP_FREEZE_DURATION,
    POWERUP_BIGGER_SCALE, POWERUP_SMALLER_SCALE, POWERUP_SPEED_BOOST_MULT,
    POWERUP_MAGNET_RANGE, POWERUP_MAGNET_STRENGTH,
    PU_BIGGER, PU_SMALLER, PU_SPEED, PU_MAGNET, PU_FREEZE,
    POWERUP_COLORS,
    PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX, PARTICLE_LIFETIME, PARTICLE_SIZE,
    PUCK_COLOR, WHITE,
    GOAL_DEPTH,
)


class Paddle:
    """Player or AI controlled paddle (mallet)."""

    def __init__(self, x, y, color, half="top"):
        self.start_x = x
        self.start_y = y
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.color = color
        self.half = half  # "top" = upper half, "bottom" = lower half
        self.base_radius = PADDLE_RADIUS
        self.radius = PADDLE_RADIUS
        self.mass = PADDLE_MASS

        # Boost / energy
        self.boost_energy = BOOST_MAX_ENERGY
        self.boosting = False

        # Active effects
        self.effects = {}  # {effect_name: remaining_time}
        self.frozen = False
        self.freeze_timer = 0.0

        # Arena modifiers (set by Game)
        self.speed_mult = 1.0
        self.friction_mult = PADDLE_FRICTION

    def reset(self):
        self.x = float(self.start_x)
        self.y = float(self.start_y)
        self.vx = 0.0
        self.vy = 0.0
        self.boost_energy = BOOST_MAX_ENERGY
        self.boosting = False
        self.effects.clear()
        self.frozen = False
        self.freeze_timer = 0.0
        self.radius = self.base_radius

    def apply_effect(self, effect_type, duration=POWERUP_DURATION):
        if effect_type == PU_FREEZE:
            self.frozen = True
            self.freeze_timer = POWERUP_FREEZE_DURATION
        else:
            self.effects[effect_type] = duration

    def update(self, dt, ax=0.0, ay=0.0):
        # Update effect timers
        expired = []
        for eff, t in self.effects.items():
            self.effects[eff] = t - dt
            if self.effects[eff] <= 0:
                expired.append(eff)
        for eff in expired:
            del self.effects[eff]

        # Update freeze
        if self.frozen:
            self.freeze_timer -= dt
            if self.freeze_timer <= 0:
                self.frozen = False
            self.vx *= 0.8
            self.vy *= 0.8
            self._clamp_position()
            return

        # Compute effective parameters from effects
        self.radius = self.base_radius
        speed_mult = self.speed_mult
        if PU_BIGGER in self.effects:
            self.radius = int(self.base_radius * POWERUP_BIGGER_SCALE)
        if PU_SMALLER in self.effects:
            self.radius = int(self.base_radius * POWERUP_SMALLER_SCALE)
        if PU_SPEED in self.effects:
            speed_mult *= POWERUP_SPEED_BOOST_MULT

        max_speed = PADDLE_MAX_SPEED * speed_mult
        accel = PADDLE_ACCELERATION

        # Boost
        if self.boosting and self.boost_energy > 0:
            max_speed *= BOOST_MULTIPLIER
            accel *= BOOST_MULTIPLIER
            self.boost_energy = max(0, self.boost_energy - BOOST_DRAIN_RATE * dt)
        else:
            self.boosting = False
            self.boost_energy = min(BOOST_MAX_ENERGY,
                                    self.boost_energy + BOOST_REGEN_RATE * dt)

        # Apply acceleration
        self.vx += ax * accel * dt
        self.vy += ay * accel * dt

        # Friction / drag
        self.vx *= self.friction_mult
        self.vy *= self.friction_mult

        # Clamp speed
        speed = math.hypot(self.vx, self.vy)
        if speed > max_speed:
            scale = max_speed / speed
            self.vx *= scale
            self.vy *= scale

        # Move
        self.x += self.vx * dt
        self.y += self.vy * dt

        self._clamp_position()

    def _clamp_position(self):
        """Keep paddle inside its half of the rink."""
        r = self.radius
        # Left / right walls
        self.x = max(RINK_LEFT + r, min(RINK_RIGHT - r, self.x))

        # Half constraint + top/bottom walls
        if self.half == "top":
            self.y = max(RINK_TOP + r, min(CENTER_LINE_Y - r, self.y))
        else:
            self.y = max(CENTER_LINE_Y + r, min(RINK_BOTTOM - r, self.y))

    def draw(self, surface):
        # Outer ring
        color = self.color
        if self.frozen:
            color = (150, 200, 255)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius)
        # Inner circle
        inner_r = max(4, self.radius - 8)
        darker = tuple(max(0, c - 60) for c in color)
        pygame.draw.circle(surface, darker, (int(self.x), int(self.y)), inner_r)
        # Highlight
        highlight_r = max(2, self.radius // 3)
        highlight_pos = (int(self.x - self.radius * 0.2), int(self.y - self.radius * 0.2))
        highlight_color = tuple(min(255, c + 80) for c in color)
        pygame.draw.circle(surface, highlight_color, highlight_pos, highlight_r)


class Puck:
    """The puck with trail, physics, and collision handling."""

    def __init__(self):
        self.x = float(RINK_CENTER_X)
        self.y = float(RINK_CENTER_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.radius = PUCK_RADIUS
        self.mass = PUCK_MASS
        self.rally_extra_speed = 0.0
        self.trail = []  # list of (x, y) positions
        self.active = False  # False during reset/countdown

        # Arena modifiers
        self.friction = PUCK_FRICTION
        self.speed_mult = 1.0

    def reset(self, direction=1):
        """Reset puck to center. direction: 1 = launched toward bottom, -1 = toward top."""
        self.x = float(RINK_CENTER_X)
        self.y = float(RINK_CENTER_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.rally_extra_speed = 0.0
        self.trail.clear()
        self.active = False

    def launch(self, direction=1):
        """Give puck an initial nudge after countdown."""
        self.active = True

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def update(self, dt):
        if not self.active:
            return

        # Friction
        self.vx *= self.friction
        self.vy *= self.friction

        # Clamp speed
        max_spd = (PUCK_MAX_SPEED + self.rally_extra_speed) * self.speed_mult
        spd = self.speed
        if spd > max_spd:
            scale = max_spd / spd
            self.vx *= scale
            self.vy *= scale

        # Move
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Trail
        if self.speed >= TRAIL_MIN_SPEED:
            self.trail.append((self.x, self.y))
            if len(self.trail) > TRAIL_LENGTH:
                self.trail.pop(0)
        elif self.trail:
            self.trail.pop(0)

    def collide_walls(self):
        """Bounce off rink walls. Returns 'goal_top', 'goal_bottom', or None."""
        r = self.radius

        # Left wall
        if self.x - r < RINK_LEFT:
            self.x = RINK_LEFT + r
            self.vx = abs(self.vx) * PUCK_WALL_RESTITUTION
            return "wall"

        # Right wall
        if self.x + r > RINK_RIGHT:
            self.x = RINK_RIGHT - r
            self.vx = -abs(self.vx) * PUCK_WALL_RESTITUTION
            return "wall"

        # Top wall - check for goal
        if self.y - r < RINK_TOP:
            if GOAL_LEFT_X < self.x < GOAL_RIGHT_X:
                # Goal for bottom player (player 2 / AI scores? No - top goal = P1's goal)
                # Top goal = puck entered top goal = point for player on bottom half
                return "goal_top"
            else:
                self.y = RINK_TOP + r
                self.vy = abs(self.vy) * PUCK_WALL_RESTITUTION
                return "wall"

        # Bottom wall - check for goal
        if self.y + r > RINK_BOTTOM:
            if GOAL_LEFT_X < self.x < GOAL_RIGHT_X:
                return "goal_bottom"
            else:
                self.y = RINK_BOTTOM - r
                self.vy = -abs(self.vy) * PUCK_WALL_RESTITUTION
                return "wall"

        return None

    def collide_paddle(self, paddle):
        """Circle-circle collision with paddle. Returns True if collision occurred."""
        dx = self.x - paddle.x
        dy = self.y - paddle.y
        dist = math.hypot(dx, dy)
        min_dist = self.radius + paddle.radius

        if dist >= min_dist or dist == 0:
            return False

        # Normal vector from paddle to puck
        nx = dx / dist
        ny = dy / dist

        # Separate overlapping objects
        overlap = min_dist - dist
        self.x += nx * overlap
        self.y += ny * overlap

        # Relative velocity
        rel_vx = self.vx - paddle.vx
        rel_vy = self.vy - paddle.vy

        # Relative velocity along normal
        rel_v_normal = rel_vx * nx + rel_vy * ny

        # Don't resolve if objects are separating
        if rel_v_normal > 0:
            return False

        # Impulse (elastic collision with restitution)
        e = PUCK_PADDLE_RESTITUTION
        j = -(1 + e) * rel_v_normal
        j /= (1 / self.mass) + (1 / paddle.mass)

        # Apply impulse to puck
        self.vx += (j / self.mass) * nx
        self.vy += (j / self.mass) * ny

        # Spin / english effect: tangential component of paddle velocity
        tx = -ny  # tangent vector
        ty = nx
        paddle_tangent_speed = paddle.vx * tx + paddle.vy * ty
        self.vx += tx * paddle_tangent_speed * SPIN_FACTOR
        self.vy += ty * paddle_tangent_speed * SPIN_FACTOR

        # Rally speed-up
        self.rally_extra_speed = min(
            self.rally_extra_speed + RALLY_SPEED_INCREMENT,
            RALLY_MAX_EXTRA_SPEED
        )

        return True

    def draw(self, surface):
        # Draw trail
        if self.trail:
            for i, (tx, ty) in enumerate(self.trail):
                alpha = int(TRAIL_ALPHA_START * (i + 1) / len(self.trail))
                r = max(2, int(self.radius * (i + 1) / len(self.trail)))
                trail_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(trail_surf, (*PUCK_COLOR[:3], alpha), (r, r), r)
                surface.blit(trail_surf, (int(tx) - r, int(ty) - r))

        # Draw puck
        pygame.draw.circle(surface, PUCK_COLOR, (int(self.x), int(self.y)), self.radius)
        # Inner dot
        pygame.draw.circle(surface, (200, 200, 200), (int(self.x), int(self.y)),
                           max(2, self.radius // 3))


class PowerUp:
    """A collectible power-up that spawns on the table."""

    def __init__(self, pu_type, x, y):
        self.type = pu_type
        self.x = x
        self.y = y
        self.radius = POWERUP_RADIUS
        self.color = POWERUP_COLORS.get(pu_type, WHITE)
        self.alive = True
        self.bob_timer = 0.0  # for visual bobbing

    def update(self, dt):
        self.bob_timer += dt

    def collides_with(self, paddle):
        """Check if paddle picks up this power-up."""
        dist = math.hypot(self.x - paddle.x, self.y - paddle.y)
        return dist < self.radius + paddle.radius

    def draw(self, surface):
        # Pulsing effect
        pulse = 1.0 + 0.15 * math.sin(self.bob_timer * 5)
        r = int(self.radius * pulse)
        # Glow
        glow_surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*self.color[:3], 40), (r * 2, r * 2), r * 2)
        surface.blit(glow_surf, (int(self.x) - r * 2, int(self.y) - r * 2))
        # Main circle
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), r)
        # Icon letter
        font = pygame.font.SysFont(None, 20)
        labels = {PU_BIGGER: "B", PU_SMALLER: "S", PU_SPEED: "F",
                  PU_MAGNET: "M", PU_FREEZE: "X"}
        label = labels.get(self.type, "?")
        text = font.render(label, True, (0, 0, 0))
        surface.blit(text, (int(self.x) - text.get_width() // 2,
                            int(self.y) - text.get_height() // 2))


class Particle:
    """A single particle for visual effects."""

    def __init__(self, x, y, color=None, speed_range=None):
        self.x = x
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        spd = random.uniform(
            speed_range[0] if speed_range else PARTICLE_SPEED_MIN,
            speed_range[1] if speed_range else PARTICLE_SPEED_MAX,
        )
        self.vx = math.cos(angle) * spd
        self.vy = math.sin(angle) * spd
        self.color = color or (
            random.randint(200, 255),
            random.randint(150, 255),
            random.randint(50, 150),
        )
        self.lifetime = PARTICLE_LIFETIME
        self.max_lifetime = PARTICLE_LIFETIME
        self.size = PARTICLE_SIZE

    @property
    def alive(self):
        return self.lifetime > 0

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.95
        self.vy *= 0.95
        self.lifetime -= dt

    def draw(self, surface):
        alpha = max(0, self.lifetime / self.max_lifetime)
        size = max(1, int(self.size * alpha))
        color = tuple(int(c * alpha) for c in self.color)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), size)


class ParticleSystem:
    """Manages a list of particles."""

    def __init__(self):
        self.particles = []

    def emit(self, x, y, count, color=None, speed_range=None):
        for _ in range(count):
            self.particles.append(Particle(x, y, color, speed_range))

    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)
