cmake_minimum_required(VERSION 3.15)  # 匹配 utils 的最低版本要求

# ========================================
# 交叉编译配置（针对 RK3568 ARM64）
# ========================================

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# 交叉编译工具链路径（请根据实际路径修改）
set(TOOLCHAIN_DIR "/home/topeet/gcc")

set(CMAKE_C_COMPILER   "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_DIR}/bin/aarch64-linux-gnu-g++")

# 强制 CMake 只在指定路径查找库，避免链接到 x86_64 系统库
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH ${TOOLCHAIN_DIR})

# ========================================

project(FaceRecognition_Core)

set(CMAKE_CXX_STANDARD 14)

# ========================================
# 1. 第三方库配置
# ========================================

# 1.1 设置 OpenCV 的路径引导
set(OpenCV_DIR ${CMAKE_SOURCE_DIR}/third_party/opencv/lib/cmake/opencv4)

# 1.2 查找 OpenCV 包
find_package(OpenCV REQUIRED)

# 1.3 打印日志
message(STATUS "OpenCV library status:")
message(STATUS "    version: ${OpenCV_VERSION}")
message(STATUS "    libraries: ${OpenCV_LIBS}")
message(STATUS "    include path: ${OpenCV_INCLUDE_DIRS}")

# 1.4 RKNN 配置
include_directories(${CMAKE_SOURCE_DIR}/third_party/rknn/include)
link_directories(${CMAKE_SOURCE_DIR}/third_party/rknn/lib)

# ========================================
# 2. 添加子目录（utils 工具库）
# ========================================

# 设置 utils 需要的变量
set(DISABLE_RGA TRUE)          # 禁用 RGA，使用 OpenCV
set(DISABLE_LIBJPEG TRUE)      # 禁用 libjpeg，使用 OpenCV

# 添加 utils 子项目（会生成 fileutils 和 imageutils 静态库）
add_subdirectory(utils)

# ========================================
# 3. 项目头文件路径
# ========================================

include_directories(${CMAKE_SOURCE_DIR}/include)
include_directories(${CMAKE_SOURCE_DIR}/utils)  # rknn_model_zoo utils 头文件
include_directories(${CMAKE_SOURCE_DIR}/examples/RetinaFace/cpp)  # RetinaFace 头文件
include_directories(${OpenCV_INCLUDE_DIRS})

# ========================================
# 4. 源文件列表
# ========================================

set(SOURCES
    src/face_engine.cpp
    src/face_aligner.cpp
    src/mobilefacenet.cpp
    src/retinaface.cpp
    src/utils.cpp
)

# ========================================
# 5. 生成动态库
# ========================================

add_library(face_engine SHARED ${SOURCES})

# ========================================
# 6. 链接库
# ========================================

target_link_libraries(face_engine
    # RKNN 运行时库
    rknnrt

    # OpenCV 静态库
    ${OpenCV_LIBS}

    # utils 子项目生成的静态库
    fileutils
    imageutils
)

# ========================================
# 7. 安装目标
# ========================================

install(TARGETS face_engine DESTINATION lib)