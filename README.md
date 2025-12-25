# SmartGate-App (智能门禁系统)

基于 RK3568 的智能人脸识别门禁系统，采用 FastAPI + Web 前端 + C++ 推理引擎架构，支持本地开发调试和嵌入式部署。

推理模型为 "RetinaFace+MobileFaceNet" 的工业黄金配置的人脸检测模型。

## ✨ 功能特性

- 🔐 **人脸识别门禁** - 基于 RetinaFace + MobileFaceNet 的高精度人脸识别
- 📱 **Web 管理界面** - 手机/电脑浏览器直接管理，无需安装 APP
- 🎥 **实时视频流** - MJPEG 实时预览摄像头画面
- 👤 **用户管理** - 人脸录入、删除、列表查看
- 🚪 **远程开门** - Web 端一键远程开门控制
- 🔑 **密码管理** - 管理员登录认证和密码修改
- 🖥️ **开发模式** - Mock 模拟硬件，支持 PC 开发调试
- ⚡ **NPU 加速** - 使用 RKNN SDK 在 NPU 上运行，低功耗高性能

## 🛠️ 技术栈

### 后端

- **FastAPI** - 现代化的 Python Web 框架
- **OpenCV** - 图像处理与视频流
- **SQLite** - 轻量级数据库
- **PyJWT** - JWT 认证
- **Uvicorn** - ASGI 服务器

### 前端
- **Bootstrap 5** - 响应式 UI 框架
- **Vanilla JavaScript** - 原生 JS，无框架依赖
- **Jinja2** - 服务端模板引擎

### AI 推理引擎
- **RetinaFace** - 人脸检测模型
- **MobileFaceNet** - 人脸特征提取
- **RKNN SDK** - 瑞芯微 NPU 推理框架

## 📁 项目结构

```shell
SmartGate-App/
├── backend/                # 后端服务
│   ├── main.py            # FastAPI 应用入口
│   ├── config.py          # 配置文件（重要）
│   ├── start_server.py    # 启动脚本
│   ├── routers/           # API 路由
│   │   ├── auth.py        # 认证接口
│   │   ├── face.py        # 人脸管理接口
│   │   ├── unlock.py      # 开门控制接口
│   │   ├── stream.py      # 视频流接口
│   │   └── pages.py       # 页面路由
│   ├── core/              # 核心功能
│   │   ├── camera.py      # 摄像头管理
│   │   ├── face_engine.py # 人脸引擎封装
│   │   ├── doorController.py  # 门锁控制
│   │   ├── backgroundThread.py # 后台守护线程
│   │   └── mock.py        # Mock 模拟（开发用）
│   ├── database/          # 数据库
│   │   └── manager.py     # 数据库管理器
│   └── utils/             # 工具函数
│       ├── auth.py        # JWT 认证
│       └── password.py    # 密码工具
├── fronted/               # 前端页面
│   ├── templates/         # HTML 模板
│   │   ├── login.html     # 登录页
│   │   ├── dashboard.html # 主控制台
│   │   ├── face_input.html    # 人脸录入
│   │   └── face_list.html     # 用户列表
│   └── static/            # 静态资源
│       ├── css/           # 样式文件
│       └── js/            # JavaScript
├── face_app/              # C++ 推理引擎
│   ├── lib/               # 编译好的 .so 库
│   └── include/           # 头文件
├── face_detection/        # 人脸检测模型
└── docs/                  # 文档
    └── 前后端集成文档.md  # 详细技术文档
```

## 🚀 快速开始

### 开发环境（PC）

**1. 安装依赖**
```bash
pip install -r backend/requirements.txt
```

**2. 配置开发模式**

确保 `backend/config.py` 中设置为开发模式：
```python
DEV_MODE = True  # 使用 Mock 模拟硬件
```

**3. 启动服务器**
```bash
python backend/start_server.py
```

**4. 访问系统**

```
浏览器打开：http://localhost:8000
默认账号：admin
默认密码：123456
```

### 生产环境（RK3568）

**1. 修改配置**

编辑 `backend/config.py`：
```python
DEV_MODE = False  # 切换到生产模式
GPIO_DOOR_PIN = 17  # 配置门锁 GPIO 引脚
```

**2. 硬件连接**
- 连接 OV5695 摄像头到 CSI 接口
- 连接门锁继电器到 GPIO17（或自定义引脚）
- 确保硬件供电正常

**3. 安装系统依赖**
```bash
# 在 RK3568 上安装必要的系统库
sudo apt-get install python3-opencv
```

**4. 启动服务**
```bash
python backend/start_server.py
```

**5. 配置自启动**（可选）
```bash
# 创建 systemd 服务文件
sudo nano /etc/systemd/system/smartgate.service
```

## 💡 核心功能说明

### 1. 人脸识别流程

```
摄像头采集 → 人脸检测(RetinaFace) → 特征提取(MobileFaceNet)
→ 特征比对(余弦相似度) → 身份验证 → 开门/拒绝
```

### 2. 双模式架构

| 模式 | 说明 | 硬件依赖 | 适用场景 |
|------|------|----------|----------|
| 开发模式 | Mock 模拟 | 无 | PC 开发调试 |
| 生产模式 | 真实硬件 | RK3568 + 摄像头 | 实际部署 |

### 3. API 接口

完整的 RESTful API，支持：
- JWT 认证授权
- 人脸录入/删除/查询
- 实时视频流（MJPEG）
- 远程开门控制
- 密码管理

详见：[前后端集成文档](docs/前后端集成文档.md)

## 🧠 人脸识别模块详解

### 架构设计

本系统采用 **RetinaFace + MobileFaceNet** 的工业级人脸识别方案：

```shell
JPEG 图片 (任意尺寸)
    ↓
[1. 图像解码] → cv::Mat (BGR)
    ↓
[2. 调整尺寸] → 640×640
    ↓
[3. RetinaFace 推理] → 人脸框 + 5个关键点 (NPU 加速)
    ↓
[4. 人脸对齐] → 仿射变换 → 112×112 RGB (CPU)
    ↓
[5. MobileFaceNet 推理] → 512维特征向量 (NPU 加速, L2归一化)
    ↓
[6. 余弦相似度计算] → 匹配结果 (0~1)
```

### 性能指标

**运行时性能（RK3568 NPU）**

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 图像解码 + 预处理 | ~20ms | OpenCV imdecode + resize |
| RetinaFace 推理 | ~40ms | NPU 硬件加速 |
| 人脸对齐 | ~5ms | 仿射变换 (CPU) |
| MobileFaceNet 推理 | ~30ms | NPU 硬件加速 |
| 特征比对 | < 1ms | 余弦相似度计算 |
| **单次识别总耗时** | **~96ms** | 约 10 FPS |

**模型规格**

| 模型 | 输入尺寸 | 输出 | 准确率 | 文件大小 |
|------|---------|------|--------|----------|
| RetinaFace | 640×640 RGB | 人脸框 + 5关键点 | 95%+ (WIDER FACE) | ~2.5MB |
| MobileFaceNet | 112×112 RGB | 512维特征向量 | 99.5%+ (LFW) | ~4MB |

### 关键参数配置

**相似度阈值建议**

| 应用场景 | 推荐阈值 | 说明 |
|---------|---------|------|
| 安全场景（支付、门禁） | **0.7** | 严格模式，低误识率 |
| 通用场景（考勤、相册） | **0.6** | 推荐值，平衡准确率和便利性 |
| 宽松场景（推荐系统） | **0.5** | 高召回率 |

> **注意**：当前系统默认使用 0.5，可在 `backend/config.py` 中修改 `SIMILARITY_THRESHOLD`

**检测参数**

```c
CONF_THRESHOLD = 0.5    // 人脸置信度阈值
NMS_THRESHOLD = 0.4     // NMS IoU 阈值
MIN_FACE_SIZE = 40      // 最小人脸尺寸(像素)
```

### 模块架构

```shell
┌─────────────────────────────────┐
│  Layer 3: FastAPI 路由层        │  ← 业务逻辑
│  - HTTP 接口                     │
│  - 数据库操作                    │
│  - JWT 认证                      │
└─────────────────────────────────┘
              ↓ 调用
┌─────────────────────────────────┐
│  Layer 2: Python Wrapper        │  ← 接口封装
│  (backend/core/face_engine.py) │
│  - ctypes 绑定 C++ 库            │
│  - 单例模式管理                  │
└─────────────────────────────────┘
              ↓ ctypes
┌─────────────────────────────────┐
│  Layer 1: C++ 动态库            │  ← 核心计算
│  (libface_engine.so)           │
│  - RKNN 模型推理                │
│  - OpenCV 图像处理              │
│  - 人脸对齐算法                 │
└─────────────────────────────────┘
```

### 使用示例

**Python 接口**

```python
from backend.core.face_engine import get_face_engine

# 获取引擎实例（单例）
engine = get_face_engine()

# 提取人脸特征
with open("face1.jpg", "rb") as f:
    feature1 = engine.extract_feature(f.read())

with open("face2.jpg", "rb") as f:
    feature2 = engine.extract_feature(f.read())

# 计算相似度
if feature1 and feature2:
    similarity = engine.compute_similarity(feature1, feature2)
    print(f"相似度: {similarity:.4f}")

    if similarity >= 0.6:
        print("✓ 是同一人")
    else:
        print("✗ 不是同一人")
```

### 技术优势

- ✅ **NPU 硬件加速** - 使用 RKNN SDK，推理速度快、功耗低
- ✅ **多尺度检测** - RetinaFace 支持 40px 以上小人脸检测
- ✅ **高精度识别** - MobileFaceNet 在 LFW 数据集达到 99.5%+ 准确率
- ✅ **轻量化部署** - 模型总大小仅 6.5MB，动态库 15MB
- ✅ **工业级架构** - C++ 核心 + Python 封装，稳定可靠

**详细技术文档**: [face_detection/README.md](face_detection/README.md)

## 📚 文档

- [前后端集成文档](docs/前后端集成文档.md) - API 接口、部署指南、常见问题
- [人脸识别模块文档](face_detection/README.md) - 架构设计、编译部署、性能优化
- [模型训练仓库](https://github.com/JuyaoHuang/SmartGaze-model-zoo) - RetinaFace 和 MobileFaceNet 的训练代码

## 🔧 配置说明

关键配置项（`backend/config.py`）：

```python
# 运行模式
DEV_MODE = True  # True=开发模式, False=生产模式

# JWT 认证
JWT_SECRET_KEY = '123456'  # 生产环境请修改
JWT_EXPIRE_HOURS = 24      # Token 有效期

# 摄像头配置
CAMERA_INDEX = 0           # 摄像头索引
CAMERA_WIDTH = 640         # 分辨率宽度
CAMERA_HEIGHT = 480        # 分辨率高度

# 人脸识别
SIMILARITY_THRESHOLD = 0.5  # 相似度阈值(0-1)

# GPIO 配置
GPIO_DOOR_PIN = None       # 门锁控制引脚(生产环境需设置)

# 服务器
SERVER_HOST = '0.0.0.0'    # 监听地址
SERVER_PORT = 8000         # 端口号
```

## 🐛 常见问题

**Q: 422 Unprocessable Entity 错误？**

A: 前后端数据格式不匹配，确保后端使用 Pydantic 模型接收 JSON。

**Q: 视频流显示灰色画面？**

A: 开发模式下 Mock 摄像头会显示灰色+文字，这是正常的。

**Q: 人脸识别失败？**

A: 生产模式下检查摄像头连接和 `.so` 库是否正确加载。

**Q: 如何修改默认密码？**

A: 修改 `config.py` 中的 `DEFAULT_ADMIN_PASSWORD`，重新初始化数据库。

更多问题参考：[前后端集成文档 - 常见问题](docs/前后端集成文档.md#7-常见问题)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目为课程设计作品，仅供学习交流使用。

## 👥 作者

- [Juyao Huang](https://github.com/JuyaoHuang) - 智能系统设计、开发与审查
- [Haoran Wu](https://github.com/owl-gugugugu) - 后端开发
- [Junshi Kong](https://github.com/kjs123456) - 前端开发 

## 🔗 相关链接

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [RKNN Toolkit2 文档](https://github.com/rockchip-linux/rknn-toolkit2)
- [Bootstrap 5 文档](https://getbootstrap.com/)

