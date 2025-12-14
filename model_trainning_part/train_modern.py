"""
现代化的MobileFaceNet训练脚本（无PIL依赖版本）
完全使用PyTorch和cv2，避免PIL依赖问题
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.utils.tensorboard import SummaryWriter
from pathlib import Path
from tqdm import tqdm
import argparse
import cv2
import numpy as np

# 从原项目导入模型定义
from model import MobileFaceNet, Arcface, l2_norm


class FaceDataset(Dataset):
    """
    自定义人脸数据集加载器
    使用cv2读取图像，避免PIL依赖
    """
    def __init__(self, root_dir, transform=None):
        """
        Args:
            root_dir: 数据集根目录，包含按类别组织的子文件夹
            transform: 可选的数据增强函数
        """
        self.root_dir = Path(root_dir)
        self.transform = transform

        # 扫描所有图片和标签
        self.samples = []
        self.class_to_idx = {}

        print(f"扫描数据集: {self.root_dir}")

        # 获取所有类别文件夹
        class_dirs = sorted([d for d in self.root_dir.iterdir() if d.is_dir()])

        for idx, class_dir in enumerate(class_dirs):
            self.class_to_idx[class_dir.name] = idx

            # 获取该类别下的所有图片
            for img_path in class_dir.glob('*.jpg'):
                self.samples.append((str(img_path), idx))

        self.num_classes = len(self.class_to_idx)
        print(f"找到 {len(self.samples)} 张图片，{self.num_classes} 个类别")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]

        # 使用cv2读取图像（BGR格式）
        image = cv2.imread(img_path)

        if image is None:
            raise ValueError(f"无法读取图像: {img_path}")

        # BGR转RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 应用变换
        if self.transform:
            image = self.transform(image)

        return image, label


class Compose:
    """组合多个变换"""
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, image):
        for t in self.transforms:
            image = t(image)
        return image


class RandomHorizontalFlip:
    """随机水平翻转"""
    def __init__(self, p=0.5):
        self.p = p

    def __call__(self, image):
        if np.random.random() < self.p:
            image = cv2.flip(image, 1)  # 1表示水平翻转
        return image


class ToTensor:
    """转换为Tensor并归一化到[0,1]"""
    def __call__(self, image):
        # HWC to CHW
        image = image.transpose((2, 0, 1))
        # numpy to tensor
        image = torch.from_numpy(image).float()
        # [0, 255] to [0, 1]
        image = image / 255.0
        return image


class Normalize:
    """标准化"""
    def __init__(self, mean, std):
        self.mean = torch.tensor(mean).view(3, 1, 1)
        self.std = torch.tensor(std).view(3, 1, 1)

    def __call__(self, tensor):
        return (tensor - self.mean) / self.std


class ModernTrainer:
    def __init__(self, args):
        self.args = args

        # 设置设备（使用GPU）
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f'使用设备: {self.device}')

        if torch.cuda.is_available():
            print(f'GPU型号: {torch.cuda.get_device_name(0)}')
            print(f'GPU数量: {torch.cuda.device_count()}')
            print(f'CUDA版本: {torch.version.cuda}')
            print(f'当前GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB')
        else:
            print('警告: 未检测到CUDA，将使用CPU训练（速度会很慢）')

        # 创建工作目录
        import os
        self.work_path = Path('work_space')
        self.model_path = self.work_path / 'models'
        self.log_path = self.work_path / 'log'

        # 安全创建目录
        try:
            if not os.path.exists(self.model_path):
                os.makedirs(self.model_path)
        except FileExistsError:
            pass  # 目录已存在，忽略错误

        try:
            if not os.path.exists(self.log_path):
                os.makedirs(self.log_path)
        except FileExistsError:
            pass

        # 初始化step
        self.step = args.initial_step

        # 加载数据
        self.setup_data()

        # 初始化模型
        self.setup_model()

        # TensorBoard
        self.writer = SummaryWriter(str(self.log_path))

    def setup_data(self):
        """设置数据加载器"""
        print(f'\n加载数据集: {self.args.data_path}')

        # 数据增强和预处理
        train_transform = Compose([
            RandomHorizontalFlip(p=0.5),
            ToTensor(),
            Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])

        # 加载数据集
        dataset = FaceDataset(self.args.data_path, train_transform)
        self.class_num = dataset.num_classes

        print(f'数据集大小: {len(dataset)}')
        print(f'类别数量: {self.class_num}')

        # 创建DataLoader
        self.train_loader = DataLoader(
            dataset,
            batch_size=self.args.batch_size,
            shuffle=True,
            num_workers=self.args.num_workers,
            pin_memory=True
        )

        print(f'每个epoch的batch数: {len(self.train_loader)}')

    def setup_model(self):
        """初始化模型、损失函数和优化器"""
        print('\n初始化模型...')

        self.model = MobileFaceNet(embedding_size=512).to(self.device)
        print('MobileFaceNet模型已创建')

        # 加载预训练模型或checkpoint
        if hasattr(self.args, 'resume') and self.args.resume:
            # 从checkpoint恢复训练
            checkpoint_model = Path(self.args.resume)
            checkpoint_head = checkpoint_model.parent / checkpoint_model.name.replace('mobilefacenet', 'arcface_head')

            if checkpoint_model.exists() and checkpoint_head.exists():
                print(f'从checkpoint恢复训练: {checkpoint_model.name}')
                self.model.load_state_dict(torch.load(checkpoint_model, map_location=self.device))

                # 临时创建head来获取class_num（从checkpoint中加载）
                temp_head_dict = torch.load(checkpoint_head, map_location=self.device)
                self.class_num = temp_head_dict['kernel'].shape[1]
                print(f'从checkpoint检测到类别数: {self.class_num}')

                # 重新加载数据集以验证class_num
                print('验证数据集类别数...')
                # setup_data会在__init__中被调用，这里self.class_num会被覆盖，所以需要保存
                saved_class_num = self.class_num
            else:
                raise FileNotFoundError(f'Checkpoint文件不存在: {checkpoint_model} 或 {checkpoint_head}')
        else:
            # 加载预训练模型
            pretrained_path = Path('mobilefacenet.pth')
            if pretrained_path.exists():
                print(f'加载预训练模型: {pretrained_path}')
                state_dict = torch.load(pretrained_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                print('预训练模型加载成功')
            else:
                print(f'警告: 未找到预训练模型 {pretrained_path}，从头开始训练')

        # 创建Arcface head
        self.head = Arcface(embedding_size=512, classnum=self.class_num).to(self.device)
        print(f'Arcface head已创建 (类别数: {self.class_num})')

        # 如果是从checkpoint恢复，加载head权重
        if hasattr(self.args, 'resume') and self.args.resume:
            checkpoint_head = Path(self.args.resume).parent / Path(self.args.resume).name.replace('mobilefacenet', 'arcface_head')
            self.head.load_state_dict(torch.load(checkpoint_head, map_location=self.device))
            print('Arcface head权重已加载')

        self.criterion = nn.CrossEntropyLoss()

        # 优化器 - 使用 MobileFaceNet 推荐的参数
        # 分离 BatchNorm 参数和其他参数
        paras_only_bn = []
        paras_wo_bn = []
        for name, param in self.model.named_parameters():
            if 'bn' in name:
                paras_only_bn.append(param)
            else:
                paras_wo_bn.append(param)

        self.optimizer = optim.SGD([
            {'params': paras_wo_bn[:-1], 'weight_decay': 4e-5},
            {'params': [paras_wo_bn[-1]] + [self.head.kernel], 'weight_decay': 4e-4},
            {'params': paras_only_bn}
        ], lr=self.args.lr, momentum=0.9)

        print(f'优化器已创建 (学习率: {self.args.lr})')

        self.milestones = [12, 15, 18]
        print(f'学习率衰减节点: {self.milestones}')

    def schedule_lr(self):
        """学习率衰减"""
        for params in self.optimizer.param_groups:
            params['lr'] /= 10
        current_lr = self.optimizer.param_groups[0]['lr']
        print(f'\n学习率已调整为: {current_lr}')

    def train_epoch(self, epoch):
        """训练一个epoch"""
        self.model.train()
        running_loss = 0.0
        running_acc = 0.0
        batch_count = 0

        # 使用tqdm显示进度条
        pbar = tqdm(self.train_loader, desc=f'Epoch {epoch}/{self.args.epochs}')

        for batch_idx, (images, labels) in enumerate(pbar):
            images = images.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad()
            embeddings = self.model(images)
            thetas = self.head(embeddings, labels)
            loss = self.criterion(thetas, labels)

            loss.backward()
            self.optimizer.step()

            # 计算准确率
            _, predicted = torch.max(thetas.data, 1)
            accuracy = (predicted == labels).float().mean()

            running_loss += loss.item()
            running_acc += accuracy.item()
            batch_count += 1
            self.step += 1

            # 更新进度条
            pbar.set_postfix({
                'loss': f'{loss.item():.4f}',
                'acc': f'{accuracy.item():.4f}',
                'step': self.step
            })

            # 记录到TensorBoard（每100个batch记录一次）
            if self.step % 100 == 0 and batch_count > 0:
                avg_loss = running_loss / batch_count
                avg_acc = running_acc / batch_count
                self.writer.add_scalar('train/loss', avg_loss, self.step)
                self.writer.add_scalar('train/accuracy', avg_acc, self.step)
                self.writer.flush()  # 强制写入磁盘
                running_loss = 0.0
                running_acc = 0.0
                batch_count = 0

    def save_model(self, epoch, extra=''):
        """保存模型"""
        model_name = f'mobilefacenet_epoch{epoch}_step{self.step}{extra}.pth'
        head_name = f'arcface_head_epoch{epoch}_step{self.step}{extra}.pth'

        torch.save(self.model.state_dict(), self.model_path / model_name)
        torch.save(self.head.state_dict(), self.model_path / head_name)

        print(f'\n模型已保存: {model_name}')

    def train(self):
        """主训练循环"""
        print('\n' + '='*60)
        print('开始训练')
        print('='*60)
        print(f'训练轮数: {self.args.epochs}')
        print(f'批大小: {self.args.batch_size}')
        print(f'初始Step: {self.step}')
        print(f'数据集: {self.args.data_path}')
        print('='*60 + '\n')

        for epoch in range(1, self.args.epochs + 1):
            print(f'\n开始 Epoch {epoch}/{self.args.epochs}')

            # 学习率调度
            if epoch in self.milestones:
                self.schedule_lr()

            # 训练一个epoch
            self.train_epoch(epoch)

        # 只保存最终模型
        self.save_model(self.args.epochs, extra='_final')

        print('\n' + '='*60)
        print('训练完成!')
        print(f'总Step数: {self.step}')
        print(f'模型保存在: {self.model_path}')
        print(f'TensorBoard日志: {self.log_path}')
        print('='*60)

        self.writer.close()


def main():
    parser = argparse.ArgumentParser(description='MobileFaceNet训练脚本（无PIL依赖版本）')
    parser.add_argument('-d', '--data_path', type=str,
                        default='datasets/casia-webface',
                        help='数据集路径')
    parser.add_argument('-b', '--batch_size', type=int, default=200,
                        help='批大小')
    parser.add_argument('-e', '--epochs', type=int, default=10,
                        help='训练轮数')
    parser.add_argument('-lr', '--lr', type=float, default=0.001,
                        help='学习率')
    parser.add_argument('-w', '--num_workers', type=int, default=4,
                        help='数据加载线程数')
    parser.add_argument('-s', '--initial_step', type=int, default=0,
                        help='初始step数（用于显示）')
    parser.add_argument('-r', '--resume', type=str, default=None,
                        help='从checkpoint恢复训练（指定mobilefacenet模型路径）')

    args = parser.parse_args()

    # 创建训练器并开始训练
    trainer = ModernTrainer(args)
    trainer.train()


if __name__ == '__main__':
    main()
    # python train_modern.py -d datasets/casia-webface -b 200 -w 4 -e 20 -s 9981
    # tensorboard --logdir=work_space/log
    #  # 从20轮训练的模型继续训练15轮
    # python train_modern.py -d datasets/casia-webface -b 200 -w 4 -e 15 -s 11461 -r work_space/models/mobilefacenet_epoch20_step11461_final.pth

