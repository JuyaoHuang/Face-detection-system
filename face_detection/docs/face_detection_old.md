# 人脸识别模块开发文档

> 基于 RK3568 平台的 RetinaFace + MobileFaceNet 人脸识别系统完整开发指南

---

我完成了人脸识别模块的全流程开发。现在我要开发后端。我稍后会给你后端的大概设计，我需要你协助我

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 系统架构](#2-系统架构)
- [3. 完整数据流](#3-完整数据流)
- [4. 模型规范](#4-模型规范)
- [5. 核心模块实现](#5-核心模块实现)
- [6. 接口设计](#6-接口设计)
- [7. 编译配置](#7-编译配置)
- [8. 测试与部署](#8-测试与部署)
- [9. 参考资料](#9-参考资料)

---

## 1. 项目概述

### 1.1 项目背景

本项目是 **人脸识别门禁系统** 的核心 AI 模块，运行在 RK3568 开发板上，实现以下功能：

1. **人脸录入**：采集用户人脸，提取 512 维特征向量存入数据库
2. **人脸验证**：实时检测人脸，与数据库中的特征向量比对，实现门禁解锁
3. **双模验证**：支持人脸识别 + 传统密码两种解锁方式

### 1.2 技术选型

| 组件 | 技术方案 | 说明 |
|------|---------|------|
| **硬件平台** | RK3568 开发板 | ARM64 架构，带 NPU 加速器 |
| **摄像头** | OV5695 MIPI 模块 | 分辨率 640×480，BGR 输出 |
| **人脸检测** | RetinaFace RKNN | 输出人脸框 + 5个关键点 |
| **人脸识别** | MobileFaceNet RKNN | 输出 512 维特征向量 |
| **后端服务** | FastAPI (Python) | 提供 Web 管理界面 |
| **AI 引擎** | C++ .so 动态库 | 封装所有 AI 推理逻辑 |
| **数据库** | SQLite | 存储用户信息和特征向量 |

### 1.3 核心优势

- **零拷贝设计**：Python 和 C++ 之间通过指针传递数据，避免内存复制
- **NPU 加速**：RetinaFace 和 MobileFaceNet 均在 NPU 上运行，实时性能优异
- **模块化架构**：C++ 负责计算密集型任务，Python 负责业务逻辑和网络 I/O

---

## 2. 系统架构

### 2.1 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│                   数据输入层 (用户交互)                        │
├──────────────────────────────────────────────────────────────┤
│  - Web 管理界面 (FastAPI + HTML/JS)                           │
│  - OV5695 摄像头采集                                           │
│  - 4x4 矩阵键盘 (密码输入)                                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                   数据处理层 (AI 推理)                         │
├──────────────────────────────────────────────────────────────┤
│  [Python 层]                                                  │
│   - FastAPI 后端 (接收图片、调用 C++ 库)                      │
│   - SQLite 数据库操作                                         │
│   - 特征向量余弦相似度计算                                     │
│                            ↕ ctypes 零拷贝                     │
│  [C++ 层]                                                     │
│   - 图像预处理 (OpenCV: 解码、缩放、颜色转换)                 │
│   - RetinaFace 推理 (RKNN NPU)                                │
│   - 人脸对齐 (OpenCV: 仿射变换)                               │
│   - MobileFaceNet 推理 (RKNN NPU)                             │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                   数据响应层 (执行控制)                        │
├──────────────────────────────────────────────────────────────┤
│  - GPIO 控制门锁 (LED 模拟)                                   │
│  - PWM 控制蜂鸣器                                             │
│  - 访问日志记录                                               │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 模块交互图

```
[FastAPI (Python)] ←─ ctypes ─→ [C++ .so Library] ←─ RKNN API ─→ [NPU Hardware]
        ↓                              ↓                              ↓
    网络 I/O                      AI 推理逻辑                     硬件加速
  (接收JPEG数据)              (预处理+推理+后处理)           (RetinaFace + MobileFaceNet)
```

---

## 3. 完整数据流

### 3.1 数据流动全景图

```
原始 JPEG 字节流 (Python)
    ↓ [Python → C++ 指针传递，零拷贝]
cv::imdecode() → cv::Mat (BGR)
    ↓
cv::resize() → 640×640 (BGR)
    ↓
cv::cvtColor() → 640×640 (RGB)
    ↓
┌─────────────────────────────────────┐
│   RetinaFace RKNN 推理               │
│   输入: 640×640×3, RGB, uint8       │
│   输出: BBox + Landmarks + Scores   │
└─────────────────────────────────────┘
    ↓
后处理 (C++)
    ├─ Anchor 解码
    ├─ 置信度过滤 (CONF_THRESHOLD = 0.5)
    ├─ NMS 去重 (NMS_THRESHOLD = 0.4)
    └─ 输出: retinaface_result
            ├─ box_rect_t (x1, y1, x2, y2)
            ├─ ponit_t[5] (5个关键点)
            └─ float score
    ↓
┌─────────────────────────────────────┐
│   人脸对齐胶水层 (C++ + OpenCV)      │
│   输入: 原图 + 5个关键点             │
│   处理: cv::warpAffine()             │
│   输出: 112×112×3, RGB, uint8       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   MobileFaceNet RKNN 推理            │
│   输入: 112×112×3, RGB, NHWC, uint8 │
│   输出: 512维特征向量 (float32)      │
└─────────────────────────────────────┘
    ↓ [C++ → Python 指针传递]
512维特征向量 (Python)
    ↓
余弦相似度计算 (Python)
    similarity = np.dot(emb1, emb2)
    is_same = similarity > threshold
```

### 3.2 关键数据转换

| 步骤 | 输入 | 输出 | 工具 |
|------|------|------|------|
| **解码** | JPEG 字节流 | cv::Mat (BGR) | cv::imdecode() |
| **缩放** | 任意尺寸 BGR | 640×640 BGR | cv::resize() |
| **颜色转换** | 640×640 BGR | 640×640 RGB | cv::cvtColor() |
| **RetinaFace** | 640×640 RGB | 人脸框 + 5关键点 | RKNN 推理 |
| **人脸对齐** | 原图 + 关键点 | 112×112 RGB | cv::warpAffine() |
| **MobileFaceNet** | 112×112 RGB | 512 维向量 | RKNN 推理 |

---

## 4. 模型规范

### 4.1 RetinaFace 模型

#### 输入规范
```python
{
    'shape': (1, 640, 640, 3),  # NHWC 格式
    'dtype': np.uint8,           # 无符号 8 位整数
    'format': 'NHWC',            # Batch, Height, Width, Channels
    'color': 'RGB',              # 红绿蓝
    'range': [0, 255]            # 原始像素值
}
```

#### 输出规范
```python
{
    'boxes': np.ndarray,      # shape: (N, 4), [x1, y1, x2, y2]
    'landmarks': np.ndarray,  # shape: (N, 5, 2), 5个关键点(x, y)
    'scores': np.ndarray      # shape: (N,), 置信度分数
}
```

#### 5个关键点顺序
```python
landmarks[i] = [
    [x0, y0],  # 0: 左眼中心
    [x1, y1],  # 1: 右眼中心
    [x2, y2],  # 2: 鼻尖
    [x3, y3],  # 3: 左嘴角
    [x4, y4]   # 4: 右嘴角
]
```

### 4.2 MobileFaceNet 模型

#### 输入规范
```python
{
    'shape': (1, 112, 112, 3),
    'dtype': np.uint8,
    'format': 'NHWC',
    'color': 'RGB',
    'range': [0, 255]
}
```

**重要提示**：模型内部会自动执行归一化：
```python
normalized = (pixel - 127.5) / 127.5  # 结果范围: [-1, 1]
```
**不需要手动归一化，直接传入 [0, 255] 的 uint8 图像即可！**

#### 输出规范
```python
{
    'shape': (1, 512),
    'dtype': np.float32,
    'normalized': True,  # L2 归一化（单位向量）
    'range': ~[-1, 1]    # 量化后可能略有偏差
}
```

#### 特征比对
```python
# 余弦相似度（因为已经L2归一化，点积即为余弦相似度）
similarity = np.dot(embedding1, embedding2)

# 阈值参考
# similarity > 0.5  : 高置信度同一人（推荐用于严格场景）
# similarity > 0.4  : 中等置信度
# similarity > 0.3  : 较宽松（推荐用于一般场景）
```

---

## 5. 核心模块实现

### 5.1 关键数据结构

#### RetinaFace 输出结构
```cpp
// 关键点
typedef struct ponit_t {
    int x, y;
} ponit_t;

// 人脸框
typedef struct box_rect_t {
    int left, top, right, bottom;
} box_rect_t;

// 单个人脸检测结果
typedef struct retinaface_object_t {
    int cls;                  // 类别 (通常为0，表示人脸)
    box_rect_t box;          // 人脸框
    float score;             // 置信度分数
    ponit_t ponit[5];        // 5个关键点
} retinaface_object_t;

// 检测结果集合
typedef struct {
    int count;                        // 检测到的人脸数量
    retinaface_object_t object[128];  // 最多128个人脸
} retinaface_result;
```

#### RKNN 上下文结构
```cpp
typedef struct {
    rknn_context rknn_ctx;              // RKNN 上下文句柄
    rknn_input_output_num io_num;       // 输入输出数量
    rknn_tensor_attr *input_attrs;      // 输入张量属性
    rknn_tensor_attr *output_attrs;     // 输出张量属性
    int model_channel;                  // 模型通道数 (3)
    int model_width;                    // 模型宽度 (640 或 112)
    int model_height;                   // 模型高度 (640 或 112)
} rknn_app_context_t;
```

### 5.2 RetinaFace 实现

#### 初始化
```cpp
int init_retinaface_model(const char *model_path, rknn_app_context_t *app_ctx) {
    // 1. 加载模型
    rknn_init(&app_ctx->rknn_ctx, model_path, ...);

    // 2. 查询输入输出信息
    rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_IN_OUT_NUM, &app_ctx->io_num);

    // 3. 获取输入输出属性
    rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_INPUT_ATTR, &app_ctx->input_attrs[0]);
    rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_OUTPUT_ATTR, &app_ctx->output_attrs[i]);

    // 4. 设置模型尺寸
    app_ctx->model_width = 640;
    app_ctx->model_height = 640;
    app_ctx->model_channel = 3;
}
```

#### 推理
```cpp
int inference_retinaface_model(rknn_app_context_t *app_ctx, image_buffer_t *src_img,
                               retinaface_result *out_result) {
    // 1. 预处理：Letterbox + BGR→RGB
    convert_image_with_letterbox(src_img, &img, &letter_box, bg_color=114);

    // 2. 设置输入
    rknn_input inputs[1];
    inputs[0].index = 0;
    inputs[0].type = RKNN_TENSOR_UINT8;
    inputs[0].fmt = RKNN_TENSOR_NHWC;
    inputs[0].size = 640 * 640 * 3;
    inputs[0].buf = img.virt_addr;  // RGB数据
    rknn_inputs_set(app_ctx->rknn_ctx, 1, inputs);

    // 3. 运行推理
    rknn_run(app_ctx->rknn_ctx, nullptr);

    // 4. 获取输出
    rknn_output outputs[3];  // location, scores, landmarks
    outputs[i].want_float = 1;  // 请求浮点输出
    rknn_outputs_get(app_ctx->rknn_ctx, 3, outputs, NULL);

    // 5. 后处理
    post_process_retinaface(app_ctx, src_img, outputs, out_result, &letter_box);

    // 6. 释放输出
    rknn_outputs_release(app_ctx->rknn_ctx, 3, outputs);
}
```

#### 后处理
```cpp
int post_process_retinaface(...) {
    float *location = (float *)outputs[0].buf;  // BBox 回归
    float *scores = (float *)outputs[1].buf;    // 分类分数
    float *landms = (float *)outputs[2].buf;    // 关键点回归

    // 1. 选择 Anchor Priors (根据模型尺寸)
    if (model_height == 640) {
        num_priors = 16800;
        prior_ptr = BOX_PRIORS_640;
    }

    // 2. 过滤有效结果 (置信度 > 0.5)
    int validCount = filterValidResult(scores, location, landms, prior_ptr, ...);

    // 3. 排序 (按置信度从高到低)
    quick_sort_indice_inverse(props, 0, validCount - 1, filter_indice);

    // 4. NMS 去重 (IoU > 0.4 的重叠框)
    nms(validCount, location, filter_indice, NMS_THRESHOLD, width, height);

    // 5. 填充结果
    for (int i = 0; i < validCount; i++) {
        result->object[result->count].box = ...;
        result->object[result->count].ponit[j] = ...;
        result->object[result->count].score = ...;
        result->count++;
    }
}
```

### 5.3 人脸对齐胶水层（关键模块）

#### 参考标准关键点
```cpp
// MobileFaceNet 训练时使用的标准人脸位置 (112×112)
const float REFERENCE_FACIAL_POINTS[5][2] = {
    {38.2946, 51.6963},  // 左眼
    {73.5318, 51.5014},  // 右眼
    {56.0252, 71.7366},  // 鼻尖
    {41.5493, 92.3655},  // 左嘴角
    {70.7299, 92.2041}   // 右嘴角
};
```

#### 仿射变换实现
```cpp
cv::Mat align_face(const cv::Mat& src_img, const ponit_t landmarks[5]) {
    // 1. 准备源关键点 (来自 RetinaFace)
    std::vector<cv::Point2f> src_points;
    for (int i = 0; i < 5; i++) {
        src_points.push_back(cv::Point2f(landmarks[i].x, landmarks[i].y));
    }

    // 2. 准备目标关键点 (标准位置)
    std::vector<cv::Point2f> dst_points;
    for (int i = 0; i < 5; i++) {
        dst_points.push_back(cv::Point2f(REFERENCE_FACIAL_POINTS[i][0],
                                         REFERENCE_FACIAL_POINTS[i][1]));
    }

    // 3. 计算仿射变换矩阵 (相似变换)
    cv::Mat transform_matrix = cv::estimateAffinePartial2D(src_points, dst_points);

    // 4. 执行仿射变换
    cv::Mat aligned_face;
    cv::warpAffine(src_img, aligned_face, transform_matrix, cv::Size(112, 112));

    // 5. BGR → RGB
    cv::cvtColor(aligned_face, aligned_face, cv::COLOR_BGR2RGB);

    return aligned_face;
}
```

**参考实现**：`model_trainning_part/mtcnn_pytorch/src/align_trans.py` 中的 `warp_and_crop_face()` 函数

### 5.4 MobileFaceNet 推理

```cpp
int inference_mobilefacenet(rknn_app_context_t *app_ctx, const cv::Mat& aligned_face,
                            float* embedding_512) {
    // 1. 准备输入 (112×112×3, RGB, uint8)
    rknn_input inputs[1];
    inputs[0].index = 0;
    inputs[0].type = RKNN_TENSOR_UINT8;
    inputs[0].fmt = RKNN_TENSOR_NHWC;
    inputs[0].size = 112 * 112 * 3;
    inputs[0].buf = aligned_face.data;  // 确保是 RGB 格式

    // 2. 设置输入
    rknn_inputs_set(app_ctx->rknn_ctx, 1, inputs);

    // 3. 运行推理
    rknn_run(app_ctx->rknn_ctx, nullptr);

    // 4. 获取输出
    rknn_output outputs[1];
    outputs[0].index = 0;
    outputs[0].want_float = 1;
    rknn_outputs_get(app_ctx->rknn_ctx, 1, outputs, NULL);

    // 5. 拷贝512维特征向量
    memcpy(embedding_512, outputs[0].buf, 512 * sizeof(float));

    // 6. 释放输出
    rknn_outputs_release(app_ctx->rknn_ctx, 1, outputs);

    return 0;
}
```

---

## 6. 接口设计

### 6.1 C++ 类定义

```cpp
class FaceEngine {
private:
    rknn_app_context_t ctx_retinaface;
    rknn_app_context_t ctx_mobilefacenet;

public:
    int init(const char* retinaface_model, const char* mobilefacenet_model);
    int extract_feature(unsigned char* jpeg_data, int data_len, float* feature_512);
    int release();
};
```

### 6.2 导出 C 接口 (供 Python ctypes 调用)

```cpp
extern "C" {
    void* FaceEngine_Create() {
        return new FaceEngine();
    }

    int FaceEngine_Init(void* engine, const char* m1, const char* m2) {
        return ((FaceEngine*)engine)->init(m1, m2);
    }

    int FaceEngine_Extract(void* engine, unsigned char* data, int len, float* out) {
        return ((FaceEngine*)engine)->extract_feature(data, len, out);
    }

    void FaceEngine_Destroy(void* engine) {
        delete (FaceEngine*)engine;
    }
}
```

### 6.3 Python Ctypes 调用示例

```python
import ctypes
import numpy as np

# 加载 .so 库
lib = ctypes.CDLL('./libface_engine.so')

# 定义函数签名
lib.FaceEngine_Create.restype = ctypes.c_void_p
lib.FaceEngine_Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
lib.FaceEngine_Extract.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte),
                                    ctypes.c_int, ctypes.POINTER(ctypes.c_float)]

# 创建引擎
engine = lib.FaceEngine_Create()
lib.FaceEngine_Init(engine, b'retinaface.rknn', b'mobilefacenet.rknn')

# 读取图片
with open('test.jpg', 'rb') as f:
    jpeg_data = f.read()

# 准备输入输出缓冲区
img_array = np.frombuffer(jpeg_data, dtype=np.uint8)
img_ptr = img_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

feature = np.zeros(512, dtype=np.float32)
feat_ptr = feature.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

# 提取特征
ret = lib.FaceEngine_Extract(engine, img_ptr, len(jpeg_data), feat_ptr)

print(f"Feature shape: {feature.shape}")
print(f"Feature norm: {np.linalg.norm(feature):.4f}")

# 释放资源
lib.FaceEngine_Destroy(engine)
```

---

## 7. 编译配置

### 7.1 项目目录结构

```
FaceRecognition_Core/
├── CMakeLists.txt              # [核心] 编译脚本
├── build/                      # [空] 用于存放编译过程文件
├── model/                      # [存放] rknn 模型文件
│   ├── retinaface.rknn
│   └── mobilefacenet.rknn
├── src/                        # [存放] C++ 源文件
│   ├── face_engine.cpp         # 主引擎实现
│   ├── face_aligner.cpp        # 人脸对齐
│   └── retinaface_postprocess.cpp  # RetinaFace 后处理
├── include/                    # [存放] 自己写的头文件
│   ├── face_engine.h
│   ├── face_aligner.h
│   └── common.h
├── 3rdparty/                   # [关键] 第三方依赖库 (随项目携带)
│   ├── rknn/
│   │   ├── include/
│   │   │   └── rknn_api.h      # 从 rknpu2 仓库复制来
│   │   └── lib/
│   │       └── librknnrt.so    # 从 rknpu2/../aarch64/ 复制来
│   └── opencv/
│       ├── include/            # 从 opencv-mobile 复制头文件
│       │   └── opencv2/
│       ├── lib/                # OpenCV 静态库 .a (libopencv_*.a)
│       └── cmake/
│           └── opencv4/
│               └── OpenCVConfig.cmake  # CMake 配置文件
└── test/
    ├── test_api.py             # Python 测试脚本
    └── test_image.jpg
```

**重要说明**：
- **OpenCV 使用静态库**（.a 文件），不是动态库（.so）
- 通过 `find_package(OpenCV)` 自动处理依赖，无需手动链接
- 编译后 `libface_engine.so` 会包含 OpenCV 功能
- **部署优势**：只需传输一个 `.so` 文件到板子，无需额外的 OpenCV 库文件

### 7.2 CMakeLists.txt 关键配置

```cmake
cmake_minimum_required(VERSION 3.10)
project(FaceRecognition_Core)

# 目标平台：RK3568 (ARM64)
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 设置 OpenCV 路径（使用 find_package）
set(OpenCV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/opencv/cmake/opencv4)

# 查找依赖包
find_package(OpenCV REQUIRED)

# 包含目录
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/rknn/include
    ${OpenCV_INCLUDE_DIRS}  # OpenCV 头文件（自动）
)

# 源文件
set(SOURCES
    src/face_engine.cpp
    src/face_aligner.cpp
    src/retinaface_postprocess.cpp
)

# 生成动态库
add_library(face_engine SHARED ${SOURCES})

# 链接库
target_link_libraries(face_engine
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/rknn/lib/librknnrt.so
    ${OpenCV_LIBS}  # OpenCV 静态库（自动）
)

# 安装
install(TARGETS face_engine DESTINATION lib)
```

**关键改进**：
1. **使用 `find_package(OpenCV)`**：自动查找 OpenCV 配置
2. **设置 `OpenCV_DIR`**：指向 `OpenCVConfig.cmake` 所在目录
3. **使用 `${OpenCV_LIBS}`**：自动链接所有需要的 OpenCV 静态库
4. **静态链接**：OpenCV 代码会被编译进 `libface_engine.so`
5. **一键部署**：生成的 `.so` 文件包含所有依赖，无需额外传输 OpenCV 库

### 7.3 编译命令

```bash
# 在 RK3568 上编译（或交叉编译）
cd FaceRecognition_Core
mkdir -p build
cd build
cmake ..
make -j4

# 输出: libface_engine.so（包含 OpenCV 静态库）
```

**编译说明**：
- 使用 `-j4` 并行编译，加快速度
- 生成的 `libface_engine.so` 已包含 OpenCV 的所有功能
- 文件大小会比动态链接版本大（因为包含了 OpenCV 代码）

### 7.4 部署到 RK3568

```bash
# 只需要传输以下文件到板子
FaceRecognition_Core/
├── build/libface_engine.so        # 编译生成的库（已包含 OpenCV）
├── model/
│   ├── retinaface.rknn           # 人脸检测模型
│   └── mobilefacenet.rknn        # 人脸识别模型
└── test/
    └── test_api.py               # 测试脚本

# 板子上只需要 RKNN 运行时库（通常已预装）
# 无需传输 OpenCV 库文件！
```

**部署优势**：
✅ **单文件部署**：只需一个 `.so` 文件，包含所有 OpenCV 功能
✅ **无依赖困扰**：不需要在板子上安装 OpenCV
✅ **版本一致**：避免库版本不匹配问题
✅ **传输便捷**：文件少，传输快

---

## 8. 测试与部署

### 8.1 完整 Pipeline 测试（Python）

```python
import cv2
import numpy as np
from rknnlite.api import RKNNLite

# ===============================
# 步骤1: 人脸检测
# ===============================
def detect_faces(image, retina_face):
    """
    使用RetinaFace检测人脸
    Args:
        image: BGR图像 (OpenCV格式)
    Returns:
        boxes: (N, 4) [x1, y1, x2, y2]
        landmarks: (N, 5, 2) 5个关键点
        scores: (N,) 置信度
    """
    boxes, landmarks, scores = retina_face.detect(image)
    return boxes, landmarks, scores

# ===============================
# 步骤2: 人脸对齐
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
def extract_feature(aligned_face, mobilefacenet):
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
# 步骤4: 人脸比对
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
```

### 8.2 调试技巧

#### 检查输入格式
```python
print(f"Shape: {face_input.shape}")           # 应为 (1, 112, 112, 3)
print(f"Dtype: {face_input.dtype}")           # 应为 uint8
print(f"Range: [{face_input.min()}, {face_input.max()}]")  # 应为 [0, 255]
```

#### 检查输出格式
```python
print(f"Shape: {embedding.shape}")            # 应为 (512,)
print(f"Dtype: {embedding.dtype}")            # 应为 float32
print(f"Range: [{embedding.min():.3f}, {embedding.max():.3f}]")
print(f"Norm: {np.linalg.norm(embedding):.3f}")  # 应约为 1.0
```

#### 可视化对齐结果
```python
import matplotlib.pyplot as plt

# 显示对齐后的人脸
plt.imshow(aligned_rgb)  # RGB格式
plt.title('Aligned Face (112x112)')
plt.axis('off')
plt.show()
```

---

## 9. 参考资料

### 9.1 已实现的示例代码

| 模块 | 路径 | 说明 |
|------|------|------|
| **RetinaFace C++** | `face_detection/examples/RetinaFace/cpp/` | 完整的推理和后处理实现 |
| **MobileFaceNet C++** | `face_detection/examples/mobilenet/cpp/` | 推理封装参考 |
| **人脸对齐 Python** | `model_trainning_part/mtcnn_pytorch/src/align_trans.py` | `warp_and_crop_face()` 函数 |

### 9.2 模型文件

| 模型 | 路径 | 类型 |
|------|------|------|
| **RetinaFace RKNN** | `model/retinaface.rknn` | 人脸检测 |
| **MobileFaceNet RKNN** | `model/mobilefacenet.rknn` | 人脸识别 |

### 9.3 关键阈值参数

| 参数 | 值 | 说明 |
|------|-----|------|
| **CONF_THRESHOLD** | 0.5 | RetinaFace 置信度阈值 |
| **NMS_THRESHOLD** | 0.4 | NMS IoU 阈值 |
| **VIS_THRESHOLD** | 0.4 | 可视化阈值 |
| **FACE_SIMILARITY_THRESHOLD** | 0.3~0.5 | 人脸相似度阈值 |

### 9.4 性能优化要点

- **内存零拷贝**：Python → C++ 使用指针传递，避免数据复制
- **Letterbox vs Resize**：RetinaFace 使用 Letterbox 保持纵横比
- **颜色空间转换**：注意 BGR ↔ RGB 转换时机

---

## 10. 常见问题 FAQ

### Q1: 为什么使用 Letterbox 预处理？
**A**: Letterbox 可以保持图像的纵横比，避免变形导致检测精度下降。

### Q2: 人脸对齐的作用是什么？
**A**: 将不同角度、位置的人脸统一对齐到标准姿态，消除姿态变化对识别的影响。

### Q3: 特征向量为什么要 L2 归一化？
**A**: 归一化后可以直接用点积计算余弦相似度，简化比对逻辑。

### Q4: 相似度阈值如何选择？
**A**:
- 门禁系统（严格）：threshold = 0.5
- 一般应用（平衡）：threshold = 0.3~0.4
- 建议在实际数据上测试调优

### Q5: 如何处理光照变化？
**A**: MobileFaceNet 对光照有一定鲁棒性，但建议在录入时采集不同光照条件下的多张照片。

### Q6: 为什么使用 OpenCV 静态库而不是动态库？
**A**:
- **简化部署**：静态链接后，只需一个 `.so` 文件即可，无需在板子上安装 OpenCV
- **避免版本冲突**：编译时锁定 OpenCV 版本，避免运行时版本不匹配
- **便于传输**：只需传输 `libface_engine.so`，不需要额外的依赖库文件
- **稳定性高**：使用 `find_package(OpenCV)` 自动处理所有依赖，减少人为错误

### Q7: 静态链接会导致 .so 文件过大吗？
**A**: 会的，但是：
- 文件大小通常在 10~20MB 左右（取决于使用的 OpenCV 模块）
- 相比部署便利性和稳定性，这个代价是值得的
- 只需传输一次，后续更新只需更新 `.so` 文件

---

## 11. 开发路线图

- [x] 分析 RetinaFace 示例代码
- [x] 总结数据流动和关键结构
- [ ] 创建 FaceRecognition_Core 项目结构
- [ ] 实现人脸对齐胶水层（cv::warpAffine）
- [ ] 实现 MobileFaceNet 推理封装
- [ ] 整合 FaceEngine 主类
- [ ] 编写 CMakeLists.txt
- [ ] 编写 Python ctypes 测试脚本
- [ ] 在 RK3568 上编译和测试

---

**文档版本**: v1.1
**最后更新**: 2025-12-15
**更新内容**: 更新为使用 OpenCV 静态库（.a）+ find_package 方案
**维护者**: Juyao Huang
