import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from game_logic import TargetGame, DIFFICULTIES


class GameTest(unittest.TestCase):
    def setUp(self):
        self.g=TargetGame(seed=42)

    def practice_clear(self):
        for _ in range(3):
            t=self.g.targets[0]
            self.assertEqual(self.g.shoot(t.x,t.y),"hit")
        self.assertEqual(self.g.phase,"ready")

    def test_practice_starts_with_target(self):
        self.assertEqual(self.g.phase,"practice")
        self.assertEqual(self.g.practice_hits,0)
        self.assertEqual(len(self.g.targets),1)

    def test_practice_hit_progress(self):
        t=self.g.targets[0]
        self.assertEqual(self.g.shoot(t.x,t.y),"hit")
        self.assertEqual(self.g.practice_hits,1)
        self.assertEqual(self.g.phase,"practice")

    def test_practice_miss_keeps_progress(self):
        self.assertEqual(self.g.shoot(0,0),"miss")
        self.assertEqual(self.g.practice_hits,0)
        self.assertEqual(self.g.shots,0)

    def test_three_hits_unlock(self):
        self.practice_clear()
        self.assertEqual(len(self.g.targets),0)

    def test_only_start_button_unlocks_game(self):
        self.practice_clear()
        self.assertEqual(self.g.shoot(100,100),"not_ready")
        self.assertEqual(self.g.phase,"ready")
        self.assertEqual(self.g.shoot(640,410),"start")
        self.assertEqual(self.g.phase,"playing")

    def test_game_spawns_targets(self):
        self.practice_clear()
        self.g.start_game()
        self.assertEqual(len(self.g.targets),3)

    def test_scoring_bullseye(self):
        self.practice_clear()
        self.g.start_game()
        t=self.g.targets[0]
        self.assertEqual(self.g.shoot(t.x,t.y),"hit")
        self.assertEqual(self.g.score,15)
        self.assertEqual(self.g.accuracy,100)
        self.assertEqual(self.g.shots,1)
        self.assertEqual(self.g.hits,1)

    def test_miss_resets_combo(self):
        self.practice_clear()
        self.g.start_game()
        t=self.g.targets[0]
        self.g.shoot(t.x,t.y)
        self.assertEqual(self.g.combo,1)
        self.g.shoot(10,10)
        self.assertEqual(self.g.combo,0)
        self.assertEqual(self.g.accuracy,50)

    def test_pause_when_tracking_lost(self):
        self.practice_clear()
        self.g.start_game()
        self.g.update(.1,tracking=False)
        self.assertEqual(self.g.elapsed,0.0)
        self.g.update(.1,tracking=True)
        self.assertAlmostEqual(self.g.elapsed,.1)

    def test_game_end_after_timer(self):
        self.practice_clear()
        self.g.start_game()
        for _ in range(int(self.g.cfg['duration']*10)+1):
            self.g.update(.1)
        self.assertEqual(self.g.phase,"results")
        self.assertEqual(self.g.time_left,0)

    def test_restart_after_results(self):
        self.practice_clear()
        self.g.start_game()
        self.g.reset()
        self.assertEqual(self.g.phase,"practice")
        self.assertEqual(self.g.shots,0)

    def test_levels(self):
        for level,cfg in DIFFICULTIES.items():
            g=TargetGame(difficulty=level,seed=1)
            for _ in range(3):
                t=g.targets[0];g.shoot(t.x,t.y)
            g.start_game()
            self.assertEqual(len(g.targets),cfg['count'])

    def test_target_moves_and_stays_in_bounds(self):
        self.practice_clear()
        self.g.start_game()
        for _ in range(100):
            self.g.update(.08)
        for target in self.g.targets:
            self.assertGreaterEqual(target.x,110+target.radius-1)
            self.assertLessEqual(target.x,1060-target.radius+1)
            self.assertGreaterEqual(target.y,255+target.radius-1)
            self.assertLessEqual(target.y,595-target.radius+1)

    def test_default_assist_hits_near_edge(self):
        t=self.g.targets[0]
        self.assertGreater(self.g.assist_px, 0)
        self.assertEqual(self.g.shoot(t.x + t.radius + 20, t.y), 'hit')
        self.assertEqual(self.g.practice_hits, 1)
        self.assertEqual(self.g.pulses[-1].text, 'ASSIST HIT!')

    def test_off_assist_misses_same_distance(self):
        g=TargetGame(assist='off')
        t=g.targets[0]
        self.assertEqual(g.assist_px, 0)
        self.assertEqual(g.shoot(t.x + t.radius + 20,t.y), 'miss')

    def test_high_assist_is_forgiving_but_not_everywhere(self):
        g=TargetGame(assist='high')
        t=g.targets[0]
        self.assertEqual(g.shoot(t.x + t.radius + 70,t.y), 'hit')
        t=g.targets[0]
        self.assertEqual(g.shoot(t.x + t.radius + 120,t.y),'miss')

    def test_game_uses_nearest_target(self):
        self.practice_clear()
        self.g.start_game()
        # Put two overlapping hitboxes near the aim. Choose closest.
        first=self.g.targets[0]
        second=self.g.targets[1]
        first.x,first.y=400.,400.
        second.x,second.y=455.,400.
        self.g.shoot(405.,400.)
        self.assertNotIn(first,self.g.targets)
        self.assertIn(second,self.g.targets)

    def test_assist_cycles_and_survives_reset(self):
        self.assertEqual(self.g.assist, 'normal')
        self.assertEqual(self.g.cycle_assist(),'high')
        self.g.reset()
        self.assertEqual(self.g.assist,'high')
        self.assertEqual(self.g.cycle_assist(),'off')

    def test_invalid_assist(self):
        with self.assertRaises(ValueError):
            TargetGame(assist='unlimited')

    def test_invalid_difficulty(self):
        with self.assertRaises(ValueError):
            TargetGame("ultra")

if __name__=="__main__":
    unittest.main()
