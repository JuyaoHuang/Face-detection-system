"""
打印MobileFaceNet网络结构
"""

import torch
from model import MobileFaceNet, Arcface
from torchsummary import torchsummary

def print_network_structure():
    print("=" * 80)
    print("MobileFaceNet 网络结构")
    print("=" * 80)

    # 创建模型
    model = MobileFaceNet(embedding_size=512)

    # 打印模型结构
    print("\n详细网络结构：\n")
    print(model)

    # 统计参数数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print("\n" + "=" * 80)
    print(f"总参数数量: {total_params:,}")
    print(f"可训练参数数量: {trainable_params:,}")
    print(f"参数大小: {total_params * 4 / 1024 / 1024:.2f} MB (假设float32)")
    print("=" * 80)

    # 测试前向传播
    print("\n测试前向传播...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)

    # 创建测试输入 (batch_size=2, channels=3, height=112, width=112)
    test_input = torch.randn(2, 3, 112, 112).to(device)

    with torch.no_grad():
        output = model(test_input)

    print(f"输入形状: {test_input.shape}")
    print(f"输出形状 (embedding): {output.shape}")
    print(f"输出范围: [{output.min().item():.4f}, {output.max().item():.4f}]")
    print(f"输出L2范数: {torch.norm(output, dim=1)}")  # 应该接近1（因为L2归一化）

    print("\n" + "=" * 80)
    print("Arcface Head 网络结构")
    print("=" * 80)

    # 创建Arcface head（假设100个类别）
    num_classes = 100
    head = Arcface(embedding_size=512, classnum=num_classes)
    print(f"\nArcface参数:")
    print(f"  - 嵌入维度: 512")
    print(f"  - 类别数: {num_classes}")
    print(f"  - Margin (m): {head.m}")
    print(f"  - Scale (s): {head.s}")
    print(f"  - Kernel形状: {head.kernel.shape}")

    head_params = sum(p.numel() for p in head.parameters())
    print(f"  - 参数数量: {head_params:,}")

    # 测试Arcface
    print("\n测试Arcface前向传播...")
    head = head.to(device)
    test_labels = torch.randint(0, num_classes, (2,)).to(device)

    with torch.no_grad():
        logits = head(output, test_labels)

    print(f"标签: {test_labels}")
    print(f"Logits形状: {logits.shape}")
    print(f"Logits范围: [{logits.min().item():.4f}, {logits.max().item():.4f}]")

    print("\n" + "=" * 80)
    print("网络层详细信息")
    print("=" * 80)

    print("\nMobileFaceNet各层详情:")
    for name, module in model.named_children():
        print(f"\n{name}:")
        print(f"  {module}")
        params = sum(p.numel() for p in module.parameters())
        print(f"  参数数量: {params:,}")


if __name__ == '__main__':
    print_network_structure()
