import pygame
import sys
import random
import math
import numpy as np

# ================================================
# AC's PVZ - FULL SINGLE-FILE recreation (files=off)
# Python 3.x - 60 FPS, Windows Vista retro speed & feel
# ALL MENU MODES ARE NOW FULLY PLAYABLE:
#   • ADVENTURE / QUICK PLAY → classic waves
#   • SURVIVAL → endless waves (difficulty ramps forever)
#   • MINI-GAMES → Whack-A-Zombie (click popping zombies for high score, 60-second timer)
#   • PUZZLES → Vasebreaker (click vases to reveal plants or zombies, survive the wave)
# + Dynamic procedural sound engine (PVZ1 style)
# + SexyEngine-style clean structure
# Everything still 100% code-drawn - no external files
# Window title: "ac's pvz"
# ================================================

pygame.init()
pygame.mixer.init(44100, -16, 2, 512)

WIDTH, HEIGHT = 900, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ac's pvz")
CLOCK = pygame.time.Clock()
FPS = 60

# Colors
SKY = (135, 206, 235)
GRASS = (34, 139, 34)
DIRT = (139, 69, 19)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BROWN = (165, 42, 42)
DARK_BROWN = (101, 67, 33)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (200, 200, 200)
STONE = (180, 180, 170)
ORANGE = (255, 165, 0)
LIGHT_BLUE = (173, 216, 230)
VASE_COLOR = (139, 69, 19)

# Grid (for main game)
ROWS = 5
COLS = 9
CELL_W = 80
CELL_H = 100
LAWN_X = 250
LAWN_Y = 80

# Fonts
BIG_FONT = pygame.font.SysFont(None, 88)
FONT = pygame.font.SysFont(None, 48)
SMALL_FONT = pygame.font.SysFont(None, 24)
TINY_FONT = pygame.font.SysFont(None, 18)

# ====================== DYNAMIC SOUND ENGINE ======================
class DynamicSoundEngine:
    def __init__(self):
        self.cache = {}
        self.create_all_sounds()

    def make_tone(self, freq, duration, waveform="sine", volume=0.6):
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        if waveform == "sine":
            wave = np.sin(2 * np.pi * freq * t)
        elif waveform == "square":
            wave = np.sign(np.sin(2 * np.pi * freq * t))
        elif waveform == "saw":
            wave = 2 * (t * freq % 1) - 1
        else:
            wave = np.sin(2 * np.pi * freq * t)
        fade = np.linspace(1, 0, len(wave))
        wave = wave * fade
        wave = (wave * volume * 32767).astype(np.int16)
        stereo = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo)

    def create_all_sounds(self):
        self.cache['pea'] = self.make_tone(1200, 0.08, "sine", 0.7)
        self.cache['sun'] = self.make_tone(800, 0.15, "sine", 0.8)
        self.cache['chomp'] = self.make_tone(180, 0.25, "square", 0.5)
        self.cache['explode'] = self.make_tone(80, 0.6, "saw", 0.9)
        self.cache['mower'] = self.make_tone(240, 0.4, "saw", 0.6)
        self.cache['plant'] = self.make_tone(420, 0.12, "sine", 0.4)
        self.cache['whack'] = self.make_tone(600, 0.09, "square", 0.8)   # mini-game whack sound

    def play(self, name):
        if name in self.cache:
            self.cache[name].play()

sound_engine = DynamicSoundEngine()

# ====================== GAME VARIABLES ======================
sun_points = 200
selected_plant = None
plants = []
zombies = []
projectiles = []
suns = []
explosions = []
lawnmowers = []
zombie_spawn_timer = 0
wave = 1
game_state = "MENU"          # MENU, GAME, MINIGAME, PUZZLE, COMING_SOON, GAMEOVER
game_mode = "ADVENTURE"      # ADVENTURE, SURVIVAL, MINIGAME, PUZZLE
menu_zombie_x = WIDTH + 100

# Mini-game & Puzzle specific variables
mini_score = 0
mini_timer = 0
puzzle_vases = []            # list of {"x":, "y":, "type": "plant" or "zombie", "opened": False}

# ====================== CLASSES ======================
class Sun:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 3
        self.value = 25
        self.rect = pygame.Rect(x, y, 40, 40)
        self.alive = True

    def update(self):
        self.y += self.speed
        self.rect.y = self.y
        if self.y > HEIGHT:
            self.alive = False

    def draw(self):
        pygame.draw.circle(SCREEN, YELLOW, (int(self.x)+20, int(self.y)+20), 20)
        pygame.draw.circle(SCREEN, WHITE, (int(self.x)+20, int(self.y)+20), 20, 5)

class Projectile:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 12
        self.rect = pygame.Rect(x, y, 20, 10)

    def update(self):
        self.x += self.speed
        self.rect.x = self.x

    def draw(self):
        pygame.draw.ellipse(SCREEN, GREEN, (int(self.x), int(self.y)-4, 28, 14))

class Explosion:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.timer = 18
        self.rect = pygame.Rect(x-80, y-80, 160, 160)

    def update(self):
        self.timer -= 1

    def draw(self):
        size = int(80 * (1 - self.timer / 18))
        pygame.draw.circle(SCREEN, ORANGE, (int(self.x), int(self.y)), size)
        pygame.draw.circle(SCREEN, YELLOW, (int(self.x), int(self.y)), size//2)

class Plant:
    def __init__(self, col, row, plant_type):
        self.col = col
        self.row = row
        self.x = LAWN_X + col * CELL_W + CELL_W // 2
        self.y = LAWN_Y + row * CELL_H + CELL_H // 2
        self.type = plant_type
        self.health = 300 if plant_type == 'wallnut' else 150 if plant_type == 'cherrybomb' else 120
        self.cooldown = 0
        self.explode_timer = 0
        self.rect = pygame.Rect(self.x-35, self.y-45, 70, 90)

    def update(self):
        self.cooldown = max(0, self.cooldown - 1)
        if self.type == 'peashooter' and self.cooldown == 0:
            for z in zombies:
                if z.row == self.row and z.x > self.x:
                    projectiles.append(Projectile(self.x + 25, self.y - 8))
                    sound_engine.play('pea')
                    self.cooldown = 22
                    break
        elif self.type == 'sunflower' and self.cooldown == 0:
            if random.random() < 0.025:
                suns.append(Sun(self.x - 15, self.y - 70))
                self.cooldown = 280
        elif self.type == 'cherrybomb':
            if self.explode_timer > 0:
                self.explode_timer -= 1
                if self.explode_timer == 0:
                    explosions.append(Explosion(self.x, self.y))
                    sound_engine.play('explode')
                    for z in zombies[:]:
                        if abs(z.x - self.x) < 110 and abs(z.y - self.y) < 110:
                            z.health = 0
                    if self in plants:
                        plants.remove(self)
                    return
        elif self.type == 'wallnut':
            pass

    def draw(self):
        if self.type == 'peashooter':
            pygame.draw.rect(SCREEN, (0, 180, 0), (self.x-8, self.y-10, 12, 55))
            pygame.draw.circle(SCREEN, (0, 220, 0), (int(self.x)+8, int(self.y)-22), 22)
            pygame.draw.circle(SCREEN, WHITE, (int(self.x)+18, int(self.y)-18), 9)
            pygame.draw.circle(SCREEN, BLACK, (int(self.x)+22, int(self.y)-18), 4)
        elif self.type == 'sunflower':
            for a in range(8):
                angle = a * 45
                vec = pygame.math.Vector2(1, 0).rotate(angle)
                px = self.x + 28 * vec.x
                py = self.y - 30 + 28 * vec.y
                pygame.draw.ellipse(SCREEN, YELLOW, (px-12, py-8, 24, 16))
            pygame.draw.circle(SCREEN, (220, 180, 0), (int(self.x), int(self.y)-30), 22)
        elif self.type == 'wallnut':
            pygame.draw.ellipse(SCREEN, (180, 140, 40), (self.x-32, self.y-38, 64, 68))
            pygame.draw.ellipse(SCREEN, (140, 100, 20), (self.x-25, self.y-30, 50, 52))
        elif self.type == 'cherrybomb':
            pygame.draw.circle(SCREEN, RED, (int(self.x), int(self.y)-20), 28)
            pygame.draw.circle(SCREEN, (255, 100, 0), (int(self.x)-10, int(self.y)-28), 12)
            pygame.draw.circle(SCREEN, (255, 100, 0), (int(self.x)+10, int(self.y)-28), 12)
            text = SMALL_FONT.render("💥", True, WHITE)
            SCREEN.blit(text, (self.x-12, self.y-38))

        if self.type == 'wallnut' and self.health < 300:
            w = 50 * (self.health / 300)
            pygame.draw.rect(SCREEN, RED, (self.x-28, self.y-48, 56, 6))
            pygame.draw.rect(SCREEN, GREEN, (self.x-28, self.y-48, w, 6))

class Zombie:
    def __init__(self, row, ztype='normal'):
        self.row = row
        self.x = WIDTH + 50
        self.y = LAWN_Y + row * CELL_H + CELL_H // 2 + random.randint(-8, 8)
        self.health = 180 if ztype == 'cone' else 130
        self.speed = 1.25
        self.ztype = ztype
        self.rect = pygame.Rect(self.x-35, self.y-45, 55, 90)
        self.eating = False
        self.eat_timer = 0

    def update(self):
        self.eating = False
        for p in plants:
            if p.row == self.row and abs(p.x - self.x) < 48:
                p.health -= 1.1
                self.eating = True
                self.eat_timer += 1
                if self.eat_timer % 18 == 0:
                    sound_engine.play('chomp')
                if p.health <= 0:
                    if p in plants:
                        plants.remove(p)
                return
        self.x -= self.speed
        self.rect.x = self.x - 35

    def draw(self):
        pygame.draw.rect(SCREEN, BROWN, (self.x-25, self.y-30, 38, 55))
        pygame.draw.circle(SCREEN, (200, 180, 140), (int(self.x), int(self.y)-38), 22)
        pygame.draw.circle(SCREEN, WHITE, (int(self.x)-9, int(self.y)-40), 7)
        pygame.draw.circle(SCREEN, WHITE, (int(self.x)+9, int(self.y)-40), 7)
        pygame.draw.circle(SCREEN, BLACK, (int(self.x)-9, int(self.y)-40), 3)
        pygame.draw.circle(SCREEN, BLACK, (int(self.x)+9, int(self.y)-40), 3)
        if self.ztype == 'cone':
            pygame.draw.polygon(SCREEN, (220, 140, 0), [(self.x-18, self.y-55), (self.x+18, self.y-55), (self.x, self.y-72)])

class LawnMower:
    def __init__(self, row):
        self.row = row
        self.x = LAWN_X - 60
        self.y = LAWN_Y + row * CELL_H + CELL_H // 2
        self.active = False
        self.speed = 12

    def update(self):
        if self.active:
            self.x += self.speed
            for z in zombies[:]:
                if z.row == self.row and abs(z.x - self.x) < 55:
                    z.health = 0
            if self.x > WIDTH + 100:
                self.active = False
            if self.x % 40 < 12:
                sound_engine.play('mower')

    def draw(self):
        color = (200, 200, 200) if self.active else (140, 140, 140)
        pygame.draw.rect(SCREEN, color, (int(self.x)-20, int(self.y)-25, 55, 38))
        pygame.draw.circle(SCREEN, BLACK, (int(self.x)+15, int(self.y)+8), 12)

def reset_game(mode="ADVENTURE"):
    global sun_points, selected_plant, plants, zombies, projectiles, suns, explosions, lawnmowers, zombie_spawn_timer, wave, game_mode, mini_score, mini_timer, puzzle_vases
    game_mode = mode
    sun_points = 200
    selected_plant = None
    plants.clear()
    zombies.clear()
    projectiles.clear()
    suns.clear()
    explosions.clear()
    lawnmowers.clear()
    for r in range(ROWS):
        lawnmowers.append(LawnMower(r))
    zombie_spawn_timer = 0
    wave = 1
    mini_score = 0
    mini_timer = 3600   # 60 seconds @ 60fps for mini-game
    puzzle_vases.clear()

def check_game_over():
    for z in zombies:
        if z.x < LAWN_X - 120:
            return True
    return False

# ====================== MENU DRAW ======================
def draw_menu():
    global menu_zombie_x
    SCREEN.fill(SKY)

    # Clouds + hills + grass
    cloud_positions = [(80, 60), (280, 35), (520, 85), (710, 50)]
    for cx, cy in cloud_positions:
        pygame.draw.ellipse(SCREEN, WHITE, (cx, cy, 120, 50))
        pygame.draw.ellipse(SCREEN, WHITE, (cx+35, cy-18, 95, 55))
        pygame.draw.ellipse(SCREEN, WHITE, (cx+70, cy+5, 75, 45))
    pygame.draw.polygon(SCREEN, (50, 180, 50), [(0, 320), (200, 260), (450, 320), (700, 240), (900, 320)])
    pygame.draw.polygon(SCREEN, (34, 139, 34), [(0, 340), (150, 280), (380, 340), (620, 260), (900, 340)])
    pygame.draw.rect(SCREEN, GRASS, (0, 340, WIDTH, HEIGHT-340))
    pygame.draw.rect(SCREEN, DIRT, (0, 380, WIDTH, 45), 6)

    # Big tree
    pygame.draw.rect(SCREEN, (101, 67, 33), (95, 220, 45, 180))
    pygame.draw.circle(SCREEN, (0, 140, 0), (110, 190), 55)
    pygame.draw.circle(SCREEN, (0, 160, 0), (75, 165), 45)
    pygame.draw.circle(SCREEN, (0, 160, 0), (145, 165), 45)
    pygame.draw.circle(SCREEN, (0, 140, 0), (70, 215), 40)
    pygame.draw.circle(SCREEN, (0, 140, 0), (150, 215), 40)

    # Hanging signs (clickable)
    sign_rects = {}
    signs = [("QUICK PLAY", 40, 200), ("MINI-GAMES", 40, 260), ("SURVIVAL", 40, 320), ("PUZZLES", 40, 380)]
    for text_str, sx, sy in signs:
        rect = pygame.Rect(sx, sy, 120, 28)
        pygame.draw.rect(SCREEN, (180, 120, 60), rect, border_radius=4)
        pygame.draw.rect(SCREEN, BLACK, rect, 4, border_radius=4)
        sign_text = TINY_FONT.render(text_str, True, BLACK)
        SCREEN.blit(sign_text, (sx + 8, sy + 6))
        sign_rects[text_str] = rect

    # Adventure gravestone
    grave_x = 420
    grave_y = 210
    pygame.draw.rect(SCREEN, STONE, (grave_x, grave_y, 210, 220), border_radius=12)
    pygame.draw.rect(SCREEN, STONE, (grave_x+15, grave_y-35, 180, 70), border_radius=30)
    pygame.draw.line(SCREEN, (100, 100, 100), (grave_x+30, grave_y+30), (grave_x+180, grave_y+30), 6)
    adv_text = FONT.render("ADVENTURE", True, BLACK)
    SCREEN.blit(adv_text, (grave_x + 105 - adv_text.get_width()//2, grave_y + 45))
    more_text = SMALL_FONT.render("MORE WAYS TO PLAY", True, BLACK)
    SCREEN.blit(more_text, (grave_x + 105 - more_text.get_width()//2, grave_y + 110))
    adventure_rect = pygame.Rect(grave_x, grave_y, 210, 220)

    # Small survival gravestone (decorative)
    small_grave_x = 680
    small_grave_y = 280
    pygame.draw.rect(SCREEN, STONE, (small_grave_x, small_grave_y, 130, 130), border_radius=8)
    pygame.draw.rect(SCREEN, STONE, (small_grave_x+20, small_grave_y-25, 90, 45), border_radius=15)
    surv_text = SMALL_FONT.render("SURVIVAL", True, BLACK)
    SCREEN.blit(surv_text, (small_grave_x + 65 - surv_text.get_width()//2, small_grave_y + 8))

    # House
    house_x = WIDTH - 310
    pygame.draw.rect(SCREEN, DARK_BROWN, (house_x, 220, 210, 160))
    pygame.draw.polygon(SCREEN, BROWN, [(house_x-25, 220), (house_x+105, 130), (house_x+235, 220)])
    pygame.draw.rect(SCREEN, (80, 40, 20), (house_x+90, 290, 35, 90))
    pygame.draw.circle(SCREEN, YELLOW, (house_x+105, 335), 6)
    pygame.draw.rect(SCREEN, LIGHT_BLUE, (house_x+30, 250, 35, 35))
    pygame.draw.rect(SCREEN, LIGHT_BLUE, (house_x+155, 250, 35, 35))

    # Animated zombie
    menu_zombie_x -= 1.2
    if menu_zombie_x < -100:
        menu_zombie_x = WIDTH + 100
    z = Zombie(2, 'normal')
    z.x = menu_zombie_x
    z.y = 380
    z.draw()

    # Title
    title_ac = BIG_FONT.render("AC'S", True, GREEN)
    title_pvz = BIG_FONT.render("PVZ", True, BROWN)
    SCREEN.blit(title_ac, (WIDTH//2 - title_ac.get_width()//2 - 110, 35))
    SCREEN.blit(title_pvz, (WIDTH//2 - title_pvz.get_width()//2 + 115, 35))

    quit_rect = pygame.Rect(710, 500, 160, 55)
    pygame.draw.rect(SCREEN, RED, quit_rect, border_radius=8)
    pygame.draw.rect(SCREEN, WHITE, quit_rect, 6, border_radius=8)
    quit_text = FONT.render("QUIT", True, WHITE)
    SCREEN.blit(quit_text, (quit_rect.x + (quit_rect.width - quit_text.get_width())//2, quit_rect.y + 8))

    return sign_rects, adventure_rect, quit_rect

# ====================== MAIN LOOP ======================
running = True
play_rect = None
quit_rect = None
sign_rects = {}
coming_mode = ""

while running:
    CLOCK.tick(FPS)
    mx, my = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if game_state == "MENU":
                # Hanging signs
                if "QUICK PLAY" in sign_rects and sign_rects["QUICK PLAY"].collidepoint(mx, my):
                    game_state = "GAME"
                    reset_game("ADVENTURE")
                    sound_engine.play('plant')
                elif "MINI-GAMES" in sign_rects and sign_rects["MINI-GAMES"].collidepoint(mx, my):
                    game_state = "MINIGAME"
                    reset_game("MINIGAME")
                    mini_score = 0
                    mini_timer = 3600
                elif "SURVIVAL" in sign_rects and sign_rects["SURVIVAL"].collidepoint(mx, my):
                    game_state = "GAME"
                    reset_game("SURVIVAL")
                    sound_engine.play('plant')
                elif "PUZZLES" in sign_rects and sign_rects["PUZZLES"].collidepoint(mx, my):
                    game_state = "PUZZLE"
                    reset_game("PUZZLE")
                    # Create vases for Vasebreaker
                    puzzle_vases = []
                    for i in range(15):
                        col = random.randint(0, COLS-1)
                        row = random.randint(0, ROWS-1)
                        puzzle_vases.append({"col": col, "row": row, "type": random.choice(["plant","zombie"]), "opened": False})
                elif adventure_rect.collidepoint(mx, my):
                    game_state = "GAME"
                    reset_game("ADVENTURE")
                    sound_engine.play('plant')
                elif quit_rect.collidepoint(mx, my):
                    running = False

            elif game_state in ("MINIGAME", "PUZZLE", "GAME"):
                # Collect sun (only in main game)
                if game_state == "GAME":
                    for sun in suns[:]:
                        if sun.rect.collidepoint(mx, my):
                            sun_points += sun.value
                            suns.remove(sun)
                            sound_engine.play('sun')
                            break
                    else:
                        if mx < 210:
                            if 80 < my < 160:   selected_plant = 'peashooter'
                            elif 170 < my < 250: selected_plant = 'sunflower'
                            elif 260 < my < 340: selected_plant = 'wallnut'
                            elif 350 < my < 430: selected_plant = 'cherrybomb'
                        elif selected_plant:
                            col = (mx - LAWN_X) // CELL_W
                            row = (my - LAWN_Y) // CELL_H
                            if 0 <= col < COLS and 0 <= row < ROWS:
                                occupied = any(p.col == col and p.row == row for p in plants)
                                cost = 100 if selected_plant == 'peashooter' else 50 if selected_plant == 'sunflower' else 50 if selected_plant == 'wallnut' else 150
                                if not occupied and sun_points >= cost:
                                    plants.append(Plant(col, row, selected_plant))
                                    sun_points -= cost
                                    sound_engine.play('plant')
                                    if selected_plant == 'cherrybomb':
                                        plants[-1].explode_timer = 120
                            selected_plant = None

                # Mini-game whack
                if game_state == "MINIGAME":
                    for z in zombies[:]:
                        if z.rect.collidepoint(mx, my):
                            z.health = 0
                            mini_score += 100
                            sound_engine.play('whack')
                            break

                # Puzzle vase click
                if game_state == "PUZZLE":
                    for v in puzzle_vases:
                        if not v["opened"]:
                            vx = LAWN_X + v["col"] * CELL_W + CELL_W // 2
                            vy = LAWN_Y + v["row"] * CELL_H + CELL_H // 2
                            if abs(mx - vx) < 40 and abs(my - vy) < 50:
                                v["opened"] = True
                                sound_engine.play('plant')
                                if v["type"] == "zombie":
                                    zombies.append(Zombie(v["row"], 'normal'))
                                else:
                                    plants.append(Plant(v["col"], v["row"], 'peashooter'))
                                break

            elif game_state == "GAMEOVER":
                if WIDTH//2 - 120 < mx < WIDTH//2 + 120 and 420 < my < 480:
                    game_state = "MENU"

    if game_state == "MENU":
        sign_rects, adventure_rect, quit_rect = draw_menu()

    elif game_state == "MINIGAME":
        # Whack-A-Zombie mini-game
        SCREEN.fill((20, 40, 20))
        title = BIG_FONT.render("WHACK-A-ZOMBIE", True, YELLOW)
        SCREEN.blit(title, (WIDTH//2 - title.get_width()//2, 30))

        # Lawn for mini-game
        for r in range(ROWS):
            for c in range(COLS):
                x = LAWN_X + c * CELL_W
                y = LAWN_Y + r * CELL_H
                pygame.draw.rect(SCREEN, GRASS, (x, y, CELL_W, CELL_H))
                pygame.draw.rect(SCREEN, DIRT, (x+5, y+5, CELL_W-10, CELL_H-10), 5)

        # Spawn popping zombies
        if random.random() < 0.08 and len(zombies) < 8:
            row = random.randint(0, ROWS-1)
            col = random.randint(0, COLS-1)
            z = Zombie(row, 'normal')
            z.x = LAWN_X + col * CELL_W + CELL_W // 2
            zombies.append(z)

        for z in zombies[:]:
            z.update()
            if z.health <= 0:
                zombies.remove(z)
            else:
                z.draw()

        mini_timer -= 1
        time_left = mini_timer // 60
        timer_text = FONT.render(f"Time: {time_left}", True, WHITE)
        SCREEN.blit(timer_text, (30, 20))
        score_text = FONT.render(f"Score: {mini_score}", True, YELLOW)
        SCREEN.blit(score_text, (WIDTH-220, 20))

        if mini_timer <= 0:
            game_state = "GAMEOVER"

        back_text = SMALL_FONT.render("Click zombies! Back to menu when time runs out", True, WHITE)
        SCREEN.blit(back_text, (WIDTH//2 - back_text.get_width()//2, 540))

    elif game_state == "PUZZLE":
        # Vasebreaker puzzle
        SCREEN.fill((20, 40, 20))
        title = BIG_FONT.render("VASEBREAKER", True, YELLOW)
        SCREEN.blit(title, (WIDTH//2 - title.get_width()//2, 30))

        for r in range(ROWS):
            for c in range(COLS):
                x = LAWN_X + c * CELL_W
                y = LAWN_Y + r * CELL_H
                pygame.draw.rect(SCREEN, GRASS, (x, y, CELL_W, CELL_H))
                pygame.draw.rect(SCREEN, DIRT, (x+5, y+5, CELL_W-10, CELL_H-10), 5)

        # Draw vases
        for v in puzzle_vases:
            vx = LAWN_X + v["col"] * CELL_W + CELL_W // 2 - 25
            vy = LAWN_Y + v["row"] * CELL_H + CELL_H // 2 - 30
            if not v["opened"]:
                pygame.draw.rect(SCREEN, VASE_COLOR, (vx, vy, 50, 60), border_radius=8)
                pygame.draw.rect(SCREEN, BLACK, (vx, vy, 50, 60), 4, border_radius=8)
                vase_text = TINY_FONT.render("?", True, WHITE)
                SCREEN.blit(vase_text, (vx + 18, vy + 20))
            else:
                if v["type"] == "zombie":
                    z = Zombie(v["row"], 'normal')
                    z.x = vx + 25
                    z.y = vy + 35
                    z.draw()

        # Update & draw normal game entities
        for p in plants[:]:
            p.update()
            if p.health <= 0:
                plants.remove(p)
        for z in zombies[:]:
            z.update()
            if z.health <= 0:
                zombies.remove(z)
        for proj in projectiles[:]:
            proj.update()
            if proj.x > WIDTH:
                projectiles.remove(proj)
                continue
            for z in zombies[:]:
                if proj.rect.colliderect(z.rect):
                    z.health -= 28
                    projectiles.remove(proj)
                    break
        for s in suns[:]:
            s.update()
            if not s.alive:
                suns.remove(s)
        for exp in explosions[:]:
            exp.update()
            if exp.timer <= 0:
                explosions.remove(exp)

        for p in plants:
            p.draw()
        for z in zombies:
            z.draw()
        for proj in projectiles:
            proj.draw()
        for s in suns:
            s.draw()
        for exp in explosions:
            exp.draw()

        if len(zombies) == 0 and all(v["opened"] for v in puzzle_vases):
            win_text = FONT.render("PUZZLE CLEARED!", True, GREEN)
            SCREEN.blit(win_text, (WIDTH//2 - win_text.get_width()//2, 480))

        back_text = SMALL_FONT.render("Click vases to break them!", True, WHITE)
        SCREEN.blit(back_text, (WIDTH//2 - back_text.get_width()//2, 540))

    elif game_state == "GAMEOVER":
        SCREEN.fill((20, 20, 20))
        go_text = BIG_FONT.render("ZOMBIES ATE YOUR BRAIN!", True, RED)
        SCREEN.blit(go_text, (WIDTH//2 - go_text.get_width()//2, 180))
        restart_rect = pygame.Rect(WIDTH//2 - 120, 420, 240, 60)
        pygame.draw.rect(SCREEN, (0, 180, 0), restart_rect)
        pygame.draw.rect(SCREEN, WHITE, restart_rect, 8)
        rst_text = FONT.render("BACK TO MENU", True, WHITE)
        SCREEN.blit(rst_text, (restart_rect.x + (restart_rect.width - rst_text.get_width())//2, restart_rect.y + 8))

    else:  # Normal GAME (Adventure / Survival)
        # Update logic (same as before)
        for p in plants[:]:
            p.update()
            if p.health <= 0:
                if p in plants:
                    plants.remove(p)

        for z in zombies[:]:
            z.update()
            if z.health <= 0:
                if z in zombies:
                    zombies.remove(z)

        for proj in projectiles[:]:
            proj.update()
            if proj.x > WIDTH:
                projectiles.remove(proj)
                continue
            for z in zombies[:]:
                if proj.rect.colliderect(z.rect):
                    z.health -= 28
                    if proj in projectiles:
                        projectiles.remove(proj)
                    break

        for s in suns[:]:
            s.update()
            if not s.alive:
                suns.remove(s)

        for exp in explosions[:]:
            exp.update()
            if exp.timer <= 0:
                explosions.remove(exp)

        for mower in lawnmowers:
            mower.update()

        for mower in lawnmowers:
            if not mower.active:
                for z in zombies:
                    if z.row == mower.row and z.x <= LAWN_X + 30:
                        mower.active = True
                        break

        zombie_spawn_timer += 1
        spawn_limit = max(50, 160 - wave * 8) if game_mode == "ADVENTURE" else max(40, 140 - wave * 12)
        if zombie_spawn_timer > spawn_limit:
            if random.random() < 0.78:
                row = random.randint(0, ROWS-1)
                ztype = 'cone' if random.random() < 0.35 + wave*0.04 else 'normal'
                zombies.append(Zombie(row, ztype))
            zombie_spawn_timer = 0
            if len(zombies) > 7:
                wave += 1

        if random.random() < 0.018:
            suns.append(Sun(random.randint(LAWN_X+40, WIDTH-80), 30))

        if check_game_over():
            game_state = "GAMEOVER"

        # Draw
        SCREEN.fill(SKY)
        for r in range(ROWS):
            for c in range(COLS):
                x = LAWN_X + c * CELL_W
                y = LAWN_Y + r * CELL_H
                pygame.draw.rect(SCREEN, GRASS, (x, y, CELL_W, CELL_H))
                pygame.draw.rect(SCREEN, DIRT, (x+5, y+5, CELL_W-10, CELL_H-10), 5)
                pygame.draw.line(SCREEN, (20, 120, 20), (x+15, y+10), (x+12, y+35), 3)
                pygame.draw.line(SCREEN, (20, 120, 20), (x+45, y+10), (x+50, y+32), 3)

        for mower in lawnmowers:
            mower.draw()
        for p in plants:
            p.draw()
        for z in zombies:
            z.draw()
        for proj in projectiles:
            proj.draw()
        for s in suns:
            s.draw()
        for exp in explosions:
            exp.draw()

        sun_text = FONT.render(f"Sun: {sun_points}", True, YELLOW)
        SCREEN.blit(sun_text, (30, 20))
        mode_text = SMALL_FONT.render(f"{game_mode} - Wave {wave}", True, WHITE)
        SCREEN.blit(mode_text, (WIDTH-220, 20))

        packets = [
            ("Pea", 100, GREEN, 'peashooter', 80),
            ("Sun", 50, YELLOW, 'sunflower', 170),
            ("Wall", 50, (180,140,40), 'wallnut', 260),
            ("Cherry", 150, RED, 'cherrybomb', 350)
        ]
        for name, cost, col, ptype, y in packets:
            pygame.draw.rect(SCREEN, (200, 200, 200), (40, y, 110, 80))
            pygame.draw.rect(SCREEN, col, (55, y+12, 70, 50))
            txt = SMALL_FONT.render(name, True, BLACK)
            SCREEN.blit(txt, (65, y+65))
            cst = SMALL_FONT.render(str(cost), True, BLACK)
            SCREEN.blit(cst, (85, y+78))

        instr = SMALL_FONT.render("Click seed → click lawn", True, WHITE)
        SCREEN.blit(instr, (260, 15))

    pygame.display.flip()

pygame.quit()
sys.exit()