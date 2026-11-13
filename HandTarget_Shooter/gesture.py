"""Two independent hand-input channels for the webcam target game.

* AIM: the continuous, smoothed position of the INDEX FINGERTIP (landmark 8).
* FIRE (INDEX_FLICK): a short, fast extension of that index finger relative to
  its own knuckle (landmark 5). Moving the whole hand does not create this
  relative movement. A fast shot freezes the crosshair only for ~0.09 seconds;
  normal movement always resumes, even if the finger stays fully extended.

THUMB / PINCH remain available as alternative single-shot gestures. This module
has no camera, OpenCV or MediaPipe dependencies and is unit-testable.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math


def _distance(a, b) -> float:
    return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))


def _clamp(value, low, high):
    return max(low, min(high, value))


FIRE_MODES = ("INDEX_FLICK", "THUMB", "PINCH")


@dataclass(frozen=True)
class HandSignal:
    found: bool
    x: float = 640.0
    y: float = 410.0
    fired: bool = False
    armed: bool = False
    pressed: bool = False
    ratio: float = 0.0
    mode: str = "INDEX_FLICK"
    motion_speed: float = 0.0


class GestureShooter:
    def __init__(self, mode: str = "INDEX_FLICK", sensitivity: float = 1.24):
        if mode == "INDEX_UP":  # compatibility with v1.2 command-line usage
            mode = "INDEX_FLICK"
        if mode not in FIRE_MODES:
            raise ValueError(f"Unknown gesture mode: {mode}")
        self.mode = mode
        self.sensitivity = sensitivity
        self.last_aim: tuple[float, float] | None = None
        self.last_aim_time: float | None = None
        self.freeze_until = 0.0
        self.armed = False
        self.open_frames = 0
        self.closed_frames = 0
        self.cooldown_until = 0.0
        self.last_fired_aim: tuple[float, float] | None = None
        self.last_observed_ratio: float | None = None
        self.calibrated_open: float | None = None
        self.calibrated_folded: float | None = None
        self._prev_ratio: float | None = None
        self._prev_time: float | None = None
        self._history: deque[tuple[float, float]] = deque(maxlen=12)
        self._seen = 0
        self._needs_reset = False
        self._shot_peak = 0.0

    def calibrate_open(self) -> bool:
        """For INDEX_FLICK, capture current resting pose to ease min stroke size.

        No calibration is needed in normal use. In THUMB/PINCH, calibrate the
        open gesture as in earlier releases. Old name kept for compatibility.
        """
        ratio = self.last_observed_ratio
        if ratio is None:
            return False
        if self.mode == "INDEX_FLICK":
            if not -1.0 <= ratio <= 2.5:
                return False
            self.calibrated_folded = ratio
            self.calibrated_open = None
        else:
            if ratio <= .40:
                return False
            self.calibrated_open = ratio
            self.calibrated_folded = None
        self.reset_trigger()
        return True

    def reset_calibration(self) -> None:
        self.calibrated_open = None
        self.calibrated_folded = None
        self.reset_trigger()

    def reset_trigger(self) -> None:
        self.armed = False
        self.open_frames = self.closed_frames = 0
        self._prev_ratio = None
        self._prev_time = None
        self._history.clear()
        self._seen = 0
        self._needs_reset = False
        self._shot_peak = 0.0
        self.freeze_until = 0.0

    def switch_mode(self) -> None:
        self.mode = FIRE_MODES[(FIRE_MODES.index(self.mode) + 1) % len(FIRE_MODES)]
        self.last_aim = None
        self.last_aim_time = None
        self.reset_calibration()

    def set_sensitivity(self, adjustment: float) -> None:
        self.sensitivity = _clamp(self.sensitivity + adjustment, .70, 1.55)
        self.reset_trigger()

    def _thresholds(self) -> tuple[float, float]:
        """(pressed, released) pose thresholds for THUMB / PINCH."""
        shift = self.sensitivity - 1.0
        if self.mode == "THUMB":
            closed = .88 + .26 * shift
            opened = 1.16 - .19 * shift
        else:
            closed = .58 + .22 * shift
            opened = .88 - .18 * shift
        opened = max(opened, closed + .10)
        if self.calibrated_open is not None:
            closed = self.calibrated_open * .90
            opened = max(self.calibrated_open * .97, closed + .06)
        return closed, opened

    def _update_aim(self, landmark, now: float, firing: bool) -> tuple[float, float]:
        target_x = 100 + _clamp((landmark.x - .10) / .80, 0, 1) * 950
        target_y = 240 + _clamp((landmark.y - .12) / .78, 0, 1) * 350
        if self.last_aim is None:
            self.last_aim = (target_x, target_y)
        elif not firing and now >= self.freeze_until:
            previous_time = self.last_aim_time if self.last_aim_time is not None else now
            dt = max(0.0, min(now - previous_time, .15))
            # Continuous position tracking without excessive noise.
            alpha = _clamp(1 - math.exp(-dt / .050), .24, .85)
            self.last_aim = (self.last_aim[0] + alpha * (target_x - self.last_aim[0]),
                             self.last_aim[1] + alpha * (target_y - self.last_aim[1]))
        self.last_aim_time = now
        return self.last_aim

    def _index_extension(self, landmarks, palm: float) -> float:
        """Projection onto the INDEX's own proximal direction, in palm units.

        Lateral fingertip wiggles must AIM, not FIRE. A simple fingertip-to-
        knuckle distance would also increase during lateral aim gestures.
        """
        base, pip, tip = landmarks[5], landmarks[6], landmarks[8]
        dx, dy = pip.x - base.x, pip.y - base.y
        length = max(math.hypot(dx, dy), .025)
        return ((tip.x - base.x) * dx + (tip.y - base.y) * dy) / (length * palm)

    def _index_flick(self, ratio: float, now: float) -> tuple[bool, float]:
        # Remove old samples. The comparison uses *relative* finger movement,
        # not absolute fingertip speed, so translating the hand only aims.
        while self._history and now - self._history[0][0] > .16:
            self._history.popleft()
        earlier = min((v for _, v in self._history), default=ratio)
        prev = self._prev_ratio
        dt = (now - self._prev_time) if self._prev_time is not None else 0.0
        speed = (ratio - prev) / dt if prev is not None and .01 <= dt <= .18 else 0.0
        progress = ratio - earlier
        shift = self.sensitivity - 1.0
        speed_needed = _clamp(3.0 - 2.0 * shift, 1.65, 3.8)
        stroke_needed = _clamp(.27 - .20 * shift, .15, .33)
        if self.calibrated_folded is not None:
            stroke_needed = max(.14, stroke_needed - .05)

        # A new shot is possible only after the index relaxes (falls back)
        # from the previous shot peak. Holding the finger up never auto-fires.
        if self._needs_reset and ratio < self._shot_peak - .20:
            self._needs_reset = False
        if self._needs_reset:
            self._shot_peak = max(self._shot_peak, ratio)

        # Need a stable reference after hand first appears or tracking resumes.
        ready = self._seen >= 2 and not self._needs_reset
        fired = bool(ready and now >= self.cooldown_until
                     and speed >= speed_needed and progress >= stroke_needed
                     and ratio >= .65)
        if fired:
            self.cooldown_until = now + .26
            self._needs_reset = True
            self._shot_peak = ratio
            self.freeze_until = now + .085
            ready = False

        self._history.append((now, ratio))
        self._prev_ratio = ratio
        self._prev_time = now
        self._seen += 1
        self.armed = ready and now >= self.cooldown_until
        return fired, speed

    def process(self, landmarks, now: float) -> HandSignal:
        if not landmarks or len(landmarks) < 21:
            self.last_aim = None
            self.last_aim_time = None
            self.last_observed_ratio = None
            self.reset_trigger()
            return HandSignal(False, mode=self.mode)

        palm = max(_distance(landmarks[5], landmarks[17]), .045)
        if self.mode == "INDEX_FLICK":
            ratio = self._index_extension(landmarks, palm)
            # Always track fingertip when aiming, even while finger is raised.
            # The firing detector is completely separate from aim movement.
            fired, speed = self._index_flick(ratio, now)
            x, y = self._update_aim(landmarks[8], now, firing=fired)
            self.last_observed_ratio = ratio
            if fired:
                self.last_fired_aim = (x, y)
            return HandSignal(True, x, y, fired, self.armed, fired,
                              ratio, self.mode, speed)

        reference = landmarks[5] if self.mode == "THUMB" else landmarks[8]
        ratio = _distance(landmarks[4], reference) / palm
        self.last_observed_ratio = ratio
        pressed_threshold, released_threshold = self._thresholds()
        pressed = ratio <= pressed_threshold
        released = ratio >= released_threshold
        # Keep the previous single-shot semantics for alternate gesture modes.
        if released:
            self.open_frames += 1
            self.closed_frames = 0
            if self.open_frames >= 2:
                self.armed = True
        elif pressed:
            self.closed_frames += 1
            self.open_frames = 0
        else:
            self.closed_frames = 0
            self.open_frames = 0
        fired = self.armed and self.closed_frames >= 1 and now >= self.cooldown_until
        if fired:
            self.armed = False
            self.open_frames = 0
            self.closed_frames = 0
            self.cooldown_until = now + .24
            self.freeze_until = now + .085
        x, y = self._update_aim(landmarks[8], now, firing=pressed)
        if fired:
            self.last_fired_aim = (x, y)
        return HandSignal(True, x, y, fired, self.armed, pressed,
                          ratio, self.mode)
