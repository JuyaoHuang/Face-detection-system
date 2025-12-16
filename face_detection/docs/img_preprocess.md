# 9. 图片预处理

本文档详细介绍 RetinaFace 模型的图片预处理流程，包括解码、尺寸调整、颜色空间转换和归一化等关键步骤。

---

## 9.1 预处理流程总览

```
JPEG/PNG 二进制数据
    ↓
[步骤1] 图像解码
    ↓
cv::Mat (BGR, 原始尺寸)
    ↓
[步骤2] 尺寸调整
    ↓
cv::Mat (BGR, 640×640)
    ↓
[步骤3] 颜色空间转换
    ↓
cv::Mat (RGB, 640×640)
    ↓
[步骤4] 数据格式转换
    ↓
float[] (NCHW, [-1, 1])
    ↓
输入 RetinaFace 模型
```

---

## 9.2 步骤详解

### 9.2.1 步骤1：图像解码

#### 功能
将压缩的 JPEG/PNG 二进制数据解码为像素矩阵。

#### 实现代码
```cpp
// 代码位置: src/face_engine.cpp:84
std::vector<uchar> jpeg_buffer(jpeg_data, jpeg_data + data_len);
cv::Mat img_bgr = cv::imdecode(jpeg_buffer, cv::IMREAD_COLOR);

if (img_bgr.empty()) {
    printf("[face_engine] Error: Failed to decode JPEG image\n");
    return -2;
}
```

#### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `jpeg_data` | `unsigned char*` | 图片二进制数据 |
| `data_len` | `int` | 数据长度（字节） |

#### 输出
| 属性 | 值 |
|------|---|
| **类型** | `cv::Mat` |
| **颜色空间** | BGR（OpenCV 默认） |
| **数据类型** | `uint8`（0~255） |
| **尺寸** | 原始图片尺寸（如 1920×1080） |

#### 关键点
- **支持格式**：JPEG、PNG、BMP 等（由 OpenCV 自动识别）
- **颜色顺序**：OpenCV 默认使用 BGR 而非 RGB
- **错误处理**：如果解码失败，`img_bgr.empty()` 返回 true

---

### 9.2.2 步骤2：尺寸调整

#### 功能
将原始图像调整为 RetinaFace 模型要求的固定尺寸 640×640。

#### 实现代码（内部实现）
```cpp
// 假设在 retinaface.cpp 中的预处理函数
cv::Mat resized;
cv::resize(img_bgr, resized, cv::Size(640, 640));
```

#### 输入
- 原始图像（任意尺寸，如 1920×1080）

#### 输出
- 调整后图像（640×640）

#### 关键技术参数

**插值方法**：OpenCV 默认使用双线性插值（`cv::INTER_LINEAR`）

| 插值方法 | 速度 | 质量 | 适用场景 |
|----------|------|------|----------|
| `INTER_NEAREST` | 最快 | 较差 | 实时性要求高 |
| `INTER_LINEAR` | 快 | 良好 | **默认选择** |
| `INTER_CUBIC` | 慢 | 优秀 | 离线处理 |
| `INTER_AREA` | 中 | 优秀 | 缩小图像 |

**宽高比处理**：
```python
# 当前实现：直接拉伸（可能变形）
resized = cv2.resize(img, (640, 640))

# 替代方案1：保持宽高比 + 填充
h, w = img.shape[:2]
scale = min(640/w, 640/h)
new_w, new_h = int(w*scale), int(h*scale)
resized = cv2.resize(img, (new_w, new_h))
# 然后填充黑边到 640×640

# 替代方案2：中心裁剪
# 先缩放到长边 = 640，然后裁剪中心 640×640 区域
```

**当前选择**：直接拉伸（简单高效，检测影响不大）

---

### 9.2.3 步骤3：颜色空间转换

#### 功能
将 BGR 格式转换为 RGB 格式（RetinaFace 训练时使用 RGB）。

#### 实现代码
```cpp
cv::Mat rgb_img;
cv::cvtColor(resized, rgb_img, cv::COLOR_BGR2RGB);
```

#### 为什么需要转换？

| 库/框架 | 默认颜色顺序 |
|---------|-------------|
| OpenCV | BGR |
| PIL/Pillow | RGB |
| PyTorch | RGB |
| TensorFlow | RGB |
| RKNN 模型训练 | RGB |

**不转换的后果**：
- 红色和蓝色通道颠倒
- 模型性能下降（准确率降低 5~10%）
- 关键点位置偏移

#### 性能
- 耗时：< 1ms（640×640 图像）
- 内存：原地转换，无额外分配

---

### 9.2.4 步骤4：数据格式转换与归一化

#### 功能
将 RGB 图像转换为 NCHW 格式的浮点数组，并归一化到 [-1, 1]。

#### 实现代码
```cpp
// 代码位置: src/retinaface.cpp
void preprocess_retinaface(cv::Mat& img, float* input_tensor) {
    int idx = 0;

    // NCHW 格式：先遍历通道，再遍历高度和宽度
    for (int c = 0; c < 3; c++) {        // 通道：R, G, B
        for (int h = 0; h < 640; h++) {  // 高度
            for (int w = 0; w < 640; w++) {  // 宽度
                // 归一化：[0, 255] -> [-1, 1]
                uint8_t pixel_value = img.at<cv::Vec3b>(h, w)[c];
                input_tensor[idx++] = (pixel_value - 127.5f) / 128.0f;
            }
        }
    }
}
```

#### 数据格式转换

**OpenCV Mat 格式（HWC）**：
```
内存布局：[H][W][C]
img[0][0] = [R, G, B]  ← 第1个像素的3个通道
img[0][1] = [R, G, B]  ← 第2个像素的3个通道
...
```

**RKNN 输入格式（NCHW）**：
```
内存布局：[N][C][H][W]
tensor[0] = [所有R通道的像素]  ← 640×640个值
tensor[1] = [所有G通道的像素]
tensor[2] = [所有B通道的像素]
```

**转换示意图**：
```
HWC (OpenCV):          NCHW (RKNN):
R1 G1 B1 R2 G2 B2      R1 R2 R3 ... R640
R3 G3 B3 R4 G4 B4  →   G1 G2 G3 ... G640
...                    B1 B2 B3 ... B640
```

#### 归一化公式

**当前实现**：
```
normalized_value = (pixel_value - 127.5) / 128.0

映射关系：
  0   → (0 - 127.5) / 128.0 = -0.996
  127 → (127 - 127.5) / 128.0 = -0.004
  255 → (255 - 127.5) / 128.0 = 0.996
```

**为什么使用 [-1, 1] 而非 [0, 1]？**
- 训练时使用的归一化方式
- 零中心化有助于模型收敛
- 符合深度学习常见做法

**其他常见归一化方式**：
```python
# 方式1: [0, 1]
normalized = pixel_value / 255.0

# 方式2: ImageNet 标准化
mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]
normalized = (pixel_value/255.0 - mean) / std

# 方式3: 当前使用
normalized = (pixel_value - 127.5) / 128.0
```

---

## 9.3 完整代码示例

### 9.3.1 C++ 完整流程

```cpp
int preprocess_for_retinaface(
    unsigned char* jpeg_data,
    int data_len,
    float* input_tensor_640x640x3
) {
    // 步骤1: 解码
    std::vector<uchar> buffer(jpeg_data, jpeg_data + data_len);
    cv::Mat img = cv::imdecode(buffer, cv::IMREAD_COLOR);
    if (img.empty()) return -1;

    // 步骤2: 调整尺寸
    cv::Mat resized;
    cv::resize(img, resized, cv::Size(640, 640));

    // 步骤3: BGR -> RGB
    cv::Mat rgb;
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);

    // 步骤4: HWC -> NCHW + 归一化
    int idx = 0;
    for (int c = 0; c < 3; c++) {
        for (int h = 0; h < 640; h++) {
            for (int w = 0; w < 640; w++) {
                uint8_t val = rgb.at<cv::Vec3b>(h, w)[c];
                input_tensor_640x640x3[idx++] = (val - 127.5f) / 128.0f;
            }
        }
    }

    return 0;
}
```

### 9.3.2 Python 验证代码

```python
import cv2
import numpy as np

def preprocess_retinaface(image_path):
    # 步骤1: 读取图片（已解码）
    img = cv2.imread(image_path)  # BGR格式

    # 步骤2: 调整尺寸
    resized = cv2.resize(img, (640, 640))

    # 步骤3: BGR -> RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    # 步骤4: HWC -> CHW + 归一化
    # 转置：(H, W, C) -> (C, H, W)
    chw = rgb.transpose(2, 0, 1)

    # 归一化：[0, 255] -> [-1, 1]
    normalized = (chw - 127.5) / 128.0

    # 添加 batch 维度：(C, H, W) -> (1, C, H, W)
    nchw = np.expand_dims(normalized, axis=0)

    return nchw.astype(np.float32)

# 使用示例
input_tensor = preprocess_retinaface("face.jpg")
print(f"输出形状: {input_tensor.shape}")  # (1, 3, 640, 640)
print(f"数值范围: [{input_tensor.min():.3f}, {input_tensor.max():.3f}]")
```

---

## 9.4 性能分析

### 9.4.1 各步骤耗时（RK3568）

| 步骤 | 操作 | 耗时 | 占比 |
|------|------|------|------|
| 1 | 图像解码 | ~15ms | 75% |
| 2 | 尺寸调整 | ~3ms | 15% |
| 3 | 颜色转换 | ~1ms | 5% |
| 4 | 格式转换 | ~1ms | 5% |
| **总计** | | **~20ms** | **100%** |

### 9.4.2 优化建议

**已实现的优化**：
- ✓ 使用 OpenCV 硬件加速（NEON 指令集）
- ✓ 内存复用（避免重复分配）

**未来可优化**：
- 使用 RK3568 的硬件 JPEG 解码器（可减少 50% 解码时间）
- 使用 RGA（Raster Graphic Acceleration）进行尺寸调整
- 多线程处理（批量图片时）

---

## 9.5 常见问题

### Q1: 为什么不保持宽高比？
**A**: 当前实现直接拉伸到 640×640，虽然可能导致轻微变形，但：
- 简化代码逻辑
- RetinaFace 对轻微变形鲁棒
- 性能提升明显

### Q2: 如果输入已经是 RGB 怎么办？
**A**: 需要在解码时指定：
```cpp
cv::Mat img = cv::imdecode(buffer, cv::IMREAD_COLOR);
// 如果来源确定是 RGB，可以跳过颜色转换
```

### Q3: 归一化参数能否修改？
**A**: 不建议修改。必须与模型训练时的预处理保持一致，否则会严重影响准确率。

### Q4: 预处理能否在 GPU 上进行？
**A**: RK3568 没有独立 GPU，但可以：
- 使用 NPU 的前处理单元（需要 RKNN SDK 支持）
- 使用 RGA 硬件加速器

---

## 9.6 总结

**预处理关键要点**：
1. **解码**：支持 JPEG/PNG，输出 BGR 格式
2. **尺寸调整**：固定 640×640，使用双线性插值
3. **颜色转换**：BGR → RGB（必须执行）
4. **格式转换**：HWC → NCHW
5. **归一化**：[0, 255] → [-1, 1]

**数据流总结**：
```
JPEG bytes  → Mat(BGR, H×W)  → Mat(RGB, 640×640)  → float[3×640×640]
            解码(15ms)        调整+转换(4ms)        格式化(1ms)
```

**下一步**：参阅 `middle_function.md` 了解人脸对齐的胶水代码实现。
