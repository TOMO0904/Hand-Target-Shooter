"""Pure game rules; intentionally independent of camera/graphics."""
from __future__ import annotations
from dataclasses import dataclass
import math
import random

WIDTH, HEIGHT = 1280, 720
PRACTICE_POSITIONS = ((398, 365), (720, 424), (538, 302))
ASSIST_LEVELS = {"off": 0, "low": 24, "normal": 44, "high": 72}

DIFFICULTIES = {
    "easy": {"duration": 60.0, "count": 2, "radius": 68, "speed": 35.0, "life": 5.0},
    "normal": {"duration": 50.0, "count": 3, "radius": 52, "speed": 75.0, "life": 4.0},
    "hard": {"duration": 40.0, "count": 4, "radius": 40, "speed": 120.0, "life": 3.0},
}


@dataclass
class Target:
    x: float
    y: float
    radius: float
    vx: float = 0.0
    vy: float = 0.0
    age: float = 0.0
    lifetime: float = 5.0
    value: int = 10


@dataclass
class Pulse:
    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    age: float = 0.0


class TargetGame:
    def __init__(self, difficulty: str = "normal", seed: int | None = None, assist: str = "normal"):
        if difficulty not in DIFFICULTIES:
            raise ValueError("difficulty must be easy, normal or hard")
        if assist not in ASSIST_LEVELS:
            raise ValueError("assist must be off, low, normal or high")
        self.difficulty = difficulty
        self.cfg = DIFFICULTIES[difficulty]
        self.assist = assist
        self.rng = random.Random(seed)
        self.reset()

    @property
    def assist_px(self) -> int:
        # Training should be forgiving, especially when learning a gesture.
        return ASSIST_LEVELS[self.assist] + (12 if self.phase == "practice" and self.assist != "off" else 0)

    def cycle_assist(self) -> str:
        # Begin with NORMAL, then HIGH for players who need more assistance.
        choices = ("off", "low", "normal", "high")
        self.assist = choices[(choices.index(self.assist) + 1) % len(choices)]
        return self.assist

    def reset(self) -> None:
        self.phase = "practice"
        self.practice_hits = 0
        self.elapsed = 0.0
        self.score = 0
        self.hits = 0
        self.shots = 0
        self.combo = 0
        self.best_combo = 0
        self.targets: list[Target] = []
        self.pulses: list[Pulse] = []
        self._set_practice_target()

    def _set_practice_target(self) -> None:
        if self.practice_hits < len(PRACTICE_POSITIONS):
            x, y = PRACTICE_POSITIONS[self.practice_hits]
            self.targets = [Target(float(x), float(y), 66.0, lifetime=9999.0)]
        else:
            self.targets = []

    @property
    def time_left(self) -> float:
        return max(0.0, float(self.cfg["duration"]) - self.elapsed)

    @property
    def accuracy(self) -> int:
        return round(100.0 * self.hits / self.shots) if self.shots else 0

    def _spawn(self) -> None:
        cfg = self.cfg
        for _ in range(55):
            x = self.rng.uniform(140, 1040)
            y = self.rng.uniform(260, 565)
            r = cfg["radius"] * self.rng.uniform(0.86, 1.10)
            if all(math.hypot(x-t.x, y-t.y) >= r + t.radius + 22 for t in self.targets):
                break
        speed = cfg["speed"] * self.rng.uniform(.6, 1.25)
        angle = self.rng.uniform(0.0, math.tau)
        self.targets.append(Target(x, y, r, speed*math.cos(angle), speed*math.sin(angle),
                                   lifetime=cfg["life"] * self.rng.uniform(.85, 1.4)))

    def start_game(self) -> bool:
        if self.phase != "ready":
            return False
        self.phase = "playing"
        self.elapsed = 0.0
        self.targets = []
        self.pulses.clear()
        self.score = self.hits = self.shots = self.combo = self.best_combo = 0
        for _ in range(self.cfg["count"]):
            self._spawn()
        return True

    def shoot(self, x: float, y: float) -> str:
        if self.phase == "results":
            return "ignored"
        if self.phase == "ready":
            if math.hypot(x - 640, y - 410) <= 95 + self.assist_px:
                self.start_game()
                return "start"
            self.pulses.append(Pulse(x, y, "SHOOT START", (140, 212, 255)))
            return "not_ready"
        self.shots += 1 if self.phase == "playing" else 0
        # Always evaluate the nearest target. With expanded hitboxes, picking
        # whichever target was drawn last would feel arbitrary / inconsistent.
        candidates = [
            (math.hypot(x-t.x, y-t.y), i)
            for i, t in enumerate(self.targets)
            if math.hypot(x-t.x, y-t.y) <= t.radius + 9 + self.assist_px
        ]
        if candidates:
            distance, target_index = min(candidates)
            t = self.targets[target_index]
            self.targets.pop(target_index)
            assisted = distance > t.radius + 9
            if self.phase == "practice":
                self.practice_hits += 1
                label = "ASSIST HIT!" if assisted else "NICE SHOT!"
                self.pulses.append(Pulse(t.x, t.y, label, (115, 255, 180)))
                if self.practice_hits >= 3:
                    self.phase = "ready"
                    self.targets = []
                else:
                    self._set_practice_target()
            else:
                self.hits += 1
                self.combo += 1
                self.best_combo = max(self.best_combo, self.combo)
                center = distance <= t.radius*.35
                bonus = 5 if center else 0
                combo_bonus = min((self.combo//5)*5, 20)
                self.score += t.value + bonus + combo_bonus
                label = ("ASSIST +" if assisted else "+") + str(t.value+bonus+combo_bonus)
                self.pulses.append(Pulse(t.x, t.y, label, (100, 235, 165)))
                self._spawn()
            return "hit"
        if self.phase == "playing":
            self.combo = 0
        self.pulses.append(Pulse(x, y, "MISS", (100, 165, 255)))
        return "miss"

    def update(self, dt: float, tracking: bool = True) -> None:
        dt = max(0.0, min(dt, .10))
        for p in self.pulses:
            p.age += dt
        self.pulses = [p for p in self.pulses if p.age < .75]
        if self.phase != "playing" or not tracking:
            return
        self.elapsed = min(float(self.cfg["duration"]), self.elapsed + dt)
        if self.time_left <= 0:
            self.phase = "results"
            self.targets = []
            return
        remaining: list[Target] = []
        for t in self.targets:
            t.age += dt
            if t.age >= t.lifetime:
                continue
            t.x += t.vx*dt
            t.y += t.vy*dt
            if t.x < 110+t.radius:
                t.x = 110+t.radius
                t.vx = abs(t.vx)
            if t.x > 1060-t.radius:
                t.x = 1060-t.radius
                t.vx = -abs(t.vx)
            if t.y < 255+t.radius:
                t.y = 255+t.radius
                t.vy = abs(t.vy)
            if t.y > 595-t.radius:
                t.y = 595-t.radius
                t.vy = -abs(t.vy)
            remaining.append(t)
        self.targets = remaining
        while len(self.targets) < self.cfg["count"]:
            self._spawn()
