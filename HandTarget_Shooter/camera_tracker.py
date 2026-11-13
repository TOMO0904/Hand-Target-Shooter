"""Windows webcam + MediaPipe Tasks interface; loaded only in camera mode."""
from pathlib import Path
import sys
import time
import cv2
import numpy as np

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),(0,17)
]


def open_camera(camera_id: int):
    if sys.platform == "win32":
        backends = [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "Media Foundation"), (cv2.CAP_ANY, "default")]
    else:
        backends = [(cv2.CAP_ANY, "default")]
    for backend, name in backends:
        cap = cv2.VideoCapture(camera_id, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            ok, image = cap.read()
            if ok and image is not None and image.size:
                print(f"Camera {camera_id} opened using {name}")
                return cap, image
            time.sleep(.08)
        cap.release()
    raise RuntimeError(f"Camera {camera_id} could not start. Close Zoom/Teams, enable camera permission, or choose camera 1.")


class HandTracker:
    def __init__(self, model_path: Path):
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("MediaPipe not installed. Run START_GAME_Windows.bat") from exc
        if not model_path.is_file() or model_path.stat().st_size < 1_000_000:
            raise FileNotFoundError("MediaPipe hand model missing/incomplete. Run download_model.py")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model_path.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=.55,
            min_hand_presence_confidence=.5,
            min_tracking_confidence=.5,
        )
        self.mp = mp
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.start = time.monotonic()
        self.last_ms = -1

    def detect(self, frame_bgr: np.ndarray):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        timestamp = max(self.last_ms+1, int((time.monotonic()-self.start)*1000))
        self.last_ms = timestamp
        results = self.detector.detect_for_video(image, timestamp)
        return results.hand_landmarks[0] if results.hand_landmarks else []

    def close(self):
        self.detector.close()


def camera_preview(frame, landmarks, size=(214, 160)):
    w,h = size
    if frame is None:
        img = np.zeros((h,w,3),dtype=np.uint8)
        cv2.putText(img,"DEMO MODE",(34, h//2),cv2.FONT_HERSHEY_SIMPLEX,.6,(180,230,255),2,cv2.LINE_AA)
        return img
    out = cv2.resize(frame,(w,h))
    p = [(int(l.x*w),int(l.y*h)) for l in landmarks]
    for a,b in HAND_CONNECTIONS:
        if len(p)>max(a,b):
            cv2.line(out,p[a],p[b],(70,240,160),2,cv2.LINE_AA)
    for i in (4,5,8):
        if len(p)>i:
            color = (155,241,114) if i==5 else (100,210,255) if i==8 else (255,180,110)
            cv2.circle(out,p[i],5,color,-1,cv2.LINE_AA)
    return out
