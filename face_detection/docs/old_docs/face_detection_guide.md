## 架构

Python (FastAPI) 负责网络 IO，C++ 负责全套繁重的 AI 逻辑（预处理+推理+后处理），两者通过动态链接库 (.so) 交互。

人脸识别模块大致代码
```
FaceRecognition_Core/
├── CMakeLists.txt              # [核心] 编译脚本
├── build/                      # [空] 用于存放编译过程文件
├── model/                      # [存放] rknn 模型文件
│   ├── retinaface.rknn
│   └── mobilefacenet.rknn
├── src/                        # [存放] C++ 源文件
│   └── face_engine.cpp         # 核心逻辑实现
├── include/                    # [存放] 自己写的头文件
│   └── face_utils.h            # 辅助函数声明
├── 3rdparty/                   # [关键] 第三方依赖库 (随项目携带)
│   ├── rknn/
│   │   ├── include/
│   │   │   └── rknn_api.h      # 从 rknpu2 仓库复制来
│   │   └── lib/
│   │       └── librknnrt.so    # 从 rknpu2/../aarch64/ 复制来 (注意是 ARM64 版)
│   └── opencv/
│       ├── include/           # 直接把下载的 include 文件夹里的内容放这就行
│       │   └── opencv4/       # 这里多了一层 opencv4
│       │       └── opencv2/
│       └── lib/               # 把下载的 lib 文件夹里的内容放这就行
│           ├── cmake/
│           ├── libopencv_core.a
│           ├── libopencv_imgproc.a
│           └── ...
└── test_api.py                 # [可选] Python 测试脚本 (用于模拟后端调用)
```

## 数据流

1. FastAPI: 接收 HTTP 请求中的图片文件（Bytes）。
2. Ctypes: 将图片数据的内存指针传递给 C++。
3. C++ Engine:
    1. cv::imdecode: 解码图片
    2. cv::resize: 缩放图片
    3. RetinaFace: RKNN 推理 + C++后处理 (NMS, Decode)
    4. Alignment: C++ 胶水 (cv::warpAffine)
    5. MobileFaceNet: RKNN 推理
4. Output: C++ 将 512 维特征向量写入 Python 预分配的内存中
5. FastAPI: 拿到向量，在 Python 端计算余弦相似度

## 数据流动串口格式

人脸识别的数据流为：

原始图片 -> opencv缩放处理 -> RetinaFace处理得到五个特征点 -> opencv进行仿射变换进行人脸对齐 -> 对齐后的图片传入mobileface进行向量化 -> 得到向量

### RetinaFace 输入要求

RetinaFace 要求的输入尺寸是 640x640，因此需要先将 fastAPI 发送过来的图片（.jpg）大小，使用opencv 进行解码和调整样式大小。

注意： ov5695摄像头的输入数据是 BGR 格式，需要转为 RGB 使用。

在送入 Retinaface 前，数据应进行以下转换：

```bash
OV5640 (输出 640x480, BGR) -> cv.resize (缩放到 320x320, BGR) -> CvtColor (转为 320x320, RGB)-> rknn_inputs_set (填入 NPU 的输入内存)-> rknn_run (NPU 推理)
```

示例：
```c++
int extract(unsigned char* input_data, int data_len, float* output_feature) {
    // 1. 解码图片
    // input_data 是内存中的 jpeg/png 数据，直接解码为 Mat
    std::vector<uchar> raw_data(input_data, input_data + data_len);
    cv::Mat img = cv::imdecode(raw_data, cv::IMREAD_COLOR);
    if (img.empty()) return -1;
    // 2. RetinaFace 预处理 (Resize) 
    cv::Mat img_640;
    cv::resize(img, img_640, cv::Size(640, 640));
    // 3. 转为 RGB
    cv::Mat img_rgb;
    cv::cvtColor(img_320, img_rgb, cv::COLOR_BGR2RGB);
```

### RetinaFace 输出

RetinaFace 输出检测框 (Box) 和 5个关键点 (Landmarks)。这些标记都在转换后的 640x640 尺寸的图片上显示。

### mobileface 输入要求

mobileface 需要的是一个 112x112 大小的图像，因此 RetinaFace 的输出并不满足要求。需要制作一个胶水件实现：人脸对齐 + 图片放缩。

## 胶水件编写

根据数据流动要求可知，该部分应该实现**仿射变换**。

注意指针传递：在 Python 和 C++ 之间传递图像时，**千万不要发生内存拷贝**。

现在有现成的例子可参考：

C++：face_detection/examples 目录下的两个目录文件的 cpp/ 部分

python：model_trainning_part/mtcnn_pytorch/src/align_trans.py（人脸对齐算法）

```bash
align_trans.py 功能分析
  核心函数：warp_and_crop_face()
  face_img = warp_and_crop_face(
      src_img,           # 原始图像
      facial_pts,        # RetinaFace检测的5个关键点
      reference_pts,     # 参考关键点（可选，有默认值）
      crop_size=(112, 112),  # 输出尺寸，正好是MobileFaceNet的输入！
      align_type='similarity'  # 对齐类型
  )

  完整工作流程
  原始图像
    ↓
  RetinaFace检测
    ↓
  人脸框 + 5个关键点(左眼、右眼、鼻子、左嘴角、右嘴角)
    ↓
  align_trans.warp_and_crop_face()
    ↓
  对齐的112x112人脸图像
    ↓
  MobileFaceNet(已训练)
    ↓
  512维特征向量

  关键优势
  1. 标准化对齐：使用相似变换或仿射变换将人脸对齐到标准姿态
  2. 尺寸匹配：默认输出112x112，完美匹配MobileFaceNet输入要求
  3. 5点对齐：支持标准的5个关键点（眼、鼻、嘴），RetinaFace正好输出这些
  4. 灵活性：支持自定义参考点和输出尺寸
```



## 整体示例（伪代码）

```c++
#include "face_engine.h"
#include <opencv2/opencv.hpp>

// 定义人脸框结构
struct FaceInfo {
    float x1, y1, x2, y2;
    float score;
    float landmarks[10]; // 5个点 x,y
};

class FaceEngine {
private:
    rknn_context ctx_retina;
    rknn_context ctx_mobile;
    // ... 定义 anchors 等 ...

    // 胶水层：人脸对齐 (你需要实现它)
    cv::Mat align_face(const cv::Mat& src, float* landmarks) {
        // 1. 定义标准人脸的5点坐标 (ref_points)
        // 2. 获取当前 landmarks (src_points)
        // 3. 计算仿射变换矩阵: cv::estimateAffinePartial2D 或 getAffineTransform
        // 4. 执行变换: cv::warpAffine(src, dst, M, cv::Size(112, 112));
        // 5. 返回对齐后的 112x112 图像
    }

    // RetinaFace 后处理 (你需要从 Model Zoo 抄录并修改)
    std::vector<FaceInfo> post_process_retina(rknn_output* outputs) {
        // 1. 遍历输出层 (Box分支, Class分支, Landmark分支)
        // 2. 根据 Anchor 解码坐标
        // 3. 过滤低置信度框
        // 4. 执行 NMS 去除重叠框
        // 5. 返回最佳人脸
    }

public:
    int init(const char* retina_path, const char* mobile_path) {
        // 标准 rknn_init 流程...
    }

    // 对外核心接口
    int extract(unsigned char* img_data, int data_len, float* out_vector) {
        // 1. 解码图片
        std::vector<uchar> raw_data(input_data, input_data + data_len);
        cv::Mat img = cv::imdecode(raw_data, cv::IMREAD_COLOR);
        if (img.empty()) return -1;
        // 2. RetinaFace 预处理 (Resize) 
        cv::Mat img_640;
        cv::resize(img, img_640, cv::Size(640, 640));
        // 3. 转为 RGB
        cv::Mat img_rgb;
        cv::cvtColor(img_320, img_rgb, cv::COLOR_BGR2RGB);
        
        // 检测
        // rknn_inputs_set(img) -> rknn_run -> rknn_outputs_get
        std::vector<FaceInfo> faces = post_process_retina(outputs);
        if (faces.empty()) return -1; // 没检测到人脸

        // 对齐 (胶水)
        cv::Mat face_aligned = align_face(img, faces[0].landmarks);

        // 识别
        // rknn_inputs_set(face_aligned) -> rknn_run -> rknn_outputs_get
        
        // 拷贝结果
        memcpy(out_vector, mobile_outputs[0].buf, 512 * sizeof(float));
        
        return 0;
    }
};

// 导出 C 函数给 Python
extern "C" {
    FaceEngine* CreateEngine(char* m1, char* m2) { return new FaceEngine(m1, m2); }
    int GetFeature(FaceEngine* engine, uchar* data, int len, float* out) { 
        return engine->extract(data, len, out); 
    }
}
```


## CMakelist 编写

用于告诉编译器如何把上面的 C++ 代码编译成 .so 文件











