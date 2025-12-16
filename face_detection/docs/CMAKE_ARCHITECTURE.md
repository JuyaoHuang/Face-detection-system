# CMake 架构文档

## 项目概述

本项目使用**多层次 CMake 架构**，主 CMakeLists.txt 作为父构建文件，管理整个人脸识别模块的编译。

---

## 目录结构

```
face_detection/
├── CMakeLists.txt                    # 【父】主构建文件
├── include/                          # 项目头文件
│   ├── face_utils.h
│   └── rknn_box_priors.h
├── src/                              # 项目源文件
│   ├── face_engine.cpp
│   ├── face_aligner.cpp
│   ├── mobilefacenet.cpp
│   ├── retinaface.cpp
│   └── utils.cpp
├── utils/                            # 【子项目】rknn_model_zoo 工具库
│   ├── CMakeLists.txt                # 子构建文件
│   ├── file_utils.c/h
│   ├── image_utils.c/h
│   ├── image_drawing.c/h
│   └── audio_utils.c/h
├── examples/                         # 【示例项目】不参与主构建
│   ├── RetinaFace/cpp/
│   │   └── CMakeLists.txt            # 独立示例
│   └── mobilenet/cpp/
│       └── CMakeLists.txt            # 独立示例
├── third_party/                      # 第三方库
│   ├── opencv/                       # OpenCV 静态库
│   └── rknn/                         # RKNN 运行时库
└── models/                           # 模型文件
    ├── RetinaFace.rknn
    └── mobilefacenet.rknn
```

---

## CMakeLists.txt 层次关系

### 1. 父 CMakeLists.txt (`face_detection/CMakeLists.txt`)

**作用**：主构建文件，生成 `libface_engine.so` 动态库

**管理内容**：
```cmake
project(FaceRecognition_Core)

# 管理的源文件：
src/face_engine.cpp
src/face_aligner.cpp
src/mobilefacenet.cpp
src/retinaface.cpp
src/utils.cpp

# 依赖的子项目：
utils/                    # 通过 add_subdirectory(utils) 引入

# 链接的库：
- rknnrt                 # RKNN 运行时库
- ${OpenCV_LIBS}         # OpenCV 静态库（自动）
- fileutils              # utils 子项目生成
- imageutils             # utils 子项目生成

# 生成目标：
libface_engine.so        # 人脸识别引擎动态库
```

---

### 2. 子项目 CMakeLists.txt (`face_detection/utils/CMakeLists.txt`)

**作用**：构建 rknn_model_zoo 工具库（静态库）

**管理内容**：
```cmake
project(rknn_model_zoo_utils)

# 生成的静态库：
1. fileutils (STATIC)
   源文件: file_utils.c
   功能: 文件读写工具

2. imageutils (STATIC)
   源文件: image_utils.c
   功能: 图像处理工具（letterbox、格式转换）
   依赖: ${LIBRGA}（已禁用，使用 OpenCV）

3. imagedrawing (STATIC)
   源文件: image_drawing.c
   功能: 图像绘制工具（画框、文字）

4. audioutils (STATIC)
   源文件: audio_utils.c
   功能: 音频处理工具（本项目未使用）
```

**父项目的引用方式**：
```cmake
# 在父 CMakeLists.txt 中
add_subdirectory(utils)                 # 引入子项目
target_link_libraries(face_engine       # 链接子项目生成的库
    fileutils
    imageutils
)
```

---

### 3. 示例项目 CMakeLists.txt（不参与主构建）

#### `examples/RetinaFace/cpp/CMakeLists.txt`
```cmake
project(rknn_retinaface_demo)

# 作用：构建独立的 RetinaFace 示例程序
# 生成：rknn_retinaface_demo（可执行文件）
# 不参与主项目构建
```

#### `examples/mobilenet/cpp/CMakeLists.txt`
```cmake
project(rknn_mobilenet_demo)

# 作用：构建独立的 MobileNet 示例程序
# 生成：rknn_mobilenet_demo（可执行文件）
# 不参与主项目构建
```

---

## 当前构建流程

### 步骤 1: CMake 配置

```bash
cd face_detection
mkdir -p build
cd build
cmake ..
```

**执行过程**：
```
1. 读取父 CMakeLists.txt
   └─> 查找 OpenCV (find_package)
   └─> 配置 RKNN 路径

2. 处理 add_subdirectory(utils)
   └─> 进入 utils/CMakeLists.txt
   └─> 构建 fileutils.a
   └─> 构建 imageutils.a
   └─> 构建 imagedrawing.a
   └─> 构建 audioutils.a

3. 返回父项目
   └─> 配置源文件 (src/*.cpp)
   └─> 配置目标 libface_engine.so
   └─> 链接依赖库
```

### 步骤 2: 编译

```bash
make -j4
```

**编译顺序**：
```
1. 编译 utils 子项目（静态库）
   [16%] Building C object utils/CMakeFiles/fileutils.dir/file_utils.c.o
   [33%] Building C object utils/CMakeFiles/imageutils.dir/image_utils.c.o
   [50%] Linking C static library libfileutils.a
   [66%] Linking C static library libimageutils.a

2. 编译主项目源文件
   [83%] Building CXX object CMakeFiles/face_engine.dir/src/face_engine.cpp.o
   [100%] Building CXX object CMakeFiles/face_engine.dir/src/face_aligner.cpp.o
   ...

3. 链接生成动态库
   [100%] Linking CXX shared library libface_engine.so
```

**生成文件**：
```
build/
├── libface_engine.so           # 主目标（动态库）
└── utils/
    ├── libfileutils.a          # 静态库（被链接进 .so）
    ├── libimageutils.a         # 静态库（被链接进 .so）
    ├── libimagedrawing.a       # 静态库
    └── libaudioutils.a         # 静态库
```

---

## 依赖关系图

```
libface_engine.so (动态库)
  ├── src/face_engine.cpp
  ├── src/face_aligner.cpp
  ├── src/mobilefacenet.cpp
  ├── src/retinaface.cpp
  ├── src/utils.cpp
  │
  ├── [链接] rknnrt (第三方动态库)
  │
  ├── [链接] OpenCV 静态库 (自动)
  │   ├── libopencv_core.a
  │   ├── libopencv_imgproc.a
  │   ├── libopencv_imgcodecs.a
  │   └── ... (其他 OpenCV 模块)
  │
  └── [链接] utils 子项目静态库
      ├── libfileutils.a
      │   └── file_utils.c
      └── libimageutils.a
          └── image_utils.c
```

---

## 关键配置项

### 1. OpenCV 配置

```cmake
# 使用 find_package 自动查找
set(OpenCV_DIR ${CMAKE_SOURCE_DIR}/third_party/opencv/lib/cmake/opencv4)
find_package(OpenCV REQUIRED)

# 结果：
# ${OpenCV_LIBS}          - 自动包含所有需要的 .a 库
# ${OpenCV_INCLUDE_DIRS}  - 自动包含头文件路径
```

### 2. RKNN 配置

```cmake
# 手动配置（无 find_package）
include_directories(${CMAKE_SOURCE_DIR}/third_party/rknn/include)
link_directories(${CMAKE_SOURCE_DIR}/third_party/rknn/lib)
target_link_libraries(face_engine rknnrt)
```

### 3. utils 子项目配置

```cmake
# 禁用不需要的功能
set(DISABLE_RGA TRUE)          # 使用 OpenCV 代替 RGA
set(DISABLE_LIBJPEG TRUE)      # 使用 OpenCV 代替 libjpeg

# 引入子项目
add_subdirectory(utils)

# 链接生成的静态库
target_link_libraries(face_engine
    fileutils
    imageutils
)
```

---

## 编译选项和宏定义

### 当前生效的宏

由于设置了 `DISABLE_RGA` 和 `DISABLE_LIBJPEG`，以下宏会自动定义：

```c
// 在 utils/image_utils.c 中
#ifdef DISABLE_RGA
    // 使用 OpenCV 实现图像处理
#else
    // 使用 RGA 硬件加速
#endif

#ifdef DISABLE_LIBJPEG
    // 使用 OpenCV 解码 JPEG
#else
    // 使用 libjpeg
#endif
```

这样可以避免依赖 RGA 和 libjpeg 库，统一使用 OpenCV。

---

## 头文件搜索路径

CMake 配置的 include 路径优先级（从高到低）：

```cmake
1. ${CMAKE_SOURCE_DIR}/include                      # 项目头文件
2. ${CMAKE_SOURCE_DIR}/utils                        # utils 工具头文件
3. ${CMAKE_SOURCE_DIR}/examples/RetinaFace/cpp      # RetinaFace 头文件
4. ${OpenCV_INCLUDE_DIRS}                           # OpenCV 头文件
5. ${CMAKE_SOURCE_DIR}/third_party/rknn/include     # RKNN 头文件
```

---

## 库文件搜索路径

```cmake
1. ${CMAKE_SOURCE_DIR}/third_party/rknn/lib         # RKNN 库路径
2. OpenCV 库路径（自动配置）
3. utils 子项目生成的库（自动配置）
```

---

## 与示例项目的区别

| 特性 | 主项目 (face_detection) | 示例项目 (examples/*/cpp) |
|------|------------------------|--------------------------|
| **目标类型** | 动态库 (.so) | 可执行文件 (demo) |
| **依赖管理** | 使用 find_package(OpenCV) | 使用 add_subdirectory(3rdparty) |
| **utils 引用** | add_subdirectory(utils) | add_subdirectory(../../../utils) |
| **是否独立** | 主项目 | 独立项目，不参与主构建 |
| **编译方式** | cd build && cmake .. && make | cd examples/*/cpp/build && cmake .. |

---

## 编译输出总结

### 最终生成物

```
build/libface_engine.so    # 人脸识别引擎动态库（约 10-20MB）
```

**包含内容**：
- ✅ 所有项目源代码（src/*.cpp）
- ✅ OpenCV 静态库（core, imgproc, imgcodecs 等）
- ✅ utils 工具库（fileutils, imageutils）
- ✅ RKNN 接口代码
- ❌ RKNN 运行时库（librknnrt.so 需单独部署）

### 部署到 RK3568

只需传输：
```
libface_engine.so          # 主库
models/RetinaFace.rknn     # 模型文件
models/mobilefacenet.rknn  # 模型文件
```

RK3568 板子上需要：
```
/usr/lib/librknnrt.so      # RKNN 运行时库（通常已预装）
```

---

## 常见问题

### Q1: 为什么不使用 examples 中的 CMakeLists.txt？

**A**: examples 中的 CMakeLists.txt 是为**独立示例程序**设计的，它们：
- 生成可执行文件（不是库）
- 使用 `add_subdirectory(../../../3rdparty)` 引用外部依赖
- 不适合作为库的构建配置

### Q2: utils 子项目生成了 4 个静态库，为什么只链接 2 个？

**A**:
- `fileutils` - 文件读写，必需
- `imageutils` - 图像处理，必需
- `imagedrawing` - 绘图功能，可选（本项目未使用）
- `audioutils` - 音频处理，可选（本项目未使用）

只链接需要的库可以减小最终 .so 文件大小。

### Q3: 如何添加新的源文件？

**A**: 在父 CMakeLists.txt 的 SOURCES 变量中添加：
```cmake
set(SOURCES
    src/face_engine.cpp
    src/face_aligner.cpp
    src/mobilefacenet.cpp
    src/retinaface.cpp
    src/utils.cpp
    src/new_module.cpp      # 添加新文件
)
```

---

## 更新日志

- **v1.0 (2025-12-15)**: 初始版本，使用 add_subdirectory 管理 utils 子项目
- 优化了模块化设计，清晰分离了主项目和工具库
- 统一使用 OpenCV，禁用了 RGA 和 libjpeg 依赖

---

**维护者**: Juyao Huang
**最后更新**: 2025-12-15
