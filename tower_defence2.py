import math, arcade
from dataclasses import dataclass

SCREEN_WIDTH, SCREEN_HEIGHT, GRID_SIZE = 800, 600, 40
ENEMY_SPEED, TOWER_COST = 1.0, 25


@dataclass
class Waypoint: x: float; y: float


class Enemy(arcade.SpriteCircle):
    def __init__(self):
        super().__init__(10, arcade.color.RED)
        self.speed, self.hp, self.waypoints, self.wp = ENEMY_SPEED, 50, [], 0

    def set_path(self, p):
        self.waypoints, self.wp = p, 0
        self.center_x, self.center_y = p[0].x, p[0].y

    def update(self):
        if self.wp >= len(self.waypoints): return
        t = self.waypoints[self.wp]
        dx, dy = t.x - self.center_x, t.y - self.center_y
        d = math.hypot(dx, dy)
        if d < self.speed:
            self.center_x, self.center_y, self.wp = t.x, t.y, self.wp + 1
        else:
            self.center_x += self.speed * dx / d
            self.center_y += self.speed * dy / d

    def reached_end(self):
        return self.wp >= len(self.waypoints)


class Bullet(arcade.SpriteCircle):
    def __init__(self, x, y, target):
        super().__init__(4, arcade.color.YELLOW)
        self.center_x, self.center_y, self.target, self.damage = x, y, target, 10

    def update(self, dt=None):  # добавлен dt=None
        if not self.target or self.target.hp <= 0:
            self.remove_from_sprite_lists()
            return
        dx = self.target.center_x - self.center_x
        dy = self.target.center_y - self.center_y
        d = math.hypot(dx, dy)
        if d < 5:
            self.target.hp -= self.damage
            self.remove_from_sprite_lists()
        else:
            self.center_x += 5 * dx / d
            self.center_y += 5 * dy / d


class Tower(arcade.SpriteCircle):
    def __init__(self, x, y):
        super().__init__(12, arcade.color.BLUE)
        self.center_x, self.center_y = x, y
        self.range, self.rate, self.timer = 120, 0.5, 0

    def update(self, dt, enemies, bullets):
        self.timer += dt
        if self.timer < self.rate: return
        target = None
        mind = self.range
        for e in enemies:
            d = math.hypot(e.center_x - self.center_x, e.center_y - self.center_y)
            if d <= self.range and d < mind and e.hp > 0:
                mind, target = d, e
        if target:
            bullets.append(Bullet(self.center_x, self.center_y, target))
            self.timer = 0


class Game(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, "TD")
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)
        self.e, self.t, self.b = arcade.SpriteList(), arcade.SpriteList(), arcade.SpriteList()
        self.waypoints = [Waypoint(0, 100), Waypoint(200, 100), Waypoint(200, 300), Waypoint(600, 300),
                          Waypoint(600, 500), Waypoint(SCREEN_WIDTH, 500)]
        self.spawn, self.wave, self.m, self.l, self.s = 0, 0, 100, 10, 0
        self.texts = [arcade.Text(f"Деньги: {self.m}", 10, 580, arcade.color.WHITE, 14),
                      arcade.Text(f"Жизни: {self.l}", 10, 560, arcade.color.WHITE, 14),
                      arcade.Text(f"Счёт: {self.s}", 10, 540, arcade.color.WHITE, 14)]

    def on_draw(self):
        self.clear()
        pts = [(w.x, w.y) for w in self.waypoints]
        arcade.draw_line_strip(pts, arcade.color.LIGHT_GRAY, 4)
        self.e.draw()
        self.t.draw()
        self.b.draw()
        for t in self.texts: t.draw()

    def on_update(self, dt):
        self.spawn += dt
        if self.wave < 10 and self.spawn >= 2:
            e = Enemy()
            e.set_path(self.waypoints)
            self.e.append(e)
            self.wave += 1
            self.spawn = 0

        for e in self.e[:]:
            e.update()
            if e.reached_end():
                self.l -= 1
                e.remove_from_sprite_lists()

        for t in self.t:
            t.update(dt, self.e, self.b)
        self.b.update()

        for e in list(self.e):
            if e.hp <= 0:
                self.s += 10
                self.m += 5
                e.remove_from_sprite_lists()

        self.texts[0].text = f"Деньги: {self.m}"
        self.texts[1].text = f"Жизни: {self.l}"
        self.texts[2].text = f"Счёт: {self.s}"

        if self.l <= 0:
            print("Game Over")
            arcade.close_window()

    def on_mouse_press(self, x, y, _, __):
        if self.m < TOWER_COST: return
        gx, gy = (x // GRID_SIZE) * GRID_SIZE + GRID_SIZE // 2, (y // GRID_SIZE) * GRID_SIZE + GRID_SIZE // 2
        if any(math.hypot(gx - w.x, gy - w.y) < GRID_SIZE for w in self.waypoints): return
        self.t.append(Tower(gx, gy))
        self.m -= TOWER_COST


if __name__ == "__main__":
    Game().run()
