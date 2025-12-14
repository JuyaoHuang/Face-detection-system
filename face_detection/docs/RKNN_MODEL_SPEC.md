# RKNN MobileFaceNet 模型输入输出规范

## 1. RKNN MobileFaceNet 输入格式

### 输入张量规范
```python
{
    'name': 'input',
    'shape': (1, 112, 112, 3),
    'dtype': np.uint8,
    'format': 'NHWC',
    'color_space': 'RGB',
    'value_range': [0, 255]
}
```

### 详细说明
- **Tensor Name**: `'input'`
- **Shape**: `(1, 112, 112, 3)`
  - `N (batch)`: 1 - 单张图片
  - `H (height)`: 112 像素
  - `W (width)`: 112 像素
  - `C (channels)`: 3 - RGB三通道
- **Data Type**: `np.uint8` (无符号8位整数)
- **Data Format**: `NHWC` (Batch, Height, Width, Channels)
- **Color Space**: RGB (红绿蓝)
- **Value Range**: [0, 255] (原始像素值)

### 预处理（在RKNN模型内部自动完成）
模型内部会自动执行以下归一化：
```python
normalized = (pixel - 127.5) / 127.5  # 结果范围: [-1, 1]
```

**⚠️ 重要**: 不需要手动归一化，直接传入 [0, 255] 的 uint8 图像即可！

---

## 2. RKNN MobileFaceNet 输出格式

### 输出张量规范
```python
{
    'name': 'output',
    'shape': (1, 512),
    'dtype': np.float32,
    'normalized': True  # L2归一化
}
```

### 详细说明
- **Tensor Name**: `'output'`
- **Shape**: `(1, 512)`
  - `N (batch)`: 1
  - `Embedding Dim`: 512 维特征向量
- **Data Type**: `np.float32` (32位浮点数)
- **Value Range**: 约 [-1, 1] (量化后可能略有偏差)
- **Normalization**: L2 归一化（单位向量）

### 特征比对
```python
# 余弦相似度（因为已经L2归一化，点积即为余弦相似度）
similarity = np.dot(embedding1, embedding2)

# 阈值参考
# similarity > 0.5  : 高置信度同一人
# similarity > 0.3  : 可能是同一人
# similarity < 0.3  : 不同人
```

---

## 3. RetinaFace 输出格式

RetinaFace 检测器输出（典型格式）：

```python
{
    'boxes': np.ndarray,      # shape: (N, 4), [x1, y1, x2, y2]
    'landmarks': np.ndarray,  # shape: (N, 5, 2), 5个关键点(x, y)
    'scores': np.ndarray      # shape: (N,), 置信度分数
}
```

### 5个关键点顺序
```python
landmarks[i] = [
    [x0, y0],  # 0: 左眼中心
    [x1, y1],  # 1: 右眼中心
    [x2, y2],  # 2: 鼻尖
    [x3, y3],  # 3: 左嘴角
    [x4, y4]   # 4: 右嘴角
]
```

---

## 4. 胶水代码：RetinaFace → MobileFaceNet

### 完整流程

```python
import cv2
import numpy as np
from rknnlite.api import RKNNLite

# ===============================
# 步骤0: 加载模型
# ===============================
# RetinaFace（假设已加载）
retina_face = ...  # 您的RetinaFace模型

# MobileFaceNet RKNN
mobilefacenet = RKNNLite()
mobilefacenet.load_rknn('mobilefacenet.rknn')
mobilefacenet.init_runtime()


# ===============================
# 步骤1: 人脸检测
# ===============================
def detect_faces(image):
    """
    使用RetinaFace检测人脸

    Args:
        image: BGR图像 (OpenCV格式)

    Returns:
        boxes: (N, 4) [x1, y1, x2, y2]
        landmarks: (N, 5, 2) 5个关键点
        scores: (N,) 置信度
    """
    # RetinaFace检测
    boxes, landmarks, scores = retina_face.detect(image)
    return boxes, landmarks, scores


# ===============================
# 步骤2: 人脸对齐（关键步骤！）
# ===============================
from mtcnn_pytorch.src.align_trans import warp_and_crop_face

def align_face(image, landmarks):
    """
    基于5个关键点对齐人脸到112x112

    Args:
        image: BGR图像 (H, W, 3)
        landmarks: (5, 2) 5个关键点 [[x, y], ...]

    Returns:
        aligned_face: RGB图像 (112, 112, 3), uint8, [0-255]
    """
    # 使用warp_and_crop_face进行对齐
    # crop_size=(112, 112) 输出112x112
    aligned_face = warp_and_crop_face(
        src_img=image,           # BGR图像
        facial_pts=landmarks,    # (5, 2) 关键点
        crop_size=(112, 112)     # 输出尺寸
    )

    # warp_and_crop_face 返回BGR，需要转为RGB
    aligned_face = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)

    return aligned_face


# ===============================
# 步骤3: 特征提取
# ===============================
def extract_feature(aligned_face):
    """
    使用MobileFaceNet提取特征

    Args:
        aligned_face: RGB图像 (112, 112, 3), uint8, [0-255]

    Returns:
        embedding: (512,) 特征向量
    """
    # 添加batch维度: (112, 112, 3) -> (1, 112, 112, 3)
    face_input = np.expand_dims(aligned_face, axis=0)

    # RKNN推理
    outputs = mobilefacenet.inference(inputs=[face_input], data_format='nhwc')

    # 提取特征向量: (1, 512) -> (512,)
    embedding = outputs[0][0]

    # 可选：再次L2归一化（确保单位向量）
    embedding = embedding / np.linalg.norm(embedding)

    return embedding


# ===============================
# 步骤4: 完整Pipeline
# ===============================
def face_recognition_pipeline(image):
    """
    完整的人脸识别流程

    Args:
        image: BGR图像 (OpenCV读取的原始图像)

    Returns:
        embeddings: List[(512,)] 每个人脸的特征向量
        boxes: List[(4,)] 每个人脸的边界框
    """
    # 1. 检测人脸
    boxes, landmarks, scores = detect_faces(image)

    if len(boxes) == 0:
        print("未检测到人脸")
        return [], []

    print(f"检测到 {len(boxes)} 张人脸")

    # 2. 对每个人脸进行对齐和特征提取
    embeddings = []
    valid_boxes = []

    for i, (box, landmark, score) in enumerate(zip(boxes, landmarks, scores)):
        try:
            # 对齐人脸
            aligned_face = align_face(image, landmark)

            # 提取特征
            embedding = extract_feature(aligned_face)

            embeddings.append(embedding)
            valid_boxes.append(box)

            print(f"人脸 {i+1}: 特征提取成功 (置信度: {score:.3f})")

        except Exception as e:
            print(f"人脸 {i+1}: 处理失败 - {e}")
            continue

    return embeddings, valid_boxes


# ===============================
# 步骤5: 人脸比对
# ===============================
def compare_faces(embedding1, embedding2, threshold=0.3):
    """
    比较两个人脸特征

    Args:
        embedding1: (512,) 特征向量1
        embedding2: (512,) 特征向量2
        threshold: 相似度阈值

    Returns:
        is_same: bool 是否同一人
        similarity: float 相似度分数
    """
    # 余弦相似度（点积，因为已L2归一化）
    similarity = np.dot(embedding1, embedding2)

    is_same = similarity > threshold

    return is_same, similarity


# ===============================
# 使用示例
# ===============================
if __name__ == '__main__':
    # 读取图像
    image = cv2.imread('test.jpg')  # BGR格式

    # 执行人脸识别
    embeddings, boxes = face_recognition_pipeline(image)

    # 如果检测到至少2张人脸，比较前两个
    if len(embeddings) >= 2:
        is_same, similarity = compare_faces(embeddings[0], embeddings[1])
        print(f"\n人脸1 vs 人脸2:")
        print(f"  相似度: {similarity:.4f}")
        print(f"  判断: {'同一人' if is_same else '不同人'}")

    # 释放资源
    mobilefacenet.release()
```

---

## 5. 数据格式转换对照表

### RetinaFace输出 → MobileFaceNet输入

| 步骤 | 数据 | 格式 |
|------|------|------|
| RetinaFace输出 | landmarks | (N, 5, 2) float32 |
| ↓ 选择一个人脸 | landmark | (5, 2) float32 |
| ↓ 人脸对齐 | aligned_face | (112, 112, 3) uint8 BGR [0-255] |
| ↓ BGR→RGB | aligned_face | (112, 112, 3) uint8 RGB [0-255] |
| ↓ 添加batch维度 | face_input | (1, 112, 112, 3) uint8 RGB [0-255] |
| MobileFaceNet输入 | ✓ | (1, 112, 112, 3) NHWC uint8 |

### MobileFaceNet输出处理

| 步骤 | 数据 | 格式 |
|------|------|------|
| MobileFaceNet输出 | outputs[0] | (1, 512) float32 |
| ↓ 去除batch维度 | embedding | (512,) float32 |
| ↓ L2归一化（可选） | embedding | (512,) float32, norm=1.0 |
| 用于比对 | ✓ | (512,) float32 |

---

## 6. 关键注意事项

### ⚠️ 颜色空间转换
```python
# RetinaFace检测通常使用BGR图像（OpenCV格式）
image_bgr = cv2.imread('test.jpg')

# align_trans.py 的 warp_and_crop_face 输入BGR，输出也是BGR
aligned_bgr = warp_and_crop_face(image_bgr, landmarks, (112, 112))

# MobileFaceNet RKNN需要RGB
aligned_rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
```

### ⚠️ Batch维度
```python
# RKNN推理必须有batch维度
aligned_rgb.shape         # (112, 112, 3) ❌
face_input.shape          # (1, 112, 112, 3) ✓

face_input = np.expand_dims(aligned_rgb, axis=0)
```

### ⚠️ 数据类型
```python
# 输入必须是uint8
aligned_rgb.dtype         # uint8 ✓
aligned_rgb.dtype         # float32 ❌

# 如果不小心转成了float32
aligned_rgb = aligned_rgb.astype(np.uint8)
```

### ⚠️ 数据格式
```python
# 必须指定NHWC格式
outputs = mobilefacenet.inference(inputs=[face_input], data_format='nhwc')
```

---

## 7. 快速参考

### MobileFaceNet RKNN 输入
```python
{
    'shape': (1, 112, 112, 3),
    'dtype': np.uint8,
    'format': 'NHWC',
    'color': 'RGB',
    'range': [0, 255]
}
```

### MobileFaceNet RKNN 输出
```python
{
    'shape': (1, 512),
    'dtype': np.float32,
    'range': ~[-1, 1],
    'normalized': 'L2'
}
```

### 相似度阈值
```python
similarity > 0.5   # 高置信度（推荐用于严格场景）
similarity > 0.4   # 中等置信度
similarity > 0.3   # 较宽松（推荐用于一般场景）
```

---

## 8. 调试技巧

### 检查输入格式
```python
print(f"Shape: {face_input.shape}")           # 应为 (1, 112, 112, 3)
print(f"Dtype: {face_input.dtype}")           # 应为 uint8
print(f"Range: [{face_input.min()}, {face_input.max()}]")  # 应为 [0, 255]
```

### 检查输出格式
```python
print(f"Shape: {embedding.shape}")            # 应为 (512,)
print(f"Dtype: {embedding.dtype}")            # 应为 float32
print(f"Range: [{embedding.min():.3f}, {embedding.max():.3f}]")
print(f"Norm: {np.linalg.norm(embedding):.3f}")  # 应约为 1.0
```

### 可视化对齐结果
```python
import matplotlib.pyplot as plt

# 显示对齐后的人脸
plt.imshow(aligned_rgb)  # RGB格式
plt.title('Aligned Face (112x112)')
plt.axis('off')
plt.show()
```
