"""RiG++ Hand Target Shooter: continuously aim with fingertip; quick finger flick shoots."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
import cv2
import numpy as np
from game_logic import TargetGame, WIDTH, HEIGHT
from gesture import GestureShooter, HandSignal
from renderer import draw
from camera_tracker import open_camera, camera_preview, HandTracker

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "hand_landmarker.task"
RECORDS = ROOT / "data" / "highscores.json"


def read_records():
    try:
        data=json.loads(RECORDS.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_record(difficulty,score):
    records=read_records()
    if score > int(records.get(difficulty,0)):
        records[difficulty]=score
        RECORDS.parent.mkdir(parents=True,exist_ok=True)
        RECORDS.write_text(json.dumps(records,indent=2),encoding="utf-8")
        return True
    return False


def save_snapshot(path: Path, difficulty="normal"):
    game=TargetGame(difficulty,seed=42)
    for _ in range(3):
        game.shoot(game.targets[0].x,game.targets[0].y)
    game.start_game()
    game.score=245
    game.hits=17
    game.shots=21
    game.combo=4
    game.update(8.6)
    signal=HandSignal(True,650,445,False,True,False,.55,"INDEX_FLICK")
    preview=camera_preview(None,[])
    out=draw(game,signal,preview,demo=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(path),out):
        raise RuntimeError("Cannot save preview to " + str(path))
    print("Wrote screenshot:",path)


def run(demo=False,camera_id=0,difficulty="normal",mode="INDEX_FLICK",assist="normal"):
    cap=None
    tracker=None
    first_frame=None
    if not demo:
        cap,first_frame=open_camera(camera_id)
        try:
            tracker=HandTracker(MODEL)
        except Exception:
            cap.release()
            raise
    game=TargetGame(difficulty,assist=assist)
    records=read_records()
    detector=GestureShooter(mode)
    title="RiG++ Hand Target Shooter | Q: Quit"
    mouse={"x":640, "y":410, "fire":False}
    def on_mouse(event,x,y,flags,param):
        if demo:
            mouse["x"],mouse["y"]=x,y
            if event==cv2.EVENT_LBUTTONDOWN:
                mouse["fire"]=True
    previous=time.monotonic()
    blink_until=0.0
    feedback_until=0.0
    feedback=""
    lost_at=None
    was_result=False
    try:
        cv2.namedWindow(title,cv2.WINDOW_NORMAL)
        cv2.resizeWindow(title,1200,675)
        cv2.setMouseCallback(title,on_mouse)
        while True:
            now=time.monotonic()
            dt=min(.1,now-previous)
            previous=now
            frame=None
            landmarks=[]
            if demo:
                fired=mouse["fire"]
                mouse["fire"]=False
                signal=HandSignal(True,mouse["x"],mouse["y"],fired,True,False,1.5,"MOUSE")
            else:
                assert cap is not None and tracker is not None
                if first_frame is not None:
                    raw=first_frame
                    first_frame=None
                    valid=True
                else:
                    valid,raw=cap.read()
                if not valid or raw is None:
                    raise RuntimeError("Webcam stopped returning frames. Try camera 1 or close other camera apps.")
                frame=cv2.flip(raw,1)
                landmarks=tracker.detect(frame)
                signal=detector.process(landmarks,now)
            if signal.found:
                lost_at=None
            elif lost_at is None:
                lost_at=now
            tracking=demo or signal.found or (lost_at is not None and now-lost_at<.45)
            # Completely stop clock if tracking is missing (after a brief drop-out tolerance).
            game.update(dt,tracking=tracking)
            if signal.fired and signal.found:
                result=game.shoot(signal.x,signal.y)
                feedback=("HIT!" if result=="hit" else "MISS" if result=="miss" else "")
                feedback_until=now+.60
                blink_until=now+.11
            if game.phase=="results" and not was_result:
                new_record=save_record(game.difficulty,game.score)
                if new_record:
                    records[game.difficulty]=game.score
                print(f"Finished: score={game.score}, hits={game.hits}, accuracy={game.accuracy}%, new_record={new_record}")
            was_result=game.phase=="results"
            preview=camera_preview(frame,landmarks)
            image=draw(game,signal,preview,demo=demo,fire_flash=now<blink_until,
                       paused=not tracking,sensitivity=detector.sensitivity,
                       best_score=int(records.get(game.difficulty,0)),
                       shot_feedback=feedback if now<feedback_until else "")
            cv2.imshow(title,image)
            key=cv2.waitKey(1)&0xff
            if key in (ord('q'),27):
                break
            if key in (ord('r'),ord('R')):
                game.reset()
                detector.reset_trigger()
                was_result=False
            if key in (ord('c'),ord('C')) and not demo:
                ok = detector.calibrate_open()
                pose = "RESTING INDEX" if detector.mode == "INDEX_FLICK" else "OPEN THUMB"
                feedback = "CALIBRATED" if ok else "SHOW " + pose
                feedback_until = now + 1.0
                print("Gesture calibration:", "ok" if ok else "show " + pose.lower())
            if key in (ord('a'),ord('A')):
                print("Aim assist:", game.cycle_assist(), f"(+{game.assist_px} px)")
            if key in (ord('m'),ord('M')):
                detector.switch_mode()
                print("Gesture mode:",detector.mode)
            if key in (ord('['),ord('-')):
                detector.set_sensitivity(+.07)
                print("Easier trigger:",round(detector.sensitivity,2))
            if key in (ord(']'),ord('=')):
                detector.set_sensitivity(-.07)
                print("Harder trigger:",round(detector.sensitivity,2))
            if key in (ord(' '),13) and game.phase=="ready":
                game.start_game()
            if key in (ord('1'),ord('2'),ord('3')):
                level={ord('1'):"easy",ord('2'):"normal",ord('3'):"hard"}[key]
                game=TargetGame(level,assist=game.assist)
                detector.reset_trigger()
                was_result=False
    finally:
        if tracker:
            tracker.close()
        if cap:
            cap.release()
        cv2.destroyAllWindows()


def main():
    p=argparse.ArgumentParser(description="RiG++ Hand Target Shooter")
    p.add_argument("--camera",type=int,default=0,help="webcam index, default 0")
    p.add_argument("--demo",action="store_true",help="no camera: mouse to aim, left click to shoot")
    p.add_argument("--snapshot",type=Path,help="write a game screenshot without webcam")
    p.add_argument("--difficulty",choices=("easy","normal","hard"),default="normal")
    p.add_argument("--mode",choices=("INDEX_FLICK","INDEX_UP","THUMB","PINCH"),default="INDEX_FLICK")
    p.add_argument("--assist",choices=("off","low","normal","high"),default="normal",
                   help="aim assist (normal is default)")
    args=p.parse_args()
    if args.snapshot:
        save_snapshot(args.snapshot,args.difficulty)
    else:
        run(args.demo,args.camera,args.difficulty,args.mode,args.assist)

if __name__=="__main__":
    try:
        main()
    except Exception as error:
        print("\nGAME ERROR:",error,file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
