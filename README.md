# SmartGate-App (智能门禁系统工程端)

本项目是基于 RK3568 的人脸识别门禁系统应用端，包含后端 (FastAPI)、前端及 C++ 推理引擎。


## What's it

目标：实现双模验证的智能门禁（人脸识别 + 传统密码）

  硬件配置：

  - RK3568 开发板（核心）
  - OV5695 摄像头模块
  - 4x4 矩阵键盘

  核心技术方案

1. 用户管理交互

   - 使用 WiFi AP 模式 + FastAPI Web 服务

   - 用户通过手机浏览器访问管理界面（录入人脸/密码、查看日志等）

2. AI 推理引擎

   - RetinaFace：人脸检测

   - MobileFaceNet：特征提取

   - 使用 RKNN SDK 在 NPU 上运行


3. 数据存储

   SQLite 数据库存储：用户信息、密码哈希、人脸特征向量（BLOB）、访问日志

4. 触发机制

   低功耗混合模式：移动侦测（待机）+ 按键唤醒 + 人脸识别（激活）

## 模型训练

本项目的模型训练源码、数据集处理及 ONNX 导出脚本位于独立的算法仓库，请点击下方链接查看：

👉 **[SmartGate-Model-Zoo (模型训练仓库)](https://github.com/JuyaoHuang/SmartGaze-model-zoo)**

## Tech Stack

- 后端：fastAPI
- 前端：原生 html
- 人脸识别模块：RetinaFace + Mobilefacenet

## Structure

## Face detection session

## Models


