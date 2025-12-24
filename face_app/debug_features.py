"""
诊断特征向量问题
检查不同人的特征向量是否真的不同
"""

import numpy as np
from test_api import FaceEngine, RETINAFACE_MODEL, MOBILEFACENET_MODEL

def analyze_features():
    print("=" * 70)
    print("特征向量诊断工具")
    print("=" * 70)

    # 创建引擎
    engine = FaceEngine(RETINAFACE_MODEL, MOBILEFACENET_MODEL)

    # 测试图片
    images = [
        "imgs/1.jpg",
        "imgs/test.jpg"
    ]

    features = {}

    for img_path in images:
        print(f"\n处理: {img_path}")
        feature, timing = engine.extract_feature(img_path, save_output=False)

        if feature is not None:
            features[img_path] = feature
            print(f"  ✓ 特征提取成功")
            print(f"  Norm: {np.linalg.norm(feature):.6f}")
            print(f"  前10个值: {feature[:10]}")
            print(f"  统计信息:")
            print(f"    Mean: {feature.mean():.6f}")
            print(f"    Std:  {feature.std():.6f}")
            print(f"    Min:  {feature.min():.6f}")
            print(f"    Max:  {feature.max():.6f}")

            # 检查是否有异常（全0或全相同）
            if np.allclose(feature, 0):
                print(f"  ⚠️  警告: 特征向量全为0!")
            elif np.allclose(feature, feature[0]):
                print(f"  ⚠️  警告: 特征向量所有值都相同!")

    # 比较两个特征
    if len(features) == 2:
        print(f"\n" + "=" * 70)
        print("特征向量对比")
        print("=" * 70)

        feat1 = features["imgs/1.jpg"]
        feat2 = features["imgs/test.jpg"]

        # 手动计算余弦相似度
        dot_product = np.dot(feat1, feat2)
        norm1 = np.linalg.norm(feat1)
        norm2 = np.linalg.norm(feat2)
        cosine_sim = dot_product / (norm1 * norm2)

        print(f"\n手动计算:")
        print(f"  点积 (dot product): {dot_product:.6f}")
        print(f"  Norm1: {norm1:.6f}")
        print(f"  Norm2: {norm2:.6f}")
        print(f"  余弦相似度: {cosine_sim:.6f}")

        # 使用引擎计算
        engine_sim, comp_time = engine.compare_faces(feat1, feat2)
        print(f"\n引擎计算:")
        print(f"  余弦相似度: {engine_sim:.6f}")
        print(f"  计算时间: {comp_time:.4f} ms")

        # 检查是否匹配
        if abs(cosine_sim - engine_sim) > 0.001:
            print(f"\n⚠️  警告: 手动计算和引擎计算结果不一致!")

        # 分析差异
        diff = feat1 - feat2
        print(f"\n特征向量差异分析:")
        print(f"  差异的L2 Norm: {np.linalg.norm(diff):.6f}")
        print(f"  差异的均值: {diff.mean():.6f}")
        print(f"  差异的标准差: {diff.std():.6f}")
        print(f"  差异的最大值: {diff.max():.6f}")
        print(f"  差异的最小值: {diff.min():.6f}")

        # 欧氏距离
        euclidean_dist = np.linalg.norm(diff)
        print(f"\n欧氏距离: {euclidean_dist:.6f}")

        # 结论
        print(f"\n" + "=" * 70)
        print("诊断结论:")
        print("=" * 70)

        if cosine_sim > 0.99:
            print("❌ 异常: 不同人的相似度 > 0.99，特征向量几乎完全相同!")
            print("   可能原因:")
            print("   1. MobileFaceNet 模型输出固定值（模型有问题）")
            print("   2. 特征提取过程有bug")
            print("   3. 图像预处理有问题")
        elif cosine_sim > 0.7:
            print("⚠️  警告: 不同人的相似度过高，可能存在问题")
        else:
            print("✓ 正常: 不同人的相似度在合理范围内")

if __name__ == "__main__":
    analyze_features()
# 执行结果
# =============================================================
# ======================================================================
# 特征向量对比
# ======================================================================

# 手动计算:
#   点积 (dot product): 0.998771
#   Norm1: 1.000000
#   Norm2: 1.000000
#   余弦相似度: 0.998772

# 引擎计算:
#   余弦相似度: 0.998771
#   计算时间: 0.0682 ms

# 特征向量差异分析:
#   差异的L2 Norm: 0.049563
#   差异的均值: -0.000038
#   差异的标准差: 0.002190
#   差异的最大值: 0.006643
#   差异的最小值: -0.006054

# 欧氏距离: 0.049563

# ======================================================================
# 诊断结论:
# ======================================================================
# ❌ 异常: 不同人的相似度 > 0.99，特征向量几乎完全相同!
#    可能原因:
#    1. MobileFaceNet 模型输出固定值（模型有问题）
#    2. 特征提取过程有bug
#    3. 图像预处理有问题