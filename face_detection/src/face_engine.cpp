#include "face_utils.h"
#include <opencv2/opencv.hpp>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

using namespace cv;

/**
 * @brief 初始化人脸识别引擎
 */
int face_engine_init(face_engine_t *engine, const char *retinaface_model_path, const char *mobilefacenet_model_path) {
    if (!engine || !retinaface_model_path || !mobilefacenet_model_path) {
        printf("[face_engine] Error: NULL pointer input\n");
        return -1;
    }

    memset(engine, 0, sizeof(face_engine_t));

    // 初始化 RetinaFace 模型
    printf("[face_engine] Initializing RetinaFace model from %s\n", retinaface_model_path);
    if (init_retinaface_model(retinaface_model_path, &engine->retinaface_ctx) != 0) {
        printf("[face_engine] Error: Failed to initialize RetinaFace model\n");
        return -1;
    }

    // 初始化 MobileFaceNet 模型
    printf("[face_engine] Initializing MobileFaceNet model from %s\n", mobilefacenet_model_path);
    if (init_mobilefacenet_model(mobilefacenet_model_path, &engine->mobilefacenet_ctx) != 0) {
        printf("[face_engine] Error: Failed to initialize MobileFaceNet model\n");
        release_retinaface_model(&engine->retinaface_ctx);
        return -1;
    }

    engine->is_initialized = 1;
    printf("[face_engine] Face engine initialized successfully\n");
    return 0;
}

/**
 * @brief 释放人脸识别引擎
 */
int face_engine_release(face_engine_t *engine) {
    if (!engine) {
        return -1;
    }

    if (engine->is_initialized) {
        release_retinaface_model(&engine->retinaface_ctx);
        release_mobilefacenet_model(&engine->mobilefacenet_ctx);
        engine->is_initialized = 0;
        printf("[face_engine] Face engine released\n");
    }

    return 0;
}

/**
 * @brief 提取人脸特征向量（完整流程）
 *
 * 流程：JPEG解码 → RetinaFace检测 → 人脸对齐 → MobileFaceNet特征提取
 *
 * @param engine 引擎上下文
 * @param jpeg_data JPEG 图像数据
 * @param data_len 数据长度
 * @param feature_512 输出 512 维特征向量
 * @return 0: 成功, -1: 失败（没有检测到人脸）, -2: 其他错误
 */
int face_engine_extract_feature(face_engine_t *engine, unsigned char *jpeg_data, int data_len, float *feature_512) {
    if (!engine || !jpeg_data || data_len <= 0 || !feature_512) {
        printf("[face_engine] Error: Invalid input parameters\n");
        return -2;
    }

    if (!engine->is_initialized) {
        printf("[face_engine] Error: Engine not initialized\n");
        return -2;
    }

    // ========================================
    // 1. 解码 JPEG 图像
    // ========================================
    std::vector<uchar> jpeg_buffer(jpeg_data, jpeg_data + data_len);
    Mat img_bgr = imdecode(jpeg_buffer, IMREAD_COLOR);
    if (img_bgr.empty()) {
        printf("[face_engine] Error: Failed to decode JPEG image\n");
        return -2;
    }

    printf("[face_engine] Decoded image: %dx%d\n", img_bgr.cols, img_bgr.rows);

    // 转换为 image_buffer_t 结构
    image_buffer_t src_img;
    src_img.width = img_bgr.cols;
    src_img.height = img_bgr.rows;
    src_img.channel = 3;
    src_img.format = 1;  // BGR
    src_img.size = img_bgr.total() * img_bgr.elemSize();
    src_img.virt_addr = img_bgr.data;

    // ========================================
    // 2. RetinaFace 人脸检测
    // ========================================
    retinaface_result_t detect_result;
    memset(&detect_result, 0, sizeof(detect_result));

    int ret = inference_retinaface_model(&engine->retinaface_ctx, &src_img, &detect_result);
    if (ret != 0) {
        printf("[face_engine] Error: RetinaFace inference failed\n");
        return -2;
    }

    if (detect_result.count == 0) {
        printf("[face_engine] Warning: No face detected\n");
        return -1;
    }

    printf("[face_engine] Detected %d face(s), using the first one (score=%.3f)\n",
           detect_result.count, detect_result.objects[0].score);

    // 使用第一个检测到的人脸
    retinaface_object_t *face_obj = &detect_result.objects[0];

    // 【调试代码】保存RetinaFace检测结果（带人脸框和关键点）
    Mat debug_img = img_bgr.clone();
    // 画人脸框
    rectangle(debug_img,
              Point(face_obj->box.left, face_obj->box.top),
              Point(face_obj->box.right, face_obj->box.bottom),
              Scalar(0, 255, 0), 2);
    // 画5个关键点
    for (int i = 0; i < 5; i++) {
        circle(debug_img,
               Point(face_obj->landmarks[i].x, face_obj->landmarks[i].y),
               3, Scalar(0, 0, 255), -1);
    }
    imwrite("debug_retinaface_detection.jpg", debug_img);
    printf("[face_engine] DEBUG: RetinaFace detection saved to debug_retinaface_detection.jpg\n");
    printf("[face_engine] DEBUG: Face box: (%d,%d) -> (%d,%d)\n",
           face_obj->box.left, face_obj->box.top,
           face_obj->box.right, face_obj->box.bottom);
    printf("[face_engine] DEBUG: Landmarks: ");
    for (int i = 0; i < 5; i++) {
        printf("(%d,%d) ", face_obj->landmarks[i].x, face_obj->landmarks[i].y);
    }
    printf("\n");
    
    // ========================================
    // 3. 人脸对齐
    // ========================================
    image_buffer_t aligned_face;
    memset(&aligned_face, 0, sizeof(aligned_face));

    ret = align_face(&src_img, face_obj->landmarks, &aligned_face);
    if (ret != 0) {
        printf("[face_engine] Error: Face alignment failed\n");
        return -2;
    }

    printf("[face_engine] Face aligned to %dx%d\n", aligned_face.width, aligned_face.height);

    // ========================================
    // 4. MobileFaceNet 特征提取
    // ========================================
    // 【终极调试】把准备送给 NPU 的数据，反向保存成图片
    // 注意：因为我们认为它是 RGB，但 OpenCV 保存图片需要 BGR，所以我们这里转一下以便人类观看
    // cv::Mat debug_final(112, 112, CV_8UC3, aligned_face.virt_addr);
    // cv::Mat debug_show;
    // cv::cvtColor(debug_final, debug_show, cv::COLOR_RGB2BGR); // 转回 BGR 以便保存查看
    // cv::imwrite("debug_final_input_to_npu.jpg", debug_show);
    
    // printf("[DEBUG] Saved NPU input to debug_final_input_to_npu.jpg\n");

    // ========================================
    // 【强制RGB格式】确保送入MobileFaceNet的绝对是RGB
    // ========================================
    printf("[face_engine] DEBUG: Checking aligned_face format before NPU inference\n");
    printf("[face_engine] DEBUG: aligned_face.format = %d (0=RGB, 1=BGR)\n", aligned_face.format);

    image_buffer_t rgb_input;
    memset(&rgb_input, 0, sizeof(rgb_input));
    rgb_input.width = aligned_face.width;
    rgb_input.height = aligned_face.height;
    rgb_input.channel = aligned_face.channel;
    rgb_input.size = aligned_face.size;
    rgb_input.format = 0;  // RGB

    // 分配新内存
    rgb_input.virt_addr = (uint8_t*)malloc(aligned_face.size);
    if (!rgb_input.virt_addr) {
        printf("[face_engine] Error: Failed to allocate memory for RGB conversion\n");
        free(aligned_face.virt_addr);
        return -2;
    }

    // 根据format决定是否需要转换
    if (aligned_face.format == 1) {
        // BGR -> RGB
        printf("[face_engine] INFO: Converting BGR to RGB\n");
        Mat bgr_mat(aligned_face.height, aligned_face.width, CV_8UC3, aligned_face.virt_addr);
        Mat rgb_mat;
        cvtColor(bgr_mat, rgb_mat, COLOR_BGR2RGB);
        memcpy(rgb_input.virt_addr, rgb_mat.data, aligned_face.size);
    } else {
        // 已经是RGB，直接拷贝
        printf("[face_engine] INFO: Format is already RGB, copying data\n");
        memcpy(rgb_input.virt_addr, aligned_face.virt_addr, aligned_face.size);
    }

    printf("[face_engine] DEBUG: RGB input pixels (first 10): ");
    for (int i = 0; i < 10; i++) {
        printf("%d ", rgb_input.virt_addr[i]);
    }
    printf("\n");

    mobilefacenet_result_t feature_result;
    memset(&feature_result, 0, sizeof(feature_result));

    ret = inference_mobilefacenet_model(&engine->mobilefacenet_ctx, &rgb_input, &feature_result);

    // 释放RGB输入缓冲区
    if (rgb_input.virt_addr) {
        free(rgb_input.virt_addr);
    }

    // 释放对齐后的图像内存
    if (aligned_face.virt_addr) {
        free(aligned_face.virt_addr);
    }

    if (ret != 0) {
        printf("[face_engine] Error: MobileFaceNet inference failed\n");
        return -2;
    }

    if (!feature_result.is_valid) {
        printf("[face_engine] Error: Feature extraction result invalid\n");
        return -2;
    }

    // ========================================
    // 5. 拷贝特征向量
    // ========================================
    memcpy(feature_512, feature_result.embedding, 512 * sizeof(float));

    printf("[face_engine] Feature extracted successfully (norm=%.4f)\n",
           sqrtf(feature_512[0] * feature_512[0] + feature_512[1] * feature_512[1])); // 简单验证

    return 0;
}

// ========================================
// C 接口导出（供 Python ctypes 调用）
// ========================================

extern "C" {

/**
 * @brief 创建 FaceEngine 实例
 */
void* FaceEngine_Create() {
    face_engine_t *engine = (face_engine_t *)malloc(sizeof(face_engine_t));
    if (engine) {
        memset(engine, 0, sizeof(face_engine_t));
    }
    return engine;
}

/**
 * @brief 初始化 FaceEngine
 */
int FaceEngine_Init(void *engine_ptr, const char *retinaface_model, const char *mobilefacenet_model) {
    if (!engine_ptr) {
        return -1;
    }
    return face_engine_init((face_engine_t *)engine_ptr, retinaface_model, mobilefacenet_model);
}

/**
 * @brief 提取特征向量
 */
int FaceEngine_ExtractFeature(void *engine_ptr, unsigned char *jpeg_data, int data_len, float *feature_512) {
    if (!engine_ptr) {
        return -2;
    }
    return face_engine_extract_feature((face_engine_t *)engine_ptr, jpeg_data, data_len, feature_512);
}

/**
 * @brief 销毁 FaceEngine 实例
 */
void FaceEngine_Destroy(void *engine_ptr) {
    if (engine_ptr) {
        face_engine_release((face_engine_t *)engine_ptr);
        free(engine_ptr);
    }
}

/**
 * @brief 计算余弦相似度（导出给 Python）
 */
float FaceEngine_CosineSimilarity(const float *emb1, const float *emb2) {
    return cosine_similarity(emb1, emb2, 512);
}

} // extern "C"
