# 7. 流节点输入输出格式

本文档详细定义人脸识别模块各个节点的输入输出格式，包括 C API 接口、Python ctypes 接口、数据结构规范以及错误码说明。

---

## 7.1 API 层级架构 

人脸识别模块提供三层 API 接口：

```
┌─────────────────────────────────────────┐
│   Python API (face_engine.py)          │  ← 最高层：FastAPI 后端使用
│   - 面向对象封装                         │
│   - 自动内存管理                         │
│   - 异常处理                             │
└─────────────────────────────────────────┘
                 ↓ ctypes
┌─────────────────────────────────────────┐
│   C Export API (extern "C")            │  ← 中间层：Python 调用入口
│   - FaceEngine_Create()                │
│   - FaceEngine_Init()                  │
│   - FaceEngine_ExtractFeature()        │
│   - FaceEngine_CosineSimilarity()      │
│   - FaceEngine_Destroy()               │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│   C++ Internal API                     │  ← 底层：实际实现逻辑
│   - face_engine_init()                 │
│   - inference_retinaface_model()       │
│   - align_face()                       │
│   - inference_mobilefacenet_model()    │
└─────────────────────────────────────────┘
```

---

## 7.2 C Export API 详细规范

### 7.2.1 `FaceEngine_Create` - 创建引擎实例

#### 函数签名
```c
void* FaceEngine_Create();
```

#### 输入参数
- **无参数**

#### 输出返回值
| 类型 | 说明 |
|------|------|
| `void*` | 成功：返回 `face_engine_t*` 指针（不透明句柄） |
| `NULL` | 失败：内存分配失败 |

#### 内存管理
- **分配方式**: 使用 `malloc()` 在堆上分配
- **释放方式**: 必须调用 `FaceEngine_Destroy()` 释放

#### 示例代码
```c
// C 端调用
void* engine = FaceEngine_Create();
if (!engine) {
    fprintf(stderr, "Failed to create engine\n");
    return -1;
}
```

```python
# Python 端调用
self.lib.FaceEngine_Create.restype = ctypes.c_void_p
self.lib.FaceEngine_Create.argtypes = []

engine_ptr = self.lib.FaceEngine_Create()
if not engine_ptr:
    raise RuntimeError("Failed to create FaceEngine instance")
```

---

### 7.2.2 `FaceEngine_Init` - 初始化引擎

#### 函数签名
```c
int FaceEngine_Init(
    void* engine,
    const char* retinaface_model,
    const char* mobilefacenet_model
);
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `engine` | `void*` | ✓ | 引擎实例指针（由 `FaceEngine_Create()` 返回） |
| `retinaface_model` | `const char*` | ✓ | RetinaFace 模型文件绝对路径（`.rknn` 格式） |
| `mobilefacenet_model` | `const char*` | ✓ | MobileFaceNet 模型文件绝对路径（`.rknn` 格式） |

**参数约束**:
- 模型路径必须是绝对路径（例如 `/userdata/models/RetinaFace.rknn`）
- 文件必须存在且可读
- 编码必须是 UTF-8

#### 输出返回值

| 返回值 | 含义 |
|--------|------|
| `0` | 成功初始化 |
| `-1` | 失败：参数为 `NULL` 或模型加载失败 |

#### 副作用
- 在内部加载 RKNN 模型到 NPU
- 分配模型推理所需的内存
- 初始化引擎状态为 `is_initialized = 1`

#### 示例代码
```c
// C 端调用
int ret = FaceEngine_Init(
    engine,
    "/userdata/models/RetinaFace.rknn",
    "/userdata/models/mobilefacenet.rknn"
);

if (ret != 0) {
    fprintf(stderr, "Failed to initialize engine\n");
    FaceEngine_Destroy(engine);
    return -1;
}
```

```python
# Python 端调用
self.lib.FaceEngine_Init.restype = ctypes.c_int
self.lib.FaceEngine_Init.argtypes = [
    ctypes.c_void_p,    # void* engine
    ctypes.c_char_p,    # const char* retinaface_model
    ctypes.c_char_p     # const char* mobilefacenet_model
]

ret = self.lib.FaceEngine_Init(
    self.engine_ptr,
    str(retinaface_model).encode('utf-8'),
    str(mobilefacenet_model).encode('utf-8')
)

if ret != 0:
    raise RuntimeError(f"Failed to initialize FaceEngine (ret={ret})")
```

---

### 7.2.3 `FaceEngine_ExtractFeature` - 提取特征向量（核心函数）

#### 函数签名
```c
int FaceEngine_ExtractFeature(
    void* engine,
    unsigned char* jpeg_data,
    int data_len,
    float* feature_512
);
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `engine` | `void*` | ✓ | 引擎实例指针 |
| `jpeg_data` | `unsigned char*` | ✓ | 图片二进制数据（JPEG/PNG 格式） |
| `data_len` | `int` | ✓ | 数据长度（字节数），必须 > 0 |
| `feature_512` | `float*` | ✓ | 输出缓冲区，用于存储 512 维特征向量 |

**参数详细说明**:

##### `jpeg_data` - 图片数据
- **支持格式**: JPEG、PNG
- **颜色空间**: RGB 或 BGR（OpenCV 会自动解码）
- **尺寸要求**: 无限制（内部会调整为 640×640）
- **内存布局**: 连续内存块
- **示例**:
  ```python
  # Python 端读取图片
  with open("face.jpg", "rb") as f:
      image_bytes = f.read()  # bytes 对象
  ```

##### `data_len` - 数据长度
- 必须等于 `jpeg_data` 的实际字节数
- 范围: `1 ~ 10MB`（建议）

##### `feature_512` - 输出缓冲区
- **类型**: 浮点数组
- **长度**: 必须预先分配 512 个 `float`（2048 字节）
- **数据范围**: 每个分量约在 `[-0.3, 0.3]` 之间（L2 归一化后）
- **向量模长**: `||v|| ≈ 1.0`

#### 输出返回值

| 返回值 | 含义 | 后续处理 |
|--------|------|----------|
| `0` | 成功：`feature_512` 包含有效特征向量 | 可进行特征比对 |
| `-1` | 失败：未检测到人脸 | 重新拍照或换图片 |
| `-2` | 失败：其他错误（图像解码失败、模型推理失败、引擎未初始化） | 检查日志排查问题 |

#### 副作用
- 在 `feature_512` 缓冲区写入 512 个浮点数
- 在控制台输出日志（如检测到的人脸数量）

#### 数据流（内部执行步骤）
```
jpeg_data (unsigned char*)
    ↓
1. cv::imdecode() 解码
    ↓
cv::Mat (BGR, 原始尺寸)
    ↓
2. inference_retinaface_model()
    ↓
retinaface_result_t (人脸框 + 5关键点)
    ↓
3. align_face() 对齐
    ↓
cv::Mat (RGB, 112×112)
    ↓
4. inference_mobilefacenet_model()
    ↓
mobilefacenet_result_t (512-dim embedding)
    ↓
5. memcpy() 拷贝到输出缓冲区
    ↓
feature_512 (float[512])
```

#### 示例代码

**C 端调用**:
```c
#include <stdio.h>
#include <stdlib.h>

// 假设已经读取图片到 jpeg_buffer
unsigned char* jpeg_buffer = ...;
int buffer_size = ...;

// 分配输出缓冲区
float feature[512];

// 调用提取函数
int ret = FaceEngine_ExtractFeature(engine, jpeg_buffer, buffer_size, feature);

if (ret == 0) {
    printf("✓ Feature extracted successfully\n");
    printf("  First 5 values: %.4f, %.4f, %.4f, %.4f, %.4f\n",
           feature[0], feature[1], feature[2], feature[3], feature[4]);
} else if (ret == -1) {
    printf("✗ No face detected in the image\n");
} else {
    printf("✗ Feature extraction failed (error code: %d)\n", ret);
}
```

**Python 端调用**:
```python
import ctypes
import numpy as np

# 定义函数签名
self.lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
self.lib.FaceEngine_ExtractFeature.argtypes = [
    ctypes.c_void_p,                   # void* engine
    ctypes.POINTER(ctypes.c_ubyte),    # unsigned char* jpeg_data
    ctypes.c_int,                      # int data_len
    ctypes.POINTER(ctypes.c_float)     # float* feature_512
]

# 准备输入数据
jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

# 准备输出缓冲区
feature_512 = np.zeros(512, dtype=np.float32)
feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

# 调用 C 函数
ret = self.lib.FaceEngine_ExtractFeature(
    self.engine_ptr,
    jpeg_ptr,
    len(image_bytes),
    feature_ptr
)

# 处理返回值
if ret == 0:
    return feature_512.tolist()  # 转换为 Python List
elif ret == -1:
    return None  # 未检测到人脸
else:
    raise RuntimeError(f"Feature extraction failed (ret={ret})")
```

---

### 7.2.4 `FaceEngine_CosineSimilarity` - 计算余弦相似度

#### 函数签名
```c
float FaceEngine_CosineSimilarity(
    const float* emb1,
    const float* emb2
);
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `emb1` | `const float*` | ✓ | 特征向量1（512维） |
| `emb2` | `const float*` | ✓ | 特征向量2（512维） |

**参数约束**:
- 两个向量必须都是 512 维
- 必须是 L2 归一化后的向量（模长为 1）
- 内存必须连续

#### 输出返回值

| 类型 | 数值范围 | 含义 |
|------|----------|------|
| `float` | `[-1.0, 1.0]` | 余弦相似度分数 |

**相似度解读**:
- `0.9 ~ 1.0`: 极高相似度（同一张照片或双胞胎）
- `0.6 ~ 0.9`: 高相似度（极可能是同一人）
- `0.4 ~ 0.6`: 中等相似度（不确定）
- `0.0 ~ 0.4`: 低相似度（不是同一人）
- `< 0.0`: 极低相似度（完全不同）

#### 计算公式
```
similarity = Σ(emb1[i] × emb2[i])  (i=0 to 511)

当向量已经 L2 归一化时:
similarity = cos(θ) = (emb1 · emb2) / (||emb1|| × ||emb2||)
           = emb1 · emb2  (因为 ||emb1|| = ||emb2|| = 1)
```

#### 示例代码

**C 端调用**:
```c
float feature1[512];
float feature2[512];

// 假设已经提取了两个特征向量
FaceEngine_ExtractFeature(engine, img1_data, img1_len, feature1);
FaceEngine_ExtractFeature(engine, img2_data, img2_len, feature2);

// 计算相似度
float similarity = FaceEngine_CosineSimilarity(feature1, feature2);

printf("Similarity: %.4f\n", similarity);

if (similarity >= 0.6) {
    printf("✓ Same person\n");
} else {
    printf("✗ Different person\n");
}
```

**Python 端调用**:
```python
# 定义函数签名
self.lib.FaceEngine_CosineSimilarity.restype = ctypes.c_float
self.lib.FaceEngine_CosineSimilarity.argtypes = [
    ctypes.POINTER(ctypes.c_float),  # const float* emb1
    ctypes.POINTER(ctypes.c_float)   # const float* emb2
]

# 准备输入数据
arr1 = np.array(feature1, dtype=np.float32)
arr2 = np.array(feature2, dtype=np.float32)

ptr1 = arr1.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
ptr2 = arr2.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

# 调用函数
similarity = self.lib.FaceEngine_CosineSimilarity(ptr1, ptr2)

print(f"Similarity: {similarity:.4f}")
```

---

### 7.2.5 `FaceEngine_Destroy` - 销毁引擎实例

#### 函数签名
```c
void FaceEngine_Destroy(void* engine);
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `engine` | `void*` | ✓ | 引擎实例指针 |

#### 输出返回值
- **无返回值** (`void`)

#### 副作用
- 释放 RKNN 模型资源
- 释放引擎内部分配的内存
- 调用 `free(engine)`

#### 注意事项
- **必须调用**: 否则会造成内存泄漏
- **调用后不可再使用**: `engine` 指针失效
- **防止重复释放**: 确保只调用一次

#### 示例代码
```c
// C 端调用
FaceEngine_Destroy(engine);
engine = NULL;  // 防止野指针
```

```python
# Python 端调用（在析构函数中）
def __del__(self):
    if hasattr(self, 'engine_ptr') and self.engine_ptr:
        self.lib.FaceEngine_Destroy(self.engine_ptr)
        print("[FaceEngine] Engine destroyed")
```

---

## 7.3 C++ Internal API 详细规范

### 7.3.1 `inference_retinaface_model` - RetinaFace 推理

#### 函数签名
```c
int inference_retinaface_model(
    rknn_app_context_t* app_ctx,
    image_buffer_t* img,
    retinaface_result_t* out_result
);
```

#### 输入参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `app_ctx` | `rknn_app_context_t*` | RKNN 应用上下文（包含模型句柄） |
| `img` | `image_buffer_t*` | 输入图像（任意尺寸，BGR 或 RGB） |
| `out_result` | `retinaface_result_t*` | 输出检测结果 |

**`image_buffer_t` 结构体定义**:
```c
typedef struct {
    int width;          // 图像宽度
    int height;         // 图像高度
    int channel;        // 通道数（通常为3）
    uint8_t* virt_addr; // 图像数据指针（连续内存）
    int size;           // 数据大小（字节）
    int format;         // 0: RGB, 1: BGR
} image_buffer_t;
```

#### 输出数据结构

**`retinaface_result_t` 定义**:
```c
typedef struct {
    int count;                          // 检测到的人脸数量 [0, 128]
    retinaface_object_t objects[128];   // 人脸列表
} retinaface_result_t;
```

**`retinaface_object_t` 定义**:
```c
typedef struct {
    int cls;              // 类别（0 表示人脸）
    box_rect_t box;       // 人脸框
    float score;          // 置信度 [0, 1]
    point_t landmarks[5]; // 5个关键点
} retinaface_object_t;
```

**`box_rect_t` 定义**:
```c
typedef struct {
    int left;    // 左上角 X 坐标
    int top;     // 左上角 Y 坐标
    int right;   // 右下角 X 坐标
    int bottom;  // 右下角 Y 坐标
} box_rect_t;
```

**`point_t` 定义**:
```c
typedef struct {
    int x;  // X 坐标（像素）
    int y;  // Y 坐标（像素）
} point_t;
```

#### 关键点顺序

| 索引 | 含义 | 位置描述 |
|------|------|----------|
| `landmarks[0]` | 左眼中心 | 人脸左侧眼睛 |
| `landmarks[1]` | 右眼中心 | 人脸右侧眼睛 |
| `landmarks[2]` | 鼻尖 | 鼻子尖端 |
| `landmarks[3]` | 左嘴角 | 嘴巴左侧 |
| `landmarks[4]` | 右嘴角 | 嘴巴右侧 |

#### 返回值
- `0`: 成功
- `-1`: 失败

#### 示例输出数据
```c
retinaface_result_t result;
// ... 执行推理 ...

printf("检测到 %d 个人脸\n", result.count);

for (int i = 0; i < result.count; i++) {
    retinaface_object_t* obj = &result.objects[i];

    printf("人脸 %d:\n", i);
    printf("  置信度: %.3f\n", obj->score);
    printf("  边界框: [%d, %d, %d, %d]\n",
           obj->box.left, obj->box.top, obj->box.right, obj->box.bottom);
    printf("  关键点:\n");
    printf("    左眼: (%d, %d)\n", obj->landmarks[0].x, obj->landmarks[0].y);
    printf("    右眼: (%d, %d)\n", obj->landmarks[1].x, obj->landmarks[1].y);
    printf("    鼻尖: (%d, %d)\n", obj->landmarks[2].x, obj->landmarks[2].y);
    printf("    左嘴角: (%d, %d)\n", obj->landmarks[3].x, obj->landmarks[3].y);
    printf("    右嘴角: (%d, %d)\n", obj->landmarks[4].x, obj->landmarks[4].y);
}
```

---

### 7.3.2 `align_face` - 人脸对齐

#### 函数签名
```c
int align_face(
    image_buffer_t* src_img,
    point_t landmarks[5],
    image_buffer_t* aligned_face
);
```

#### 输入参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `src_img` | `image_buffer_t*` | 原始图像 |
| `landmarks` | `point_t[5]` | 5个关键点坐标 |
| `aligned_face` | `image_buffer_t*` | 输出对齐后的人脸图像 |

#### 输出数据

**`aligned_face` 结构体内容**:
```c
aligned_face->width = 112;
aligned_face->height = 112;
aligned_face->channel = 3;
aligned_face->format = 0;  // RGB
aligned_face->size = 112 * 112 * 3;
aligned_face->virt_addr = malloc(112 * 112 * 3);  // 需要手动释放！
```

**注意**: `virt_addr` 是动态分配的，**必须在使用后释放**：
```c
if (aligned_face.virt_addr) {
    free(aligned_face.virt_addr);
}
```

#### 参考关键点坐标

对齐时使用的标准模板（112×112 图像坐标系）：
```c
static const float REFERENCE_FACIAL_POINTS[5][2] = {
    {38.2946f, 51.6963f},  // 左眼
    {73.5318f, 51.5014f},  // 右眼
    {56.0252f, 71.7366f},  // 鼻尖
    {41.5493f, 92.3655f},  // 左嘴角
    {70.7299f, 92.2041f}   // 右嘴角
};
```

#### 返回值
- `0`: 成功
- `-1`: 失败（关键点无效或仿射变换失败）

---

### 7.3.3 `inference_mobilefacenet_model` - MobileFaceNet 推理

#### 函数签名
```c
int inference_mobilefacenet_model(
    rknn_app_context_t* app_ctx,
    image_buffer_t* aligned_face,
    mobilefacenet_result_t* out_result
);
```

#### 输入参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `app_ctx` | `rknn_app_context_t*` | RKNN 应用上下文 |
| `aligned_face` | `image_buffer_t*` | 对齐后的人脸图像（112×112，RGB） |
| `out_result` | `mobilefacenet_result_t*` | 输出特征向量 |

#### 输出数据结构

**`mobilefacenet_result_t` 定义**:
```c
typedef struct {
    float embedding[512];  // 512维特征向量
    int is_valid;          // 是否有效（1: 有效, 0: 无效）
} mobilefacenet_result_t;
```

**`embedding` 数组特性**:
- **长度**: 512
- **类型**: `float`
- **数值范围**: 每个分量约在 `[-0.3, 0.3]` 之间
- **向量模长**: `||v|| = 1.0`（L2 归一化）
- **用途**: 用于人脸比对和识别

#### 返回值
- `0`: 成功
- `-1`: 失败

#### 示例代码
```c
mobilefacenet_result_t result;
int ret = inference_mobilefacenet_model(&ctx, &aligned_face, &result);

if (ret == 0 && result.is_valid) {
    printf("✓ Feature extracted\n");

    // 计算向量模长（验证归一化）
    float norm = 0.0f;
    for (int i = 0; i < 512; i++) {
        norm += result.embedding[i] * result.embedding[i];
    }
    norm = sqrtf(norm);

    printf("  向量模长: %.4f (应接近1.0)\n", norm);
    printf("  前5维: %.4f, %.4f, %.4f, %.4f, %.4f\n",
           result.embedding[0], result.embedding[1], result.embedding[2],
           result.embedding[3], result.embedding[4]);
}
```

---

## 7.4 Python API 详细规范

### 7.4.1 `FaceEngine` 类

#### 类定义
```python
class FaceEngine:
    """人脸识别引擎包裹类（单例模式）"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """单例模式：确保全局只有一个引擎实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化人脸识别引擎"""
        # 加载动态库，初始化模型
        pass

    def extract_feature(self, image_bytes: bytes) -> Optional[List[float]]:
        """提取人脸特征向量"""
        pass

    def compute_similarity(self, feature1: List[float], feature2: List[float]) -> float:
        """计算两个特征向量的余弦相似度"""
        pass
```

---

### 7.4.2 `extract_feature` 方法

#### 方法签名
```python
def extract_feature(self, image_bytes: bytes) -> Optional[List[float]]:
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `image_bytes` | `bytes` | ✓ | 图片的二进制数据（JPEG/PNG格式） |

**获取图片字节的方式**:
```python
# 方式1: 从文件读取
with open("face.jpg", "rb") as f:
    image_bytes = f.read()

# 方式2: 从 FastAPI 上传文件
from fastapi import UploadFile

async def upload_face(file: UploadFile):
    image_bytes = await file.read()

# 方式3: 从 URL 下载
import requests
response = requests.get("https://example.com/face.jpg")
image_bytes = response.content
```

#### 输出返回值

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 成功 | `List[float]` | 512维特征向量，长度为512的列表 |
| 失败 | `None` | 未检测到人脸或处理失败 |

**成功返回示例**:
```python
feature = engine.extract_feature(image_bytes)
# feature = [0.123, -0.045, 0.234, ..., -0.012]  # 512个浮点数
print(f"特征维度: {len(feature)}")  # 输出: 512
print(f"前5维: {feature[:5]}")
```

#### 异常处理
- **不抛出异常**: 所有错误通过返回 `None` 表示
- **日志输出**: 错误信息会打印到控制台

#### 示例代码
```python
from face_engine import get_face_engine

engine = get_face_engine()

# 示例1: 处理单张图片
with open("person.jpg", "rb") as f:
    image_bytes = f.read()

feature = engine.extract_feature(image_bytes)

if feature:
    print(f"✓ 成功提取特征，维度: {len(feature)}")
else:
    print("✗ 未检测到人脸")

# 示例2: 批量处理
import os

features = []
for filename in os.listdir("faces/"):
    if filename.endswith(".jpg"):
        with open(f"faces/{filename}", "rb") as f:
            img_bytes = f.read()

        feature = engine.extract_feature(img_bytes)
        if feature:
            features.append((filename, feature))

print(f"成功处理 {len(features)} 张人脸")
```

---

### 7.4.3 `compute_similarity` 方法

#### 方法签名
```python
def compute_similarity(self, feature1: List[float], feature2: List[float]) -> float:
```

#### 输入参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `feature1` | `List[float]` | ✓ | 512维特征向量1 |
| `feature2` | `List[float]` | ✓ | 512维特征向量2 |

**参数约束**:
- 两个列表长度必须都是 512
- 列表中的元素必须是浮点数
- 如果参数无效，返回 `0.0`

#### 输出返回值

| 类型 | 数值范围 | 说明 |
|------|----------|------|
| `float` | `[0.0, 1.0]` | 余弦相似度分数 |

**相似度阈值参考**:
```python
if similarity >= 0.7:
    print("✓ 高度相似（同一人）")
elif similarity >= 0.6:
    print("✓ 可能是同一人")
elif similarity >= 0.4:
    print("？ 不确定")
else:
    print("✗ 不是同一人")
```

#### 示例代码
```python
# 提取两张人脸的特征
with open("person1.jpg", "rb") as f:
    feature1 = engine.extract_feature(f.read())

with open("person2.jpg", "rb") as f:
    feature2 = engine.extract_feature(f.read())

# 计算相似度
if feature1 and feature2:
    similarity = engine.compute_similarity(feature1, feature2)
    print(f"相似度: {similarity:.4f}")

    if similarity >= 0.6:
        print("✓ 是同一人")
    else:
        print("✗ 不是同一人")
else:
    print("错误: 未能提取特征")
```

---

## 7.5 数据格式总结表

### 7.5.1 输入数据格式汇总

| 节点 | 参数名 | 类型 | 格式 | 尺寸 | 备注 |
|------|--------|------|------|------|------|
| `FaceEngine_ExtractFeature` | `jpeg_data` | `unsigned char*` | JPEG/PNG | 任意 | 二进制流 |
| `inference_retinaface_model` | `img` | `image_buffer_t*` | BGR/RGB | 任意 | 内部调整为640×640 |
| `align_face` | `src_img` | `image_buffer_t*` | BGR/RGB | 任意 | 原始检测图像 |
| `align_face` | `landmarks` | `point_t[5]` | 整数坐标 | - | 5个关键点 |
| `inference_mobilefacenet_model` | `aligned_face` | `image_buffer_t*` | RGB | 112×112 | 对齐后人脸 |
| Python `extract_feature` | `image_bytes` | `bytes` | JPEG/PNG | 任意 | Python字节对象 |

---

### 7.5.2 输出数据格式汇总

| 节点 | 输出参数 | 类型 | 内容 | 数量/维度 | 备注 |
|------|----------|------|------|-----------|------|
| `FaceEngine_ExtractFeature` | `feature_512` | `float*` | 特征向量 | 512 | L2归一化 |
| `FaceEngine_CosineSimilarity` | 返回值 | `float` | 相似度 | 1 | [0, 1] |
| `inference_retinaface_model` | `out_result` | `retinaface_result_t*` | 人脸列表 | 0~128 | 包含框和关键点 |
| `align_face` | `aligned_face` | `image_buffer_t*` | 对齐图像 | 112×112×3 | RGB格式 |
| `inference_mobilefacenet_model` | `out_result` | `mobilefacenet_result_t*` | 特征向量 | 512 | 包含is_valid标志 |
| Python `extract_feature` | 返回值 | `List[float]` | 特征向量 | 512 | 或None（失败） |
| Python `compute_similarity` | 返回值 | `float` | 相似度 | 1 | [0.0, 1.0] |

---

## 7.6 错误码和返回值规范

### 7.6.1 C API 返回值

| 函数 | 返回值 | 含义 |
|------|--------|------|
| `FaceEngine_Init` | `0` | 成功 |
|  | `-1` | 失败（参数错误或模型加载失败） |
| `FaceEngine_ExtractFeature` | `0` | 成功 |
|  | `-1` | 未检测到人脸 |
|  | `-2` | 其他错误（解码失败、推理失败、引擎未初始化） |
| `inference_retinaface_model` | `0` | 成功 |
|  | `-1` | 失败 |
| `align_face` | `0` | 成功 |
|  | `-1` | 失败 |
| `inference_mobilefacenet_model` | `0` | 成功 |
|  | `-1` | 失败 |

---

### 7.6.2 Python API 返回值

| 方法 | 成功返回 | 失败返回 |
|------|----------|----------|
| `extract_feature` | `List[float]` (512维) | `None` |
| `compute_similarity` | `float` [0.0, 1.0] | `0.0` (当参数无效时) |

---

## 7.7 内存管理规范

### 7.7.1 C API 内存责任

| 函数 | 内存分配者 | 释放责任 |
|------|-----------|----------|
| `FaceEngine_Create` | C库（malloc） | **调用者**必须调用 `FaceEngine_Destroy` |
| `FaceEngine_ExtractFeature` | **调用者**预先分配 `feature_512[512]` | 调用者负责（通常栈上分配） |
| `align_face` | C库（malloc `virt_addr`） | **调用者**必须 `free(aligned_face.virt_addr)` |

### 7.7.2 Python API 内存管理

- **自动管理**: Python 的 GC 会自动释放
- **ctypes 零拷贝**: 使用 `numpy` 避免数据拷贝
- **引擎单例**: 全局只有一个实例，程序退出时自动释放

---

## 7.8 完整调用示例

### 7.8.1 C 端完整流程
```c
#include <stdio.h>
#include "face_utils.h"

int main() {
    // 1. 创建引擎
    void* engine = FaceEngine_Create();
    if (!engine) return -1;

    // 2. 初始化
    int ret = FaceEngine_Init(
        engine,
        "/userdata/models/RetinaFace.rknn",
        "/userdata/models/mobilefacenet.rknn"
    );
    if (ret != 0) {
        FaceEngine_Destroy(engine);
        return -1;
    }

    // 3. 读取图片（假设已有函数）
    unsigned char* img1_data;
    int img1_len = read_jpeg_file("face1.jpg", &img1_data);

    unsigned char* img2_data;
    int img2_len = read_jpeg_file("face2.jpg", &img2_data);

    // 4. 提取特征
    float feature1[512];
    float feature2[512];

    ret = FaceEngine_ExtractFeature(engine, img1_data, img1_len, feature1);
    if (ret != 0) {
        printf("提取特征1失败\n");
        goto cleanup;
    }

    ret = FaceEngine_ExtractFeature(engine, img2_data, img2_len, feature2);
    if (ret != 0) {
        printf("提取特征2失败\n");
        goto cleanup;
    }

    // 5. 计算相似度
    float similarity = FaceEngine_CosineSimilarity(feature1, feature2);
    printf("相似度: %.4f\n", similarity);

    // 6. 清理资源
cleanup:
    free(img1_data);
    free(img2_data);
    FaceEngine_Destroy(engine);

    return 0;
}
```

---

### 7.8.2 Python 端完整流程
```python
from backend.core.face_engine import get_face_engine

# 1. 获取引擎实例（单例）
engine = get_face_engine()

# 2. 读取图片
with open("face1.jpg", "rb") as f:
    img1_bytes = f.read()

with open("face2.jpg", "rb") as f:
    img2_bytes = f.read()

# 3. 提取特征
feature1 = engine.extract_feature(img1_bytes)
feature2 = engine.extract_feature(img2_bytes)

# 4. 验证结果
if not feature1:
    print("错误: 图片1未检测到人脸")
    exit(1)

if not feature2:
    print("错误: 图片2未检测到人脸")
    exit(1)

# 5. 计算相似度
similarity = engine.compute_similarity(feature1, feature2)

print(f"相似度: {similarity:.4f}")

if similarity >= 0.6:
    print("✓ 是同一人")
else:
    print("✗ 不是同一人")

# 6. 无需手动清理（Python GC 自动管理）
```

---

## 7.9 常见问题

### Q1: 为什么 `FaceEngine_ExtractFeature` 返回 -1？
**A**: 图片中没有检测到人脸，可能原因：
- 图片中确实没有人脸
- 人脸太小（< 40×40像素）
- 人脸角度过大（侧脸超过60°）
- 图像质量差（模糊、过曝、欠曝）

### Q2: `feature_512` 缓冲区需要多大？
**A**: 必须预先分配 512 个 `float`，即 2048 字节。

### Q3: Python 端如何避免内存拷贝？
**A**: 使用 `numpy.frombuffer()` + `ctypes.data_as()`：
```python
jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
```

### Q4: 相似度阈值如何选择？
**A**: 根据应用场景：
- 安全场景（如支付）: 0.7（严格）
- 通用场景（如相册分类）: 0.6（平衡）
- 宽松场景（如推荐系统）: 0.5（宽松）

---

## 7.10 总结

本文档详细定义了人脸识别模块的完整 API 规范：

1. **C Export API**: 5个核心函数供 Python 调用
2. **C++ Internal API**: 底层实现细节
3. **Python API**: 面向对象封装
4. **数据结构**: 详细的输入输出格式
5. **错误处理**: 完整的返回值规范
6. **内存管理**: 明确的责任划分

**关键要点**:
- 所有输入图片自动调整尺寸
- 特征向量固定 512 维，L2 归一化
- Python 端零拷贝数据传递
- 错误通过返回值传递，不抛异常

**下一步**: 参阅 `模型功能和作用.md` 了解 RetinaFace 和 MobileFaceNet 的详细原理。
