# RK3568 开发板部署指南

## 📦 需要传输的文件清单

### 1. 核心库文件
```
face_detection/build/
└── libface_engine.so          # 主动态库（~10-20MB）
```

### 2. 模型文件
```
face_detection/models/
├── RetinaFace.rknn            # 人脸检测模型
└── mobilefacenet.rknn         # 人脸识别模型
```

### 3. 测试脚本
```
face_detection/
└── test_api.py                # Python 测试脚本
```

### 4. 测试图片（可选）
```
test_images/
├── person1.jpg
└── person2.jpg
```

---

## 📂 开发板目录结构（建议）

在 RK3568 开发板上创建以下目录：

```
/userdata/face_app/
├── libface_engine.so          # 主库
├── models/
│   ├── RetinaFace.rknn
│   └── mobilefacenet.rknn
├── test_api.py
└── test_images/               # 测试图片（可选）
    ├── person1.jpg
    └── person2.jpg
```

---

## 🚀 部署步骤

### 步骤 1：在 VMWare 中打包文件

```bash
cd ~/project/face_detection

# 创建部署包目录
mkdir -p deploy_package/models

# 复制文件
cp build/libface_engine.so deploy_package/
cp models/*.rknn deploy_package/models/
cp test_api.py deploy_package/

# 打包（方便传输）
tar -czf face_app_deploy.tar.gz deploy_package/

# 查看打包结果
ls -lh face_app_deploy.tar.gz
```

### 步骤 2：传输到开发板

**方法 A：使用 scp（需要网络连接）**
```bash
# 在 VMWare 中执行
scp face_app_deploy.tar.gz root@<开发板IP>:/userdata/
```

**方法 B：使用 U 盘**
1. 将 `face_app_deploy.tar.gz` 复制到 U 盘
2. 将 U 盘插入开发板
3. 挂载 U 盘并复制文件

**方法 C：使用串口传输（较慢）**
使用 `sz` 命令通过串口传输

### 步骤 3：在开发板上解压

```bash
# SSH 或串口登录到开发板
cd /userdata
tar -xzf face_app_deploy.tar.gz
mv deploy_package face_app
cd face_app

# 查看文件
ls -lh
ls -lh models/
```

### 步骤 4：设置环境变量

```bash
# 临时设置（仅当前会话有效）
export LD_LIBRARY_PATH=/userdata/face_app:$LD_LIBRARY_PATH

# 永久设置（写入配置文件）
echo 'export LD_LIBRARY_PATH=/userdata/face_app:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### 步骤 5：检查依赖库

```bash
# 检查 libface_engine.so 的依赖
ldd libface_engine.so

# 应该看到：
# librknnrt.so => /usr/lib/librknnrt.so (找到)
# libpthread.so => ... (找到)
# libc.so => ... (找到)
# 如果有 "not found"，需要安装对应的库
```

### 步骤 6：安装 Python 依赖

```bash
# 检查 Python 和 numpy
python3 --version
python3 -c "import numpy; print(numpy.__version__)"

# 如果 numpy 未安装
pip3 install numpy

# 或者使用板子预装的包管理器
# apt-get install python3-numpy
```

---

## 🧪 测试验证

### 测试 1：检查库是否正确

```bash
cd /userdata/face_app

# 查看库信息
file libface_engine.so
# 应该显示：ELF 64-bit LSB shared object, ARM aarch64

# 检查符号
nm -D libface_engine.so | grep FaceEngine
# 应该看到：FaceEngine_Create, FaceEngine_Init, FaceEngine_ExtractFeature 等
```

### 测试 2：Python 脚本测试

**修改 test_api.py 的路径**（重要！）

在开发板上编辑 `test_api.py`：

```python
# 修改第 20-22 行的路径为绝对路径
LIB_PATH = "/userdata/face_app/libface_engine.so"
RETINAFACE_MODEL = "/userdata/face_app/models/RetinaFace.rknn"
MOBILEFACENET_MODEL = "/userdata/face_app/models/mobilefacenet.rknn"
```

**运行测试**

```bash
cd /userdata/face_app

# 测试 1：单张图片特征提取
python3 test_api.py --image test_images/person1.jpg

# 测试 2：两张图片比对
python3 test_api.py --image test_images/person1.jpg --image2 test_images/person2.jpg
```

**预期输出**

```
✓ Successfully loaded library: /userdata/face_app/libface_engine.so
Initializing FaceEngine...
  RetinaFace model: /userdata/face_app/models/RetinaFace.rknn
  MobileFaceNet model: /userdata/face_app/models/mobilefacenet.rknn
✓ FaceEngine initialized successfully

Extracting feature from: test_images/person1.jpg
✓ Feature extracted successfully
  Feature shape: (512,)
  Feature norm: 1.0000
  Feature range: [-0.5234, 0.6789]

✓ Test completed successfully!
```

---

## 🔧 常见问题排查

### Q1: 找不到 librknnrt.so

**错误**：
```
error while loading shared libraries: librknnrt.so: cannot open shared object file
```

**解决**：
```bash
# 检查系统是否有 RKNN 库
find /usr -name "librknnrt.so"

# 如果找到，添加到 LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# 如果没有，需要从 SDK 安装
```

### Q2: 权限不足

**错误**：
```
Permission denied
```

**解决**：
```bash
chmod +x /userdata/face_app/libface_engine.so
chmod +x /userdata/face_app/test_api.py
```

### Q3: No face detected

**可能原因**：
1. 图片质量差、人脸不清晰
2. 模型文件损坏或格式错误
3. 置信度阈值太高

**解决**：
```bash
# 检查模型文件完整性
md5sum models/RetinaFace.rknn
md5sum models/mobilefacenet.rknn

# 与 VMWare 中的原文件对比 MD5
```

### Q4: Python 版本不兼容

**错误**：
```
SyntaxError: invalid syntax
```

**解决**：
```bash
# 确认 Python 版本 >= 3.6
python3 --version

# 如果版本太低，使用板子的默认 Python3
which python3
```

### Q5: RKNN 初始化失败

**错误**：
```
rknn_init fail! ret=-1
```

**可能原因**：
1. NPU 驱动未加载
2. 模型文件与 RKNN 版本不匹配
3. 内存不足

**解决**：
```bash
# 检查 NPU 设备
ls -l /dev/rknpu*

# 检查内存
free -h

# 重启 NPU 服务（如果有）
# systemctl restart rknn_server
```

---

## 📊 性能验证

在开发板上运行性能测试：

```bash
# 测试单次推理时间
time python3 test_api.py --image test_images/person1.jpg

# 预期耗时（RK3568 NPU）：
# - RetinaFace: 20-50ms
# - MobileFaceNet: 5-15ms
# - 总耗时: 30-70ms
```

---

## 🔄 更新部署

如果需要更新 `.so` 库或模型：

```bash
# 1. 在 VMWare 重新编译
cd ~/project/face_detection/build
make -j4

# 2. 只传输更新的文件
scp libface_engine.so root@<开发板IP>:/userdata/face_app/

# 3. 在开发板上测试
cd /userdata/face_app
python3 test_api.py --image test_images/person1.jpg
```

---

## 📝 部署检查清单

在部署前确认：

- [ ] `libface_engine.so` 是 ARM64 格式（`file` 命令验证）
- [ ] 两个 `.rknn` 模型文件存在且完整
- [ ] 开发板已安装 Python 3.x 和 numpy
- [ ] 开发板有 `/dev/rknpu` 设备（NPU 驱动）
- [ ] 开发板有 `librknnrt.so` 库（RKNN 运行时）
- [ ] `test_api.py` 中的路径已修改为绝对路径
- [ ] 设置了 `LD_LIBRARY_PATH` 环境变量
- [ ] 有测试图片可用

---

## 🎯 下一步：集成到后端

部署成功后，可以：

1. **集成到 FastAPI 后端**
   - 使用 `backend/core/face_engine.py` 包裹类
   - 实现 `/api/face/capture` 和 `/api/face/recognize` 接口

2. **连接数据库**
   - 存储用户人脸特征向量
   - 实现人脸比对逻辑

3. **部署完整系统**
   - FastAPI 后端 + FaceEngine + 数据库 + 前端

---

**部署完成后，请运行测试验证所有功能正常！**

维护者：Juyao Huang

更新时间：2025-12-15
