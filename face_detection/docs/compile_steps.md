# 人脸检测模块编译运行步骤

> 详细介绍在 VMWare Ubuntu 环境中交叉编译 face_detection 模块的完整流程

---

## 目录

- [1. 环境准备](#1-环境准备)
- [2. 依赖库安装](#2-依赖库安装)
- [3. CMake 配置](#3-cmake-配置)
- [4. 编译过程](#4-编译过程)
- [5. 验证编译结果](#5-验证编译结果)

---

## 1. 环境准备

### 1.1 VMWare 虚拟机配置

#### 1.1.1 系统要求

| 项目 | 配置要求 | 说明 |
|------|---------|------|
| **操作系统** | Ubuntu 20.04 LTS (x86_64) | 推荐使用 LTS 版本 |
| **内存** | 至少 4GB | 推荐 8GB 以上 |
| **硬盘空间** | 至少 20GB | 用于存放工具链、依赖库和编译产物 |
| **VMWare 版本** | VMWare Workstation 15+ | 或 VMWare Player |

#### 1.1.2 VMWare 虚拟机创建

1. **创建新虚拟机**
   - 选择"自定义（高级）"安装
   - 虚拟机硬件兼容性：Workstation 15.x

2. **系统配置**
   - 安装 Ubuntu 20.04 LTS Desktop
   - 处理器配置：2 核（推荐 4 核）
   - 内存：4GB（推荐 8GB）
   - 硬盘：20GB（动态分配）

3. **网络配置**
   - 网络适配器：NAT 模式（用于访问外网下载依赖）
   - 或桥接模式（与开发板在同一网络，便于文件传输）

#### 1.1.3 系统基础配置

安装完成后，在 Ubuntu 中执行以下命令：

```bash
# 更新软件源
sudo apt update

# 安装基础工具
sudo apt install -y vim git wget curl build-essential

# 安装 SSH 服务（可选，用于远程连接）
sudo apt install -y openssh-server
sudo systemctl enable ssh
sudo systemctl start ssh
```

### 1.2 目录结构规划

建议在 VMWare 中创建以下目录结构：

```bash
# 创建工作目录
mkdir -p ~/project
mkdir -p ~/toolchain
mkdir -p ~/libs

# 目录说明：
# ~/project          - 存放项目源码
# ~/toolchain        - 存放交叉编译工具链
# ~/libs             - 存放第三方依赖库（OpenCV, RKNN）
```

**最终目录布局**：
```
/home/topeet/
├── project/
│   └── face_detection/          # 项目源码
├── toolchain/
│   └── gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/  # 交叉编译器
└── libs/
    ├── opencv-mobile-4.6.0-armlinux/    # OpenCV ARM64 版本
    └── rknpu2/                          # RKNN SDK
```

---

## 2. 依赖库安装

### 2.1 交叉编译工具链

#### 2.1.1 下载工具链

**工具链信息**：
- 名称：gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu
- 架构：x86_64 → ARM64 (aarch64)
- 版本：GCC 6.3.1
- 用途：在 x86 Ubuntu 上编译 ARM64 二进制文件

**下载地址**：
```
https://releases.linaro.org/components/toolchain/binaries/6.3-2017.05/aarch64-linux-gnu/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu.tar.xz
```

**下载和解压**：

```bash
# 进入工具链目录
cd ~/toolchain

# 下载工具链（约 200MB）
wget https://releases.linaro.org/components/toolchain/binaries/6.3-2017.05/aarch64-linux-gnu/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu.tar.xz

# 解压
tar -xf gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu.tar.xz

# 验证
ls gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin/
# 应该看到：aarch64-linux-gnu-gcc, aarch64-linux-gnu-g++, 等文件
```

#### 2.1.2 验证工具链

```bash
# 设置临时环境变量
export PATH=~/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin:$PATH

# 验证编译器
aarch64-linux-gnu-gcc --version

# 应该输出：
# aarch64-linux-gnu-gcc (Linaro GCC 6.3-2017.05) 6.3.1 20170404
```

**工具链路径**（后续 CMake 配置会用到）：
```
/home/topeet/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu
```

### 2.2 OpenCV 静态库

#### 2.2.1 下载 OpenCV Mobile

**库信息**：
- 名称：opencv-mobile
- 版本：4.6.0
- 架构：armlinux (ARM64)
- 类型：静态库（.a 文件）
- 维护者：nihui

**下载地址**：
```
https://github.com/nihui/opencv-mobile/releases/download/v15/opencv-mobile-4.6.0-armlinux.zip
```

**为什么使用 OpenCV 4.6.0？**
- 与 gcc-linaro-6.3.1 编译器版本兼容
- 静态库形式，便于部署
- 已针对 ARM 架构优化
- 包含必要的图像处理模块（core, imgproc, imgcodecs）

**下载和解压**：

```bash
# 进入库目录
cd ~/libs

# 下载 OpenCV（约 20MB）
wget https://github.com/nihui/opencv-mobile/releases/download/v15/opencv-mobile-4.6.0-armlinux.zip

# 解压
unzip opencv-mobile-4.6.0-armlinux.zip

# 查看目录结构
ls opencv-mobile-4.6.0-armlinux/
# 应该看到：include/, lib/, cmake/
```

#### 2.2.2 OpenCV 目录结构

```
opencv-mobile-4.6.0-armlinux/
├── include/
│   └── opencv2/              # OpenCV 头文件
│       ├── core.hpp
│       ├── imgproc.hpp
│       ├── imgcodecs.hpp
│       └── ...
├── lib/
│   ├── libopencv_core.a      # 核心模块（静态库）
│   ├── libopencv_imgproc.a   # 图像处理模块
│   ├── libopencv_imgcodecs.a # 图像编解码模块
│   └── ...
└── cmake/
    └── opencv4/
        └── OpenCVConfig.cmake  # CMake 配置文件
```

**OpenCV 路径**（后续 CMake 配置会用到）：
```
/home/topeet/libs/opencv-mobile-4.6.0-armlinux
```

### 2.3 RKNN SDK

#### 2.3.1 下载 RKNN SDK

**SDK 信息**：
- 名称：rknpu2
- 版本：1.4.0+
- 平台：RK3568
- 组件：librknnrt.so（运行时库）

**下载地址**：
```
https://github.com/rockchip-linux/rknpu2
```

**下载和解压**：

```bash
# 进入库目录
cd ~/libs

# 克隆 RKNN SDK 仓库
git clone https://github.com/rockchip-linux/rknpu2.git

# 或者下载 Release 版本
wget https://github.com/rockchip-linux/rknpu2/archive/refs/tags/v1.4.0.tar.gz
tar -xf v1.4.0.tar.gz
mv rknpu2-1.4.0 rknpu2
```

#### 2.3.2 提取 RKNN 库文件

我们只需要两个文件：
1. `rknn_api.h`（头文件）
2. `librknnrt.so`（运行时库，ARM64 版本）

```bash
# 创建项目第三方库目录
cd ~/project/face_detection
mkdir -p third_party/rknn/include
mkdir -p third_party/rknn/lib

# 复制头文件
cp ~/libs/rknpu2/runtime/RK3568/Linux/librknn_api/include/rknn_api.h \
   third_party/rknn/include/

# 复制 ARM64 运行时库
cp ~/libs/rknpu2/runtime/RK3568/Linux/librknn_api/aarch64/librknnrt.so \
   third_party/rknn/lib/

# 验证
ls third_party/rknn/include/
# 应该看到：rknn_api.h

ls third_party/rknn/lib/
# 应该看到：librknnrt.so
```

### 2.4 安装 CMake

```bash
# 安装 CMake（版本 >= 3.10）
sudo apt install -y cmake

# 验证版本
cmake --version
# 应该输出：cmake version 3.16.3 或更高
```

### 2.5 依赖库清单总结

| 依赖库 | 版本 | 路径 | 用途 |
|--------|------|------|------|
| **gcc-linaro** | 6.3.1 | `~/toolchain/gcc-linaro-6.3.1-...` | 交叉编译器 |
| **OpenCV** | 4.6.0 | `~/libs/opencv-mobile-4.6.0-armlinux` | 图像处理（静态库） |
| **RKNN SDK** | 1.4.0+ | `~/project/face_detection/third_party/rknn` | NPU 推理运行时 |
| **CMake** | 3.16.3+ | 系统路径 | 构建系统 |

---

## 3. CMake 配置

### 3.1 项目 CMakeLists.txt 结构

项目的 `face_detection/CMakeLists.txt` 文件负责配置整个编译过程。

**核心配置内容**：
1. 交叉编译工具链设置
2. OpenCV 路径配置
3. RKNN 库链接
4. 源文件和头文件管理
5. 生成动态库 libface_engine.so

### 3.2 交叉编译配置

在 `CMakeLists.txt` 的**最开头**（`project()` 之前）添加交叉编译配置：

```cmake
cmake_minimum_required(VERSION 3.10)

# ================= 交叉编译配置 =================
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# 设置交叉编译工具链路径（根据实际路径修改）
set(TOOLCHAIN_DIR "/home/topeet/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu")

# 指定编译器
set(CMAKE_C_COMPILER   "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-g++")

# 强制 CMake 只在指定路径查找库，避免链接到系统的 x86 库
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH ${TOOLCHAIN_DIR})
# ================================================

project(FaceRecognition_Core)
```

**配置说明**：
- `CMAKE_SYSTEM_NAME`：目标系统为 Linux
- `CMAKE_SYSTEM_PROCESSOR`：目标架构为 aarch64（ARM64）
- `CMAKE_C_COMPILER`：指定 C 编译器为 aarch64-linux-gnu-gcc
- `CMAKE_CXX_COMPILER`：指定 C++ 编译器为 aarch64-linux-gnu-g++
- `CMAKE_FIND_ROOT_PATH_MODE_*`：防止链接到 x86 系统库

### 3.3 OpenCV 配置

```cmake
# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 设置 OpenCV 路径（使用 find_package 自动查找）
set(OpenCV_DIR "/home/topeet/libs/opencv-mobile-4.6.0-armlinux/cmake/opencv4")

# 查找 OpenCV
find_package(OpenCV REQUIRED)

if(OpenCV_FOUND)
    message(STATUS "OpenCV version: ${OpenCV_VERSION}")
    message(STATUS "OpenCV include dirs: ${OpenCV_INCLUDE_DIRS}")
    message(STATUS "OpenCV libraries: ${OpenCV_LIBS}")
else()
    message(FATAL_ERROR "OpenCV not found")
endif()
```

**配置说明**：
- `OpenCV_DIR`：指向 OpenCVConfig.cmake 所在目录
- `find_package(OpenCV REQUIRED)`：自动查找 OpenCV 配置
- 成功后会设置 `${OpenCV_INCLUDE_DIRS}` 和 `${OpenCV_LIBS}` 变量

### 3.4 包含目录和源文件

```cmake
# 包含目录
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include          # 项目头文件
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rknn/include  # RKNN 头文件
    ${OpenCV_INCLUDE_DIRS}                       # OpenCV 头文件（自动）
)

# 源文件
set(SOURCES
    src/face_engine.cpp
    src/face_aligner.cpp
    src/retinaface.cpp
    src/mobilefacenet.cpp
    src/utils.cpp
)
```

### 3.5 生成动态库

```cmake
# 生成动态库
add_library(face_engine SHARED ${SOURCES})

# 链接库
target_link_libraries(face_engine
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rknn/lib/librknnrt.so  # RKNN 运行时
    ${OpenCV_LIBS}                                                  # OpenCV 静态库（自动）
)

# 设置输出目录
set_target_properties(face_engine PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build
)

# 安装规则（可选）
install(TARGETS face_engine DESTINATION lib)
```

**配置说明**：
- `add_library(face_engine SHARED ...)`：生成动态库 libface_engine.so
- `target_link_libraries(...)`：链接 RKNN 和 OpenCV 库
- `${OpenCV_LIBS}`：自动包含所有需要的 OpenCV 静态库
- 输出目录设置为 `face_detection/build/`

### 3.6 完整 CMakeLists.txt 示例

```cmake
cmake_minimum_required(VERSION 3.10)

# ================= 交叉编译配置 =================
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(TOOLCHAIN_DIR "/home/topeet/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu")

set(CMAKE_C_COMPILER   "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-g++")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH ${TOOLCHAIN_DIR})
# ================================================

project(FaceRecognition_Core)

# C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# OpenCV 配置
set(OpenCV_DIR "/home/topeet/libs/opencv-mobile-4.6.0-armlinux/cmake/opencv4")
find_package(OpenCV REQUIRED)

# 包含目录
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rknn/include
    ${OpenCV_INCLUDE_DIRS}
)

# 源文件
set(SOURCES
    src/face_engine.cpp
    src/face_aligner.cpp
    src/retinaface.cpp
    src/mobilefacenet.cpp
    src/utils.cpp
)

# 生成动态库
add_library(face_engine SHARED ${SOURCES})

# 链接库
target_link_libraries(face_engine
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rknn/lib/librknnrt.so
    ${OpenCV_LIBS}
)

# 输出目录
set_target_properties(face_engine PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build
)

# 安装
install(TARGETS face_engine DESTINATION lib)
```

---

## 4. 编译过程

### 4.1 编译前检查

在开始编译前，确认以下内容：

```bash
# 1. 确认工具链已安装
ls ~/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-gcc

# 2. 确认 OpenCV 已下载
ls ~/libs/opencv-mobile-4.6.0-armlinux/cmake/opencv4/OpenCVConfig.cmake

# 3. 确认 RKNN 库已复制
ls ~/project/face_detection/third_party/rknn/lib/librknnrt.so

# 4. 确认 CMakeLists.txt 中的路径正确
cat ~/project/face_detection/CMakeLists.txt | grep TOOLCHAIN_DIR
cat ~/project/face_detection/CMakeLists.txt | grep OpenCV_DIR
```

### 4.2 创建构建目录

```bash
# 进入项目目录
cd ~/project/face_detection

# 创建 build 目录
mkdir -p build
cd build
```

### 4.3 运行 CMake 配置

```bash
# 运行 CMake 配置
cmake ..

# 预期输出：
# -- The C compiler identification is GNU 6.3.1
# -- The CXX compiler identification is GNU 6.3.1
# -- Detecting C compiler ABI info - done
# -- Detecting CXX compiler ABI info - done
# -- OpenCV version: 4.6.0
# -- OpenCV include dirs: /home/topeet/libs/opencv-mobile-4.6.0-armlinux/include/opencv4
# -- OpenCV libraries: opencv_core;opencv_imgproc;opencv_imgcodecs;...
# -- Configuring done
# -- Generating done
# -- Build files have been written to: /home/topeet/project/face_detection/build
```

**常见 CMake 错误及解决方法**：

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Could not find OpenCV` | OpenCV_DIR 路径错误 | 检查 `OpenCV_DIR` 是否指向正确的 cmake 目录 |
| `compiler not found` | 工具链路径错误 | 检查 `TOOLCHAIN_DIR` 是否正确 |
| `librknnrt.so not found` | RKNN 库未复制 | 确认 `third_party/rknn/lib/librknnrt.so` 存在 |

### 4.4 编译

```bash
# 使用 make 编译（-j4 表示使用 4 个线程并行编译）
make -j4

# 预期输出：
# Scanning dependencies of target face_engine
# [ 20%] Building CXX object CMakeFiles/face_engine.dir/src/face_engine.cpp.o
# [ 40%] Building CXX object CMakeFiles/face_engine.dir/src/face_aligner.cpp.o
# [ 60%] Building CXX object CMakeFiles/face_engine.dir/src/retinaface.cpp.o
# [ 80%] Building CXX object CMakeFiles/face_engine.dir/src/mobilefacenet.cpp.o
# [100%] Building CXX object CMakeFiles/face_engine.dir/src/utils.cpp.o
# [100%] Linking CXX shared library ../build/libface_engine.so
# [100%] Built target face_engine
```

**编译时间**：
- 单线程（make）：约 5-10 分钟
- 4 线程（make -j4）：约 2-3 分钟

**常见编译错误及解决方法**：

| 错误类型 | 可能原因 | 解决方法 |
|---------|---------|---------|
| **头文件找不到** | include 路径配置错误 | 检查 `include_directories()` |
| **链接错误** | 库文件路径错误 | 检查 `target_link_libraries()` |
| **符号未定义** | 缺少源文件或库 | 确认所有源文件都在 `SOURCES` 中 |
| **C++ 标准错误** | 编译器版本不支持 C++11 | 确认使用 gcc 6.3.1 |

### 4.5 清理重新编译

如果编译出错需要重新编译：

```bash
# 清理编译产物
cd ~/project/face_detection/build
make clean

# 或完全删除 build 目录重新开始
cd ~/project/face_detection
rm -rf build
mkdir build
cd build
cmake ..
make -j4
```

---

## 5. 验证编译结果

### 5.1 检查生成的库文件

```bash
# 查看生成的 .so 文件
cd ~/project/face_detection/build
ls -lh libface_engine.so

# 应该看到：
# -rwxr-xr-x 1 topeet topeet 15M Dec 16 10:30 libface_engine.so
```

**文件大小**：
- 约 10-20MB（包含静态链接的 OpenCV 代码）
- 如果小于 5MB，可能是编译配置错误

### 5.2 验证文件架构

```bash
# 使用 file 命令检查架构
file libface_engine.so

# 必须显示 ARM64 架构：
# libface_engine.so: ELF 64-bit LSB shared object, ARM aarch64, version 1 (SYSV), dynamically linked, not stripped
```

**关键信息**：
- `ELF 64-bit`：64 位 ELF 格式
- `ARM aarch64`：ARM64 架构（正确！）
- `dynamically linked`：动态库

**错误示例**：
如果显示 `x86-64`，说明交叉编译配置未生效，编译的是 x86 版本！
```bash
# 错误示例：
# libface_engine.so: ELF 64-bit LSB shared object, x86-64, ...
```

### 5.3 检查依赖库

```bash
# 查看依赖的动态库
readelf -d libface_engine.so | grep NEEDED

# 应该看到：
# 0x0000000000000001 (NEEDED)             Shared library: [librknnrt.so]
# 0x0000000000000001 (NEEDED)             Shared library: [libpthread.so.0]
# 0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
# 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
# 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
# 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
```

**依赖分析**：
- `librknnrt.so`：RKNN 运行时（正常）
- `libpthread.so.0`：线程库（系统提供）
- `libstdc++.so.6`：C++ 标准库（系统提供）
- **注意**：没有 `libopencv_*.so`，说明 OpenCV 已静态链接（正确！）

### 5.4 检查导出的符号

```bash
# 查看导出的函数符号
nm -D libface_engine.so | grep FaceEngine

# 应该看到：
# 00000000000xxxxx T FaceEngine_Create
# 00000000000xxxxx T FaceEngine_Init
# 00000000000xxxxx T FaceEngine_ExtractFeature
# 00000000000xxxxx T FaceEngine_CosineSimilarity
# 00000000000xxxxx T FaceEngine_Destroy
```

**符号类型说明**：
- `T`：表示这是一个全局导出的函数（正确）
- 如果没有这些符号，说明 C 接口未正确导出

### 5.5 测试脚本验证（在 VMWare 上无法运行）

在 VMWare 上**无法运行**编译出的库（因为架构不同），但可以检查是否能加载：

```bash
# 尝试加载库（会失败，但可以看到错误信息）
python3 -c "import ctypes; ctypes.CDLL('./libface_engine.so')"

# 预期错误：
# OSError: ./libface_engine.so: cannot open shared object file: Exec format error
# 这是正常的，因为库是 ARM64 格式，无法在 x86 系统上运行
```

### 5.6 编译成功检查清单

在传输到开发板之前，确认以下内容：

- [ ] `libface_engine.so` 文件存在于 `build/` 目录
- [ ] 文件大小在 10-20MB 之间
- [ ] `file` 命令显示 `ARM aarch64` 架构
- [ ] `readelf -d` 显示依赖 `librknnrt.so`
- [ ] `nm -D` 显示导出了 FaceEngine_* 函数
- [ ] CMake 配置无错误
- [ ] 编译过程无错误

如果所有检查都通过，说明**编译成功**，可以将 `libface_engine.so` 传输到 RK3568 开发板进行测试。

---

## 附录

### A. 编译环境变量总结

```bash
# 交叉编译工具链
export PATH=~/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin:$PATH

# 可选：添加到 ~/.bashrc 永久生效
echo 'export PATH=~/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### B. 快速编译脚本

创建 `build.sh` 脚本简化编译流程：

```bash
#!/bin/bash
# build.sh - 快速编译脚本

set -e  # 遇到错误立即退出

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始编译 face_detection 模块...${NC}"

# 清理旧的 build 目录
if [ -d "build" ]; then
    echo "清理旧的 build 目录..."
    rm -rf build
fi

# 创建 build 目录
mkdir build
cd build

# 运行 CMake
echo -e "${GREEN}运行 CMake 配置...${NC}"
cmake ..

# 编译
echo -e "${GREEN}开始编译（使用 4 线程）...${NC}"
make -j4

# 验证
echo -e "${GREEN}验证编译结果...${NC}"
if [ -f "libface_engine.so" ]; then
    echo -e "${GREEN}✓ libface_engine.so 生成成功${NC}"
    file libface_engine.so
    ls -lh libface_engine.so
else
    echo -e "${RED}✗ 编译失败，未找到 libface_engine.so${NC}"
    exit 1
fi

echo -e "${GREEN}编译完成！${NC}"
```

使用方法：
```bash
cd ~/project/face_detection
chmod +x build.sh
./build.sh
```

### C. 常见问题排查

#### Q1: CMake 找不到编译器

**错误信息**：
```
CMake Error: your C compiler: "CMAKE_C_COMPILER-NOTFOUND" was not found
```

**解决方法**：
```bash
# 检查工具链路径
ls ~/toolchain/gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-gcc

# 修改 CMakeLists.txt 中的 TOOLCHAIN_DIR 为实际路径
```

#### Q2: OpenCV 找不到

**错误信息**：
```
CMake Error at CMakeLists.txt:X (find_package):
  Could not find a package configuration file provided by "OpenCV"
```

**解决方法**：
```bash
# 检查 OpenCV 路径
ls ~/libs/opencv-mobile-4.6.0-armlinux/cmake/opencv4/OpenCVConfig.cmake

# 修改 CMakeLists.txt 中的 OpenCV_DIR 为正确路径
```

#### Q3: 链接时找不到 librknnrt.so

**错误信息**：
```
/usr/bin/ld: cannot find -lrknnrt
```

**解决方法**：
```bash
# 确认 RKNN 库已复制到 third_party/rknn/lib/
ls third_party/rknn/lib/librknnrt.so

# 如果不存在，重新复制
cp ~/libs/rknpu2/runtime/RK3568/Linux/librknn_api/aarch64/librknnrt.so \
   third_party/rknn/lib/
```

---

**文档版本**: v1.0
**最后更新**: 2025-12-16
**维护者**: Juyao Huang
