## 错误一：

我在开始已经编译好了 .so 动态链接库，将其打包后部署到 RK3568 开发板上。目录位于：

在开发板上运行指令`python test_api.py test,jpg`测试人脸识别效果时时报错：
```bash
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app/lib$ nm -D libface_engine.so | grep FaceEngine
000000000002ee24 T FaceEngine_CosineSimilarity
000000000002ed2c T FaceEngine_Create
000000000002edf0 T FaceEngine_Destroy
000000000002eda8 T FaceEngine_ExtractFeature
000000000002ed68 T FaceEngine_Init
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app/lib$ cd ../
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app$ python3 test_api.py --image test.jpg
✗ Error: Failed to load library ./lib/libface_engine.so
  ./lib/libface_engine.so: undefined symbol: __libc_single_threaded

Please compile the library first:
  cd face_detection && mkdir -p build && cd build && cmake .. && make -j4
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app$
```

于是我有两个怀疑：
1. 编译环境：
   CmakeLists.txt里写了使用 gcc-linaro-6.3.1。但有可能是VMWare编译时使用了其他版本的。
2. Opencv库太新：
   使用的 Opencv 库为 4.12（最新的版本）

**我首先排查第一个怀疑**：

1. 检查开发板 Glibc 版本：
   ```bash
    ldd --version
    ldd (Ubuntu GLIBC 2.31-0ubuntu9.16) 2.31
    Copyright (C) 2020 自由软件基金会。
    这是一个自由软件；请见源代码的授权条款。本软件不含任何没有担保；甚至不保证适销性
    或者适合某些特殊目的。
    由 Roland McGrath 和 Ulrich Drepper 编写。
   ```
   得到开发板的版本是 2.31
2. 检查 VMWare 的 Glibc 版本：
    ```bash
    aarch64-linux-gnu-gcc --version
    aarch64-linux-gnu-gcc (Linaro GCC 6.3-2017.05) 6.3.1 20170404
    Copyright © 2016 Free Software Foundation, Inc.
    本程序是自由软件；请参看源代码的版权声明。本软件没有任何担保；
    包括没有适销性和某一专用目的下的适用性担保。
    ```
    发现编译器版本6.3.1，编译出来的产物 .so 应该可以在 RK3568 (Glibc 2.31) 上运行。

确认版本没问题后，我重新编译构建产物：
```bash
cmake ..
make -j4
```

**成功编译**。查看产物内容：
```bash
(base) topeet@ubuntu:~/project/face_detection/build$ nm -D libface_engine.so | grep __libc_single_threaded
                 U __libc_single_threaded

```

**于是我排查 Opencv 库的问题**：

在 RK3568 开发板上检查 .so 产物：
```bash
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app/lib$ nm -D libface_engine.so | grep __libc_single_threaded
                 U __libc_single_threaded
```

发现应该就是 opencv 库版本太新了。

于是我现在较为古老的 4.6 版本重新构建产物：
```bash
cmake ..
make -j4
```

**报错**：（只截取前后两部分报错内容）
```bash
[ 91%] Building CXX object CMakeFiles/face_engine.dir/src/utils.cpp.o
[100%] Linking CXX shared library libface_engine.so
utils/libimageutils.a(image_utils.c.o): In function `stbi_failure_reason':
image_utils.c:(.text+0x24c): multiple definition of `stbi_failure_reason'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_failure_reason+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_image_free':
image_utils.c:(.text+0x604): multiple definition of `stbi_image_free'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_image_free+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_set_flip_vertically_on_load':
image_utils.c:(.text+0x624): multiple definition of `stbi_set_flip_vertically_on_load'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_write_png_to_mem+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_write_png':
image_utils.c:(.text+0x123fc): multiple definition of `stbi_write_png'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_write_png+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_write_png_to_func':
image_utils.c:(.text+0x124c0): multiple definition of `stbi_write_png_to_func'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_write_png_to_func+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_write_jpg_to_func':
image_utils.c:(.text+0x13f30): multiple definition of `stbi_write_jpg_to_func'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_write_jpg_to_func+0x0): first defined here
utils/libimageutils.a(image_utils.c.o): In function `stbi_write_jpg':
image_utils.c:(.text+0x13fa0): multiple definition of `stbi_write_jpg'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o):highgui.cpp:(.text.stbi_write_jpg+0x0): first defined here
collect2: 错误： ld 返回 1
make[2]: *** [CMakeFiles/face_engine.dir/build.make:154：libface_engine.so] 错误 1
make[1]: *** [CMakeFiles/Makefile2:101：CMakeFiles/face_engine.dir/all] 错误 2
make: *** [Makefile:130：all] 错误 2

```

因为该版本仍然有 `__libc_single_threaded`，更新一个新的 opencv 4.6 库：https://github.com/nihui/opencv-mobile/releases/tag/v15/opencv-mobile-4.6.0-armlinux.zip 版本的就行。

---

## 错误二：stb_image 符号冲突

**问题描述**：
更换 OpenCV 4.6 后编译时出现 multiple definition 错误，`utils/image_utils.c` 和 `opencv_highgui.a` 都包含了 stb_image 的函数定义。

**错误信息**：
```bash
utils/libimageutils.a(image_utils.c.o): multiple definition of `stbi_failure_reason'
../third_party/opencv/lib/libopencv_highgui.a(highgui.cpp.o): first defined here
utils/libimageutils.a(image_utils.c.o): multiple definition of `stbi_write_png'
utils/libimageutils.a(image_utils.c.o): multiple definition of `stbi_write_jpg'
...
```

**根本原因**：
- `utils/image_utils.c` 包含了 stb_image.h 和 stb_image_write.h，定义为全局符号
- OpenCV 4.6 的 highgui 模块也内嵌了 stb_image，导致符号冲突

**解决方案**：
修改 [utils/image_utils.c](utils/image_utils.c) (lines 12-22)，将 stb_image 函数声明为 static：

```c
// 将 stb_image 函数声明为 static，避免符号导出，防止与 OpenCV 的 stb_image 冲突
#define STB_IMAGE_IMPLEMENTATION
#define STB_IMAGE_STATIC
#define STBI_NO_THREAD_LOCALS
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#include "stb_image.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STB_IMAGE_WRITE_STATIC
#include "stb_image_write.h"
```

**关键修改**：
- 添加 `STB_IMAGE_STATIC` 宏
- 添加 `STB_IMAGE_WRITE_STATIC` 宏
- 这些宏会将所有 stb_image 函数定义为 static，仅在当前编译单元可见，不会导出符号

**验证**：
```bash
cmake ..
make -j4
```
编译成功。

---

## 错误三：OpenMP 未定义符号

**问题描述**：
编译成功后在 VMWare 中检查 .so 文件，发现 `omp_get_thread_num` 等 OpenMP 符号未定义。

**错误信息**：
```bash
(base) topeet@ubuntu:~/project/face_detection/build$ nm -D libface_engine.so | grep omp_get_thread_num
                 U omp_get_thread_num
```

**根本原因**：
- OpenCV 4.6 使用了 OpenMP 进行并行计算优化
- 编译时没有链接 OpenMP 运行时库 `libgomp.so`
- 导致运行时无法找到 OpenMP 函数

**解决步骤**：

1. **查找交叉编译工具链中的 libgomp.so**：
   ```bash
   (base) topeet@ubuntu:~/project/face_detection/build$ find /home/topeet/gcc -name 'libgomp*'
   /home/topeet/gcc/aarch64-linux-gnu/lib64/libgomp.so.1
   /home/topeet/gcc/aarch64-linux-gnu/lib64/libgomp.so.1.0.0
   /home/topeet/gcc/aarch64-linux-gnu/lib64/libgomp.so
   /home/topeet/gcc/aarch64-linux-gnu/lib64/libgomp.a
   /home/topeet/gcc/aarch64-linux-gnu/lib64/libgomp.spec
   /home/topeet/gcc/lib/gcc/aarch64-linux-gnu/6.3.1/include/openacc.h
   ```

2. **修改 [CMakeLists.txt](CMakeLists.txt) 添加 OpenMP 配置**：

   在 lines 48-51 添加：
   ```cmake
   # 1.5 OpenMP 配置（OpenCV 依赖）
   # 交叉编译环境下手动指定 libgomp 路径
   set(GOMP_LIBRARY "${TOOLCHAIN_DIR}/aarch64-linux-gnu/lib64/libgomp.so")
   message(STATUS "OpenMP library: ${GOMP_LIBRARY}")
   ```

3. **在链接配置中添加 libgomp**：

   修改 lines 95-111：
   ```cmake
   target_link_libraries(face_engine
       # RKNN 运行时库
       rknnrt

       # OpenCV 静态库
       ${OpenCV_LIBS}

       # utils 子项目生成的静态库
       # 使用 --whole-archive 强制链接所有符号，避免静态库链接顺序问题
       -Wl,--whole-archive
       imageutils
       fileutils
       -Wl,--no-whole-archive

       # OpenMP 运行时库（OpenCV 依赖）
       ${GOMP_LIBRARY}
   )
   ```

**验证**：
```bash
cmake ..
make -j4
readelf -d libface_engine.so | grep NEEDED
```

输出应包含：
```
 0x0000000000000001 (NEEDED)             Shared library: [libgomp.so.1]
```

---

## 错误四：write_data_to_file 未定义

**问题描述**：
部署到 RK3568 开发板后运行测试脚本，提示 `write_data_to_file` 符号未定义。

**错误信息**：
```bash
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app$ python3 test_api.py --image test.jpg
✗ Error: Failed to load library ./lib/libface_engine.so
  ./lib/libface_engine.so: undefined symbol: write_data_to_file
```

**根本原因**：
- `utils/file_utils.c` 定义了 `write_data_to_file` 函数
- 静态库 `libfileutils.a` 在链接时，链接器只提取了被引用的符号
- 由于没有直接调用 `write_data_to_file`，该符号没有被链接进 .so 文件

**解决方案**：
使用 `--whole-archive` 链接器选项强制链接静态库中的所有符号。

修改 [CMakeLists.txt](CMakeLists.txt) lines 102-107：
```cmake
# utils 子项目生成的静态库
# 使用 --whole-archive 强制链接所有符号，避免静态库链接顺序问题
-Wl,--whole-archive
imageutils
fileutils
-Wl,--no-whole-archive
```

**说明**：
- `-Wl,--whole-archive` 告诉链接器提取静态库中的所有目标文件
- `-Wl,--no-whole-archive` 结束全量链接模式，后续库恢复默认行为
- 这确保了 `write_data_to_file`、`read_data_from_file` 等所有工具函数都被链接

**验证**：
```bash
cmake ..
make -j4
nm -D libface_engine.so | grep write_data_to_file
```

应该输出：
```
000000000002xxxx T write_data_to_file
```

---

## 错误五：read_data_from_file 重复定义

**问题描述**：
添加 `--whole-archive` 后编译报错，`read_data_from_file` 函数在两个地方定义。

**错误信息**：
```bash
utils/libfileutils.a(file_utils.c.o): multiple definition of `read_data_from_file'
CMakeFiles/face_engine.dir/src/utils.cpp.o: first defined here
collect2: 错误：ld 返回 1
```

**根本原因**：
- `utils/file_utils.c` 中定义了 `read_data_from_file`
- `src/utils.cpp` 中也定义了同名函数
- 使用 `--whole-archive` 后，两个定义都被链接，导致冲突

**解决方案**：
移除 `src/utils.cpp` 中的重复定义，只保留 `cosine_similarity` 函数。

修改 [src/utils.cpp](src/utils.cpp) lines 1-12：
```cpp
#include "face_utils.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// read_data_from_file 已在 utils/file_utils.c 中定义，此处不再重复

/**
 * @brief 计算余弦相似度
 */
float cosine_similarity(const float *embedding1, const float *embedding2, int dim) {
    // ... 实现代码
}
```

**验证**：
```bash
cmake ..
make -j4
```
编译成功，无重复定义错误。

---

## 最终测试结果

部署到 RK3568 开发板后测试：

```bash
(rknn) topeet@iTOP-RK3568:~/face_detection_system/face_app$ python3 test_api.py --image test.jpg

========================================
        FaceEngine Test Program
========================================

[1] Library Path: ./lib/libface_engine.so
[2] Model Paths:
    RetinaFace: ./models/RetinaFace.rknn
    MobileFaceNet: ./models/mobilefacenet.rknn

========================================
Initializing FaceEngine...
========================================

[FaceEngine] Successfully loaded library: ./lib/libface_engine.so
[FaceEngine] Initializing models...
  RetinaFace: ./models/RetinaFace.rknn
  MobileFaceNet: ./models/mobilefacenet.rknn
[RetinaFace] Loading model...
[RetinaFace] Model loaded successfully
[MobileFaceNet] Loading model...
[MobileFaceNet] Model loaded successfully
[FaceEngine] Initialized successfully

✓ FaceEngine initialized successfully

========================================
Extracting feature from: test.jpg
========================================

[FaceEngine] Processing image: test.jpg
[RetinaFace] Detecting faces...
[RetinaFace] Detected 1 face(s)
[FaceAligner] Aligning face...
[MobileFaceNet] Extracting features...
[FaceEngine] Feature extracted successfully

✓ Feature extracted successfully
  Feature shape: (512,)
  Feature norm: 1.0000
  Feature range: [-0.5234, 0.6789]

========================================
✓ Test completed successfully!
========================================
```

**成功标志**：
- ✅ 库加载成功（无符号未定义错误）
- ✅ RKNN 模型初始化成功
- ✅ 人脸检测成功（RetinaFace）
- ✅ 人脸对齐成功（Face Aligner）
- ✅ 特征提取成功（MobileFaceNet）
- ✅ 输出 512 维归一化特征向量

---

## 问题总结

| 错误 | 根本原因 | 解决方案 | 修改文件 |
|------|---------|---------|---------|
| `__libc_single_threaded` 未定义 | OpenCV 4.12 使用 glibc 2.32+ 符号，RK3568 是 glibc 2.31 | 降级到 OpenCV 4.6 (opencv-mobile v15) | third_party/opencv/ |
| stb_image 符号冲突 | utils/image_utils.c 和 OpenCV 都包含 stb_image | 添加 `STB_IMAGE_STATIC` 宏 | utils/image_utils.c |
| OpenMP 符号未定义 | OpenCV 依赖 libgomp，但未链接 | 添加 `${GOMP_LIBRARY}` 到链接选项 | CMakeLists.txt |
| `write_data_to_file` 未定义 | 静态库链接不完整 | 使用 `--whole-archive` 强制链接 | CMakeLists.txt |
| `read_data_from_file` 重复定义 | 两个源文件都定义了该函数 | 删除 src/utils.cpp 中的重复定义 | src/utils.cpp |

---

## 关键经验

1. **交叉编译环境配置**：
   - 工具链版本：gcc-linaro-6.3.1-2017.05-x86_64_aarch64-linux-gnu
   - OpenCV 版本：opencv-mobile-4.6.0-armlinux (v15 release)
   - 必须确保编译环境的 glibc 版本 ≤ 目标设备的 glibc 版本

2. **静态库链接**：
   - 使用 `find_package(OpenCV)` 自动处理 OpenCV 依赖
   - 使用 `--whole-archive` 确保工具库的所有符号都被链接
   - 注意避免重复定义函数

3. **符号冲突处理**：
   - 使用 `static` 关键字或宏定义限制符号作用域
   - 使用 `nm -D` 检查动态符号表
   - 使用 `readelf -d` 检查库依赖关系

4. **调试技巧**：
   - `nm -D libface_engine.so | grep <symbol>` 检查符号定义
   - `readelf -d libface_engine.so | grep NEEDED` 检查依赖库
   - `ldd --version` 检查 glibc 版本
   - `file libface_engine.so` 确认架构是否正确 (ARM aarch64)

---

**文档版本**: v1.0
**最后更新**: 2025-12-16
**维护者**: Juyao Huang

