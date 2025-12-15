#ifndef _FACE_UTILS_H_
#define _FACE_UTILS_H_

#include <stdint.h>
#include "rknn_api.h"

#ifdef __cplusplus
extern "C" {
#endif

// ========================================
// 基础数据结构
// ========================================
// 图像缓冲区结构
typedef struct {
    int width;
    int height;
    int channel;
    uint8_t *virt_addr;  // 图像数据指针
    int size;            // 数据大小（字节）
    int format;          // 0: RGB, 1: BGR
} image_buffer_t;

// 点结构（关键点）
typedef struct {
    int x;
    int y;
} point_t;

// 浮点数点结构（用于仿射变换）
typedef struct {
    float x;
    float y;
} pointf_t;

// 人脸框结构
typedef struct {
    int left;
    int top;
    int right;
    int bottom;
} box_rect_t;

// ========================================
// RetinaFace 相关结构
// ========================================

// RetinaFace 检测结果（单个人脸）
typedef struct {
    int cls;              // 类别（通常为0，表示人脸）
    box_rect_t box;       // 人脸框
    float score;          // 置信度分数
    point_t landmarks[5]; // 5个关键点：左眼、右眼、鼻尖、左嘴角、右嘴角
} retinaface_object_t;

// RetinaFace 检测结果集合
typedef struct {
    int count;                          // 检测到的人脸数量
    retinaface_object_t objects[128];   // 最多128个人脸
} retinaface_result_t;

// RKNN 应用上下文
typedef struct {
    rknn_context rknn_ctx;
    rknn_input_output_num io_num;
    rknn_tensor_attr *input_attrs;
    rknn_tensor_attr *output_attrs;
    int model_channel;
    int model_width;
    int model_height;
} rknn_app_context_t;

// ========================================
// MobileFaceNet 相关结构
// ========================================

// MobileFaceNet 特征向量结果
typedef struct {
    float embedding[512];  // 512维特征向量
    int is_valid;          // 是否有效
} mobilefacenet_result_t;

// ========================================
// FaceEngine 完整流程结构
// ========================================

// 人脸识别引擎上下文
typedef struct {
    rknn_app_context_t retinaface_ctx;   // RetinaFace 上下文
    rknn_app_context_t mobilefacenet_ctx; // MobileFaceNet 上下文
    int is_initialized;                   // 是否已初始化
} face_engine_t;

// ========================================
// 常量定义
// ========================================

// RetinaFace 阈值
#define CONF_THRESHOLD 0.5f     // 置信度阈值
#define NMS_THRESHOLD 0.4f      // NMS IoU 阈值
#define VIS_THRESHOLD 0.4f      // 可视化阈值

// 模型尺寸
#define RETINAFACE_INPUT_SIZE 640
#define MOBILEFACENET_INPUT_SIZE 112

// MobileFaceNet 标准参考关键点（112x112图像）
static const float REFERENCE_FACIAL_POINTS[5][2] = {
    {38.2946f, 51.6963f},  // 左眼
    {73.5318f, 51.5014f},  // 右眼
    {56.0252f, 71.7366f},  // 鼻尖
    {41.5493f, 92.3655f},  // 左嘴角
    {70.7299f, 92.2041f}   // 右嘴角
};

// ========================================
// RetinaFace 函数声明
// ========================================

/**
 * @brief 初始化 RetinaFace 模型
 * @param model_path 模型文件路径
 * @param app_ctx RKNN 应用上下文
 * @return 0: 成功, -1: 失败
 */
int init_retinaface_model(const char *model_path, rknn_app_context_t *app_ctx);

/**
 * @brief 释放 RetinaFace 模型
 * @param app_ctx RKNN 应用上下文
 * @return 0: 成功, -1: 失败
 */
int release_retinaface_model(rknn_app_context_t *app_ctx);

/**
 * @brief RetinaFace 推理
 * @param app_ctx RKNN 应用上下文
 * @param img 输入图像
 * @param out_result 输出检测结果
 * @return 0: 成功, -1: 失败
 */
int inference_retinaface_model(rknn_app_context_t *app_ctx, image_buffer_t *img, retinaface_result_t *out_result);

// ========================================
// MobileFaceNet 函数声明
// ========================================

/**
 * @brief 初始化 MobileFaceNet 模型
 * @param model_path 模型文件路径
 * @param app_ctx RKNN 应用上下文
 * @return 0: 成功, -1: 失败
 */
int init_mobilefacenet_model(const char *model_path, rknn_app_context_t *app_ctx);

/**
 * @brief 释放 MobileFaceNet 模型
 * @param app_ctx RKNN 应用上下文
 * @return 0: 成功, -1: 失败
 */
int release_mobilefacenet_model(rknn_app_context_t *app_ctx);

/**
 * @brief MobileFaceNet 推理
 * @param app_ctx RKNN 应用上下文
 * @param aligned_face 对齐后的人脸图像 (112x112, RGB)
 * @param out_result 输出特征向量
 * @return 0: 成功, -1: 失败
 */
int inference_mobilefacenet_model(rknn_app_context_t *app_ctx, image_buffer_t *aligned_face, mobilefacenet_result_t *out_result);

// ========================================
// 人脸对齐函数声明
// ========================================

/**
 * @brief 人脸对齐（仿射变换）
 * @param src_img 原始图像
 * @param landmarks 5个关键点
 * @param aligned_face 输出对齐后的人脸图像 (112x112, RGB)
 * @return 0: 成功, -1: 失败
 */
int align_face(image_buffer_t *src_img, point_t landmarks[5], image_buffer_t *aligned_face);

// ========================================
// FaceEngine 函数声明
// ========================================

/**
 * @brief 初始化人脸识别引擎
 * @param engine 引擎上下文
 * @param retinaface_model_path RetinaFace 模型路径
 * @param mobilefacenet_model_path MobileFaceNet 模型路径
 * @return 0: 成功, -1: 失败
 */
int face_engine_init(face_engine_t *engine, const char *retinaface_model_path, const char *mobilefacenet_model_path);

/**
 * @brief 释放人脸识别引擎
 * @param engine 引擎上下文
 * @return 0: 成功, -1: 失败
 */
int face_engine_release(face_engine_t *engine);

/**
 * @brief 提取人脸特征向量
 * @param engine 引擎上下文
 * @param jpeg_data JPEG 图像数据
 * @param data_len 数据长度
 * @param feature_512 输出 512 维特征向量
 * @return 0: 成功, -1: 失败（没有检测到人脸）, -2: 其他错误
 */
int face_engine_extract_feature(face_engine_t *engine, unsigned char *jpeg_data, int data_len, float *feature_512);

// ========================================
// 工具函数声明
// ========================================

/**
 * @brief 从文件读取数据
 * @param filename 文件名
 * @param data 输出数据指针
 * @return 数据长度（字节），-1 表示失败
 */
int read_data_from_file(const char *filename, char **data);

/**
 * @brief 计算余弦相似度
 * @param embedding1 特征向量1
 * @param embedding2 特征向量2
 * @param dim 向量维度
 * @return 相似度 [0, 1]
 */
float cosine_similarity(const float *embedding1, const float *embedding2, int dim);

#ifdef __cplusplus
}
#endif

#endif // _FACE_UTILS_H_
