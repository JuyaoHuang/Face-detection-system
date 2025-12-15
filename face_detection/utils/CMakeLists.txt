cmake_minimum_required(VERSION 3.15)

project(rknn_model_zoo_utils)

# ===================================================
# 关键修复: 禁用 RGA 和 LibJPEG 依赖
# 这会告诉 image_utils.c 不要引用 im2d.h，也不要用 rga 函数
# ===================================================
add_definitions(-DDISABLE_RGA)
add_definitions(-DDISABLE_LIBJPEG)

# ===================================================
# 1. fileutils 静态库（文件读写）
# ===================================================
add_library(fileutils STATIC
    file_utils.c
)
target_include_directories(fileutils PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# ===================================================
# 2. imagedrawing 静态库（图像绘制）
# ===================================================
add_library(imagedrawing STATIC
    image_drawing.c
)
target_include_directories(imagedrawing PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# ===================================================
# 3. imageutils 静态库（图像处理 - 使用 CPU）
# ===================================================
add_library(imageutils STATIC
    image_utils.c
)
target_include_directories(imageutils PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# 注意：由于禁用了 RGA 和 LibJPEG，imageutils 不需要链接任何外部库
# 图像处理将使用 CPU 实现（convert_image_cpu）

# ===================================================
# 注意：audioutils 库已移除（audio_utils.c 不存在，且项目未使用）
# ===================================================
