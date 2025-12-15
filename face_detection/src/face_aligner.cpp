#include "face_utils.h"
#include <opencv2/opencv.hpp>
#include <vector>
#include <cstring>

using namespace cv;

/**
 * @brief 人脸对齐（仿射变换）
 *
 * 根据RetinaFace检测到的5个关键点，将人脸对齐到标准姿态（112x112, RGB）
 *
 * @param src_img 原始图像（BGR格式）
 * @param landmarks 5个关键点（左眼、右眼、鼻尖、左嘴角、右嘴角）
 * @param aligned_face 输出对齐后的人脸图像 (112x112, RGB)
 * @return 0: 成功, -1: 失败
 */
int align_face(image_buffer_t *src_img, point_t landmarks[5], image_buffer_t *aligned_face) {
    if (!src_img || !landmarks || !aligned_face) {
        printf("[face_aligner] Error: NULL pointer input\n");
        return -1;
    }

    if (!src_img->virt_addr || src_img->width <= 0 || src_img->height <= 0) {
        printf("[face_aligner] Error: Invalid source image\n");
        return -1;
    }

    // 1. 将 image_buffer_t 转换为 cv::Mat
    Mat src_mat(src_img->height, src_img->width, CV_8UC3, src_img->virt_addr);

    // 注意：src_img 可能是 BGR 或 RGB，这里假设是 BGR（OpenCV 默认）
    // 如果 src_img->format == 0 (RGB)，需要转换
    if (src_img->format == 0) {
        cvtColor(src_mat, src_mat, COLOR_RGB2BGR);
    }

    // 2. 准备源关键点（来自 RetinaFace 检测结果）
    std::vector<Point2f> src_points;
    for (int i = 0; i < 5; i++) {
        src_points.push_back(Point2f(landmarks[i].x, landmarks[i].y));
    }

    // 3. 准备目标关键点（MobileFaceNet 训练时的标准位置）
    std::vector<Point2f> dst_points;
    for (int i = 0; i < 5; i++) {
        dst_points.push_back(Point2f(REFERENCE_FACIAL_POINTS[i][0],
                                     REFERENCE_FACIAL_POINTS[i][1]));
    }

    // 4. 计算仿射变换矩阵（相似变换：旋转 + 缩放 + 平移）
    // 使用 getAffineTransform (更兼容，需要3个点)
    // 使用：左眼、右眼、鼻尖（前3个关键点）
    std::vector<Point2f> src_3pts = {src_points[0], src_points[1], src_points[2]};
    std::vector<Point2f> dst_3pts = {dst_points[0], dst_points[1], dst_points[2]};

    Mat transform_matrix = getAffineTransform(src_3pts, dst_3pts);

    if (transform_matrix.empty()) {
        printf("[face_aligner] Error: Failed to compute affine transform matrix\n");
        return -1;
    }

    // 5. 执行仿射变换
    Mat aligned_face_bgr;
    warpAffine(src_mat, aligned_face_bgr, transform_matrix,
               Size(MOBILEFACENET_INPUT_SIZE, MOBILEFACENET_INPUT_SIZE));

    // 6. BGR → RGB（MobileFaceNet 需要 RGB 输入）
    Mat aligned_face_rgb;
    cvtColor(aligned_face_bgr, aligned_face_rgb, COLOR_BGR2RGB);

    // 7. 分配输出缓冲区
    int output_size = MOBILEFACENET_INPUT_SIZE * MOBILEFACENET_INPUT_SIZE * 3;
    aligned_face->width = MOBILEFACENET_INPUT_SIZE;
    aligned_face->height = MOBILEFACENET_INPUT_SIZE;
    aligned_face->channel = 3;
    aligned_face->format = 0;  // RGB
    aligned_face->size = output_size;

    // 注意：这里分配内存，调用者需要负责释放
    aligned_face->virt_addr = (uint8_t *)malloc(output_size);
    if (!aligned_face->virt_addr) {
        printf("[face_aligner] Error: Failed to allocate memory for aligned face\n");
        return -1;
    }

    // 8. 拷贝对齐后的图像数据
    memcpy(aligned_face->virt_addr, aligned_face_rgb.data, output_size);

    return 0;
}
