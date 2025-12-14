#!/bin/bash
# CASIA-WebFace数据集训练脚本
# 使用预训练的MobileFaceNet模型进行二次训练

echo "开始训练 CASIA-WebFace 数据集"
echo "================================"
echo "网络: MobileFaceNet"
echo "数据集: casia-webface"
echo "批大小: 200"
echo "训练轮数: 20"
echo "初始Step: 9981"
echo "Workers: 4"
echo "================================"

python train.py -net mobilefacenet -b 200 -w 4 -d casia-webface -e 20 -s 9981

echo "训练完成!"
echo "TensorBoard日志位于: work_space/log"
echo "模型保存位于: work_space/models"
