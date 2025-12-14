"""
将训练好的MobileFaceNet模型转换为ONNX格式
用于后续在RK3568开发板上部署（RKNN）
"""

import torch
import torch.onnx
from model import MobileFaceNet
from pathlib import Path
import argparse


def convert_to_onnx(checkpoint_path, output_path, input_shape=(1, 3, 112, 112)):
    """
    将PyTorch模型转换为ONNX格式

    Args:
        checkpoint_path: PyTorch模型权重路径 (.pth)
        output_path: 输出ONNX模型路径 (.onnx)
        input_shape: 输入张量形状 (batch, channels, height, width)
    """
    print("=" * 60)
    print("MobileFaceNet PyTorch → ONNX 转换工具")
    print("=" * 60)

    # 设置设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n使用设备: {device}")

    # 加载模型
    print(f"\n加载PyTorch模型: {checkpoint_path}")
    model = MobileFaceNet(embedding_size=512)

    # 加载权重
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint)
    model.eval()
    model.to(device)

    print(f"✓ 模型加载成功")
    print(f"  - 输入尺寸: {input_shape}")
    print(f"  - 输出维度: 512")

    # 创建示例输入
    dummy_input = torch.randn(input_shape).to(device)

    # 测试前向传播
    print("\n测试前向传播...")
    with torch.no_grad():
        output = model(dummy_input)
    print(f"✓ 前向传播成功")
    print(f"  - 输出形状: {output.shape}")
    print(f"  - 输出范围: [{output.min().item():.4f}, {output.max().item():.4f}]")

    # 转换为ONNX
    print(f"\n开始转换为ONNX...")
    print(f"输出路径: {output_path}")

    torch.onnx.export(
        model,                          # 模型
        dummy_input,                    # 示例输入
        output_path,                    # 输出路径
        export_params=True,             # 导出参数
        opset_version=11,               # ONNX opset版本（RK3568建议使用11或12）
        do_constant_folding=True,       # 常量折叠优化
        input_names=['input'],          # 输入名称
        output_names=['output'],        # 输出名称
        dynamic_axes={                  # 动态轴（batch维度）
            'input': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )

    print(f"✓ ONNX模型转换成功!")

    # 验证ONNX模型
    print("\n验证ONNX模型...")
    try:
        import onnx
        import onnxruntime as ort

        # 加载ONNX模型
        onnx_model = onnx.load(output_path)
        onnx.checker.check_model(onnx_model)
        print("✓ ONNX模型格式验证通过")

        # 使用ONNX Runtime测试
        ort_session = ort.InferenceSession(output_path)

        # 准备输入
        ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.cpu().numpy()}

        # 推理
        ort_outputs = ort_session.run(None, ort_inputs)

        # 比较PyTorch和ONNX输出
        pytorch_output = output.cpu().numpy()
        onnx_output = ort_outputs[0]

        max_diff = abs(pytorch_output - onnx_output).max()
        print(f"✓ ONNX Runtime推理成功")
        print(f"  - PyTorch vs ONNX最大差异: {max_diff:.6f}")

        if max_diff < 1e-5:
            print(f"  - 精度验证: ✓ 优秀 (差异 < 1e-5)")
        elif max_diff < 1e-3:
            print(f"  - 精度验证: ✓ 良好 (差异 < 1e-3)")
        else:
            print(f"  - 精度验证: ⚠ 注意 (差异较大)")

    except ImportError:
        print("⚠ 未安装onnx/onnxruntime，跳过验证")
        print("  安装命令: pip install onnx onnxruntime")
    except Exception as e:
        print(f"⚠ 验证过程出错: {e}")

    # 输出模型信息
    output_file = Path(output_path)
    file_size_mb = output_file.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("转换完成!")
    print("=" * 60)
    print(f"ONNX模型路径: {output_path}")
    print(f"模型大小: {file_size_mb:.2f} MB")
    print(f"\n下一步: 使用RKNN Toolkit转换为.rknn模型")
    print(f"参考命令:")
    print(f"  rknn-toolkit2: ")
    print(f"    from rknn.api import RKNN")
    print(f"    rknn = RKNN()")
    print(f"    rknn.config(target_platform='rk3568')")
    print(f"    rknn.load_onnx('{output_path}')")
    print(f"    rknn.build(do_quantization=True)")
    print(f"    rknn.export_rknn('mobilefacenet.rknn')")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='将MobileFaceNet转换为ONNX格式')
    parser.add_argument('-i', '--input', type=str, required=True,
                        help='输入PyTorch模型路径 (.pth)')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='输出ONNX模型路径 (.onnx)，默认与输入同名')
    parser.add_argument('--batch-size', type=int, default=1,
                        help='batch size (默认: 1)')

    args = parser.parse_args()

    # 生成输出路径
    if args.output is None:
        input_path = Path(args.input)
        output_path = str(input_path.with_suffix('.onnx'))
    else:
        output_path = args.output

    # 输入形状
    input_shape = (args.batch_size, 3, 112, 112)

    # 转换
    convert_to_onnx(args.input, output_path, input_shape)


if __name__ == '__main__':
    # 示例用法
    # python convert_to_onnx.py -i work_space/models/mobilefacenet_epoch15_step12571_final.pth -o mobilefacenet.onnx
    main()
