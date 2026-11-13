import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import dataclass
import unittest
from gesture import GestureShooter

@dataclass
class Point:
    x:float=.5
    y:float=.6


def mock_hand(kind='open'):
    l=[Point() for _ in range(21)]
    l[5]=Point(.43,.50) # index MCP
    l[17]=Point(.63,.50) # pinky MCP: palm width .20
    l[8]=Point(.45,.19) # index tip
    l[4]=({'open':Point(.15,.5),'pressed':Point(.43,.51),'pinch':Point(.45,.19)}[kind])
    return l


def index_hand(kind='folded'):
    l=mock_hand('open')
    l[6]=Point(.44,.40) # index PIP
    l[7]=Point(.45,.31) # index DIP
    l[8]=Point(.49,.52) if kind=='folded' else Point(.44,.18)
    return l


class GestureTest(unittest.TestCase):
    def test_requires_open_before_trigger(self):
        g=GestureShooter("THUMB")
        self.assertFalse(g.process(mock_hand('pressed'),1).fired)
        self.assertFalse(g.process(mock_hand('pressed'),1.04).fired)
        self.assertFalse(g.process(mock_hand('open'),1.10).armed)
        self.assertTrue(g.process(mock_hand('open'),1.14).armed)
        self.assertTrue(g.process(mock_hand('pressed'),1.18).fired)
        self.assertFalse(g.process(mock_hand('pressed'),1.22).fired)

    def test_single_shot_until_release(self):
        g=GestureShooter("THUMB")
        for t in (1,1.04):g.process(mock_hand('open'),t)
        self.assertTrue(g.process(mock_hand('pressed'),1.10).fired)
        self.assertFalse(g.process(mock_hand('pressed'),1.14).fired)
        for t in (1.18,1.22,2,2.04):
            self.assertFalse(g.process(mock_hand('pressed'),t).fired)
        for t in (2.1,2.14):g.process(mock_hand('open'),t)
        self.assertTrue(g.process(mock_hand('pressed'),2.4).fired)
        self.assertFalse(g.process(mock_hand('pressed'),2.44).fired)

    def test_missing_hand_clears_arming(self):
        g=GestureShooter("THUMB")
        g.process(mock_hand('open'),1)
        self.assertTrue(g.process(mock_hand('open'),1.04).armed)
        self.assertFalse(g.process([],1.1).found)
        self.assertFalse(g.process(mock_hand('pressed'),1.2).fired)

    def test_pinch_mode(self):
        g=GestureShooter('PINCH')
        g.process(mock_hand('open'),1)
        self.assertTrue(g.process(mock_hand('open'),1.03).armed)
        self.assertTrue(g.process(mock_hand('pinch'),1.06).fired)
        self.assertFalse(g.process(mock_hand('pinch'),1.10).fired)

    def test_switch_mode_rearms(self):
        g=GestureShooter("THUMB")
        g.process(mock_hand('open'),1)
        g.process(mock_hand('open'),1.04)
        g.switch_mode()
        self.assertEqual(g.mode,'PINCH')
        self.assertFalse(g.armed)
        g.switch_mode()
        self.assertEqual(g.mode,'INDEX_FLICK')

    def test_aim_stays_still_when_firing_hand_moves(self):
        g=GestureShooter("THUMB")
        initial=g.process(mock_hand('open'),1)
        g.process(mock_hand('open'),1.04)
        hand=mock_hand('pressed')
        hand[8]=Point(.72,.65)  # index tip drifts during thumb folding
        shot=g.process(hand,1.08)
        self.assertTrue(shot.fired)
        self.assertAlmostEqual(shot.x,initial.x)
        self.assertAlmostEqual(shot.y,initial.y)

    def test_cannot_shoot_from_closed_pose_without_first_opening(self):
        g=GestureShooter("THUMB")
        for i in range(10):
            self.assertFalse(g.process(mock_hand('pressed'),1+i*.04).fired)

    def test_user_calibration_shoots_after_relative_fold(self):
        g=GestureShooter("THUMB")
        hand=mock_hand('open')
        # A smaller thumb opening that might not arm with default absolute rule.
        hand[4] = Point(.23,.50)
        g.process(hand,1)
        self.assertTrue(g.calibrate_open())
        g.process(hand,1.05)
        self.assertTrue(g.process(hand,1.09).armed)
        closed=mock_hand('pressed')
        shot=g.process(closed,1.13)
        self.assertTrue(shot.fired)

    def test_switching_fire_mode_clears_calibration(self):
        g=GestureShooter("THUMB")
        g.process(mock_hand('open'),1)
        self.assertTrue(g.calibrate_open())
        g.switch_mode()
        self.assertIsNone(g.calibrated_open)

    def test_calibration_without_hand_fails(self):
        g=GestureShooter("THUMB")
        self.assertFalse(g.calibrate_open())

    def test_adjust_sensitivity_clamped(self):
        g=GestureShooter("THUMB")
        g.set_sensitivity(100)
        self.assertEqual(g.sensitivity,1.55)
        g.set_sensitivity(-100)
        self.assertEqual(g.sensitivity,.7)

    def test_index_flick_is_default(self):
        self.assertEqual(GestureShooter().mode, "INDEX_FLICK")

    def test_index_up_legacy_alias(self):
        self.assertEqual(GestureShooter("INDEX_UP").mode, "INDEX_FLICK")

    def test_index_flick_shoots_on_fast_extension(self):
        g = GestureShooter()
        g.process(index_hand('folded'), 1.00)
        g.process(index_hand('folded'), 1.04)
        self.assertTrue(g.process(index_hand('folded'), 1.08).armed)
        shot = g.process(index_hand('raised'), 1.11)
        self.assertTrue(shot.fired)
        self.assertGreater(shot.motion_speed, 3.0)

    def test_index_tip_aim_moves_continuously_while_extended(self):
        g = GestureShooter()
        g.process(index_hand('raised'), 1.00)
        g.process(index_hand('raised'), 1.04)
        s = g.process(index_hand('raised'), 1.08)
        for i in range(1, 8):
            h = index_hand('raised')
            for j in (5, 8, 17):
                h[j].x += .025 * i
            later = g.process(h, 1.08 + .04 * i)
            self.assertFalse(later.fired)
        self.assertGreater(later.x, s.x + 110)

    def test_index_flick_uses_tip_not_knuckle(self):
        g = GestureShooter()
        folded = g.process(index_hand('folded'), 1.00)
        g.process(index_hand('folded'), 1.04)
        h = index_hand('folded')
        h[8].x += .075
        tip_changed = g.process(h, 1.08)
        self.assertGreater(tip_changed.x, folded.x)
        self.assertFalse(tip_changed.fired)  # lateral movement is not a rapid UP-flick

    def test_index_flick_shoot_freezes_aim_only_temporarily(self):
        g = GestureShooter()
        initial = g.process(index_hand('folded'), 1)
        g.process(index_hand('folded'), 1.04)
        g.process(index_hand('folded'), 1.08)
        shot = g.process(index_hand('raised'), 1.12)
        self.assertTrue(shot.fired)
        self.assertAlmostEqual(shot.x, initial.x)
        self.assertAlmostEqual(shot.y, initial.y)
        moved = index_hand('raised')
        for j in (5, 8, 17):
            moved[j].x += .16
        during_freeze = g.process(moved, 1.15)
        self.assertAlmostEqual(during_freeze.x, shot.x)
        after_freeze = g.process(moved, 1.23)
        self.assertGreater(after_freeze.x, shot.x)

    def test_index_flick_hold_does_not_stop_aim(self):
        g = GestureShooter()
        g.process(index_hand('folded'), 1)
        g.process(index_hand('folded'), 1.04)
        g.process(index_hand('folded'), 1.08)
        shot = g.process(index_hand('raised'), 1.12)
        self.assertTrue(shot.fired)
        for i in range(1, 20):
            h = index_hand('raised')
            for j in (5, 8, 17):
                h[j].x += .007 * i
            after = g.process(h, 1.12 + .04 * i)
            self.assertFalse(after.fired)
        self.assertGreater(after.x, shot.x + 65)

    def test_slow_index_extension_only_moves_aim(self):
        g = GestureShooter()
        h = index_hand('folded')
        g.process(h, 1)
        g.process(h, 1.04)
        g.process(h, 1.08)
        for i in range(1, 20):
            h = index_hand('folded')
            h[8].y -= min(.011 * i, .209)
            signal = g.process(h, 1.08 + i * .04)
            self.assertFalse(signal.fired)
        self.assertTrue(signal.armed)

    def test_whole_hand_fast_translation_does_not_shoot(self):
        g = GestureShooter()
        g.process(index_hand('raised'), 1)
        g.process(index_hand('raised'), 1.04)
        g.process(index_hand('raised'), 1.08)
        h = index_hand('raised')
        for j in (5, 6, 7, 8, 17):
            h[j].x += .20
            h[j].y += .15
        s = g.process(h, 1.11)
        self.assertFalse(s.fired)
        self.assertAlmostEqual(s.motion_speed, 0, places=3)

    def test_flick_jitter_does_not_shoot(self):
        g = GestureShooter()
        for i in range(35):
            h = index_hand('raised')
            h[8].y += .003 if i % 2 else -.003
            self.assertFalse(g.process(h, 1 + i * .033).fired)

    def test_index_flick_one_shot_until_relaxed(self):
        g = GestureShooter()
        for i in range(3):
            g.process(index_hand('folded'), 1 + i*.04)
        self.assertTrue(g.process(index_hand('raised'), 1.12).fired)
        for i in range(20):
            self.assertFalse(g.process(index_hand('raised'), 1.16+i*.04).fired)
        g.process(index_hand('folded'), 2.00)
        g.process(index_hand('folded'), 2.04)
        self.assertTrue(g.process(index_hand('raised'), 2.08).fired)

    def test_index_flick_calibration_optional(self):
        g = GestureShooter()
        g.process(index_hand('folded'), 1)
        self.assertTrue(g.calibrate_open())
        self.assertIsNotNone(g.calibrated_folded)
        for i in range(3):
            g.process(index_hand('folded'), 1.1+i*.04)
        self.assertTrue(g.process(index_hand('raised'), 1.25).fired)

    def test_index_flick_initial_pose_not_a_shot(self):
        g = GestureShooter()
        self.assertFalse(g.process(index_hand('raised'), 1).fired)
        self.assertFalse(g.process(index_hand('raised'), 1.04).fired)
        self.assertFalse(g.process(index_hand('raised'), 1.08).fired)

    def test_index_flick_missing_hand_resets_detector(self):
        g = GestureShooter()
        for i in range(3):
            g.process(index_hand('folded'), 1+i*.04)
        self.assertFalse(g.process([], 1.12).found)
        self.assertFalse(g.process(index_hand('raised'), 1.16).fired)

    def test_index_flick_more_sensitivity_is_easier(self):
        g = GestureShooter()
        g.set_sensitivity(.25)
        self.assertGreater(g.sensitivity, 1.24)
        self.assertFalse(g.process(index_hand('folded'), 1).fired)

    def test_fire_modes_cycle(self):
        g = GestureShooter()
        g.switch_mode()
        self.assertEqual(g.mode, 'THUMB')
        g.switch_mode()
        self.assertEqual(g.mode, 'PINCH')
        g.switch_mode()
        self.assertEqual(g.mode, 'INDEX_FLICK')

    def test_aim_moves_and_clamps(self):
        g=GestureShooter("THUMB")
        s=g.process(mock_hand(),1)
        self.assertGreaterEqual(s.x,100)
        self.assertLessEqual(s.x,1050)
        self.assertGreaterEqual(s.y,240)
        self.assertLessEqual(s.y,590)

if __name__=='__main__':unittest.main()
