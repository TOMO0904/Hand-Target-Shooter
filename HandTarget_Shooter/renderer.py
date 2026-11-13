"""OpenCV renderer: no remote assets or pygame required."""
from __future__ import annotations
import math
import numpy as np
import cv2
from game_logic import WIDTH, HEIGHT, TargetGame, Target
from gesture import HandSignal

NAVY = (26, 18, 14)
WHITE = (245, 241, 233)
MUTED = (178, 176, 160)
CYAN = (250, 226, 97)
GREEN = (155, 241, 114)
PINK = (166, 106, 255)


def txt(canvas, text, x, y, scale=.60, color=WHITE, thick=1):
    cv2.putText(canvas, str(text), (int(x),int(y)), cv2.FONT_HERSHEY_DUPLEX,
                scale, color, thick, cv2.LINE_AA)


def rect(canvas, x1, y1, x2, y2, fill, stroke=None, width=1):
    cv2.rectangle(canvas,(int(x1),int(y1)),(int(x2),int(y2)),fill,-1)
    if stroke is not None:
        cv2.rectangle(canvas,(int(x1),int(y1)),(int(x2),int(y2)),stroke,width)


def background():
    h,w = HEIGHT, WIDTH
    top = np.array([32,20,16],dtype=np.float32)
    bottom = np.array([57,27,30],dtype=np.float32)
    grad = np.linspace(0,1,h,dtype=np.float32)[:,None,None]
    image = np.broadcast_to(top[None,None,:]*(1-grad)+bottom[None,None,:]*grad,(h,w,3)).copy().astype('uint8')
    for x in range(30,w,56):
        cv2.line(image,(x,230),(x,h-60),(48,39,38),1)
    for y in range(244,h-65,56):
        cv2.line(image,(30,y),(w-30,y),(48,39,38),1)
    rng=np.random.default_rng(2026)
    for x,y in rng.integers([35,255],[1240,600],size=(85,2)):
        cv2.circle(image,(int(x),int(y)),1,(86,67,76),-1)
    cv2.line(image,(30,622),(1250,622),(100,79,65),2)
    return image

BASE = background()


def draw_target(im: np.ndarray, target: Target, assist_px:int=0):
    x,y,r = int(target.x),int(target.y),int(target.radius)
    if assist_px:
        # Visible, faint tolerance ring: this is how far a shot can miss by.
        cv2.circle(im,(x,y),r+9+assist_px,(88,106,94),1,cv2.LINE_AA)
    cv2.circle(im,(x+7,y+9),r+12,(17,14,19),-1,cv2.LINE_AA)
    cv2.circle(im,(x,y),r+13,(95,65,55),5,cv2.LINE_AA)
    cv2.circle(im,(x,y),r+7,(130,179,58),2,cv2.LINE_AA)
    cv2.circle(im,(x,y),r,(193,168,68),-1,cv2.LINE_AA)
    cv2.circle(im,(x,y),int(r*.76),(250,228,104),-1,cv2.LINE_AA)
    cv2.circle(im,(x,y),int(r*.53),(201,156,56),-1,cv2.LINE_AA)
    cv2.circle(im,(x,y),int(r*.28),(250,244,210),-1,cv2.LINE_AA)
    cv2.circle(im,(x,y),int(r*.13),(146,103,80),-1,cv2.LINE_AA)
    for angle in (0,90,180,270):
        a=math.radians(angle)
        xx=int(x+math.cos(a)*(r+17))
        yy=int(y+math.sin(a)*(r+17))
        xx2=int(x+math.cos(a)*(r+30))
        yy2=int(y+math.sin(a)*(r+30))
        cv2.line(im,(xx,yy),(xx2,yy2),(162,205,121),2,cv2.LINE_AA)
    if target.lifetime < 100:
        remaining = max(0,1-target.age/target.lifetime)
        cv2.ellipse(im,(x,y),(r+20,r+20),-90,0,360*remaining,(110,250,185),4,cv2.LINE_AA)


def crosshair(im, x:float,y:float,armed:bool, pressed:bool, found:bool, flashed:bool=False):
    x,y=int(x),int(y)
    color = GREEN if armed else (120,210,255) if found else (80,85,95)
    if pressed:
        color = PINK
    if flashed:
        color = WHITE
    cv2.circle(im,(x,y),24,color,2,cv2.LINE_AA)
    cv2.circle(im,(x,y),4,color,-1,cv2.LINE_AA)
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        cv2.line(im,(x+dx*30,y+dy*30),(x+dx*43,y+dy*43),color,3,cv2.LINE_AA)
    return im


def camera_box(img, preview, found:bool, demo=False):
    x,y=1037,90
    rect(img,x-9,y-31,x+229,y+174,(58,37,30),(116,82,67),2)
    txt(img,"CAMERA / " + ("DEMO" if demo else "LIVE"),x,y-11,.44,CYAN,1)
    if preview is not None:
        hh,ww=preview.shape[:2]
        img[y:y+hh,x:x+ww] = preview
    txt(img,"HAND OK" if found else "HAND NOT FOUND",x,y+163,.41,GREEN if found else (128,180,255),1)


def draw_panel(img,game:TargetGame,signal:HandSignal):
    rect(img,32,104,998,204,(49,32,26),(87,70,62),2)
    if game.phase == "practice":
        txt(img,"TRAINING",52,143,.88,CYAN,2)
        txt(img,f"HIT {game.practice_hits} / 3",55,185,.82,WHITE,2)
        if signal.mode == "INDEX_FLICK":
            txt(img,"MOVE INDEX fingertip to AIM",355,144,.62,WHITE,1)
            txt(img,"Quick INDEX flick = SHOOT (no holding pose)",355,182,.50,MUTED,1)
        elif signal.mode == "THUMB":
            txt(img,"Aim with INDEX fingertip",355,144,.59,WHITE,1)
            txt(img,"Fold THUMB to shoot",355,182,.52,MUTED,1)
        else:
            txt(img,"Aim with INDEX fingertip",355,144,.59,WHITE,1)
            txt(img,"PINCH fingers to shoot",355,182,.52,MUTED,1)
    elif game.phase == "ready":
        txt(img,"TRAINING COMPLETE",52,145,.82,GREEN,2)
        txt(img,"Shoot START or press SPACE",52,182,.6,WHITE,1)
    elif game.phase == "playing":
        txt(img,"SCORE",52,140,.48,MUTED,1)
        txt(img,f"{game.score:05d}",52,184,.95,WHITE,2)
        txt(img,"HITS",270,140,.48,MUTED,1)
        txt(img,f"{game.hits}",270,184,.95,GREEN,2)
        txt(img,"ACCURACY",422,140,.48,MUTED,1)
        txt(img,f"{game.accuracy}%",422,184,.95,WHITE,2)
        txt(img,"COMBO",649,140,.48,MUTED,1)
        txt(img,f"x{game.combo}",649,184,.95,PINK,2)
        txt(img,"TIME",835,140,.48,MUTED,1)
        txt(img,f"{game.time_left:04.1f}",830,184,.86,CYAN,2)
        total = max(1.0,game.cfg['duration'])
        rect(img,32,208,32+int(966*game.time_left/total),214,(96,198,210))
    else:
        txt(img,"SESSION COMPLETE",52,145,.82,CYAN,2)
        txt(img,f"FINAL SCORE: {game.score}   |   HIT RATE: {game.accuracy}%",52,186,.68,WHITE,2)


def draw_footer(img, signal:HandSignal, demo:bool, difficulty:str, paused:bool,
                sensitivity=1.0, assist="normal", assist_px=44, shot_feedback=""):
    rect(img,0,630,WIDTH,HEIGHT,(42,29,26))
    txt(img,f"FIRE {signal.mode}  |  {difficulty.upper()}  |  TRIGGER {sensitivity:.2f}  |  ASSIST {assist.upper()} (+{assist_px}px)",
        25,655,.44,MUTED,1)
    txt(img,"M: FIRE MODE   - / =: TRIGGER   C: CALIBRATE   A: AIM ASSIST   1/2/3: LEVEL   R: RETRY   Q: QUIT",
        25,695,.40,WHITE,1)
    if demo:
        label = "DEMO: MOUSE + CLICK"
    elif paused:
        label = "PAUSED - SHOW HAND"
    elif not signal.found:
        label = "SHOW HAND TO CAMERA"
    elif signal.mode == "INDEX_FLICK":
        label = "QUICK INDEX FLICK TO SHOOT" if signal.armed else "RESET FINGER / WAIT"
    elif signal.mode == "THUMB":
        label = "FOLD THUMB TO FIRE!" if signal.armed else "OPEN THUMB TO ARM"
    else:
        label = "PINCH TO FIRE!" if signal.armed else "SEPARATE FINGERS"
    txt(img,label,790,680,.46,GREEN if signal.armed else CYAN,1)
    if signal.found and not demo:
        label = (f"FLICK {signal.motion_speed:.1f}/s" if signal.mode == "INDEX_FLICK"
                 else f"RATIO {signal.ratio:.2f}")
        txt(img,label,1030,611,.42,PINK if signal.fired else MUTED,1)
    if shot_feedback:
        txt(img,shot_feedback,650,611,.72,GREEN if shot_feedback=="HIT!" else PINK,2)


def draw(game:TargetGame,signal:HandSignal,preview=None,demo=False,fire_flash=False,paused=False,
         sensitivity=1.0,best_score=0,shot_feedback=""):
    im=BASE.copy()
    rect(im,0,0,WIDTH,78,(49,29,22))
    rect(im,30,17,41,65,(121,232,244))
    txt(im,"HAND / TARGET",60,49,1.04,WHITE,2)
    txt(im,"WEBCAM ARCADE",475,48,.49,CYAN,1)
    txt(im,f"DIFFICULTY: {game.difficulty.upper()}",692,49,.55,WHITE,1)
    txt(im,f"BEST {best_score:05d}",1060,48,.51,GREEN,1)
    draw_panel(im,game,signal)
    camera_box(im,preview,signal.found,demo)
    for t in game.targets:
        draw_target(im,t,game.assist_px)
    for p in game.pulses:
        yy = int(p.y-35-p.age*46)
        txt(im,p.text,p.x-36,yy,.62,p.color,2)
    if game.phase == "practice":
        if signal.mode == "INDEX_FLICK":
            txt(im,"STEP 1  MOVE index fingertip steadily to AIM",35,599,.43,MUTED,1)
            txt(im,"STEP 2  QUICKLY flick index UP to SHOOT, then relax.",35,616,.40,MUTED,1)
            txt(im,"A: hit assist  -: easier shot  C: optional resting pose",525,599,.37,CYAN,1)
        else:
            txt(im,"STEP 1  Move your index fingertip to aim",35,599,.43,MUTED,1)
            txt(im,"STEP 2  Fold thumb or pinch, release and repeat",35,616,.40,MUTED,1)
            txt(im,"Outer ring = aim assist. A: change  C: calibrate OPEN hand",525,599,.37,CYAN,1)
    if game.phase == "ready":
        rect(im,340,277,926,558,(60,37,34),(111,96,69),2)
        txt(im,"YOU ARE READY!",424,325,.90,GREEN,2)
        cv2.circle(im,(640,410),85,(134,196,89),4,cv2.LINE_AA)
        cv2.circle(im,(640,410),68,(132,159,60),-1,cv2.LINE_AA)
        txt(im,"START",560,424,1.08,WHITE,2)
        txt(im,"SHOOT HERE  /  SPACE",483,534,.62,WHITE,1)
    if game.phase == "results":
        rect(im,305,252,970,562,(52,37,33),(142,111,85),2)
        txt(im,"TIME UP!",503,316,1.15,CYAN,2)
        txt(im,f"SCORE {game.score:05d}",477,380,.95,WHITE,2)
        txt(im,f"HITS {game.hits}    SHOTS {game.shots}    COMBO {game.best_combo}",390,428,.61,GREEN,1)
        txt(im,"R: PRACTICE AGAIN",450,493,.62,WHITE,2)
        txt(im,f"PERSONAL BEST: {best_score}",476,533,.46,CYAN,1)
    if signal.found:
        crosshair(im,signal.x,signal.y,signal.armed,signal.pressed,True,fire_flash)
    elif not demo and game.phase in ("practice", "ready", "playing"):
        shade=im.copy()
        rect(shade,378,338,887,480,(47,41,35),(117,94,76),2)
        im=cv2.addWeighted(im,.35,shade,.65,0)
        txt(im,"SHOW YOUR HAND",463,399,.76,WHITE,2)
        txt(im,"Time pauses while tracking is lost",421,439,.53,CYAN,1)
    draw_footer(im,signal,demo,game.difficulty,paused,sensitivity,
                game.assist,game.assist_px,shot_feedback)
    return im
