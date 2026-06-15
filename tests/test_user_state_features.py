import os
import sys
from types import SimpleNamespace

import numpy as np


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.user_state_features import (  # noqa: E402
    FRAME_FEATURE_FIELDS,
    USER_STATE_FEATURE_FIELDS,
    WINDOW_FEATURE_FIELDS,
    UserStateFeatureExtractor,
)


def test_feature_extractor_initializes():
    extractor = UserStateFeatureExtractor()

    assert extractor.window_seconds == 3.0
    assert isinstance(extractor.get_window_features(), dict)


def test_empty_frame_without_face_does_not_crash():
    extractor = UserStateFeatureExtractor()

    features = extractor.update(frame=None, face_landmarker_result=None, timestamp=1.0)

    assert isinstance(features, dict)
    assert features["face_missing"] == 1.0
    assert features["face_confidence"] == 0.0
    assert "brightness_mean" in features


def test_window_statistics_output_dict():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    extractor.update(frame=frame, face_landmarker_result=None, timestamp=1.0)
    extractor.update(frame=frame, face_landmarker_result=None, timestamp=2.0)
    stats = extractor.get_window_features()

    assert isinstance(stats, dict)
    assert set(WINDOW_FEATURE_FIELDS) <= set(stats)
    assert stats["recent_duration"] == 1.0
    assert stats["face_missing_ratio"] == 1.0


def test_features_include_required_fields_with_mock_face():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)
    landmarks = _mock_face_landmarks()
    result = SimpleNamespace(face_landmarks=[landmarks], face_blendshapes=[], facial_transformation_matrixes=[])

    features = extractor.update(frame=frame, face_landmarker_result=result, timestamp=1.0)

    assert set(USER_STATE_FEATURE_FIELDS) <= set(features)
    assert set(FRAME_FEATURE_FIELDS) <= set(features)
    assert features["face_missing"] == 0.0
    assert features["face_bbox_area"] > 0.0
    assert features["brightness"] == 120.0


def test_normal_pitch_near_neutral_does_not_count_as_looking_down():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)

    for timestamp in (0.0, 1.0, 2.1, 2.4, 2.7):
        result = SimpleNamespace(
            face_landmarks=[_mock_face_landmarks(chin_y=0.76)],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )
        features = extractor.update(frame=frame, face_landmarker_result=result, timestamp=timestamp)

    assert features["looking_down_ratio"] < 0.2


def test_pitch_delta_over_threshold_increases_looking_down_ratio():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)

    for timestamp in (0.0, 1.0, 2.1):
        neutral = SimpleNamespace(
            face_landmarks=[_mock_face_landmarks(chin_y=0.76)],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )
        extractor.update(frame=frame, face_landmarker_result=neutral, timestamp=timestamp)

    for timestamp in (2.4, 2.7, 3.0):
        looking_down = SimpleNamespace(
            face_landmarks=[_mock_face_landmarks(chin_y=0.94)],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )
        features = extractor.update(frame=frame, face_landmarker_result=looking_down, timestamp=timestamp)

    assert features["looking_down_ratio"] >= 0.3


def test_face_missing_does_not_count_as_looking_down():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)

    for timestamp in (0.0, 1.0, 2.0):
        features = extractor.update(frame=frame, face_landmarker_result=None, timestamp=timestamp)

    assert features["face_missing_ratio"] == 1.0
    assert features["looking_down_ratio"] == 0.0


def test_head_yaw_range_and_looking_side_ratio_are_computed():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)

    for timestamp, nose_x in ((0.0, 0.50), (1.0, 0.50), (2.1, 0.50), (2.4, 0.72), (2.7, 0.28)):
        result = SimpleNamespace(
            face_landmarks=[_mock_face_landmarks(nose_x=nose_x)],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )
        features = extractor.update(frame=frame, face_landmarker_result=result, timestamp=timestamp)

    assert features["head_yaw_min"] < 0.0
    assert features["head_yaw_max"] > 0.0
    assert features["head_yaw_range"] >= 35.0
    assert features["looking_side_ratio"] > 0.0


def test_face_center_x_std_is_computed_from_visible_faces():
    extractor = UserStateFeatureExtractor(window_seconds=3.0)
    frame = np.full((20, 20, 3), 120, dtype=np.uint8)

    for timestamp, x_offset in ((0.0, 0.0), (1.0, 0.04), (2.0, -0.04)):
        result = SimpleNamespace(
            face_landmarks=[_mock_face_landmarks(x_offset=x_offset)],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )
        features = extractor.update(frame=frame, face_landmarker_result=result, timestamp=timestamp)

    assert features["face_center_x_std"] > 0.0


def _mock_face_landmarks(chin_y=0.76, nose_x=0.50, x_offset=0.0):
    points = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(478)]
    for idx, x, y in (
        (1, nose_x, 0.48),
        (13, 0.50, 0.56),
        (14, 0.50, 0.58),
        (33, 0.42, 0.42),
        (61, 0.44, 0.62),
        (105, 0.42, 0.34),
        (133, 0.48, 0.42),
        (144, 0.46, 0.44),
        (152, 0.50, chin_y),
        (158, 0.46, 0.40),
        (159, 0.45, 0.40),
        (160, 0.44, 0.40),
        (234, 0.25, 0.50),
        (263, 0.58, 0.42),
        (291, 0.56, 0.62),
        (334, 0.58, 0.34),
        (362, 0.52, 0.42),
        (373, 0.54, 0.44),
        (380, 0.56, 0.44),
        (385, 0.54, 0.40),
        (386, 0.55, 0.40),
        (387, 0.56, 0.40),
        (454, 0.75, 0.50),
    ):
        points[idx] = SimpleNamespace(x=x + x_offset, y=y, z=0.0)
    return points
