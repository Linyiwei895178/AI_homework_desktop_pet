# MediaPipe Tasks 模型说明

Python 3.13 下本项目使用 MediaPipe Tasks API 的 `FaceLandmarker` 做本地人脸关键点检测。

需要手动下载模型文件：

```text
face_landmarker.task
```

放置路径：

```text
models/vision/mediapipe_models/face_landmarker.task
```

不要把 `.task` 模型文件提交到 GitHub。模型文件不存在、Tasks API 不可用或初始化失败时，`UserStateDetector` 会自动降级到 OpenCV Haar + DeepFace + Qwen-VL。

参考：

- https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python
- https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
