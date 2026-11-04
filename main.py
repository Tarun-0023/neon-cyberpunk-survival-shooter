"""
Neon Cyberpunk Survival Shooter
A complete 2D survival shooter game with pygame-ce
"""

import pygame
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

# Colors (Neon Cyberpunk Palette)
BLACK = (0, 0, 0)
DARK_BG = (10, 5, 20)
GRID_COLOR = (30, 15, 50)
NEON_PINK = (255, 0, 128)
NEON_CYAN = (0, 255, 255)
NEON_PURPLE = (180, 0, 255)
NEON_GREEN = (0, 255, 100)
NEON_ORANGE = (255, 100, 0)
NEON_YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
RED = (255, 50, 50)

class GameState(Enum):
    MENU = 1
    PLAYING = 2
    PAUSED = 3
    LEVEL_UP = 4
    GAME_OVER = 5


@dataclass
class Upgrade:
    name: str
    description: str
    effect: str
    color: Tuple[int, int, int]


class Particle:
    """Visual particle effects"""
    def __init__(self, x, y, color, velocity, lifetime=1.0, size=3):
        self.x = x
        self.y = y
        self.color = color
        self.vx, self.vy = velocity
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.size = size
        self.alpha = 255

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= dt
        self.alpha = int(255 * (self.lifetime / self.max_lifetime))
        # Slow down
        self.vx *= 0.95
        self.vy *= 0.95

    def is_dead(self):
        return self.lifetime <= 0

    def draw(self, screen):
        if self.alpha > 0:
            color_with_alpha = (*self.color[:3], max(0, min(255, self.alpha)))
            surf = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color_with_alpha, (self.size, self.size), self.size)
            screen.blit(surf, (int(self.x - self.size), int(self.y - self.size)))


class DamageNumber:
    """Floating damage numbers"""
    def __init__(self, x, y, damage, color):
        self.x = x
        self.y = y
        self.damage = damage
        self.color = color
        self.lifetime = 1.0
        self.vy = -50

    def update(self, dt):
        self.y += self.vy * dt
        self.lifetime -= dt
        self.vy += 20 * dt  # Gravity

    def is_dead(self):
        return self.lifetime <= 0

    def draw(self, screen, font):
        alpha = int(255 * self.lifetime)
        text = font.render(str(int(self.damage)), True, self.color)
        text.set_alpha(alpha)
        screen.blit(text, (int(self.x), int(self.y)))


class XPOrb:
    """Experience orbs dropped by enemies"""
    def __init__(self, x, y, value=1):
        self.x = x
        self.y = y
        self.value = value
        self.radius = 6
        self.collection_radius = 150
        self.attracted = False
        self.speed = 300

    def update(self, dt, player_x, player_y):
        dx = player_x - self.x
        dy = player_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Attract to player when close
        if distance < self.collection_radius:
            self.attracted = True

        if self.attracted and distance > 1:
            # Move towards player
            dx /= distance
            dy /= distance
            self.x += dx * self.speed * dt
            self.y += dy * self.speed * dt

        return distance < 20  # Collected

    def draw(self, screen):
        # Glow effect
        for i in range(3):
            glow_radius = self.radius + (3 - i) * 2
            alpha = 80 // (i + 1)
            surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*NEON_CYAN[:3], alpha), (glow_radius, glow_radius), glow_radius)
            screen.blit(surf, (int(self.x - glow_radius), int(self.y - glow_radius)))

        pygame.draw.circle(screen, NEON_CYAN, (int(self.x), int(self.y)), self.radius)


class Projectile:
    """Player projectile"""
    def __init__(self, x, y, angle, damage, speed=500, pierce=0):
        self.x = x
        self.y = y
        self.angle = angle
        self.damage = damage
        self.speed = speed
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = 4
        self.lifetime = 3.0
        self.pierce = pierce
        self.hit_enemies = set()

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= dt

    def is_dead(self):
        return self.lifetime <= 0 or self.pierce < 0

    def can_hit(self, enemy_id):
        if enemy_id in self.hit_enemies:
            return False
        self.hit_enemies.add(enemy_id)
        self.pierce -= 1
        return True

    def draw(self, screen):
        # Draw glowing projectile with trail
        surf = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*NEON_PINK[:3], 150), (self.radius * 2, self.radius * 2), self.radius * 2)
        pygame.draw.circle(surf, NEON_PINK, (self.radius * 2, self.radius * 2), self.radius)
        screen.blit(surf, (int(self.x - self.radius * 2), int(self.y - self.radius * 2)))


class Enemy:
    """Base enemy class"""
    def __init__(self, x, y, enemy_type="basic"):
        self.x = x
        self.y = y
        self.type = enemy_type
        self.id = id(self)

        # Type-specific stats
        if enemy_type == "basic":
            self.max_hp = 3
            self.speed = 80
            self.damage = 10
            self.color = NEON_GREEN
            self.radius = 15
            self.xp_value = 1
        elif enemy_type == "fast":
            self.max_hp = 2
            self.speed = 150
            self.damage = 5
            self.color = NEON_YELLOW
            self.radius = 12
            self.xp_value = 2
        elif enemy_type == "tank":
            self.max_hp = 10
            self.speed = 50
            self.damage = 20
            self.color = NEON_PURPLE
            self.radius = 25
            self.xp_value = 5
        elif enemy_type == "elite":
            self.max_hp = 20
            self.speed = 100
            self.damage = 15
            self.color = NEON_ORANGE
            self.radius = 20
            self.xp_value = 10

        self.hp = self.max_hp
        self.flash_timer = 0

    def take_damage(self, damage):
        self.hp -= damage
        self.flash_timer = 0.1
        return self.hp <= 0

    def update(self, dt, player_x, player_y):
        self.flash_timer = max(0, self.flash_timer - dt)

        # Move towards player
        dx = player_x - self.x
        dy = player_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            dx /= distance
            dy /= distance
            self.x += dx * self.speed * dt
            self.y += dy * self.speed * dt

    def draw(self, screen):
        # Glow effect
        for i in range(2):
            glow_radius = self.radius + (2 - i) * 3
            alpha = 50 // (i + 1)
            surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*self.color[:3], alpha), (glow_radius, glow_radius), glow_radius)
            screen.blit(surf, (int(self.x - glow_radius), int(self.y - glow_radius)))

        # Flash white when hit
        color = WHITE if self.flash_timer > 0 else self.color
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)

        # HP bar
        if self.hp < self.max_hp:
            bar_width = self.radius * 2
            bar_height = 4
            bar_x = self.x - bar_width // 2
            bar_y = self.y - self.radius - 10

            # Background
            pygame.draw.rect(screen, (50, 50, 50), (int(bar_x), int(bar_y), bar_width, bar_height))
            # HP
            hp_width = int((self.hp / self.max_hp) * bar_width)
            pygame.draw.rect(screen, RED, (int(bar_x), int(bar_y), hp_width, bar_height))


class Player:
    """Player character"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 12
        self.max_hp = 100
        self.hp = self.max_hp
        self.speed = 200
        self.damage = 10
        self.fire_rate = 3  # Shots per second
        self.fire_cooldown = 0
        self.projectile_count = 1
        self.pierce = 0

        # Dash ability
        self.dash_speed = 600
        self.dash_duration = 0.2
        self.dash_cooldown_max = 2.0
        self.dash_timer = 0
        self.dash_cooldown = 0
        self.dashing = False

        # Invulnerability frames
        self.invuln_timer = 0
        self.invuln_duration = 1.0

        # XP and leveling
        self.xp = 0
        self.level = 1
        self.xp_to_next_level = 10

    def take_damage(self, damage):
        if self.invuln_timer <= 0:
            self.hp -= damage
            self.invuln_timer = self.invuln_duration
            return True
        return False

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def add_xp(self, amount):
        self.xp += amount
        if self.xp >= self.xp_to_next_level:
            self.xp -= self.xp_to_next_level
            self.level += 1
            self.xp_to_next_level = int(self.xp_to_next_level * 1.5)
            return True  # Level up
        return False

    def update(self, dt):
        self.fire_cooldown = max(0, self.fire_cooldown - dt)
        self.invuln_timer = max(0, self.invuln_timer - dt)
        self.dash_cooldown = max(0, self.dash_cooldown - dt)

        if self.dashing:
            self.dash_timer -= dt
            if self.dash_timer <= 0:
                self.dashing = False

    def move(self, dx, dy, dt):
        if dx != 0 or dy != 0:
            length = math.sqrt(dx * dx + dy * dy)
            dx /= length
            dy /= length

            speed = self.dash_speed if self.dashing else self.speed
            self.x += dx * speed * dt
            self.y += dy * speed * dt

            # Keep in bounds
            self.x = max(self.radius, min(WINDOW_WIDTH - self.radius, self.x))
            self.y = max(self.radius, min(WINDOW_HEIGHT - self.radius, self.y))

    def dash(self):
        if self.dash_cooldown <= 0 and not self.dashing:
            self.dashing = True
            self.dash_timer = self.dash_duration
            self.dash_cooldown = self.dash_cooldown_max
            return True
        return False

    def can_shoot(self):
        return self.fire_cooldown <= 0

    def shoot(self, target_x, target_y):
        if not self.can_shoot():
            return []

        self.fire_cooldown = 1.0 / self.fire_rate
        projectiles = []

        # Calculate base angle to mouse
        dx = target_x - self.x
        dy = target_y - self.y
        base_angle = math.atan2(dy, dx)

        # Spread projectiles
        if self.projectile_count == 1:
            angles = [base_angle]
        else:
            spread = math.pi / 6  # 30 degree spread
            angles = []
            for i in range(self.projectile_count):
                offset = spread * (i - (self.projectile_count - 1) / 2) / max(1, (self.projectile_count - 1))
                angles.append(base_angle + offset)

        for angle in angles:
            projectiles.append(Projectile(self.x, self.y, angle, self.damage, pierce=self.pierce))

        return projectiles

    def draw(self, screen):
        # Dash trail effect
        if self.dashing:
            for i in range(3):
                alpha = 100 - i * 30
                surf = pygame.Surface((self.radius * 2 + i * 4, self.radius * 2 + i * 4), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*NEON_CYAN[:3], alpha),
                                 (self.radius + i * 2, self.radius + i * 2), self.radius + i * 2)
                screen.blit(surf, (int(self.x - self.radius - i * 2), int(self.y - self.radius - i * 2)))

        # Invulnerability flicker
        if self.invuln_timer > 0 and int(self.invuln_timer * 20) % 2 == 0:
            return

        # Glow effect
        for i in range(2):
            glow_radius = self.radius + (2 - i) * 4
            alpha = 80 // (i + 1)
            surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*NEON_CYAN[:3], alpha), (glow_radius, glow_radius), glow_radius)
            screen.blit(surf, (int(self.x - glow_radius), int(self.y - glow_radius)))

        pygame.draw.circle(screen, NEON_CYAN, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.radius - 4)


class Game:
    """Main game class"""
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Neon Survival Shooter")
        self.clock = pygame.time.Clock()
        self.running = True

        # Fonts
        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_large = pygame.font.Font(None, 72)

        # Game state
        self.state = GameState.MENU
        self.reset_game()

        # Screen shake
        self.shake_amount = 0

    def reset_game(self):
        """Reset game to initial state"""
        self.player = Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.xp_orbs = []
        self.damage_numbers = []

        self.score = 0
        self.enemies_defeated = 0
        self.survival_time = 0
        self.enemy_spawn_timer = 0
        self.enemy_spawn_rate = 1.0
        self.difficulty_multiplier = 1.0

        self.upgrade_choices = []

    def spawn_enemy(self):
        """Spawn an enemy at a random position outside the screen"""
        side = random.randint(0, 3)

        if side == 0:  # Top
            x = random.randint(0, WINDOW_WIDTH)
            y = -50
        elif side == 1:  # Bottom
            x = random.randint(0, WINDOW_WIDTH)
            y = WINDOW_HEIGHT + 50
        elif side == 2:  # Left
            x = -50
            y = random.randint(0, WINDOW_HEIGHT)
        else:  # Right
            x = WINDOW_WIDTH + 50
            y = random.randint(0, WINDOW_HEIGHT)

        # Choose enemy type based on time
        rand = random.random()
        if self.survival_time < 30:
            enemy_type = "basic"
        elif self.survival_time < 60:
            enemy_type = "fast" if rand < 0.3 else "basic"
        elif self.survival_time < 120:
            if rand < 0.2:
                enemy_type = "tank"
            elif rand < 0.5:
                enemy_type = "fast"
            else:
                enemy_type = "basic"
        else:
            if rand < 0.1:
                enemy_type = "elite"
            elif rand < 0.3:
                enemy_type = "tank"
            elif rand < 0.6:
                enemy_type = "fast"
            else:
                enemy_type = "basic"

        self.enemies.append(Enemy(x, y, enemy_type))

    def create_particles(self, x, y, color, count=10):
        """Create particle burst"""
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(50, 200)
            velocity = (math.cos(angle) * speed, math.sin(angle) * speed)
            self.particles.append(Particle(x, y, color, velocity, random.uniform(0.3, 0.8)))

    def screen_shake(self, amount):
        """Trigger screen shake"""
        self.shake_amount = max(self.shake_amount, amount)

    def generate_upgrades(self):
        """Generate 3 random upgrade choices"""
        all_upgrades = [
            Upgrade("Fire Rate", "Shoot faster", "fire_rate", NEON_PINK),
            Upgrade("Movement Speed", "Move faster", "speed", NEON_CYAN),
            Upgrade("Damage", "Deal more damage", "damage", NEON_ORANGE),
            Upgrade("Max Health", "Increase max HP by 20", "max_hp", NEON_GREEN),
            Upgrade("Heal", "Restore 50 HP", "heal", NEON_GREEN),
            Upgrade("Multi-Shot", "Fire additional projectile", "projectile", NEON_PURPLE),
            Upgrade("Pierce", "Projectiles pierce enemies", "pierce", NEON_YELLOW),
            Upgrade("Dash Cooldown", "Dash more often", "dash", NEON_CYAN),
        ]

        self.upgrade_choices = random.sample(all_upgrades, min(3, len(all_upgrades)))

    def apply_upgrade(self, upgrade):
        """Apply selected upgrade to player"""
        if upgrade.effect == "fire_rate":
            self.player.fire_rate += 0.5
        elif upgrade.effect == "speed":
            self.player.speed += 30
        elif upgrade.effect == "damage":
            self.player.damage += 5
        elif upgrade.effect == "max_hp":
            self.player.max_hp += 20
            self.player.hp += 20
        elif upgrade.effect == "heal":
            self.player.heal(50)
        elif upgrade.effect == "projectile":
            self.player.projectile_count += 1
        elif upgrade.effect == "pierce":
            self.player.pierce += 1
        elif upgrade.effect == "dash":
            self.player.dash_cooldown_max = max(0.5, self.player.dash_cooldown_max - 0.3)

    def handle_events(self):
        """Handle input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == GameState.PLAYING:
                        self.state = GameState.PAUSED
                    elif self.state == GameState.PAUSED:
                        self.state = GameState.PLAYING
                    elif self.state in [GameState.MENU, GameState.GAME_OVER]:
                        self.running = False

                if event.key == pygame.K_SPACE:
                    if self.state == GameState.PLAYING:
                        self.player.dash()

                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.state == GameState.MENU:
                        self.reset_game()
                        self.state = GameState.PLAYING
                    elif self.state == GameState.GAME_OVER:
                        self.reset_game()
                        self.state = GameState.MENU

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.state == GameState.LEVEL_UP:
                        # Check if clicked on an upgrade
                        mouse_x, mouse_y = event.pos
                        for i, upgrade in enumerate(self.upgrade_choices):
                            button_x = WINDOW_WIDTH // 2 - 150
                            button_y = 250 + i * 120
                            button_rect = pygame.Rect(button_x, button_y, 300, 100)
                            if button_rect.collidepoint(mouse_x, mouse_y):
                                self.apply_upgrade(upgrade)
                                self.state = GameState.PLAYING
                                break

    def update(self, dt):
        """Update game logic"""
        if self.state != GameState.PLAYING:
            return

        self.survival_time += dt
        self.difficulty_multiplier = 1 + self.survival_time / 60  # Increase every minute

        # Update player
        self.player.update(dt)

        # Player movement (WASD)
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_s]:
            dy += 1
        self.player.move(dx, dy, dt)

        # Player shooting (mouse)
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:  # Left click held
            mouse_x, mouse_y = pygame.mouse.get_pos()
            new_projectiles = self.player.shoot(mouse_x, mouse_y)
            for proj in new_projectiles:
                self.projectiles.append(proj)
                self.create_particles(self.player.x, self.player.y, NEON_PINK, 3)

        # Spawn enemies
        self.enemy_spawn_timer += dt
        spawn_interval = self.enemy_spawn_rate / self.difficulty_multiplier
        if self.enemy_spawn_timer >= spawn_interval:
            self.enemy_spawn_timer = 0
            self.spawn_enemy()

        # Update projectiles
        for proj in self.projectiles[:]:
            proj.update(dt)
            if proj.is_dead() or proj.x < -50 or proj.x > WINDOW_WIDTH + 50 or proj.y < -50 or proj.y > WINDOW_HEIGHT + 50:
                self.projectiles.remove(proj)

        # Update enemies
        for enemy in self.enemies[:]:
            enemy.update(dt, self.player.x, self.player.y)

            # Check collision with player
            dx = self.player.x - enemy.x
            dy = self.player.y - enemy.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < self.player.radius + enemy.radius:
                if self.player.take_damage(enemy.damage):
                    self.screen_shake(5)
                    self.create_particles(self.player.x, self.player.y, RED, 15)

        # Check projectile-enemy collisions
        for proj in self.projectiles[:]:
            for enemy in self.enemies[:]:
                dx = proj.x - enemy.x
                dy = proj.y - enemy.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < proj.radius + enemy.radius:
                    if proj.can_hit(enemy.id):
                        if enemy.take_damage(proj.damage):
                            # Enemy killed
                            self.enemies.remove(enemy)
                            self.enemies_defeated += 1
                            self.score += enemy.xp_value * 10
                            self.create_particles(enemy.x, enemy.y, enemy.color, 20)
                            self.screen_shake(3)

                            # Drop XP orb
                            for _ in range(enemy.xp_value):
                                offset_x = random.uniform(-10, 10)
                                offset_y = random.uniform(-10, 10)
                                self.xp_orbs.append(XPOrb(enemy.x + offset_x, enemy.y + offset_y))
                        else:
                            # Enemy hit
                            self.create_particles(enemy.x, enemy.y, WHITE, 5)

                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y - 20, proj.damage, NEON_ORANGE))

        # Update XP orbs
        for orb in self.xp_orbs[:]:
            if orb.update(dt, self.player.x, self.player.y):
                self.xp_orbs.remove(orb)
                if self.player.add_xp(orb.value):
                    # Level up!
                    self.generate_upgrades()
                    self.state = GameState.LEVEL_UP
                    self.create_particles(self.player.x, self.player.y, NEON_YELLOW, 30)

        # Update particles
        for particle in self.particles[:]:
            particle.update(dt)
            if particle.is_dead():
                self.particles.remove(particle)

        # Update damage numbers
        for num in self.damage_numbers[:]:
            num.update(dt)
            if num.is_dead():
                self.damage_numbers.remove(num)

        # Check game over
        if self.player.hp <= 0:
            self.state = GameState.GAME_OVER

        # Update screen shake
        self.shake_amount *= 0.9
        if self.shake_amount < 0.1:
            self.shake_amount = 0

    def draw_grid(self):
        """Draw animated grid background"""
        grid_size = 40
        offset_x = int(self.survival_time * 20) % grid_size
        offset_y = int(self.survival_time * 20) % grid_size

        for x in range(-grid_size, WINDOW_WIDTH + grid_size, grid_size):
            pygame.draw.line(self.screen, GRID_COLOR, (x - offset_x, 0), (x - offset_x, WINDOW_HEIGHT))
        for y in range(-grid_size, WINDOW_HEIGHT + grid_size, grid_size):
            pygame.draw.line(self.screen, GRID_COLOR, (0, y - offset_y), (WINDOW_WIDTH, y - offset_y))

    def draw_hud(self):
        """Draw HUD elements"""
        padding = 10

        # Health bar
        bar_width = 200
        bar_height = 25
        bar_x = padding
        bar_y = padding

        pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        hp_width = int((self.player.hp / self.player.max_hp) * bar_width)
        pygame.draw.rect(self.screen, NEON_GREEN, (bar_x, bar_y, hp_width, bar_height))
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)

        hp_text = self.font_small.render(f"HP: {int(self.player.hp)}/{self.player.max_hp}", True, WHITE)
        self.screen.blit(hp_text, (bar_x + 5, bar_y + 3))

        # XP bar
        bar_y += bar_height + 5
        pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        xp_width = int((self.player.xp / self.player.xp_to_next_level) * bar_width)
        pygame.draw.rect(self.screen, NEON_CYAN, (bar_x, bar_y, xp_width, bar_height))
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)

        xp_text = self.font_small.render(f"Level {self.player.level}", True, WHITE)
        self.screen.blit(xp_text, (bar_x + 5, bar_y + 3))

        # Dash cooldown indicator
        dash_y = bar_y + bar_height + 10
        dash_size = 50

        if self.player.dashing:
            color = NEON_YELLOW
            text = "DASH!"
        elif self.player.dash_cooldown > 0:
            color = (100, 100, 100)
            text = f"{self.player.dash_cooldown:.1f}s"
        else:
            color = NEON_CYAN
            text = "READY"

        pygame.draw.rect(self.screen, color, (bar_x, dash_y, dash_size, dash_size), 3)
        dash_text = self.font_small.render(text, True, color)
        text_rect = dash_text.get_rect(center=(bar_x + dash_size // 2, dash_y + dash_size // 2))
        self.screen.blit(dash_text, text_rect)

        # Stats (top right)
        stats_x = WINDOW_WIDTH - 220
        stats_y = padding

        time_text = self.font_medium.render(f"Time: {int(self.survival_time)}s", True, NEON_CYAN)
        self.screen.blit(time_text, (stats_x, stats_y))

        score_text = self.font_medium.render(f"Score: {self.score}", True, NEON_PINK)
        self.screen.blit(score_text, (stats_x, stats_y + 40))

        kills_text = self.font_medium.render(f"Kills: {self.enemies_defeated}", True, NEON_ORANGE)
        self.screen.blit(kills_text, (stats_x, stats_y + 80))

    def draw_menu(self):
        """Draw main menu"""
        self.screen.fill(DARK_BG)
        self.draw_grid()

        title = self.font_large.render("NEON SURVIVAL", True, NEON_PINK)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        subtitle = self.font_medium.render("SHOOTER", True, NEON_CYAN)
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 270))
        self.screen.blit(subtitle, subtitle_rect)

        instructions = [
            "WASD - Move",
            "Mouse - Aim and Shoot",
            "SPACE - Dash",
            "",
            "Press ENTER to Start",
            "Press ESC to Quit"
        ]

        y = 350
        for instruction in instructions:
            text = self.font_medium.render(instruction, True, WHITE)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y))
            self.screen.blit(text, text_rect)
            y += 40

    def draw_pause(self):
        """Draw pause screen overlay"""
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        pause_text = self.font_large.render("PAUSED", True, NEON_CYAN)
        text_rect = pause_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(pause_text, text_rect)

        continue_text = self.font_medium.render("Press ESC to Continue", True, WHITE)
        continue_rect = continue_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60))
        self.screen.blit(continue_text, continue_rect)

    def draw_level_up(self):
        """Draw level up screen"""
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        title = self.font_large.render("LEVEL UP!", True, NEON_YELLOW)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)

        subtitle = self.font_medium.render("Choose an Upgrade", True, WHITE)
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 200))
        self.screen.blit(subtitle, subtitle_rect)

        # Draw upgrade choices
        for i, upgrade in enumerate(self.upgrade_choices):
            button_x = WINDOW_WIDTH // 2 - 150
            button_y = 250 + i * 120
            button_width = 300
            button_height = 100

            # Check if mouse is hovering
            mouse_x, mouse_y = pygame.mouse.get_pos()
            button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            is_hover = button_rect.collidepoint(mouse_x, mouse_y)

            # Draw button
            color = upgrade.color if is_hover else (upgrade.color[0] // 2, upgrade.color[1] // 2, upgrade.color[2] // 2)
            pygame.draw.rect(self.screen, color, button_rect)
            pygame.draw.rect(self.screen, WHITE, button_rect, 3)

            # Draw text
            name_text = self.font_medium.render(upgrade.name, True, WHITE)
            name_rect = name_text.get_rect(center=(button_x + button_width // 2, button_y + 30))
            self.screen.blit(name_text, name_rect)

            desc_text = self.font_small.render(upgrade.description, True, WHITE)
            desc_rect = desc_text.get_rect(center=(button_x + button_width // 2, button_y + 65))
            self.screen.blit(desc_text, desc_rect)

    def draw_game_over(self):
        """Draw game over screen"""
        self.screen.fill(DARK_BG)
        self.draw_grid()

        title = self.font_large.render("GAME OVER", True, RED)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        stats = [
            f"Survival Time: {int(self.survival_time)}s",
            f"Final Score: {self.score}",
            f"Enemies Defeated: {self.enemies_defeated}",
            f"Level Reached: {self.player.level}",
        ]

        y = 320
        for stat in stats:
            text = self.font_medium.render(stat, True, NEON_CYAN)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y))
            self.screen.blit(text, text_rect)
            y += 50

        restart_text = self.font_medium.render("Press ENTER to Return to Menu", True, WHITE)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, y + 50))
        self.screen.blit(restart_text, restart_rect)

    def draw(self):
        """Draw everything"""
        # Apply screen shake offset
        shake_x = random.randint(-int(self.shake_amount), int(self.shake_amount)) if self.shake_amount > 0 else 0
        shake_y = random.randint(-int(self.shake_amount), int(self.shake_amount)) if self.shake_amount > 0 else 0

        if self.state == GameState.MENU:
            self.draw_menu()
        elif self.state == GameState.GAME_OVER:
            self.draw_game_over()
        else:
            # Draw game
            self.screen.fill(DARK_BG)
            self.draw_grid()

            # Create shake surface
            if self.shake_amount > 0:
                game_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                game_surface.fill(DARK_BG)
                draw_target = game_surface
            else:
                draw_target = self.screen

            # Draw game objects
            for orb in self.xp_orbs:
                orb.draw(draw_target)

            for particle in self.particles:
                particle.draw(draw_target)

            for proj in self.projectiles:
                proj.draw(draw_target)

            for enemy in self.enemies:
                enemy.draw(draw_target)

            self.player.draw(draw_target)

            for num in self.damage_numbers:
                num.draw(draw_target, self.font_small)

            # Apply shake
            if self.shake_amount > 0:
                self.screen.blit(game_surface, (shake_x, shake_y))

            self.draw_hud()

            if self.state == GameState.PAUSED:
                self.draw_pause()
            elif self.state == GameState.LEVEL_UP:
                self.draw_level_up()

        pygame.display.flip()

    def run(self):
        """Main game loop"""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds

            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.run()
