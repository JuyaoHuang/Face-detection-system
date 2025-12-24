#include "face_utils.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/**
 * @brief 初始化 MobileFaceNet 模型
 */
int init_mobilefacenet_model(const char *model_path, rknn_app_context_t *app_ctx) {
    if (!model_path || !app_ctx) {
        printf("[mobilefacenet] Error: NULL pointer input\n");
        return -1;
    }

    int ret;
    char *model_data = NULL;
    int model_len = read_data_from_file(model_path, &model_data);
    if (model_data == NULL || model_len <= 0) {
        printf("[mobilefacenet] Error: Failed to load model from %s\n", model_path);
        return -1;
    }

    // 初始化 RKNN 上下文
    ret = rknn_init(&app_ctx->rknn_ctx, model_data, model_len, 0, NULL);
    free(model_data);
    if (ret < 0) {
        printf("[mobilefacenet] Error: rknn_init failed! ret=%d\n", ret);
        return -1;
    }

    // 查询输入输出数量
    ret = rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_IN_OUT_NUM, &app_ctx->io_num, sizeof(app_ctx->io_num));
    if (ret != RKNN_SUCC) {
        printf("[mobilefacenet] Error: rknn_query io_num failed! ret=%d\n", ret);
        return -1;
    }

    printf("[mobilefacenet] Model input num: %d, output num: %d\n",
           app_ctx->io_num.n_input, app_ctx->io_num.n_output);

    // 查询输入属性
    app_ctx->input_attrs = (rknn_tensor_attr *)malloc(app_ctx->io_num.n_input * sizeof(rknn_tensor_attr));
    memset(app_ctx->input_attrs, 0, app_ctx->io_num.n_input * sizeof(rknn_tensor_attr));
    for (int i = 0; i < app_ctx->io_num.n_input; i++) {
        app_ctx->input_attrs[i].index = i;
        ret = rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_INPUT_ATTR, &app_ctx->input_attrs[i], sizeof(rknn_tensor_attr));
        if (ret != RKNN_SUCC) {
            printf("[mobilefacenet] Error: rknn_query input_attr failed! ret=%d\n", ret);
            return -1;
        }
    }

    // 查询输出属性
    app_ctx->output_attrs = (rknn_tensor_attr *)malloc(app_ctx->io_num.n_output * sizeof(rknn_tensor_attr));
    memset(app_ctx->output_attrs, 0, app_ctx->io_num.n_output * sizeof(rknn_tensor_attr));
    for (int i = 0; i < app_ctx->io_num.n_output; i++) {
        app_ctx->output_attrs[i].index = i;
        ret = rknn_query(app_ctx->rknn_ctx, RKNN_QUERY_OUTPUT_ATTR, &app_ctx->output_attrs[i], sizeof(rknn_tensor_attr));
        if (ret != RKNN_SUCC) {
            printf("[mobilefacenet] Error: rknn_query output_attr failed! ret=%d\n", ret);
            return -1;
        }
    }

    // 设置模型尺寸
    app_ctx->model_width = MOBILEFACENET_INPUT_SIZE;
    app_ctx->model_height = MOBILEFACENET_INPUT_SIZE;
    app_ctx->model_channel = 3;

    printf("[mobilefacenet] Model initialized successfully\n");
    return 0;
}

/**
 * @brief 释放 MobileFaceNet 模型
 */
int release_mobilefacenet_model(rknn_app_context_t *app_ctx) {
    if (!app_ctx) {
        return -1;
    }

    if (app_ctx->input_attrs) {
        free(app_ctx->input_attrs);
        app_ctx->input_attrs = NULL;
    }

    if (app_ctx->output_attrs) {
        free(app_ctx->output_attrs);
        app_ctx->output_attrs = NULL;
    }

    if (app_ctx->rknn_ctx) {
        rknn_destroy(app_ctx->rknn_ctx);
        app_ctx->rknn_ctx = 0;
    }

    printf("[mobilefacenet] Model released\n");
    return 0;
}

/**
 * @brief MobileFaceNet 推理
 */
int inference_mobilefacenet_model(rknn_app_context_t *app_ctx, image_buffer_t *aligned_face, mobilefacenet_result_t *out_result) {
    if (!app_ctx || !aligned_face || !out_result) {
        printf("[mobilefacenet] Error: NULL pointer input\n");
        return -1;
    }

    if (aligned_face->width != MOBILEFACENET_INPUT_SIZE ||
        aligned_face->height != MOBILEFACENET_INPUT_SIZE ||
        aligned_face->channel != 3) {
        printf("[mobilefacenet] Error: Invalid input size (%dx%dx%d), expected (%dx%dx3)\n",
               aligned_face->width, aligned_face->height, aligned_face->channel,
               MOBILEFACENET_INPUT_SIZE, MOBILEFACENET_INPUT_SIZE);
        return -1;
    }

    int ret;

    // 【调试代码】
    uint8_t* pixel_data = (uint8_t*)aligned_face->virt_addr;
    printf("[mobilefacenet] DEBUG：Input pixels (UINT8): %d %d %d %d %d ...\n",
    pixel_data[0], pixel_data[1], pixel_data[2], pixel_data[100], pixel_data[101]);

    // 1. 预处理：将UINT8 [0-255] 转换为 FLOAT32 [-1, 1]
    // 公式：output = (input - 127.5) / 127.5
    int total_pixels = aligned_face->width * aligned_face->height * aligned_face->channel;
    float* normalized_data = (float*)malloc(total_pixels * sizeof(float));
    if (!normalized_data) {
        printf("[mobilefacenet] Error: Failed to allocate memory for normalized data\n");
        return -1;
    }

    uint8_t* src_data = (uint8_t*)aligned_face->virt_addr;
    for (int i = 0; i < total_pixels; i++) {
        normalized_data[i] = (src_data[i] - 127.5f) / 127.5f;
    }

    printf("[mobilefacenet] DEBUG：Normalized pixels (FLOAT32): %.4f %.4f %.4f %.4f %.4f ...\n",
           normalized_data[0], normalized_data[1], normalized_data[2],
           normalized_data[100], normalized_data[101]);

    // 2. 设置输入
    rknn_input inputs[1];
    memset(inputs, 0, sizeof(inputs));
    inputs[0].index = 0;
    inputs[0].type = RKNN_TENSOR_FLOAT32;
    inputs[0].fmt = RKNN_TENSOR_NHWC;  // RKNN 会自动转换为模型需要的 NCHW
    inputs[0].size = total_pixels * sizeof(float);
    inputs[0].buf = normalized_data;

    ret = rknn_inputs_set(app_ctx->rknn_ctx, app_ctx->io_num.n_input, inputs);
    if (ret < 0) {
        printf("[mobilefacenet] Error: rknn_inputs_set failed! ret=%d\n", ret);
        free(normalized_data);  // 释放内存
        return -1;
    }

    // 3. 运行推理
    ret = rknn_run(app_ctx->rknn_ctx, NULL);
    if (ret < 0) {
        printf("[mobilefacenet] Error: rknn_run failed! ret=%d\n", ret);
        free(normalized_data);  // 释放内存
        return -1;
    }

    // 4. 获取输出
    rknn_output outputs[1];
    memset(outputs, 0, sizeof(outputs));
    outputs[0].index = 0;
    outputs[0].want_float = 1;  // 请求浮点输出

    ret = rknn_outputs_get(app_ctx->rknn_ctx, app_ctx->io_num.n_output, outputs, NULL);
    if (ret < 0) {
        printf("[mobilefacenet] Error: rknn_outputs_get failed! ret=%d\n", ret);
        free(normalized_data);  // 释放内存
        return -1;
    }

    // 5. 拷贝特征向量（512维）
    float *output_data = (float *)outputs[0].buf;
    memcpy(out_result->embedding, output_data, 512 * sizeof(float));
    out_result->is_valid = 1;

    // 6. L2 归一化（注意：由于PyTorch模型已经做了归一化，这里计算的norm应该约为1.0）
    float norm = 0.0f;
    for (int i = 0; i < 512; i++) {
        norm += out_result->embedding[i] * out_result->embedding[i];
    }
    norm = sqrtf(norm);
    printf("[mobilefacenet] DEBUG: Raw feature norm BEFORE normalization = %.4f\n", norm);

    // 打印前20个特征值（归一化前）
    printf("[mobilefacenet] DEBUG: First 20 features (before norm): ");
    for (int i = 0; i < 20; i++) {
        printf("%.4f ", out_result->embedding[i]);
    }
    printf("\n");

    if (norm > 1e-6f) {
        for (int i = 0; i < 512; i++) {
            out_result->embedding[i] /= norm;
        }
    }

    // 打印前20个特征值（归一化后）
    printf("[mobilefacenet] DEBUG: First 20 features (after norm): ");
    for (int i = 0; i < 20; i++) {
        printf("%.4f ", out_result->embedding[i]);
    }
    printf("\n");

    // 7. 释放输出
    rknn_outputs_release(app_ctx->rknn_ctx, app_ctx->io_num.n_output, outputs);

    // 8. 释放归一化数据内存
    free(normalized_data);

    return 0;
}
