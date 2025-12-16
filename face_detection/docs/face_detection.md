# 人脸检测识别系统完整文档

> 基于 RK3568 开发板的 RetinaFace + MobileFaceNet 人脸识别门禁系统

---

## 目录

- [1. 项目架构](#1-项目架构)
- [2. 项目部署指南](#2-项目部署指南)
- [3. 项目使用方法](#3-项目使用方法)
- [4. 项目后端集成介绍](#4-项目后端集成介绍)
- [5. 编译运行步骤](./compile_steps.md)
- [6. 人脸识别模块的数据流](./dataflow.md)
- [7. 每个流节点的输入输出数据格式](./format_out_in.md)
- [8. 两个模型的功能和作用](./model_function.md)
- [9. 流入模型的图片数据预处理](./img_preprocess.md)
- [10. 胶水件的代码介绍](./middle_function.md)

---

## 1. 项目架构

### 1.1 模块概述

**face_detection** 是一个基于 RK3568 平台的**人脸识别 C++ 核心库**，封装了完整的人脸检测与特征提取功能。该模块利用 NPU 硬件加速，将图像输入转化为 512 维人脸特征向量，供上层应用（如 Python 后端）调用。

**核心功能**：
1. **人脸检测**：使用 RetinaFace 模型检测图像中的人脸，输出人脸边界框和 5 个关键点
2. **人脸对齐**：基于关键点进行仿射变换，将人脸对齐到标准姿态（112×112）
3. **特征提取**：使用 MobileFaceNet 模型提取 512 维 L2 归一化特征向量
4. **C 接口导出**：提供 C 接口供 Python 通过 ctypes 调用（零拷贝数据传递）

**设计目标**：
- **高性能**：利用 RKNN NPU 加速，总处理时间 30-70ms
- **易部署**：静态链接 OpenCV，生成单个 .so 文件（10-20MB）
- **跨语言**：通过 ctypes 提供 Python 友好接口
- **可移植**：支持交叉编译，在 x86 VMWare 上编译 ARM64 二进制

### 1.2 技术栈

| 组件 | 技术方案 | 说明 |
|------|---------|------|
| **目标平台** | RK3568 ARM64 | 搭载 NPU 加速器（用于 RKNN 模型推理） |
| **人脸检测模型** | RetinaFace (RKNN) | 输入 640×640 RGB，输出人脸框 + 5 个关键点 |
| **人脸识别模型** | MobileFaceNet (RKNN) | 输入 112×112 RGB，输出 512 维特征向量 |
| **图像处理库** | OpenCV 4.6.0 (静态) | 图像解码、缩放、颜色转换、仿射变换 |
| **推理框架** | RKNN Runtime API | 加载 .rknn 模型并在 NPU 上执行推理 |
| **编译工具** | gcc-linaro-6.3.1 | 交叉编译器（x86 → ARM64） |
| **构建系统** | CMake 3.10+ | 自动化编译配置（含交叉编译设置） |
| **编程语言** | C++ 11 | 核心代码实现 |
| **接口导出** | C API (extern "C") | 供 Python ctypes 调用 |

### 1.3 模块架构图

#### 1.3.1 内部数据流

```
JPEG/PNG 字节流 (输入)
    ↓
cv::imdecode() → cv::Mat (BGR)
    ↓
cv::resize() → 640×640 (BGR)
    ↓
cv::cvtColor() → 640×640 (RGB)
    ↓
┌─────────────────────────────────────┐
│   RetinaFace RKNN 推理               │
│   输入: 640×640×3, RGB, uint8       │
│   输出: BBox + 5 Landmarks + Scores │
│   运行: NPU 硬件加速                 │
└─────────────────────────────────────┘
    ↓
后处理 (C++)
    ├─ Anchor 解码
    ├─ 置信度过滤 (CONF_THRESHOLD = 0.5)
    ├─ NMS 去重 (NMS_THRESHOLD = 0.4)
    └─ 输出: box_rect_t + ponit_t[5]
    ↓
┌─────────────────────────────────────┐
│   人脸对齐胶水层 (OpenCV)            │
│   输入: 原图 + 5 个关键点            │
│   处理: cv::estimateAffinePartial2D │
│          cv::warpAffine             │
│   输出: 112×112×3, RGB, uint8       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   MobileFaceNet RKNN 推理            │
│   输入: 112×112×3, RGB, NHWC, uint8 │
│   输出: 512 维特征向量 (float32)     │
│   运行: NPU 硬件加速                 │
└─────────────────────────────────────┘
    ↓
512 维特征向量 (输出)
```

#### 1.3.2 模块与外部交互

```
┌──────────────────────┐
│  Python 上层应用      │
│  (ctypes 调用)       │
└──────────────────────┘
         ↓ ↑
  指针传递 (零拷贝)
         ↓ ↑
┌──────────────────────┐
│  libface_engine.so   │
│  (C++ 核心库)        │
│                      │
│  ┌────────────────┐  │
│  │ FaceEngine     │  │
│  │ - init()       │  │
│  │ - extract()    │  │
│  │ - destroy()    │  │
│  └────────────────┘  │
│         ↓            │
│  ┌────────────────┐  │
│  │ RetinaFace     │  │──→ RKNN API → NPU
│  └────────────────┘  │
│         ↓            │
│  ┌────────────────┐  │
│  │ FaceAligner    │  │──→ OpenCV
│  └────────────────┘  │
│         ↓            │
│  ┌────────────────┐  │
│  │ MobileFaceNet  │  │──→ RKNN API → NPU
│  └────────────────┘  │
└──────────────────────┘
```

### 1.4 核心组件

#### 1.4.1 FaceEngine 主引擎
- **职责**：统一接口，协调各组件工作流程
- **核心方法**：
  - `init()`：加载两个 RKNN 模型，初始化上下文
  - `extract_feature()`：端到端提取人脸特征向量
  - `release()`：释放模型资源

#### 1.4.2 RetinaFace 检测器
- **职责**：检测图像中的人脸，输出边界框和关键点
- **输入**：640×640×3 RGB uint8
- **输出**：
  - 人脸框（box_rect_t）：左上角和右下角坐标
  - 5 个关键点（ponit_t[5]）：左眼、右眼、鼻尖、左嘴角、右嘴角
  - 置信度分数（float）

#### 1.4.3 FaceAligner 对齐器（胶水层）
- **职责**：将检测到的人脸对齐到标准姿态
- **核心技术**：
  - 基于 5 个关键点计算仿射变换矩阵
  - 使用预定义的标准参考点（MobileFaceNet 训练时的位置）
  - 执行 cv::warpAffine 生成 112×112 对齐人脸
- **重要性**：消除姿态变化对识别的影响，提升准确率

#### 1.4.4 MobileFaceNet 识别器
- **职责**：提取对齐人脸的特征向量
- **输入**：112×112×3 RGB NHWC uint8
- **输出**：512 维 L2 归一化特征向量（float32）
- **特性**：输出向量可直接用于余弦相似度计算

### 1.5 模块目录结构

```
face_detection/
├── CMakeLists.txt                 # CMake 构建配置（含交叉编译设置）
├── build/                         # 编译输出目录
│   └── libface_engine.so          # 生成的动态库（~10-20MB，含 OpenCV）
├── models/                        # RKNN 模型文件
│   ├── RetinaFace.rknn            # 人脸检测模型
│   └── mobilefacenet.rknn         # 人脸识别模型
├── src/                           # C++ 源代码
│   ├── face_engine.cpp            # 主引擎实现（FaceEngine 类）
│   ├── face_aligner.cpp           # 人脸对齐（仿射变换）
│   ├── retinaface.cpp             # RetinaFace 推理封装
│   ├── mobilefacenet.cpp          # MobileFaceNet 推理封装
│   └── utils.cpp                  # 工具函数（后处理、NMS 等）
├── include/                       # C++ 头文件
│   ├── face_engine.h              # FaceEngine 类定义
│   ├── face_aligner.h             # 人脸对齐接口
│   └── common.h                   # 公共数据结构
├── third_party/                   # 第三方依赖库
│   ├── rknn/                      # RKNN 运行时库
│   │   ├── include/rknn_api.h     # RKNN API 头文件
│   │   └── lib/librknnrt.so       # RKNN 动态库（ARM64）
│   └── opencv/                    # OpenCV 静态库
│       ├── include/opencv2/       # OpenCV 头文件
│       ├── lib/*.a                # OpenCV 静态库
│       └── cmake/opencv4/         # CMake 配置文件
├── test_api.py                    # Python 测试脚本
├── DEPLOYMENT_GUIDE.md            # 部署指南
└── docs/
    └── ARCHITECTURE_SUMMARY.md    # 架构总结
```

### 1.6 核心优势

#### 1.6.1 性能优化
- **NPU 硬件加速**：两个模型均运行在 NPU 上，推理速度远超 CPU
- **静态链接 OpenCV**：将 OpenCV 静态库编译进 .so，无需额外依赖
- **零拷贝接口**：Python 通过指针直接访问 C++ 内存，避免数据复制

#### 1.6.2 部署便利
- **单文件部署**：编译生成的 `libface_engine.so` 包含所有依赖（除 librknnrt.so）
- **跨平台编译**：在 VMWare Ubuntu x86 上交叉编译 ARM64 二进制
- **无需安装 OpenCV**：开发板上无需安装 OpenCV 库

#### 1.6.3 易于集成
- **C 接口导出**：提供简洁的 C API，方便多种语言调用
- **Python 友好**：通过 ctypes 封装，提供 Pythonic 接口
- **可扩展性**：模块化设计，可轻松替换模型或添加功能

### 1.7 关键技术指标

| 指标 | 数值 | 说明 |
|------|------|------|
| **人脸检测速度** | 20-50ms | RetinaFace 在 RK3568 NPU 上的推理时间 |
| **特征提取速度** | 5-15ms | MobileFaceNet 在 RK3568 NPU 上的推理时间 |
| **总处理时间** | 30-70ms | 从接收图片到返回特征向量的总耗时 |
| **特征向量维度** | 512 | MobileFaceNet 输出的特征向量长度 |
| **特征向量归一化** | L2 归一化 | 输出为单位向量，可直接计算余弦相似度 |
| **支持图片格式** | JPEG, PNG | 通过 OpenCV cv::imdecode 解码 |
| **输入图片尺寸** | 无限制 | 自动缩放到 640×640（保持纵横比） |
| **检测置信度阈值** | 0.5 | 低于此值的检测结果会被过滤 |
| **NMS IoU 阈值** | 0.4 | 用于去除重叠的检测框 |
| **.so 文件大小** | 10-20MB | 包含静态链接的 OpenCV 库 |

---

## 2. 项目部署指南

本节介绍如何将编译好的 **face_detection 模块**部署到 RK3568 开发板上。部署过程包括：在 VMWare 中打包文件、传输到开发板、配置环境、运行测试。

### 2.1 部署前提

#### 2.1.1 编译完成
- 已在 VMWare Ubuntu 上成功编译出 ARM64 格式的 `libface_engine.so`
- 验证方法：`file build/libface_engine.so` 应显示 `ELF 64-bit LSB shared object, ARM aarch64`

#### 2.1.2 文件准备
确保以下文件已就绪：
```
face_detection/build/libface_engine.so    # 编译生成的动态库（10-20MB）
face_detection/models/RetinaFace.rknn      # 人脸检测模型
face_detection/models/mobilefacenet.rknn   # 人脸识别模型
face_detection/test_api.py                 # Python 测试脚本
```

### 2.2 需要传输的文件清单

#### 2.2.1 核心文件（必需）
```
face_app/                              # 开发板目标目录
├── libface_engine.so                   # 主动态库（~10-20MB）
├── models/
│   ├── RetinaFace.rknn                # 人脸检测模型
│   └── mobilefacenet.rknn             # 人脸识别模型
└── test_api.py                        # Python 测试脚本
```

#### 2.2.2 测试图片（可选）
```
face_app/test_images/
├── person1.jpg
└── person2.jpg
```

### 2.3 在 VMWare 中打包文件

#### 步骤 1：创建部署包目录
```bash
cd ~/project/face_detection

# 创建部署包目录
mkdir -p deploy_package/models

# 复制核心文件
cp build/libface_engine.so deploy_package/
cp models/*.rknn deploy_package/models/
cp test_api.py deploy_package/

# 复制测试图片（可选）
mkdir -p deploy_package/test_images
cp test_images/* deploy_package/test_images/  # 如果有测试图片
```

#### 步骤 2：打包压缩（方便传输）
```bash
# 打包
tar -czf face_app_deploy.tar.gz deploy_package/

# 查看打包结果
ls -lh face_app_deploy.tar.gz
# 应显示：face_app_deploy.tar.gz (约 15-25MB)
```

### 2.4 传输到开发板

#### 方法 A：使用 scp（推荐，需要网络连接）
```bash
# 在 VMWare 中执行
scp face_app_deploy.tar.gz root@<开发板IP>:/userdata/

# 示例：
# scp face_app_deploy.tar.gz root@192.168.1.100:/userdata/
```

#### 方法 B：使用 U 盘
1. 将 `face_app_deploy.tar.gz` 复制到 U 盘
2. 将 U 盘插入开发板
3. 在开发板上挂载 U 盘并复制文件：
   ```bash
   # 挂载 U 盘（假设设备为 /dev/sda1）
   mount /dev/sda1 /mnt
   
   # 复制文件
   cp /mnt/face_app_deploy.tar.gz /userdata/
   
   # 卸载 U 盘
   umount /mnt
   ```

#### 方法 C：使用串口传输（较慢，适用于网络不可用的情况）
```bash
# 在串口工具中使用 sz 命令
sz face_app_deploy.tar.gz
```

### 2.5 在开发板上解压和配置

#### 步骤 1：解压文件
通过 SSH 或串口登录到开发板：
```bash
# 进入目标目录
cd /userdata

# 解压
tar -xzf face_app_deploy.tar.gz

# 重命名为 face_app
mv deploy_package face_app

# 进入目录
cd face_app

# 查看文件
ls -lh
# 应显示：libface_engine.so, models/, test_api.py

ls -lh models/
# 应显示：RetinaFace.rknn, mobilefacenet.rknn
```

#### 步骤 2：设置环境变量
```bash
# 临时设置（仅当前会话有效）
export LD_LIBRARY_PATH=/userdata/face_app:$LD_LIBRARY_PATH

# 永久设置（写入配置文件）
echo 'export LD_LIBRARY_PATH=/userdata/face_app:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

**说明**：设置 `LD_LIBRARY_PATH` 是为了让系统能找到 `libface_engine.so` 和其依赖的 `librknnrt.so`。

#### 步骤 3：检查依赖库
```bash
# 检查 libface_engine.so 的依赖
ldd libface_engine.so

# 应该看到：
# librknnrt.so => /usr/lib/librknnrt.so (找到)
# libpthread.so.0 => ... (找到)
# libc.so.6 => ... (找到)
# libdl.so.2 => ... (找到)

# 如果有 "not found"，需要安装对应的库或调整 LD_LIBRARY_PATH
```

#### 步骤 4：安装 Python 依赖
```bash
# 检查 Python 版本
python3 --version
# 应显示：Python 3.x

# 检查 numpy
python3 -c "import numpy; print(numpy.__version__)"

# 如果 numpy 未安装
pip3 install numpy

# 或使用系统包管理器
# apt-get install python3-numpy  # Debian/Ubuntu
```

### 2.6 修改测试脚本路径

在开发板上编辑 `test_api.py`，将路径修改为绝对路径：

```bash
# 使用 vi 或 nano 编辑
vi test_api.py
```

修改以下行（通常在文件头部）：
```python
# 修改前：
# LIB_PATH = "./libface_engine.so"
# RETINAFACE_MODEL = "./models/RetinaFace.rknn"
# MOBILEFACENET_MODEL = "./models/mobilefacenet.rknn"

# 修改后：
LIB_PATH = "/userdata/face_app/libface_engine.so"
RETINAFACE_MODEL = "/userdata/face_app/models/RetinaFace.rknn"
MOBILEFACENET_MODEL = "/userdata/face_app/models/mobilefacenet.rknn"
```

### 2.7 验证部署

#### 测试 1：检查库文件格式
```bash
cd /userdata/face_app

# 查看库文件架构
file libface_engine.so
# 应显示：ELF 64-bit LSB shared object, ARM aarch64

# 检查导出的符号
nm -D libface_engine.so | grep FaceEngine
# 应显示：
# FaceEngine_Create
# FaceEngine_Init
# FaceEngine_ExtractFeature
# FaceEngine_Destroy
# FaceEngine_CosineSimilarity
```

#### 测试 2：Python 脚本测试（单张图片）
```bash
cd /userdata/face_app

# 测试单张图片特征提取
python3 test_api.py --image test_images/person1.jpg
```

**预期输出**：
```
✓ Successfully loaded library: /userdata/face_app/libface_engine.so
Initializing FaceEngine...
  RetinaFace model: /userdata/face_app/models/RetinaFace.rknn
  MobileFaceNet model: /userdata/face_app/models/mobilefacenet.rknn
✓ FaceEngine initialized successfully

Extracting feature from: test_images/person1.jpg
✓ Feature extracted successfully
  Feature shape: (512,)
  Feature norm: 1.0000
  Feature range: [-0.5234, 0.6789]

✓ Test completed successfully!
```

#### 测试 3：人脸比对测试（两张图片）
```bash
# 测试两张图片的相似度
python3 test_api.py --image test_images/person1.jpg --image2 test_images/person2.jpg
```

**预期输出**（如果是同一人）：
```
✓ Feature 1 extracted: (512,)
✓ Feature 2 extracted: (512,)
Cosine similarity: 0.7823
Result: Same person (threshold=0.4)
```

### 2.8 常见问题排查

#### Q1: 找不到 librknnrt.so
**错误现象**：
```
error while loading shared libraries: librknnrt.so: cannot open shared object file
```

**解决方法**：
```bash
# 方法 1：查找系统中的 librknnrt.so
find /usr -name "librknnrt.so"

# 如果找到（例如 /usr/lib/librknnrt.so），添加到环境变量
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# 方法 2：如果系统中没有，从 RKNN SDK 安装
# （需要从 rknpu2/runtime/RK3568/Linux/librknn_api/aarch64/ 复制）
```

#### Q2: 权限不足
**错误现象**：
```
Permission denied
```

**解决方法**：
```bash
# 给文件添加执行权限
chmod +x /userdata/face_app/libface_engine.so
chmod +x /userdata/face_app/test_api.py
```

#### Q3: No face detected
**可能原因**：
1. 图片质量差、人脸不清晰
2. 模型文件损坏或格式错误
3. 置信度阈值设置过高

**解决方法**：
```bash
# 检查模型文件完整性
md5sum models/RetinaFace.rknn
md5sum models/mobilefacenet.rknn

# 与 VMWare 中的原文件对比 MD5 值，确保传输过程中没有损坏
```

#### Q4: RKNN 初始化失败
**错误现象**：
```
rknn_init fail! ret=-1
```

**可能原因**：
1. NPU 驱动未加载
2. 模型文件与 RKNN 版本不匹配
3. 内存不足

**解决方法**：
```bash
# 检查 NPU 设备
ls -l /dev/rknpu*
# 应显示：/dev/rknpu0

# 检查内存
free -h

# 如果有 rknn_server 服务，重启它
# systemctl restart rknn_server
```

#### Q5: Python 版本不兼容
**错误现象**：
```
SyntaxError: invalid syntax
```

**解决方法**：
```bash
# 确认 Python 版本 >= 3.6
python3 --version

# 如果版本太低，使用板子的默认 Python3
which python3
```

### 2.9 性能验证

在开发板上运行性能测试：

```bash
# 测试单次推理时间
time python3 test_api.py --image test_images/person1.jpg

# 预期耗时（RK3568 NPU）：
# - RetinaFace 推理: 20-50ms
# - MobileFaceNet 推理: 5-15ms
# - 总耗时: 30-70ms
```

### 2.10 更新部署

如果需要更新 `.so` 库或模型文件：

#### 步骤 1：在 VMWare 重新编译
```bash
cd ~/project/face_detection/build
make -j4
```

#### 步骤 2：只传输更新的文件
```bash
# 方法 1：使用 scp
scp build/libface_engine.so root@<开发板IP>:/userdata/face_app/

# 方法 2：如果更新模型
scp models/RetinaFace.rknn root@<开发板IP>:/userdata/face_app/models/
```

#### 步骤 3：在开发板上测试
```bash
cd /userdata/face_app
python3 test_api.py --image test_images/person1.jpg
```

### 2.11 部署检查清单

在部署前确认：

- [ ] `libface_engine.so` 是 ARM64 格式（`file` 命令验证）
- [ ] 两个 `.rknn` 模型文件存在且完整（MD5 校验）
- [ ] 开发板已安装 Python 3.x 和 numpy
- [ ] 开发板有 `/dev/rknpu0` 设备（NPU 驱动已加载）
- [ ] 开发板有 `librknnrt.so` 库（RKNN 运行时）
- [ ] `test_api.py` 中的路径已修改为绝对路径
- [ ] 设置了 `LD_LIBRARY_PATH` 环境变量
- [ ] 有测试图片可用（包含清晰的正面人脸）

### 2.12 部署成功标志

部署成功后，应能看到以下输出：

```bash
$ python3 test_api.py --image test_images/person1.jpg

✓ Successfully loaded library
✓ FaceEngine initialized successfully
✓ Feature extracted successfully
  Feature shape: (512,)
  Feature norm: 1.0000
✓ Test completed successfully!
```

如果看到上述输出，说明 **face_detection 模块已成功部署并可正常工作**！

---

## 3. 项目使用方法

本节介绍如何在应用程序中使用 **face_detection 模块**。该模块提供两种调用方式：**Python 接口**（推荐）和 **C/C++ 接口**（高级用户）。

### 3.1 Python 接口（推荐）

#### 3.1.1 基本使用流程

```python
import ctypes
import numpy as np

# 1. 加载动态库
lib = ctypes.CDLL('./libface_engine.so')

# 2. 定义函数签名
lib.FaceEngine_Create.restype = ctypes.c_void_p
lib.FaceEngine_Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
lib.FaceEngine_Init.restype = ctypes.c_int
lib.FaceEngine_ExtractFeature.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_float)
]
lib.FaceEngine_ExtractFeature.restype = ctypes.c_int

# 3. 创建引擎实例
engine = lib.FaceEngine_Create()

# 4. 初始化模型
ret = lib.FaceEngine_Init(
    engine,
    b'models/RetinaFace.rknn',
    b'models/mobilefacenet.rknn'
)

if ret != 0:
    print(f"初始化失败，错误码：{ret}")
    exit(1)

# 5. 读取图片
with open('test.jpg', 'rb') as f:
    jpeg_data = f.read()

# 6. 准备输入输出缓冲区
img_array = np.frombuffer(jpeg_data, dtype=np.uint8)
img_ptr = img_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

feature_512 = np.zeros(512, dtype=np.float32)
feat_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

# 7. 提取特征
ret = lib.FaceEngine_ExtractFeature(engine, img_ptr, len(jpeg_data), feat_ptr)

if ret == 0:
    print("特征提取成功")
    print(f"特征向量: {feature_512[:10]}...")  # 显示前10维
    print(f"向量范数: {np.linalg.norm(feature_512):.4f}")
elif ret == -1:
    print("未检测到人脸")
else:
    print(f"特征提取失败，错误码：{ret}")

# 8. 释放资源
lib.FaceEngine_Destroy(engine)
```

#### 3.1.2 完整的 Python 类封装

以下是一个完整的 Python 封装类，提供更友好的接口：

```python
"""
FaceEngine Python 封装类
"""
import ctypes
import numpy as np
from typing import Optional, Tuple

class FaceEngine:
    """人脸识别引擎"""

    def __init__(self, lib_path: str, retinaface_model: str, mobilefacenet_model: str):
        """
        初始化人脸识别引擎

        Args:
            lib_path: libface_engine.so 的路径
            retinaface_model: RetinaFace 模型路径
            mobilefacenet_model: MobileFaceNet 模型路径
        """
        # 加载动态库
        self.lib = ctypes.CDLL(lib_path)

        # 定义函数签名
        self.lib.FaceEngine_Create.restype = ctypes.c_void_p
        self.lib.FaceEngine_Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.FaceEngine_Init.restype = ctypes.c_int
        self.lib.FaceEngine_ExtractFeature.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float)
        ]
        self.lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
        self.lib.FaceEngine_Destroy.argtypes = [ctypes.c_void_p]
        self.lib.FaceEngine_CosineSimilarity.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float)
        ]
        self.lib.FaceEngine_CosineSimilarity.restype = ctypes.c_float

        # 创建引擎实例
        self.engine = self.lib.FaceEngine_Create()
        if not self.engine:
            raise RuntimeError("创建 FaceEngine 实例失败")

        # 初始化模型
        ret = self.lib.FaceEngine_Init(
            self.engine,
            retinaface_model.encode('utf-8'),
            mobilefacenet_model.encode('utf-8')
        )
        if ret != 0:
            raise RuntimeError(f"初始化 FaceEngine 失败，错误码：{ret}")

        print("FaceEngine 初始化成功")

    def extract_feature(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        提取人脸特征向量

        Args:
            image_bytes: 图片的二进制数据（JPEG/PNG 格式）

        Returns:
            np.ndarray: 512 维特征向量（成功）
            None: 未检测到人脸或处理失败
        """
        # 准备输入
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img_ptr = img_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

        # 准备输出
        feature_512 = np.zeros(512, dtype=np.float32)
        feat_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 调用 C++ 函数
        ret = self.lib.FaceEngine_ExtractFeature(
            self.engine,
            img_ptr,
            len(image_bytes),
            feat_ptr
        )

        if ret == 0:
            return feature_512
        elif ret == -1:
            print("未检测到人脸")
            return None
        else:
            print(f"特征提取失败，错误码：{ret}")
            return None

    def compute_similarity(self, feature1: np.ndarray, feature2: np.ndarray) -> float:
        """
        计算两个特征向量的余弦相似度

        Args:
            feature1: 512 维特征向量1
            feature2: 512 维特征向量2

        Returns:
            float: 余弦相似度 [0, 1]
        """
        ptr1 = feature1.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr2 = feature2.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        similarity = self.lib.FaceEngine_CosineSimilarity(ptr1, ptr2)
        return float(similarity)

    def compare_faces(self, feature1: np.ndarray, feature2: np.ndarray,
                      threshold: float = 0.4) -> Tuple[bool, float]:
        """
        比较两个人脸特征是否为同一人

        Args:
            feature1: 特征向量1
            feature2: 特征向量2
            threshold: 相似度阈值（默认 0.4）

        Returns:
            (is_same, similarity): 是否为同一人，相似度分数
        """
        similarity = self.compute_similarity(feature1, feature2)
        is_same = similarity > threshold
        return is_same, similarity

    def __del__(self):
        """释放资源"""
        if hasattr(self, 'engine') and self.engine:
            self.lib.FaceEngine_Destroy(self.engine)
            print("FaceEngine 已释放")
```

#### 3.1.3 使用示例

**示例 1：单张图片特征提取**

```python
# 创建引擎
engine = FaceEngine(
    lib_path='./libface_engine.so',
    retinaface_model='./models/RetinaFace.rknn',
    mobilefacenet_model='./models/mobilefacenet.rknn'
)

# 读取图片
with open('person1.jpg', 'rb') as f:
    image_data = f.read()

# 提取特征
feature = engine.extract_feature(image_data)

if feature is not None:
    print(f"特征维度: {feature.shape}")
    print(f"向量范数: {np.linalg.norm(feature):.4f}")
    print(f"特征范围: [{feature.min():.4f}, {feature.max():.4f}]")
```

**示例 2：人脸比对**

```python
# 读取两张图片
with open('person1.jpg', 'rb') as f:
    image1 = f.read()

with open('person2.jpg', 'rb') as f:
    image2 = f.read()

# 提取特征
feature1 = engine.extract_feature(image1)
feature2 = engine.extract_feature(image2)

if feature1 is not None and feature2 is not None:
    # 比对人脸
    is_same, similarity = engine.compare_faces(feature1, feature2, threshold=0.4)

    print(f"相似度: {similarity:.4f}")
    print(f"结果: {'同一人' if is_same else '不同人'}")
```

**示例 3：批量处理**

```python
import os
from pathlib import Path

# 批量提取图片特征
image_dir = Path('./images')
features = {}

for img_path in image_dir.glob('*.jpg'):
    with open(img_path, 'rb') as f:
        image_data = f.read()

    feature = engine.extract_feature(image_data)
    if feature is not None:
        features[img_path.name] = feature
        print(f"✓ {img_path.name}: 特征提取成功")
    else:
        print(f"✗ {img_path.name}: 未检测到人脸")

print(f"\n成功提取 {len(features)} 张图片的特征")

# 人脸比对矩阵
print("\n相似度矩阵:")
names = list(features.keys())
for i, name1 in enumerate(names):
    for j, name2 in enumerate(names):
        if i < j:
            sim = engine.compute_similarity(features[name1], features[name2])
            print(f"{name1} vs {name2}: {sim:.4f}")
```

### 3.2 C/C++ 接口（高级用户）

#### 3.2.1 导出的 C 接口

`libface_engine.so` 导出以下 C 接口：

```c
// 创建引擎实例
void* FaceEngine_Create();

// 初始化引擎（加载模型）
int FaceEngine_Init(void* engine,
                    const char* retinaface_model,
                    const char* mobilefacenet_model);

// 提取人脸特征向量
int FaceEngine_ExtractFeature(void* engine,
                               unsigned char* jpeg_data,
                               int data_len,
                               float* feature_512);

// 计算余弦相似度
float FaceEngine_CosineSimilarity(const float* emb1, const float* emb2);

// 销毁引擎实例
void FaceEngine_Destroy(void* engine);
```

#### 3.2.2 返回值说明

| 函数 | 返回值 | 说明 |
|------|--------|------|
| `FaceEngine_Create` | `void*` | 引擎实例指针，失败返回 NULL |
| `FaceEngine_Init` | `int` | 0=成功，非0=失败 |
| `FaceEngine_ExtractFeature` | `int` | 0=成功，-1=未检测到人脸，其他=错误 |
| `FaceEngine_CosineSimilarity` | `float` | 余弦相似度 [0, 1] |

#### 3.2.3 C 语言使用示例

```c
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>

int main() {
    // 1. 加载动态库
    void* lib = dlopen("./libface_engine.so", RTLD_LAZY);
    if (!lib) {
        printf("加载库失败: %s\n", dlerror());
        return -1;
    }

    // 2. 获取函数指针
    void* (*FaceEngine_Create)() = dlsym(lib, "FaceEngine_Create");
    int (*FaceEngine_Init)(void*, const char*, const char*) = dlsym(lib, "FaceEngine_Init");
    int (*FaceEngine_ExtractFeature)(void*, unsigned char*, int, float*) =
        dlsym(lib, "FaceEngine_ExtractFeature");
    void (*FaceEngine_Destroy)(void*) = dlsym(lib, "FaceEngine_Destroy");

    // 3. 创建引擎
    void* engine = FaceEngine_Create();
    if (!engine) {
        printf("创建引擎失败\n");
        return -1;
    }

    // 4. 初始化
    int ret = FaceEngine_Init(engine,
                              "models/RetinaFace.rknn",
                              "models/mobilefacenet.rknn");
    if (ret != 0) {
        printf("初始化失败: %d\n", ret);
        FaceEngine_Destroy(engine);
        return -1;
    }

    // 5. 读取图片（省略文件读取代码）
    unsigned char* jpeg_data = ...; // 从文件读取
    int data_len = ...;

    // 6. 提取特征
    float feature_512[512];
    ret = FaceEngine_ExtractFeature(engine, jpeg_data, data_len, feature_512);

    if (ret == 0) {
        printf("特征提取成功\n");
        printf("前10维: ");
        for (int i = 0; i < 10; i++) {
            printf("%.4f ", feature_512[i]);
        }
        printf("\n");
    } else if (ret == -1) {
        printf("未检测到人脸\n");
    } else {
        printf("特征提取失败: %d\n", ret);
    }

    // 7. 清理
    FaceEngine_Destroy(engine);
    dlclose(lib);

    return 0;
}
```

### 3.3 API 参考

#### 3.3.1 FaceEngine_Create

**功能**：创建 FaceEngine 实例

**签名**：
```c
void* FaceEngine_Create();
```

**返回值**：
- 成功：返回引擎实例指针
- 失败：返回 NULL

**注意事项**：
- 每个实例独立管理模型和内存
- 多线程环境下建议每个线程创建独立实例

#### 3.3.2 FaceEngine_Init

**功能**：初始化引擎，加载 RKNN 模型

**签名**：
```c
int FaceEngine_Init(void* engine,
                    const char* retinaface_model,
                    const char* mobilefacenet_model);
```

**参数**：
- `engine`: FaceEngine 实例指针
- `retinaface_model`: RetinaFace 模型文件路径（.rknn）
- `mobilefacenet_model`: MobileFaceNet 模型文件路径（.rknn）

**返回值**：
- `0`: 初始化成功
- `-1`: 模型文件不存在
- `-2`: RKNN 初始化失败
- 其他：其他错误

**注意事项**：
- 必须在调用其他函数之前调用此函数
- 模型文件路径可以是相对路径或绝对路径

#### 3.3.3 FaceEngine_ExtractFeature

**功能**：从图片中提取人脸特征向量

**签名**：
```c
int FaceEngine_ExtractFeature(void* engine,
                               unsigned char* jpeg_data,
                               int data_len,
                               float* feature_512);
```

**参数**：
- `engine`: FaceEngine 实例指针
- `jpeg_data`: 图片的二进制数据（JPEG/PNG 格式）
- `data_len`: 图片数据的字节长度
- `feature_512`: 输出缓冲区，512 个 float（由调用者分配）

**返回值**：
- `0`: 成功提取特征
- `-1`: 未检测到人脸
- `-2`: 图片解码失败
- `-3`: RetinaFace 推理失败
- `-4`: MobileFaceNet 推理失败

**注意事项**：
- `feature_512` 必须由调用者预先分配 512 * sizeof(float) 的内存
- 输出特征向量已经过 L2 归一化，范数约为 1.0
- 如果图片中有多个人脸，只返回第一个检测到的人脸特征
- 支持任意尺寸的输入图片，内部会自动缩放

#### 3.3.4 FaceEngine_CosineSimilarity

**功能**：计算两个特征向量的余弦相似度

**签名**：
```c
float FaceEngine_CosineSimilarity(const float* emb1, const float* emb2);
```

**参数**：
- `emb1`: 512 维特征向量1
- `emb2`: 512 维特征向量2

**返回值**：
- 余弦相似度，范围 [0, 1]（已归一化的向量点积结果）

**相似度阈值参考**：
- `> 0.5`: 高置信度同一人（推荐用于严格场景）
- `> 0.4`: 中等置信度同一人（推荐用于一般场景）
- `> 0.3`: 较宽松（可能是同一人）
- `< 0.3`: 不同人

#### 3.3.5 FaceEngine_Destroy

**功能**：销毁 FaceEngine 实例，释放资源

**签名**：
```c
void FaceEngine_Destroy(void* engine);
```

**参数**：
- `engine`: FaceEngine 实例指针

**注意事项**：
- 必须在程序结束前调用，否则会导致内存泄漏
- 调用后 `engine` 指针失效，不应再使用

### 3.4 常见使用场景

#### 3.4.1 人脸录入

```python
# 录入用户人脸
def enroll_user(engine, user_id: int, image_path: str):
    """录入用户人脸到数据库"""
    with open(image_path, 'rb') as f:
        image_data = f.read()

    feature = engine.extract_feature(image_data)
    if feature is None:
        print(f"用户 {user_id} 人脸录入失败：未检测到人脸")
        return False

    # 存储到数据库（示例）
    # db.save_feature(user_id, feature.tolist())

    print(f"用户 {user_id} 人脸录入成功")
    return True
```

#### 3.4.2 人脸验证

```python
# 验证用户身份
def verify_user(engine, user_id: int, image_path: str, threshold: float = 0.4):
    """验证用户身份"""
    # 从数据库加载用户特征
    # stored_feature = db.load_feature(user_id)
    stored_feature = np.array(stored_feature, dtype=np.float32)

    # 提取当前图片特征
    with open(image_path, 'rb') as f:
        image_data = f.read()

    current_feature = engine.extract_feature(image_data)
    if current_feature is None:
        print("验证失败：未检测到人脸")
        return False

    # 比对特征
    is_same, similarity = engine.compare_faces(stored_feature, current_feature, threshold)

    if is_same:
        print(f"验证成功：相似度 {similarity:.4f}")
        return True
    else:
        print(f"验证失败：相似度 {similarity:.4f} < 阈值 {threshold}")
        return False
```

#### 3.4.3 1:N 识别

```python
# 在数据库中搜索匹配的用户
def identify_user(engine, image_path: str, threshold: float = 0.4):
    """识别用户（1:N 搜索）"""
    # 提取查询特征
    with open(image_path, 'rb') as f:
        image_data = f.read()

    query_feature = engine.extract_feature(image_data)
    if query_feature is None:
        print("识别失败：未检测到人脸")
        return None

    # 从数据库加载所有用户特征
    # all_users = db.load_all_features()

    best_match = None
    best_similarity = 0.0

    for user_id, stored_feature in all_users.items():
        stored_feature = np.array(stored_feature, dtype=np.float32)
        similarity = engine.compute_similarity(query_feature, stored_feature)

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = user_id

    if best_similarity > threshold:
        print(f"识别成功：用户 {best_match}，相似度 {best_similarity:.4f}")
        return best_match
    else:
        print(f"识别失败：最高相似度 {best_similarity:.4f} < 阈值 {threshold}")
        return None
```

### 3.5 性能优化建议

#### 3.5.1 重用引擎实例
```python
# ✓ 推荐：重用实例
engine = FaceEngine(...)
for img_path in image_list:
    feature = engine.extract_feature(read_image(img_path))

# ✗ 不推荐：每次都创建新实例
for img_path in image_list:
    engine = FaceEngine(...)  # 重复加载模型，浪费时间
    feature = engine.extract_feature(read_image(img_path))
```

#### 3.5.2 批量处理
```python
# 批量提取特征（利用 NPU 并行能力）
features = []
for img_path in image_list:
    feature = engine.extract_feature(read_image(img_path))
    if feature is not None:
        features.append(feature)

# 批量比对（NumPy 向量化操作）
query_feature = features[0]
similarities = np.array([
    engine.compute_similarity(query_feature, feat)
    for feat in features[1:]
])
```

#### 3.5.3 多线程注意事项
```python
# 每个线程使用独立的引擎实例
import threading

def worker_thread(image_list):
    # 线程内创建独立引擎
    engine = FaceEngine(...)

    for img_path in image_list:
        feature = engine.extract_feature(read_image(img_path))
        # 处理特征...

# 启动多个线程
threads = []
for img_batch in batches:
    t = threading.Thread(target=worker_thread, args=(img_batch,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
```

---

## 4. 项目后端集成介绍

本节介绍如何在 **FastAPI 后端**中集成和调用 **face_detection 模块**。通过 Python 封装类，后端可以轻松调用 C++ 核心库提供的人脸识别功能。

### 4.1 集成架构

```
FastAPI 后端
    ↓
backend/core/face_engine.py (Python 封装类)
    ↓ ctypes 调用
face_detection/build/libface_engine.so (C++ 核心库)
    ↓ RKNN API
NPU 硬件加速
```

### 4.2 FaceEngine Python 封装类

#### 4.2.1 文件位置

```
backend/
├── core/
│   └── face_engine.py          # FaceEngine Python 封装类
├── routers/
│   └── face.py                 # 人脸识别 API 路由
└── main.py                     # FastAPI 主入口
```

#### 4.2.2 FaceEngine 类设计

`backend/core/face_engine.py` 提供了一个完整的 Python 封装类，负责：
1. 加载 `libface_engine.so` 动态库
2. 定义 ctypes 函数签名
3. 管理引擎生命周期（单例模式）
4. 提供 Pythonic 接口

**核心代码结构**：

```python
"""
FaceEngine Python Wrapper for FastAPI Backend
封装 libface_engine.so，提供 Python 友好的接口
"""

import ctypes
import numpy as np
from pathlib import Path
from typing import Optional, List


class FaceEngine:
    """
    人脸识别引擎包裹类（单例模式）

    负责加载 C++ .so 库，管理内存指针，提供 Python 友好的接口
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """单例模式：确保全局只有一个引擎实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化人脸识别引擎"""
        if self._initialized:
            return

        # 1. 路径管理
        backend_dir = Path(__file__).parent.parent.resolve()
        project_root = backend_dir.parent

        lib_path = project_root / "face_detection" / "build" / "libface_engine.so"
        retinaface_model = project_root / "face_detection" / "models" / "RetinaFace.rknn"
        mobilefacenet_model = project_root / "face_detection" / "models" / "mobilefacenet.rknn"

        # 2. 加载动态库
        self.lib = ctypes.CDLL(str(lib_path))

        # 3. 定义 C 函数签名
        self._define_function_signatures()

        # 4. 创建引擎实例
        self.engine_ptr = self.lib.FaceEngine_Create()
        if not self.engine_ptr:
            raise RuntimeError("Failed to create FaceEngine instance")

        # 5. 初始化模型
        ret = self.lib.FaceEngine_Init(
            self.engine_ptr,
            str(retinaface_model).encode('utf-8'),
            str(mobilefacenet_model).encode('utf-8')
        )

        if ret != 0:
            self.lib.FaceEngine_Destroy(self.engine_ptr)
            raise RuntimeError(f"Failed to initialize FaceEngine (ret={ret})")

        print("[FaceEngine] Initialized successfully")
        self._initialized = True

    def _define_function_signatures(self):
        """定义 C 函数的参数类型"""
        # void* FaceEngine_Create()
        self.lib.FaceEngine_Create.restype = ctypes.c_void_p
        self.lib.FaceEngine_Create.argtypes = []

        # int FaceEngine_Init(void*, const char*, const char*)
        self.lib.FaceEngine_Init.restype = ctypes.c_int
        self.lib.FaceEngine_Init.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p
        ]

        # int FaceEngine_ExtractFeature(void*, unsigned char*, int, float*)
        self.lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
        self.lib.FaceEngine_ExtractFeature.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float)
        ]

        # float FaceEngine_CosineSimilarity(const float*, const float*)
        self.lib.FaceEngine_CosineSimilarity.restype = ctypes.c_float
        self.lib.FaceEngine_CosineSimilarity.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float)
        ]

        # void FaceEngine_Destroy(void*)
        self.lib.FaceEngine_Destroy.restype = None
        self.lib.FaceEngine_Destroy.argtypes = [ctypes.c_void_p]

    def extract_feature(self, image_bytes: bytes) -> Optional[List[float]]:
        """
        提取人脸特征向量（FastAPI 接口）

        Args:
            image_bytes: 图片的二进制数据（JPEG/PNG格式）

        Returns:
            List[float]: 512维特征向量（成功）
            None: 未检测到人脸或处理失败
        """
        if not image_bytes:
            print("[FaceEngine] Error: Empty image data")
            return None

        # 转换为 ctypes 数组
        jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
        jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

        # 准备输出缓冲区（512维浮点数组）
        feature_512 = np.zeros(512, dtype=np.float32)
        feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 调用 C++ 函数
        ret = self.lib.FaceEngine_ExtractFeature(
            self.engine_ptr,
            jpeg_ptr,
            len(image_bytes),
            feature_ptr
        )

        # 处理返回值
        if ret == 0:
            # 成功：转换为 Python List
            return feature_512.tolist()
        elif ret == -1:
            # 未检测到人脸
            print("[FaceEngine] No face detected in the image")
            return None
        else:
            # 其他错误
            print(f"[FaceEngine] Feature extraction failed (ret={ret})")
            return None

    def compute_similarity(self, feature1: List[float], feature2: List[float]) -> float:
        """
        计算两个特征向量的余弦相似度

        Args:
            feature1: 512维特征向量1
            feature2: 512维特征向量2

        Returns:
            float: 余弦相似度 [0, 1]
        """
        if not feature1 or not feature2:
            return 0.0

        if len(feature1) != 512 or len(feature2) != 512:
            print("[FaceEngine] Error: Feature vectors must be 512-dimensional")
            return 0.0

        # 转换为 numpy 数组
        arr1 = np.array(feature1, dtype=np.float32)
        arr2 = np.array(feature2, dtype=np.float32)

        # 转换为 ctypes 指针
        ptr1 = arr1.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr2 = arr2.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 调用 C++ 函数
        similarity = self.lib.FaceEngine_CosineSimilarity(ptr1, ptr2)
        return float(similarity)

    def __del__(self):
        """释放资源（防止内存泄漏）"""
        if hasattr(self, 'engine_ptr') and self.engine_ptr:
            self.lib.FaceEngine_Destroy(self.engine_ptr)
            print("[FaceEngine] Engine destroyed")


# 全局单例实例（供 FastAPI 使用）
_face_engine_instance: Optional[FaceEngine] = None


def get_face_engine() -> FaceEngine:
    """
    获取全局 FaceEngine 实例（单例模式）

    供 FastAPI 路由函数调用
    """
    global _face_engine_instance
    if _face_engine_instance is None:
        _face_engine_instance = FaceEngine()
    return _face_engine_instance
```

### 4.3 FastAPI 路由集成

#### 4.3.1 路由定义示例

在 `backend/routers/face.py` 中定义人脸识别相关的 API 路由：

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from ..core.face_engine import get_face_engine

router = APIRouter(prefix="/api/face", tags=["人脸识别"])


@router.post("/extract")
async def extract_face_feature(image: UploadFile = File(...)):
    """
    提取人脸特征向量

    Args:
        image: 上传的图片文件（JPEG/PNG）

    Returns:
        {
            "success": true,
            "feature": [512维特征向量],
            "message": "特征提取成功"
        }
    """
    # 读取图片数据
    image_bytes = await image.read()

    # 获取引擎实例
    engine = get_face_engine()

    # 提取特征
    feature = engine.extract_feature(image_bytes)

    if feature is None:
        raise HTTPException(status_code=400, detail="未检测到人脸")

    return {
        "success": True,
        "feature": feature,
        "message": "特征提取成功"
    }


@router.post("/compare")
async def compare_faces(
    image1: UploadFile = File(...),
    image2: UploadFile = File(...)
):
    """
    比较两张图片的人脸相似度

    Args:
        image1: 第一张图片
        image2: 第二张图片

    Returns:
        {
            "success": true,
            "similarity": 0.7823,
            "is_same": true,
            "message": "比对完成"
        }
    """
    # 读取图片
    image1_bytes = await image1.read()
    image2_bytes = await image2.read()

    # 获取引擎
    engine = get_face_engine()

    # 提取特征
    feature1 = engine.extract_feature(image1_bytes)
    feature2 = engine.extract_feature(image2_bytes)

    if feature1 is None or feature2 is None:
        raise HTTPException(status_code=400, detail="无法提取人脸特征")

    # 计算相似度
    similarity = engine.compute_similarity(feature1, feature2)
    is_same = similarity > 0.4  # 阈值可配置

    return {
        "success": True,
        "similarity": similarity,
        "is_same": is_same,
        "message": "比对完成"
    }


@router.post("/verify")
async def verify_user(
    user_id: int,
    image: UploadFile = File(...)
):
    """
    验证用户身份（1:1 验证）

    Args:
        user_id: 用户ID
        image: 待验证的人脸图片

    Returns:
        {
            "success": true,
            "verified": true,
            "similarity": 0.8234,
            "message": "验证成功"
        }
    """
    # 读取图片
    image_bytes = await image.read()

    # 获取引擎
    engine = get_face_engine()

    # 提取当前图片特征
    current_feature = engine.extract_feature(image_bytes)
    if current_feature is None:
        raise HTTPException(status_code=400, detail="未检测到人脸")

    # 从数据库加载用户特征（示例）
    # stored_feature = db.get_user_feature(user_id)
    # 假设已从数据库获取
    stored_feature = [...]  # 512维特征向量

    # 计算相似度
    similarity = engine.compute_similarity(stored_feature, current_feature)
    verified = similarity > 0.4

    return {
        "success": True,
        "verified": verified,
        "similarity": similarity,
        "message": "验证成功" if verified else "验证失败"
    }


@router.post("/identify")
async def identify_user(image: UploadFile = File(...)):
    """
    识别用户（1:N 搜索）

    Args:
        image: 待识别的人脸图片

    Returns:
        {
            "success": true,
            "user_id": 123,
            "similarity": 0.8567,
            "message": "识别成功"
        }
    """
    # 读取图片
    image_bytes = await image.read()

    # 获取引擎
    engine = get_face_engine()

    # 提取查询特征
    query_feature = engine.extract_feature(image_bytes)
    if query_feature is None:
        raise HTTPException(status_code=400, detail="未检测到人脸")

    # 从数据库加载所有用户特征（示例）
    # all_users = db.get_all_user_features()
    all_users = {
        # user_id: feature_vector
    }

    # 查找最匹配的用户
    best_match = None
    best_similarity = 0.0

    for user_id, stored_feature in all_users.items():
        similarity = engine.compute_similarity(query_feature, stored_feature)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = user_id

    # 判断是否超过阈值
    if best_similarity > 0.4:
        return {
            "success": True,
            "user_id": best_match,
            "similarity": best_similarity,
            "message": "识别成功"
        }
    else:
        return {
            "success": False,
            "user_id": None,
            "similarity": best_similarity,
            "message": "未找到匹配用户"
        }
```

#### 4.3.2 主应用集成

在 `backend/main.py` 中注册路由：

```python
from fastapi import FastAPI
from .routers import face
from .core.face_engine import get_face_engine

app = FastAPI(title="人脸识别门禁系统")

# 注册路由
app.include_router(face.router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化 FaceEngine"""
    try:
        engine = get_face_engine()
        print("[Main] FaceEngine initialized on startup")
    except Exception as e:
        print(f"[Main] Failed to initialize FaceEngine: {e}")
        # 可以选择是否继续启动应用


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    print("[Main] Shutting down...")


@app.get("/")
async def root():
    return {"message": "人脸识别门禁系统 API", "status": "running"}
```

### 4.4 调用流程示例

#### 4.4.1 完整的人脸录入流程

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..core.face_engine import get_face_engine
from ..database import db  # 假设的数据库模块

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.post("/{user_id}/enroll")
async def enroll_user_face(
    user_id: int,
    image: UploadFile = File(...)
):
    """
    录入用户人脸

    流程：
    1. 接收图片
    2. 提取特征向量
    3. 存储到数据库
    """
    # 1. 读取图片
    image_bytes = await image.read()

    # 2. 提取特征
    engine = get_face_engine()
    feature = engine.extract_feature(image_bytes)

    if feature is None:
        raise HTTPException(status_code=400, detail="未检测到人脸，请上传清晰的正面照")

    # 3. 存储到数据库
    try:
        db.save_user_feature(user_id, feature)
        return {
            "success": True,
            "user_id": user_id,
            "message": "人脸录入成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库错误：{str(e)}")
```

#### 4.4.2 完整的门禁验证流程

```python
@router.post("/access/verify")
async def verify_access(image: UploadFile = File(...)):
    """
    门禁验证（实时识别）

    流程：
    1. 接收摄像头图片
    2. 提取特征向量
    3. 在数据库中搜索匹配用户（1:N）
    4. 返回验证结果
    """
    # 1. 读取图片
    image_bytes = await image.read()

    # 2. 提取特征
    engine = get_face_engine()
    query_feature = engine.extract_feature(image_bytes)

    if query_feature is None:
        return {
            "success": False,
            "access_granted": False,
            "message": "未检测到人脸"
        }

    # 3. 加载所有已注册用户特征
    all_users = db.get_all_user_features()

    # 4. 查找最匹配的用户
    best_match = None
    best_similarity = 0.0

    for user_id, stored_feature in all_users.items():
        similarity = engine.compute_similarity(query_feature, stored_feature)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = user_id

    # 5. 判断是否允许访问
    threshold = 0.4  # 可从配置文件读取
    access_granted = best_similarity > threshold

    # 6. 记录访问日志
    if access_granted:
        db.log_access(user_id=best_match, success=True, similarity=best_similarity)
        user_info = db.get_user_info(best_match)
        message = f"欢迎，{user_info['name']}"
    else:
        db.log_access(user_id=None, success=False, similarity=best_similarity)
        message = "未识别，禁止进入"

    return {
        "success": True,
        "access_granted": access_granted,
        "user_id": best_match if access_granted else None,
        "similarity": best_similarity,
        "message": message
    }
```

### 4.5 关键技术点

#### 4.5.1 单例模式

```python
class FaceEngine:
    _instance = None
    _initialized = False

    def __new__(cls):
        """确保全局只有一个引擎实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**优势**：
- 避免重复加载模型（节省内存和启动时间）
- 全局共享同一个 RKNN 上下文
- FastAPI 多线程环境下的资源管理

#### 4.5.2 路径管理

```python
# 自动定位项目根目录
backend_dir = Path(__file__).parent.parent.resolve()
project_root = backend_dir.parent

lib_path = project_root / "face_detection" / "build" / "libface_engine.so"
```

**优势**：
- 不依赖当前工作目录
- 支持任意位置启动应用
- 易于部署和测试

#### 4.5.3 零拷贝数据传递

```python
# Python → C++：通过指针传递
jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

# C++ → Python：直接访问内存
feature_512 = np.zeros(512, dtype=np.float32)
feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
```

**优势**：
- 避免内存复制开销
- 提高数据传输效率
- 适合大规模图像处理

### 4.6 错误处理

#### 4.6.1 初始化错误

```python
try:
    engine = get_face_engine()
except RuntimeError as e:
    # 模型加载失败，记录日志并返回错误
    logger.error(f"FaceEngine initialization failed: {e}")
    raise HTTPException(status_code=503, detail="人脸识别服务不可用")
```

#### 4.6.2 推理错误

```python
feature = engine.extract_feature(image_bytes)
if feature is None:
    # 未检测到人脸或推理失败
    raise HTTPException(status_code=400, detail="未检测到人脸或图片格式错误")
```

#### 4.6.3 数据库错误

```python
try:
    db.save_user_feature(user_id, feature)
except Exception as e:
    logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500, detail="数据库错误")
```

### 4.7 性能优化建议

#### 4.7.1 异步处理

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)


@router.post("/extract")
async def extract_face_feature(image: UploadFile = File(...)):
    """异步提取特征"""
    image_bytes = await image.read()
    engine = get_face_engine()

    # 在线程池中执行 CPU 密集型任务
    loop = asyncio.get_event_loop()
    feature = await loop.run_in_executor(
        executor,
        engine.extract_feature,
        image_bytes
    )

    if feature is None:
        raise HTTPException(status_code=400, detail="未检测到人脸")

    return {"success": True, "feature": feature}
```

#### 4.7.2 结果缓存

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_user_feature(user_id: int):
    """缓存用户特征向量"""
    return db.get_user_feature(user_id)
```

#### 4.7.3 批量处理

```python
@router.post("/batch/extract")
async def batch_extract_features(images: List[UploadFile] = File(...)):
    """批量提取特征"""
    engine = get_face_engine()
    results = []

    for image in images:
        image_bytes = await image.read()
        feature = engine.extract_feature(image_bytes)
        results.append({
            "filename": image.filename,
            "feature": feature,
            "success": feature is not None
        })

    return {"success": True, "results": results}
```

---

