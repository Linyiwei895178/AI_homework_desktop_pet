import sys
import time
from types import SimpleNamespace

from models.vision.shared_camera import SharedCameraCapture


class _FakeFrame:
    def __init__(self, value):
        self.value = value

    def copy(self):
        return _FakeFrame(self.value)


class _FakeCapture:
    def __init__(self, opened=True):
        self.opened = opened
        self.released = False
        self.read_count = 0

    def isOpened(self):
        return self.opened

    def set(self, *_args):
        return True

    def read(self):
        self.read_count += 1
        return True, _FakeFrame(self.read_count)

    def release(self):
        self.released = True


def test_shared_camera_reads_latest_frame_without_real_camera(monkeypatch):
    capture = _FakeCapture(opened=True)
    fake_cv2 = SimpleNamespace(
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_BUFFERSIZE=5,
        VideoCapture=lambda _index: capture,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    camera = SharedCameraCapture(read_interval=0.01)
    assert camera.start() is True
    try:
        frame = None
        deadline = time.time() + 1.0
        while time.time() < deadline and frame is None:
            frame = camera.get_frame()
            time.sleep(0.01)

        assert frame is not None
        assert frame.value >= 1
        assert camera.last_frame_at() > 0
    finally:
        camera.stop()

    assert capture.released is True


def test_shared_camera_returns_false_when_camera_unavailable(monkeypatch):
    fake_cv2 = SimpleNamespace(
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_BUFFERSIZE=5,
        VideoCapture=lambda _index: _FakeCapture(opened=False),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    camera = SharedCameraCapture()

    assert camera.start() is False
    assert "摄像头无法打开" in camera.last_error()
