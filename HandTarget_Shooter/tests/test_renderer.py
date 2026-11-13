import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from game_logic import TargetGame, WIDTH, HEIGHT
from gesture import HandSignal
from renderer import draw
from camera_tracker import camera_preview

class DrawTest(unittest.TestCase):
    def test_practice_game_results(self):
        game=TargetGame(seed=1)
        signal=HandSignal(True,550,350,False,True,False,1.3,'THUMB')
        for phase in ('practice','ready','playing','results'):
            if phase=='ready':
                for _ in range(3):
                    t=game.targets[0];game.shoot(t.x,t.y)
            if phase=='playing':game.start_game()
            if phase=='results':game.phase='results'
            image=draw(game,signal,camera_preview(None,[]),True)
            self.assertEqual(image.shape,(HEIGHT,WIDTH,3))
            self.assertGreater(int(image.sum()),0)
    def test_no_hand_overlay(self):
        game=TargetGame(seed=1)
        image=draw(game,HandSignal(False),None,False)
        self.assertEqual(image.shape,(HEIGHT,WIDTH,3))

if __name__=='__main__':unittest.main()
