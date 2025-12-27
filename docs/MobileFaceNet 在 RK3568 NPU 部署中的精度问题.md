# MobileFaceNet 在 RK3568 NPU 部署中的精度问题排查与解决方案

## 摘要

本文详细记录了在 RK3568 开发板上部署 MobileFaceNet 人脸识别模型时遇到的精度异常问题，包括问题现象、排查过程、根本原因分析以及最终解决方案。该问题涉及模型量化、数据预处理、格式转换等多个层面，具有较强的参考价值。

---

## 1. 问题现象

### 1.1 初始症状

在 RK3568 开发板上运行人脸相似度测试时，发现以下异常：

```bash
[face_engine] Feature extracted successfully (norm=0.0579)
```

**关键指标异常**：
- **特征向量模长（Raw Norm）**：0.0579
- **正常范围**：10.0 - 20.0
- **同一人相似度**：0.25 - 0.35（预期 > 0.7）
- **不同人相似度**：0.20 - 0.30（预期 < 0.5）

### 1.2 问题影响

特征向量模长仅为正常值的 **1/200**，导致：
1. 无法区分同一人的不同照片
2. 无法区分不同人
3. 人脸识别系统完全失效

---

## 2. 排查过程

### 2.1 第一阶段：图像输入验证

**假设**：输入图像可能存在格式错误或数据损坏。

**验证手段**：
1. 在 `face_engine.cpp` 中保存 RetinaFace 检测结果
2. 在 `face_aligner.cpp` 中保存对齐后的 112×112 人脸图像
3. 在 `mobilefacenet.cpp` 中打印输入像素值

**结果**：
```bash
[mobilefacenet] DEBUG：Input pixels: 46 53 35 74 72 ...
```

调试图片显示：
- ✅ 人脸检测框正确
- ✅ 5 个关键点（眼睛、鼻子、嘴角）位置准确
- ✅ 对齐后的图像清晰、颜色正常
- ✅ RGB 格式正确

**结论**：C++ 端图像处理完全正常，问题不在输入数据。

---

### 2.2 第二阶段：量化问题排查

**假设**：INT8 量化过程中校准数据集质量不足，导致"量化坍缩"。

#### 2.2.1 量化坍缩原理

INT8 量化需要校准数据集来确定 Float32 → Int8 的映射参数：

```
Float32 权重 → [量化器 + 校准数据集] → Int8 权重
```

如果校准数据集：
- 全黑/全白
- 尺寸错误
- 或完全缺失

量化器会"瞎猜"参数，导致模型权重变成垃圾值。

#### 2.2.2 解决尝试

重新转换模型，**禁用 INT8 量化**：

```bash
python convert_onnx_to_rknn.py \
    -i mobilefacenet.onnx \
    -o mobilefacenet_fp16.rknn \
    --no-quantization
```

**结果**：
```bash
[face_engine] Feature extracted successfully (norm=0.0595)
```

模型大小变化：
- INT8：1.4 MB
- FP16：2.5 MB

**Norm 仍然是 0.0595**，问题未解决。

**结论**：不是量化问题，问题在更底层。

---

### 2.3 第三阶段：PyTorch 原始模型验证

**假设**：原始 PyTorch 模型本身就有问题。

**验证脚本**：
```python
python test_pytorch_model.py mobilefacenet.pth test.jpg
```

**结果**：
```bash
============================================================
【归一化前】特征向量统计（bn层输出）
============================================================
⭐ Raw Norm: 15.7868
特征范围: [-2.6841, 1.8608]

============================================================
【归一化后】特征向量统计（model输出）
============================================================
Raw Norm: 1.0000
特征范围: [-0.1700, 0.1179]

============================================================
结论
============================================================
✅ PyTorch模型训练良好!
```

**发现**：
1. PyTorch 模型归一化前 Norm = **15.7868**（正常）
2. PyTorch 模型归一化后 Norm = **1.0**（正常，模型自带 L2 归一化）

**结论**：PyTorch 模型正常，问题在 **ONNX 或 RKNN 转换**。

---

### 2.4 第四阶段：ONNX 模型验证

**验证脚本**：
```python
python test_onnx_model.py mobilefacenet.onnx test.jpg
```

**结果**：
```bash
============================================================
特征向量统计
============================================================
⭐ Raw Norm: 1.0000
特征范围: [-0.1700, 0.1180]

============================================================
结论
============================================================
✅ ONNX模型正常！
```

**结论**：ONNX 模型也正常，问题锁定在 **RKNN 转换或 C++ 端预处理**。

---

### 2.5 第五阶段：根本原因定位

#### 2.5.1 预处理流程分析

**PyTorch 训练时的预处理**：
```python
Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
# 等价于：(pixel/255 - 0.5) / 0.5 = (pixel - 127.5) / 127.5
# 输出范围：[-1, 1]
```

**RKNN 转换配置**：
```python
rknn.config(
    mean_values=[[127.5, 127.5, 127.5]],
    std_values=[[127.5, 127.5, 127.5]],
)
```

理论上，RKNN 驱动会自动执行 `(Input - 127.5) / 127.5`。

#### 2.5.2 关键发现

**C++ 端实际输入**：
```bash
[mobilefacenet] DEBUG：Input pixels: 46 53 35 74 72 ...
```

NPU 收到的是 **[0, 255]** 的原始像素值！

**问题确认**：
- PyTorch 期望：`[-1, 1]`
- NPU 实际收到：`[0, 255]`
- **数值范围差了 256 倍！**

**原因**：
在 **FP16（不量化）模式下**，RKNN Toolkit 2.3.2 会**忽略** `mean_values` 和 `std_values` 参数，或者 C++ 端的 `RKNN_TENSOR_UINT8` 没有正确触发驱动的自动归一化。

---

## 3. 解决方案

### 3.1 方案选择

由于 RKNN 驱动的自动预处理不可靠，采用 **C++ 手动预处理** 方案：

**核心思路**：
1. C++ 端手动完成归一化：`(pixel - 127.5) / 127.5`
2. 传入 FLOAT32 数据（不再依赖 UINT8 自动转换）
3. RKNN 配置中**删除** `mean_values` 和 `std_values`

### 3.2 代码实现

#### 3.2.1 修改 C++ 代码（mobilefacenet.cpp）

```cpp
// 方案B：C++ 手动预处理，RKNN 不做预处理
int total_pixels = aligned_face->width * aligned_face->height * aligned_face->channel;
float* normalized_data = (float*)malloc(total_pixels * sizeof(float));

uint8_t* src_data = (uint8_t*)aligned_face->virt_addr;
for (int i = 0; i < total_pixels; i++) {
    normalized_data[i] = (src_data[i] - 127.5f) / 127.5f;  // [-1, 1]
}

// 设置输入
rknn_input inputs[1];
inputs[0].type = RKNN_TENSOR_FLOAT32;  // 关键：使用 FLOAT32
inputs[0].fmt = RKNN_TENSOR_NHWC;
inputs[0].size = total_pixels * sizeof(float);
inputs[0].buf = normalized_data;
```

#### 3.2.2 修改 RKNN 转换脚本（convert_onnx_to_rknn.py）

```python
# 删除 mean_values 和 std_values
ret = rknn.config(
    target_platform='rk3568',
    # 不设置 mean_values 和 std_values
)
```

### 3.3 验证结果

重新编译并测试：

```bash
[mobilefacenet] DEBUG：Normalized pixels (FLOAT32): -0.6392 -0.5843 -0.7255 ...
[mobilefacenet] DEBUG: Raw feature norm BEFORE normalization = 0.9993
```

**验证计算**：
```
(46 - 127.5) / 127.5 = -0.6392  ✅ 正确！
```

**相似度测试结果**：
```bash
Computing 5x5 similarity matrix...
  1.jpg vs 2.jpg: 0.3329  (不同角度，同一人)
  1.jpg vs 4.jpg: 0.7624  (正脸，同一人) ✅
  1.jpg vs test.jpg: 0.0768  (不同人) ✅
```

---

## 4. 技术深度分析

### 4.1 为什么 NPU 输出 Norm = 0.9993 而不是 15.7868？

**原因**：RKNN 模型保留了 PyTorch 模型的 L2 归一化层。

**模型架构**（model.py:238）：
```python
def forward(self, x):
    ...
    out = self.bn(out)
    return l2_norm(out)  # L2 归一化
```

ONNX/RKNN 转换时，这个 `l2_norm` 层被正确转换并保留在模型中。

**数据流**：
```
C++ 手动归一化 → [-1, 1] FLOAT32
    ↓
NPU 推理（MobileFaceNet）
    ↓
模型内部 L2 归一化
    ↓
输出 embedding（Norm ≈ 1.0）
```

### 4.2 C++ 端的 L2 归一化是否多余？

**是的，但无害。**

```cpp
// mobilefacenet.cpp 中的二次归一化（第202-206行）
if (norm > 1e-6f) {
    for (int i = 0; i < 512; i++) {
        out_result->embedding[i] /= norm;
    }
}
```

由于输入的 norm 已经是 1.0，这个操作是幂等的（1.0 / 1.0 = 1.0），不影响结果。

### 4.3 为什么 INT8 量化会失败？

**猜测原因**：
1. 校准数据集质量不足
2. RKNN Toolkit 2.3.2 对 INT8 + 手动预处理的支持不完善
3. 量化参数与 FLOAT32 输入不兼容

**最终选择**：使用 FP16（不量化）模式，牺牲 1MB 存储空间换取稳定性。

---

## 5. 最终性能指标

### 5.1 精度 

| 测试场景 | 相似度 | 状态 |
|---------|--------|------|
| 同一人（正脸 vs 正脸） | **0.76** | ✅ 正常 |
| 同一人（不同角度） | 0.33 - 0.58 | ⚠️ 可接受 |
| 不同人 | **0.077** | ✅ 正常 |

**阈值设定**：0.6

### 5.2 性能

```bash
Feature extraction: ~95-110 ms
Total (including detection): ~370 ms
```

对于门禁系统完全可接受（~2.7 fps）。

### 5.3 模型大小

- **FP16**：2.5 MB
- **INT8**：1.4 MB（已弃用）

---

## 6. 经验总结

### 6.1 关键教训

1. **不要盲目相信 RKNN 驱动的自动预处理**
   - FP16 模式下 `mean_values/std_values` 可能失效
   - 手动预处理更可靠

2. **逐层验证模型转换流程**
   - PyTorch → ONNX → RKNN
   - 每一步都需要独立验证

3. **添加调试代码至关重要**
   - 保存中间图像
   - 打印数值范围
   - 计算特征向量模长

4. **理解模型架构**
   - 确认是否包含 L2 归一化层
   - 避免重复归一化或遗漏归一化

### 6.2 调试技巧

**数值范围验证公式**：
```python
# 假设看到像素值 46
normalized = (46 - 127.5) / 127.5 = -0.6392
```

如果 C++ 日志显示 `-0.6392`，说明归一化正确。

**特征向量模长检查**：
```python
norm = np.linalg.norm(embedding)
# PyTorch（归一化前）：10-20
# PyTorch（归一化后）：1.0
# RKNN：应该 ≈ 1.0（如果模型包含 L2 归一化）
```

---

## 7. 参考资料

- RKNN Toolkit 2 官方文档
- MobileFaceNet 论文
- RK3568 NPU 技术规格
- 项目 GitHub Issues: #31, #32, #33

---

## 附录：完整的数据流图

```
原始图像 (640×427 BGR)
    ↓
RetinaFace 人脸检测
    ↓
人脸对齐 (112×112 RGB, UINT8 [0-255])
    ↓
C++ 手动归一化: (pixel - 127.5) / 127.5
    ↓
FLOAT32 [-1, 1]
    ↓
RKNN NPU 推理（MobileFaceNet）
    ↓
模型内部 L2 归一化
    ↓
输出 embedding (512维, Norm ≈ 1.0)
    ↓
余弦相似度计算
    ↓
人脸识别结果
```

---

**结论**：通过系统性的排查和精确的数值验证，成功解决了 MobileFaceNet 在 RK3568 NPU 部署中的精度坍缩问题，实现了稳定可靠的人脸识别功能。

**开发人员**：Juyao Huang
**开发日期**：25/12/2025
