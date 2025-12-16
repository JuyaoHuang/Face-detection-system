# 6. 人脸识别模块的数据流

本文档详细介绍人脸识别模块从原始图片输入到特征向量输出的完整数据流转过程。

---

## 6.1 数据流总览

人脸识别模块的核心数据流包含 **5 个关键阶段**：

```
原始图片 (JPEG/PNG)
    ↓
[阶段1] 图像预处理
    ↓
预处理后的图像 (Mat: BGR, 640×640)
    ↓
[阶段2] RetinaFace 人脸检测
    ↓
人脸框 + 5 个关键点坐标
    ↓
[阶段3] 人脸对齐
    ↓
对齐后的人脸图像 (Mat: RGB, 112×112)
    ↓
[阶段4] MobileFaceNet 特征提取
    ↓
512 维特征向量 (float[512])
    ↓
[阶段5] 特征比对（可选）
    ↓
余弦相似度分数 (float: 0~1)
```

---

## 6.2 阶段 1：图像预处理

### 6.2.1 输入数据

- **数据类型**: `unsigned char*`（原始 JPEG/PNG 二进制数据）
- **来源**:
  - Python 端: `bytes` 对象（通过 `open(image_path, 'rb').read()` 获取）
  - C++ 端: 文件读取或网络传输的二进制流

### 6.2.2 处理步骤

#### 步骤 1: 图像解码

```cpp
// 代码位置: src/utils.cpp
cv::Mat load_image(const unsigned char* jpeg_data, int data_len) {
    // 将二进制数据转换为 cv::Mat
    std::vector<uchar> buf(jpeg_data, jpeg_data + data_len);
    cv::Mat img = cv::imdecode(buf, cv::IMREAD_COLOR);

    if (img.empty()) {
        std::cerr << "[ERROR] Failed to decode image" << std::endl;
        return cv::Mat();
    }
    return img;  // 返回 BGR 格式的 Mat
}
```

**数据变化**:
```
JPEG 字节流 (unsigned char[N])
    ↓
OpenCV Mat 对象 (BGR, 原始尺寸, uint8)
```

#### 步骤 2: 尺寸调整

```cpp
// RetinaFace 模型要求固定输入尺寸 640×640
cv::Mat resized;
cv::resize(img, resized, cv::Size(640, 640));
```

**数据变化**:
```
原始图像 (BGR, H×W×3)
    ↓
调整后图像 (BGR, 640×640×3, uint8)
```

**注意事项**:
- 使用 OpenCV 默认插值方法（双线性插值）
- 会改变图像的宽高比（可能产生拉伸/压缩）
- 像素值范围保持 [0, 255]

#### 步骤 3: 颜色空间转换（针对 RetinaFace）

```cpp
// 某些模型训练时使用 RGB，需要转换
cv::Mat rgb_img;
cv::cvtColor(resized, rgb_img, cv::COLOR_BGR2RGB);
```

**数据变化**:
```
BGR 图像 (640×640×3)
    ↓
RGB 图像 (640×640×3)
```

### 6.2.3 输出数据

- **数据类型**: `cv::Mat`
- **格式**: RGB 或 BGR（取决于模型训练时的设置）
- **尺寸**: 640×640×3
- **数据范围**: [0, 255] (uint8)

---

## 6.3 阶段 2：RetinaFace 人脸检测

### 6.3.1 输入数据准备

#### 步骤 1: 数据归一化

```cpp
// 代码位置: src/face_engine.cpp
void preprocess_for_retinaface(cv::Mat& img, float* input_tensor) {
    int idx = 0;
    for (int c = 0; c < 3; c++) {        // 通道顺序: R, G, B
        for (int h = 0; h < 640; h++) {
            for (int w = 0; w < 640; w++) {
                // 归一化: [0, 255] -> [-1, 1]
                input_tensor[idx++] = (img.at<cv::Vec3b>(h, w)[c] - 127.5) / 128.0;
            }
        }
    }
}
```

**数据变化**:
```
RGB Mat (640×640×3, uint8, [0, 255])
    ↓
浮点数组 (float[3×640×640], [-1, 1])
```

**内存布局**:
```
NCHW 格式: [Batch, Channel, Height, Width]
- Batch = 1
- Channel = 3 (R, G, B)
- Height = 640
- Width = 640
```

#### 步骤 2: RKNN 模型推理

```cpp
// 设置输入
rknn_input inputs[1];
inputs[0].index = 0;
inputs[0].type = RKNN_TENSOR_FLOAT32;
inputs[0].size = 3 * 640 * 640 * sizeof(float);
inputs[0].buf = input_tensor;

// 执行推理
rknn_inputs_set(retinaface_ctx, 1, inputs);
rknn_run(retinaface_ctx, nullptr);

// 获取输出
rknn_output outputs[3];  // RetinaFace 有 3 个输出头
rknn_outputs_get(retinaface_ctx, 3, outputs, nullptr);
```

### 6.3.2 模型输出解析

RetinaFace 模型输出 **3 个张量**（对应不同尺度的特征图）：

| 输出节点 | 形状 | 含义 |
|---------|------|------|
| `output0` | [1, N₁, 15] | 大目标检测分支 |
| `output1` | [1, N₂, 15] | 中目标检测分支 |
| `output2` | [1, N₃, 15] | 小目标检测分支 |

每个检测框的 **15 个通道** 包含：
```
[0:4]   -> 边界框坐标 (x, y, w, h)
[4:14]  -> 5 个关键点坐标 (左眼, 右眼, 鼻尖, 左嘴角, 右嘴角)
          每个点 2 个值 (x, y)
[14]    -> 置信度分数
```

#### 步骤 3: Anchor 解码

```cpp
// 代码位置: src/retinaface_detector.cpp
std::vector<FaceBox> decode_anchors(float* raw_output, int num_anchors) {
    std::vector<FaceBox> boxes;

    for (int i = 0; i < num_anchors; i++) {
        float confidence = raw_output[i * 15 + 14];

        // 过滤低置信度检测
        if (confidence < 0.5) continue;

        // 解码边界框（将相对偏移转换为绝对坐标）
        float cx = (anchors[i].x + raw_output[i * 15 + 0] * anchor_variance) * 640;
        float cy = (anchors[i].y + raw_output[i * 15 + 1] * anchor_variance) * 640;
        float w  = anchors[i].w * exp(raw_output[i * 15 + 2]) * 640;
        float h  = anchors[i].h * exp(raw_output[i * 15 + 3]) * 640;

        // 解码关键点
        std::vector<cv::Point2f> landmarks(5);
        for (int j = 0; j < 5; j++) {
            landmarks[j].x = (anchors[i].x + raw_output[i * 15 + 4 + j*2 + 0] * anchor_variance) * 640;
            landmarks[j].y = (anchors[i].y + raw_output[i * 15 + 4 + j*2 + 1] * anchor_variance) * 640;
        }

        boxes.push_back({cx, cy, w, h, confidence, landmarks});
    }

    return boxes;
}
```

#### 步骤 4: NMS（非极大值抑制）

```cpp
std::vector<FaceBox> nms(std::vector<FaceBox>& boxes, float iou_threshold = 0.4) {
    // 按置信度降序排序
    std::sort(boxes.begin(), boxes.end(),
              [](const FaceBox& a, const FaceBox& b) {
                  return a.confidence > b.confidence;
              });

    std::vector<bool> suppressed(boxes.size(), false);
    std::vector<FaceBox> result;

    for (size_t i = 0; i < boxes.size(); i++) {
        if (suppressed[i]) continue;

        result.push_back(boxes[i]);

        // 抑制与当前框重叠度高的其他框
        for (size_t j = i + 1; j < boxes.size(); j++) {
            if (compute_iou(boxes[i], boxes[j]) > iou_threshold) {
                suppressed[j] = true;
            }
        }
    }

    return result;
}
```

### 6.3.3 输出数据

- **数据类型**: `std::vector<FaceBox>`
- **内容**: 检测到的人脸列表，每个人脸包含：
  - 边界框坐标 `(x, y, w, h)`
  - 5 个关键点 `std::vector<cv::Point2f>(5)`
  - 置信度分数 `float`

**关键点顺序**:
```
landmarks[0] -> 左眼中心
landmarks[1] -> 右眼中心
landmarks[2] -> 鼻尖
landmarks[3] -> 左嘴角
landmarks[4] -> 右嘴角
```

---

## 6.4 阶段 3：人脸对齐

### 6.4.1 目标

将检测到的倾斜人脸图像变换为**正面标准姿态**，为特征提取做准备。

### 6.4.2 处理步骤

#### 步骤 1: 定义标准模板

```cpp
// 代码位置: src/face_alignment.cpp
// MobileFaceNet 训练时使用的标准人脸关键点位置（112×112 图像）
const std::vector<cv::Point2f> STANDARD_LANDMARKS = {
    cv::Point2f(38.2946f, 51.6963f),  // 左眼
    cv::Point2f(73.5318f, 51.5014f),  // 右眼
    cv::Point2f(56.0252f, 71.7366f),  // 鼻尖
    cv::Point2f(41.5493f, 92.3655f),  // 左嘴角
    cv::Point2f(70.7299f, 92.2041f)   // 右嘴角
};
```

#### 步骤 2: 计算仿射变换矩阵

```cpp
cv::Mat align_face(const cv::Mat& img, const std::vector<cv::Point2f>& detected_landmarks) {
    // 使用最小二乘法估计仿射变换矩阵
    cv::Mat transform_matrix = cv::estimateAffinePartial2D(
        detected_landmarks,      // 源点（检测到的关键点）
        STANDARD_LANDMARKS,      // 目标点（标准模板）
        cv::noArray(),
        cv::LMEDS               // 使用 LMedS 算法（更鲁棒）
    );

    // 应用仿射变换
    cv::Mat aligned_face;
    cv::warpAffine(
        img,                    // 输入图像
        aligned_face,           // 输出图像
        transform_matrix,       // 变换矩阵 (2×3)
        cv::Size(112, 112)      // 输出尺寸
    );

    return aligned_face;
}
```

**仿射变换矩阵形式**:
```
[a  b  tx]
[c  d  ty]

其中:
- (a, b, c, d) 控制旋转、缩放、错切
- (tx, ty) 控制平移
```

#### 步骤 3: 颜色空间转换

```cpp
// MobileFaceNet 要求 RGB 输入
cv::Mat rgb_face;
cv::cvtColor(aligned_face, rgb_face, cv::COLOR_BGR2RGB);
```

### 6.4.3 输出数据

- **数据类型**: `cv::Mat`
- **格式**: RGB
- **尺寸**: 112×112×3
- **数据范围**: [0, 255] (uint8)

**数据变化总结**:
```
原始检测人脸 (倾斜, 任意尺寸)
    ↓ 仿射变换
正面对齐人脸 (RGB, 112×112)
```

---

## 6.5 阶段 4：MobileFaceNet 特征提取

### 6.5.1 输入数据准备

```cpp
void preprocess_for_mobilefacenet(const cv::Mat& face, float* input_tensor) {
    int idx = 0;
    for (int c = 0; c < 3; c++) {        // 通道顺序: R, G, B
        for (int h = 0; h < 112; h++) {
            for (int w = 0; w < 112; w++) {
                // 归一化: [0, 255] -> [-1, 1]
                input_tensor[idx++] = (face.at<cv::Vec3b>(h, w)[c] - 127.5) / 128.0;
            }
        }
    }
}
```

**数据变化**:
```
RGB Mat (112×112×3, uint8, [0, 255])
    ↓
浮点数组 (float[3×112×112], [-1, 1])
```

### 6.5.2 RKNN 推理

```cpp
// 设置输入
rknn_input inputs[1];
inputs[0].index = 0;
inputs[0].type = RKNN_TENSOR_FLOAT32;
inputs[0].size = 3 * 112 * 112 * sizeof(float);
inputs[0].buf = input_tensor;

// 执行推理
rknn_inputs_set(mobilefacenet_ctx, 1, inputs);
rknn_run(mobilefacenet_ctx, nullptr);

// 获取输出
rknn_output outputs[1];
outputs[0].want_float = 1;  // 要求输出浮点格式
rknn_outputs_get(mobilefacenet_ctx, 1, outputs, nullptr);
```

### 6.5.3 特征向量后处理

#### 步骤 1: L2 归一化

```cpp
void l2_normalize(float* feature, int dim = 512) {
    // 计算 L2 范数
    float norm = 0.0f;
    for (int i = 0; i < dim; i++) {
        norm += feature[i] * feature[i];
    }
    norm = std::sqrt(norm);

    // 归一化（防止除零）
    if (norm > 1e-6) {
        for (int i = 0; i < dim; i++) {
            feature[i] /= norm;
        }
    }
}
```

**数据变化**:
```
原始特征向量 (float[512], 任意范围)
    ↓ L2 归一化
单位特征向量 (float[512], ||v|| = 1)
```

**L2 归一化的作用**:
- 消除幅度差异，只保留方向信息
- 使余弦相似度计算等价于内积：`cos(θ) = v1 · v2`
- 提高特征比对的鲁棒性

### 6.5.4 输出数据

- **数据类型**: `float[512]`
- **数据范围**: 归一化后每个分量约在 [-0.3, 0.3] 之间
- **向量模长**: ||v|| = 1（单位向量）

---

## 6.6 阶段 5：特征比对（可选）

当需要判断两张人脸是否为同一人时，执行此阶段。

### 6.6.1 余弦相似度计算

```cpp
float compute_cosine_similarity(const float* emb1, const float* emb2, int dim = 512) {
    float dot_product = 0.0f;

    // 计算内积（因为已经 L2 归一化，所以等价于余弦相似度）
    for (int i = 0; i < dim; i++) {
        dot_product += emb1[i] * emb2[i];
    }

    return dot_product;  // 范围: [-1, 1]
}
```

**数学原理**:
```
cos(θ) = (v1 · v2) / (||v1|| × ||v2||)

当 ||v1|| = ||v2|| = 1 时:
cos(θ) = v1 · v2
```

### 6.6.2 相似度阈值判断

```cpp
bool is_same_person(float similarity, float threshold = 0.6) {
    return similarity >= threshold;
}
```

**典型阈值设置**:
- `threshold = 0.5`: 宽松（误识率高，漏检率低）
- `threshold = 0.6`: 平衡（推荐）
- `threshold = 0.7`: 严格（误识率低，漏检率高）

### 6.6.3 输出数据

- **数据类型**: `float`
- **数据范围**: [-1, 1]
  - `1.0`: 完全相同（同一张照片）
  - `0.6~0.9`: 极可能是同一人
  - `0.4~0.6`: 不确定
  - `< 0.4`: 不是同一人

---

## 6.7 完整数据流示例（Python 端调用）

```python
from face_engine import get_face_engine

# 初始化引擎
engine = get_face_engine()

# 读取图片
with open("person1.jpg", "rb") as f:
    img1_bytes = f.read()

with open("person2.jpg", "rb") as f:
    img2_bytes = f.read()

# 提取特征（内部完成阶段 1-4）
feature1 = engine.extract_feature(img1_bytes)  # List[float], len=512
feature2 = engine.extract_feature(img2_bytes)

# 特征比对（阶段 5）
if feature1 and feature2:
    similarity = engine.compute_similarity(feature1, feature2)
    print(f"相似度: {similarity:.4f}")

    if similarity >= 0.6:
        print("✓ 是同一人")
    else:
        print("✗ 不是同一人")
else:
    print("错误: 未检测到人脸")
```

**数据流追踪**:
```
person1.jpg (文件)
    ↓ open().read()
bytes 对象 (Python)
    ↓ ctypes 传递
unsigned char* (C++)
    ↓ 阶段1: 解码 + 调整尺寸
cv::Mat (640×640×3)
    ↓ 阶段2: RetinaFace
FaceBox (边界框 + 5关键点)
    ↓ 阶段3: 人脸对齐
cv::Mat (112×112×3, 正面)
    ↓ 阶段4: MobileFaceNet
float[512] (特征向量)
    ↓ ctypes 返回
List[float] (Python)
```

---

## 6.8 关键数据结构定义

### 6.8.1 FaceBox 结构体

```cpp
// 代码位置: include/face_engine.h
struct FaceBox {
    float x, y, w, h;                    // 边界框 (中心坐标 + 宽高)
    float confidence;                     // 置信度 [0, 1]
    std::vector<cv::Point2f> landmarks;   // 5 个关键点
};
```

### 6.8.2 C 接口函数签名

```cpp
// 特征提取函数
int FaceEngine_ExtractFeature(
    void* engine,               // 引擎实例指针
    unsigned char* jpeg_data,   // 输入: JPEG 二进制数据
    int data_len,               // 输入: 数据长度
    float* feature_512          // 输出: 512 维特征向量
);

// 返回值:
//   0  -> 成功
//  -1  -> 未检测到人脸
//  -2  -> 图像解码失败
//  -3  -> 模型推理失败
```

### 6.8.3 Python 端数据类型映射

```python
import ctypes
import numpy as np

# C++ -> Python 类型映射
self.lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
self.lib.FaceEngine_ExtractFeature.argtypes = [
    ctypes.c_void_p,                   # void* engine
    ctypes.POINTER(ctypes.c_ubyte),    # unsigned char*
    ctypes.c_int,                      # int data_len
    ctypes.POINTER(ctypes.c_float)     # float* feature_512
]

# 使用示例
jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

feature_512 = np.zeros(512, dtype=np.float32)
feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

ret = self.lib.FaceEngine_ExtractFeature(
    self.engine_ptr, jpeg_ptr, len(image_bytes), feature_ptr
)
```

---

## 6.9 性能特征

### 6.9.1 内存占用

| 阶段 | 内存分配 | 大小 |
|------|---------|------|
| 图像预处理 | cv::Mat (640×640) | ~1.2 MB |
| RetinaFace 输入 | float[3×640×640] | ~4.7 MB |
| RetinaFace 输出 | float[N×15] | < 0.1 MB |
| 人脸对齐 | cv::Mat (112×112) | ~0.04 MB |
| MobileFaceNet 输入 | float[3×112×112] | ~0.15 MB |
| MobileFaceNet 输出 | float[512] | 2 KB |

**峰值内存**: 约 6~7 MB（单张图片处理）

### 6.9.2 处理时间（RK3568 板子实测）

| 阶段 | 耗时 | 占比 |
|------|------|------|
| 图像解码 + 预处理 | ~20 ms | 15% |
| RetinaFace 推理 | ~60 ms | 45% |
| 人脸对齐 | ~5 ms | 4% |
| MobileFaceNet 推理 | ~40 ms | 30% |
| 特征比对 | < 1 ms | < 1% |
| **总计** | **~125 ms** | **100%** |

**备注**: 时间会因图片尺寸、人脸数量而波动。

---

## 6.10 数据流优化要点

### 6.10.1 零拷贝传输

Python 端使用 `numpy` 和 `ctypes` 实现零拷贝数据传递：

```python
# ✓ 零拷贝（推荐）
jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

# ✗ 有拷贝（避免）
jpeg_list = list(image_bytes)  # 会创建新的 Python list
```

### 6.10.2 内存复用

```cpp
// C++ 端可以复用缓冲区
class FaceEngine {
private:
    float* retinaface_input_buffer;   // 预分配 3×640×640
    float* mobilefacenet_input_buffer; // 预分配 3×112×112

public:
    FaceEngine() {
        // 构造函数中一次性分配
        retinaface_input_buffer = new float[3 * 640 * 640];
        mobilefacenet_input_buffer = new float[3 * 112 * 112];
    }

    ~FaceEngine() {
        delete[] retinaface_input_buffer;
        delete[] mobilefacenet_input_buffer;
    }
};
```

### 6.10.3 批处理优化（未实现）

当前实现是单张图片处理，可扩展为批处理：

```cpp
// 伪代码：批量处理 N 张人脸
std::vector<float*> batch_features;
for (const auto& face_box : detected_faces) {
    cv::Mat aligned = align_face(img, face_box.landmarks);
    float* feature = extract_feature(aligned);
    batch_features.push_back(feature);
}
```

---

## 6.11 常见问题与数据流故障排查

### 问题 1: 特征提取返回 -1（未检测到人脸）

**可能原因**:
1. 图片中确实没有人脸
2. 人脸太小（< 40×40 像素）
3. 人脸角度过大（侧脸 > 60°）
4. 图像质量太差（模糊、过曝）

**调试方法**:
```cpp
// 在 RetinaFace 输出后打印检测结果
std::cout << "检测到 " << face_boxes.size() << " 个人脸" << std::endl;
for (const auto& box : face_boxes) {
    std::cout << "  置信度: " << box.confidence << std::endl;
}
```

### 问题 2: 相似度异常低（明明是同一人却 < 0.3）

**可能原因**:
1. 人脸对齐失败（关键点检测不准）
2. 模型文件损坏
3. L2 归一化未执行

**调试方法**:
```cpp
// 检查特征向量的模长
float norm = 0.0f;
for (int i = 0; i < 512; i++) {
    norm += feature[i] * feature[i];
}
std::cout << "特征向量模长: " << std::sqrt(norm) << std::endl;
// 应该接近 1.0
```

### 问题 3: 内存泄漏

**检查点**:
```cpp
// 确保 RKNN 输出被正确释放
rknn_outputs_get(ctx, num_outputs, outputs, nullptr);
// ... 使用 outputs ...
rknn_outputs_release(ctx, num_outputs, outputs);  // 必须调用！
```

---

## 6.12 总结

本文档详细介绍了人脸识别模块的完整数据流，关键要点：

1. **5 大阶段**: 预处理 → 检测 → 对齐 → 提取 → 比对
2. **数据格式变化**: JPEG bytes → Mat → float[] → 512-dim vector
3. **关键技术**:
   - RetinaFace: Anchor-based 多尺度检测
   - MobileFaceNet: 轻量级特征提取
   - 仿射变换: 人脸对齐核心
   - L2 归一化: 特征标准化
4. **性能**: 单张图片约 125ms（RK3568）
5. **Python-C++ 接口**: 通过 ctypes 实现零拷贝传输

**下一步**: 参阅 `流节点输入输出格式.md` 了解每个函数的详细接口定义。
