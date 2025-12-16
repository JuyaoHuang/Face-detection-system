# 人脸识别系统架构总结

基于 RetinaFace + MobileFaceNet 的完整数据流动分析

---

## 1. 系统架构

```
[FastAPI (Python)] ←─ ctypes ─→ [C++ .so Library] ←─ RKNN API ─→ [NPU Hardware]
        ↓                              ↓                              ↓
    网络 I/O                      AI 推理逻辑                     硬件加速
  (接收JPEG数据)              (预处理+推理+后处理)           (RetinaFace + MobileFaceNet)
```

---

## 2. 完整数据流程

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

---

## 3. 关键数据结构

### 3.1 RetinaFace 输出结构

```cpp
// 单个人脸检测结果
typedef struct retinaface_object_t {
    int cls;                  // 类别 (通常为0，表示人脸)
    box_rect_t box;          // 人脸框
    float score;             // 置信度分数
    ponit_t ponit[5];        // 5个关键点
} retinaface_object_t;

// 人脸框
typedef struct box_rect_t {
    int left, top, right, bottom;
} box_rect_t;

// 关键点
typedef struct ponit_t {
    int x, y;
} ponit_t;

// 5个关键点顺序：
// ponit[0]: 左眼中心
// ponit[1]: 右眼中心
// ponit[2]: 鼻尖
// ponit[3]: 左嘴角
// ponit[4]: 右嘴角

// 检测结果集合
typedef struct {
    int count;                        // 检测到的人脸数量
    retinaface_object_t object[128];  // 最多128个人脸
} retinaface_result;
```

### 3.2 RKNN 上下文结构

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

---

## 4. RetinaFace 详细流程

### 4.1 初始化

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

### 4.2 推理

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

### 4.3 后处理

```cpp
int post_process_retinaface(...) {
    float *location = (float *)outputs[0].buf;  // BBox 回归
    float *scores = (float *)outputs[1].buf;    // 分类分数
    float *landms = (float *)outputs[2].buf;    // 关键点回归

    // 1. 选择 Anchor Priors (根据模型尺寸)
    if (model_height == 320) {
        num_priors = 4200;
        prior_ptr = BOX_PRIORS_320;
    } else if (model_height == 640) {
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

---

## 5. 人脸对齐胶水层（需实现）

### 5.1 参考标准关键点

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

### 5.2 仿射变换实现

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

    // 5. BGR → RGB (如果需要)
    cv::cvtColor(aligned_face, aligned_face, cv::COLOR_BGR2RGB);

    return aligned_face;
}
```

---

## 6. MobileFaceNet 推理流程（需实现）

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

## 7. 完整 FaceEngine 接口

### 7.1 C++ 类定义

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

### 7.2 导出 C 接口 (供 Python ctypes 调用)

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

---

## 8. Python Ctypes 调用示例

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

## 9. 性能优化要点

### 9.1 内存零拷贝
- Python → C++：使用指针传递，避免数据复制
- C++ 内部：尽量复用缓冲区

### 9.2 Letterbox vs Resize
- RetinaFace：使用 Letterbox（保持纵横比）
- MobileFaceNet：直接 warpAffine（仿射变换已处理变形）

### 9.3 颜色空间转换
```
OpenCV 读取 → BGR
RetinaFace 需要 → RGB (cv::cvtColor)
MobileFaceNet 需要 → RGB (已在对齐时转换)
```

---

## 10. 关键阈值参数

| 参数 | 值 | 说明 |
|------|-----|------|
| CONF_THRESHOLD | 0.5 | RetinaFace 置信度阈值 |
| NMS_THRESHOLD | 0.4 | NMS IoU 阈值 |
| VIS_THRESHOLD | 0.4 | 可视化阈值 |
| FACE_SIMILARITY_THRESHOLD | 0.3~0.5 | 人脸相似度阈值 |

---

## 11. 编译配置要点

### CMakeLists.txt 关键配置

```cmake
# 目标平台：RK3568 (ARM64)
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# 链接库
target_link_libraries(face_engine
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/rknn/lib/librknnrt.so
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/opencv/lib/libopencv_core.so
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/opencv/lib/libopencv_imgproc.so
    ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/opencv/lib/libopencv_imgcodecs.so
)
```

---

## 12. 项目目录结构

```
FaceRecognition_Core/
├── CMakeLists.txt
├── build/
├── model/
│   ├── retinaface.rknn
│   └── mobilefacenet.rknn
├── src/
│   ├── face_engine.cpp
│   ├── face_aligner.cpp
│   └── retinaface_postprocess.cpp
├── include/
│   ├── face_engine.h
│   ├── face_aligner.h
│   └── common.h
├── 3rdparty/
│   ├── rknn/
│   │   ├── include/rknn_api.h
│   │   └── lib/librknnrt.so
│   └── opencv/
│       ├── include/opencv2/
│       └── lib/*.so
└── test/
    ├── test_api.py
    └── test_image.jpg
```

---

## 13. 下一步行动计划

1. ✅ 分析完成
2. ⏭️ 创建项目结构
3. ⏭️ 实现人脸对齐胶水层
4. ⏭️ 整合 RetinaFace + MobileFaceNet
5. ⏭️ 编写 CMakeLists.txt
6. ⏭️ Python 接口测试
7. ⏭️ 性能优化

---

**准备就绪！开始实现！** 🚀

## ToDO

  🎯 下一步：开始实现

  我现在可以为您创建完整的 C++ 项目：

  选项 A：一次性创建完整项目 ⭐ 推荐

  - 创建目录结构
  - 实现所有核心模块（人脸对齐、FaceEngine、接口）
  - 编写 CMakeLists.txt
  - Python 测试脚本

  选项 B：逐步实现

  - 先创建项目结构
  - 再逐个实现模块（可以边实现边讨论）

  选项 C：针对性实现

  - 只实现某个特定模块（比如人脸对齐胶水层）

---
  请告诉我您想要：
  1. 选项 A/B/C？
  2. 是否需要我立即开始创建项目？

[×] 分析 RetinaFace 示例代码
[×] 总结数据流动和关键结构
[ ] 创建 FaceRecognition_Core 项目结构
[ ] 实现人脸对齐胶水层（cv::warpAffine）
[ ] 实现 MobileFaceNet 推理封装
[ ] 整合 FaceEngine 主类
[ ] 编写 CMakeLists.txt
[ ] 编写 Python ctypes 测试脚本
