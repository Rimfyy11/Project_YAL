import math
import arcade
import random
import sqlite3
from datetime import datetime
from dataclasses import dataclass

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
GRID_SIZE = 40

COST_BASIC = 25
COST_SNIPER = 60
BLAST_RADIUS = 60


def init_db():
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            score INTEGER,
            mode TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_score(score, mode):
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%d.%m %H:%M")
    cursor.execute("INSERT INTO records (score, mode, date) VALUES (?, ?, ?)", (score, mode, date_str))
    conn.commit()
    conn.close()


def get_top_scores(limit=5):
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT score, mode, date FROM records ORDER BY score DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return []
    conn.close()
    return rows


@dataclass
class Waypoint:
    x: float
    y: float


class Enemy(arcade.Sprite):
    def __init__(self, filename, scale, speed=1.0, hp=50):
        super().__init__(filename, scale)
        self.speed = speed
        self.hp_max = hp
        self.hp = hp
        self.waypoints = []
        self.wp = 0

    def set_path(self, p):
        self.waypoints = p
        self.wp = 0
        if len(p) > 0:
            self.center_x, self.center_y = p[0].x, p[0].y

    def update(self, delta_time: float = 1 / 60):
        if self.wp >= len(self.waypoints): return
        t = self.waypoints[self.wp]
        dx = t.x - self.center_x
        dy = t.y - self.center_y
        d = math.hypot(dx, dy)
        self.angle += 1
        if d < self.speed:
            self.center_x, self.center_y = t.x, t.y
            self.wp += 1
        else:
            self.center_x += self.speed * dx / d
            self.center_y += self.speed * dy / d

    def reached_end(self):
        return self.wp >= len(self.waypoints)


class FastEnemy(Enemy):
    def __init__(self):
        super().__init__(":resources:images/space_shooter/meteorGrey_small1.png", 0.8, speed=2.5, hp=25)


class StrongEnemy(Enemy):
    def __init__(self):
        super().__init__(":resources:images/space_shooter/meteorGrey_big1.png", 0.6, speed=0.7, hp=150)


class Rocket(arcade.Sprite):
    def __init__(self, x, y, target, damage, all_enemies):
        super().__init__(":resources:images/space_shooter/laserRed01.png", 0.8)
        self.center_x, self.center_y = x, y
        self.target = target
        self.damage = damage
        self.speed_val = 8
        self.all_enemies = all_enemies
        dx = target.center_x - x
        dy = target.center_y - y
        self.angle = math.degrees(math.atan2(dy, dx)) - 90

    def update(self, delta_time: float = 1 / 60):
        if not self.target or self.target.hp <= 0:
            self.remove_from_sprite_lists()
            return
        dx = self.target.center_x - self.center_x
        dy = self.target.center_y - self.center_y
        d = math.hypot(dx, dy)
        self.angle = math.degrees(math.atan2(dy, dx)) - 90

        if d < self.speed_val:
            for e in self.all_enemies:
                dist = math.hypot(e.center_x - self.center_x, e.center_y - self.center_y)
                if dist <= BLAST_RADIUS:
                    e.hp -= self.damage
            self.remove_from_sprite_lists()
        else:
            self.center_x += self.speed_val * dx / d
            self.center_y += self.speed_val * dy / d


class Tower(arcade.Sprite):
    def __init__(self, filename, scale, x, y, range_dist, rate, damage):
        super().__init__(filename, scale)
        self.center_x, self.center_y = x, y
        self.range = range_dist
        self.rate = rate
        self.damage = damage
        self.timer = 0
        self.current_target = None

    def attack_logic(self, dt, enemies, bullets):
        self.timer += dt

        if not self.current_target or self.current_target.hp <= 0 or \
                math.hypot(self.current_target.center_x - self.center_x,
                           self.current_target.center_y - self.center_y) > self.range:
            self.current_target = None
            min_dist = self.range
            for e in enemies:
                d = math.hypot(e.center_x - self.center_x, e.center_y - self.center_y)
                if d <= self.range and d < min_dist and e.hp > 0:
                    min_dist = d
                    self.current_target = e

        if self.current_target:
            dx = self.current_target.center_x - self.center_x
            dy = self.current_target.center_y - self.center_y
            self.angle = math.degrees(math.atan2(dy, dx)) - 90

            if self.timer >= self.rate:
                self.shoot(self.current_target, bullets, enemies)
                self.timer = 0

    def shoot(self, target, bullets, all_enemies):
        pass

    def draw_laser(self):
        pass


class BasicTower(Tower):
    def __init__(self, x, y):
        # Перезарядка 0.5 сек, урон 10
        super().__init__(":resources:images/space_shooter/playerShip1_blue.png", 0.6, x, y, 150, 0.5, 10)
        self.is_firing = False
        self.fire_timer = 0.0
        self.fire_duration = 0.15  # Луч виден 0.15 секунды

    def attack_logic(self, dt, enemies, bullets):
        # Обновляем таймер видимости лазера
        if self.is_firing:
            self.fire_timer -= dt
            if self.fire_timer <= 0:
                self.is_firing = False

        super().attack_logic(dt, enemies, bullets)

    def shoot(self, target, bullets, all_enemies):
        target.hp -= self.damage
        self.is_firing = True
        self.fire_timer = self.fire_duration

    def draw_laser(self):
        # Рисуем только если сейчас фаза "выстрела"
        if self.is_firing and self.current_target and self.current_target.hp > 0:
            arcade.draw_line(self.center_x, self.center_y,
                             self.current_target.center_x, self.current_target.center_y,
                             arcade.color.CYAN, 3)
            # Добавим красивый эффект "пятна" на цели
            arcade.draw_circle_filled(self.current_target.center_x, self.current_target.center_y, 5, arcade.color.CYAN)


class SniperTower(Tower):
    def __init__(self, x, y):
        super().__init__(":resources:images/space_shooter/playerShip2_orange.png", 0.7, x, y, 300, 2.0, 50)

    def shoot(self, target, bullets, all_enemies):
        bullets.append(Rocket(self.center_x, self.center_y, target, self.damage, all_enemies))

    def draw_laser(self):
        pass


class Game(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, "Космическая Оборона: Laser Pulse")
        init_db()
        self.background = arcade.load_texture(":resources:images/backgrounds/stars.png")

        self.state = "MENU"
        self.difficulty = "NORMAL"

        self.btn_start = (SCREEN_WIDTH // 2, 400, 200, 50)
        self.btn_records = (SCREEN_WIDTH // 2, 300, 200, 50)
        self.btn_exit = (SCREEN_WIDTH // 2, 200, 200, 50)
        self.btn_back = (100, 50, 100, 40)
        self.btn_normal = (SCREEN_WIDTH // 2, 350, 200, 50)
        self.btn_hard = (SCREEN_WIDTH // 2, 250, 200, 50)
        self.btn_pause = (SCREEN_WIDTH - 60, SCREEN_HEIGHT - 30, 100, 40)
        self.btn_resume = (SCREEN_WIDTH // 2, 350, 200, 50)
        self.btn_menu_exit = (SCREEN_WIDTH // 2, 250, 200, 50)

        self.top_scores = []
        self.setup_game()

    def setup_game(self):
        self.e = arcade.SpriteList()
        self.t = arcade.SpriteList()
        self.b = arcade.SpriteList()
        self.waypoints = [
            Waypoint(0, 100), Waypoint(200, 100), Waypoint(200, 300),
            Waypoint(600, 300), Waypoint(600, 500), Waypoint(SCREEN_WIDTH, 500)
        ]
        start_money = 120 if self.difficulty == "NORMAL" else 80
        start_lives = 5 if self.difficulty == "NORMAL" else 1
        self.spawn_timer = 0
        self.money = start_money
        self.lives = start_lives
        self.score = 0
        self.wave_num = 1
        self.enemies_to_spawn = 10
        self.spawned_count = 0
        self.selected_type = "BASIC"
        self.game_over_saved = False
        self.towers_objects = []

    def draw_btn(self, btn, text, color=arcade.color.GRAY, text_color=arcade.color.WHITE):
        x, y, w, h = btn
        arcade.draw_rect_filled(arcade.XYWH(x, y, w, h), color)
        arcade.draw_text(text, x, y, text_color, 20, anchor_x="center", anchor_y="center", font_name="Arial")

    def on_draw(self):
        self.clear()
        arcade.draw_texture_rect(self.background,
                                 arcade.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH, SCREEN_HEIGHT))

        if self.state == "MENU":
            arcade.draw_text("КОСМИЧЕСКАЯ ОБОРОНА", SCREEN_WIDTH // 2, 500, arcade.color.GOLD, 40, anchor_x="center",
                             font_name="Arial", bold=True)
            self.draw_btn(self.btn_start, "Играть", arcade.color.DARK_BLUE)
            self.draw_btn(self.btn_records, "Рекорды")
            self.draw_btn(self.btn_exit, "Выход", arcade.color.DARK_RED)

        elif self.state == "DIFFICULTY":
            arcade.draw_text("ВЫБЕРИ СЛОЖНОСТЬ", SCREEN_WIDTH // 2, 500, arcade.color.WHITE, 30, anchor_x="center",
                             font_name="Arial")
            self.draw_btn(self.btn_normal, "Нормально", arcade.color.GREEN)
            self.draw_btn(self.btn_hard, "ХАРДКОР", arcade.color.RED)

        elif self.state == "RECORDS":
            arcade.draw_text("ТОП 5 РЕКОРДОВ", SCREEN_WIDTH // 2, 520, arcade.color.GOLD, 30, anchor_x="center",
                             font_name="Arial")
            self.draw_btn(self.btn_back, "Назад")
            y = 450
            for i, row in enumerate(self.top_scores):
                s, m, d = row
                mode_str = "Хард" if m == "HARD" else "Норм"
                arcade.draw_text(f"{i + 1}. {s} ({mode_str}) - {d}", SCREEN_WIDTH // 2, y, arcade.color.WHITE, 20,
                                 anchor_x="center", font_name="Arial")
                y -= 40

        elif self.state in ["GAME", "PAUSE", "GAMEOVER", "WIN"]:
            pts = [(w.x, w.y) for w in self.waypoints]
            if len(pts) > 1:
                arcade.draw_line_strip(pts, (200, 200, 200, 60), 40)

            self.t.draw()

            for tower in self.towers_objects:
                tower.draw_laser()

            self.e.draw()
            self.b.draw()

            arcade.draw_text(f"Золото: {self.money}", 10, 570, arcade.color.WHITE, 16, font_name="Arial")
            arcade.draw_text(f"Жизни: {self.lives}", 10, 550,
                             arcade.color.RED if self.lives == 1 else arcade.color.WHITE, 16, font_name="Arial")
            arcade.draw_text(f"Волна: {self.wave_num}", 10, 530, arcade.color.WHITE, 16, font_name="Arial")
            arcade.draw_text(f"Счет: {self.score}", 10, 510, arcade.color.WHITE, 16, font_name="Arial")

            self.draw_btn(self.btn_pause, "Пауза", arcade.color.DARK_GRAY, arcade.color.WHITE)

            t_name = "Ракетница" if self.selected_type == 'SNIPER' else "Лазер"
            arcade.draw_text(f"Выбрано: {t_name}", 10, 30, arcade.color.YELLOW, 14, font_name="Arial")
            arcade.draw_text("1: Лазер (25$) | 2: Ракетница (60$)", 300, 30, arcade.color.WHITE, 14, font_name="Arial")

            if self.state == "PAUSE":
                arcade.draw_rect_filled(arcade.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH, SCREEN_HEIGHT),
                                        (0, 0, 0, 150))
                arcade.draw_text("ПАУЗА", SCREEN_WIDTH / 2, 450, arcade.color.WHITE, 40, anchor_x="center",
                                 font_name="Arial")
                self.draw_btn(self.btn_resume, "Продолжить", arcade.color.GREEN)
                self.draw_btn(self.btn_menu_exit, "Выйти в Меню", arcade.color.RED)

            elif self.state == "GAMEOVER":
                arcade.draw_rect_filled(arcade.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, 400, 200), arcade.color.BLACK)
                arcade.draw_text("ВЫ ПРОИГРАЛИ", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 20, arcade.color.RED, 30,
                                 anchor_x="center", font_name="Arial")
                arcade.draw_text("Нажми для меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 40, arcade.color.GRAY, 14,
                                 anchor_x="center", font_name="Arial")

            elif self.state == "WIN":
                arcade.draw_rect_filled(arcade.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, 400, 200), arcade.color.BLACK)
                arcade.draw_text("ПОБЕДА!", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 20, arcade.color.GOLD, 30,
                                 anchor_x="center", font_name="Arial")
                arcade.draw_text(f"Итоговый счет: {self.score}", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 20,
                                 arcade.color.WHITE, 20, anchor_x="center", font_name="Arial")
                arcade.draw_text("Нажми для меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50, arcade.color.GRAY, 14,
                                 anchor_x="center", font_name="Arial")

    def on_update(self, dt):
        if self.state != "GAME": return

        self.spawn_timer += dt
        spawn_rate = 1.0 if self.difficulty == "HARD" else 1.5
        if self.spawned_count < self.enemies_to_spawn and self.spawn_timer >= spawn_rate:
            self.spawn_enemy()
            self.spawned_count += 1
            self.spawn_timer = 0

        if self.spawned_count == self.enemies_to_spawn and len(self.e) == 0:
            self.start_next_wave()

        self.e.update()
        self.b.update()

        for t in self.towers_objects:
            t.attack_logic(dt, self.e, self.b)

        for e in self.e:
            if e.reached_end():
                self.lives -= 1
                e.remove_from_sprite_lists()
                if self.lives <= 0:
                    self.end_game(win=False)

        for e in list(self.e):
            if e.hp <= 0:
                self.score += 10 * (2 if self.difficulty == "HARD" else 1)
                self.money += 15
                e.remove_from_sprite_lists()

    def end_game(self, win):
        self.state = "WIN" if win else "GAMEOVER"
        if not self.game_over_saved:
            add_score(self.score, self.difficulty)
            self.game_over_saved = True

    def spawn_enemy(self):
        r = random.random()
        enemy = None
        strong_chance = 0.5 if self.difficulty == "HARD" else 0.3
        if self.wave_num >= 3 and r < strong_chance:
            enemy = StrongEnemy()
        elif self.wave_num >= 2 and r > 0.7:
            enemy = FastEnemy()
        else:
            enemy = Enemy(":resources:images/space_shooter/meteorGrey_med1.png", 0.7)
        enemy.set_path(self.waypoints)
        self.e.append(enemy)

    def start_next_wave(self):
        self.wave_num += 1
        if self.wave_num > 5:
            self.end_game(win=True)
        else:
            self.spawned_count = 0
            self.enemies_to_spawn += 3 if self.difficulty == "NORMAL" else 5
            self.money += 50

    def check_btn(self, x, y, btn):
        bx, by, bw, bh = btn
        return (bx - bw / 2 < x < bx + bw / 2) and (by - bh / 2 < y < by + bh / 2)

    def on_mouse_press(self, x, y, button, modifiers):
        if self.state == "MENU":
            if self.check_btn(x, y, self.btn_start):
                self.state = "DIFFICULTY"
            elif self.check_btn(x, y, self.btn_records):
                self.top_scores = get_top_scores()
                self.state = "RECORDS"
            elif self.check_btn(x, y, self.btn_exit):
                arcade.close_window()

        elif self.state == "DIFFICULTY":
            if self.check_btn(x, y, self.btn_normal):
                self.difficulty = "NORMAL"
                self.setup_game()
                self.state = "GAME"
            elif self.check_btn(x, y, self.btn_hard):
                self.difficulty = "HARD"
                self.setup_game()
                self.state = "GAME"

        elif self.state == "RECORDS":
            if self.check_btn(x, y, self.btn_back): self.state = "MENU"

        elif self.state == "GAME":
            if self.check_btn(x, y, self.btn_pause):
                self.state = "PAUSE"
                return

            cost = COST_BASIC if self.selected_type == "BASIC" else COST_SNIPER
            if self.money < cost: return
            gx = (x // GRID_SIZE) * GRID_SIZE + GRID_SIZE // 2
            gy = (y // GRID_SIZE) * GRID_SIZE + GRID_SIZE // 2

            for i in range(len(self.waypoints) - 1):
                p1, p2 = self.waypoints[i], self.waypoints[i + 1]
                if min(p1.x, p2.x) - 20 <= gx <= max(p1.x, p2.x) + 20 and min(p1.y, p2.y) - 20 <= gy <= max(p1.y,
                                                                                                            p2.y) + 20: return

            for t in self.t:
                if t.center_x == gx and t.center_y == gy: return

            new_tower = None
            if self.selected_type == "BASIC":
                new_tower = BasicTower(gx, gy)
            else:
                new_tower = SniperTower(gx, gy)

            self.t.append(new_tower)
            self.towers_objects.append(new_tower)
            self.money -= cost

        elif self.state == "PAUSE":
            if self.check_btn(x, y, self.btn_resume):
                self.state = "GAME"
            elif self.check_btn(x, y, self.btn_menu_exit):
                self.state = "MENU"

        elif self.state in ["GAMEOVER", "WIN"]:
            self.state = "MENU"

    def on_key_press(self, key, modifiers):
        if self.state == "GAME":
            if key == arcade.key.KEY_1:
                self.selected_type = "BASIC"
            elif key == arcade.key.KEY_2:
                self.selected_type = "SNIPER"
            elif key == arcade.key.ESCAPE:
                self.state = "PAUSE"
        elif self.state == "PAUSE":
            if key == arcade.key.ESCAPE: self.state = "GAME"


if __name__ == "__main__":
    game = Game()
    game.run()
