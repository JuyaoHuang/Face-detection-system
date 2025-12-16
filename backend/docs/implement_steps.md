---
  🎯 我的理解总结

  1. 整体架构 - 五层设计

  这是一个典型的分层架构，职责清晰：

  L1 FastAPI          → 处理 HTTP、视频流、权限
  L2 Service Logic    → 业务逻辑 + 后台守护线程（⭐️核心）
  L3 Core Wrapper     → FaceEngine(已完成) + GlobalCamera(待开发)
  L4 Native .so       → C++ 动态库（已完成）
  L5 SQLite          → 存储用户、特征向量、日志

  关键点：L2 的后台守护线程是核心业务，负责自动开门。

---
  2. 三条数据流 - 理解系统如何工作

  数据流 A：视频预览（给管理员看实时画面）

  - GlobalCamera 持续读取摄像头
  - FastAPI 用生成器 yield 将 JPEG 流式推送到浏览器
  - 手机/网页用 <img src="/api/video_stream"> 实时显示

  数据流 B：人脸录入（管理员点击按钮录入）

  - 手机发送 POST 请求 + 用户名
  - 后端从 GlobalCamera 截取当前帧
  - 调用 FaceEngine 提取特征 → 存入 SQLite

  数据流 C：自动开门（⭐️核心业务逻辑）

  - 后台线程每 100ms 轮询一次
  - 检测画面是否有人（移动侦测）
  - 调用 FaceEngine 提取特征
  - 查询数据库所有用户特征，计算相似度
  - 如果相似度 >= 阈值（0.5 或 0.6）→ 触发 GPIO 开锁

  关键理解：
  - ✅ 自动开门不需要手机参与，完全在板子上独立运行
  - ✅ 手机只用于管理（录入、查看日志、修改设置）

---
  3. 两种工作模式

| 模式             | 触发方式         | 是否开门     | 使用场景             |
| ---------------- | ---------------- | ------------ | -------------------- |
| 路线一：自动守卫 | 后台线程自动检测 | ✅ 是         | 日常使用（核心业务） |
| 路线二：HTTP API | 手机/前端发请求  | ❌ 通常不开门 | 管理和测试           |

  关键理解：
  - /api/face/recognize 只是测试接口，返回识别结果但不开门
  - 真正开门的是后台线程（数据流 C）

---
  4. 核心组件的职责

  ✅ 已完成：

  - face_engine.py - Python Wrapper，调用 libface_engine.so

  ⏳ 待开发：

| 组件               | 职责           | 为什么重要                 |
| ------------------ | -------------- | -------------------------- |
| GlobalCamera       | 单例摄像头管理 | 避免多处同时打开摄像头冲突 |
| background_task.py | 后台守护线程   | ⭐️ 核心业务（自动开门）     |
| db_manager.py      | 数据库封装     | 存储用户特征向量、日志     |
| routers/face.py    | 人脸管理 API   | 录入、列表、删除           |
| routers/stream.py  | MJPEG 视频流   | 实时预览（管理界面）       |
| routers/auth.py    | 认证 API       | 登录保护                   |
| routers/monitor.py | 监控 API       | 日志查询、测试识别         |

---
  5. 数据存储设计

  SQLite 数据库需要存储：
  - 用户表: 用户名、特征向量（BLOB，512维浮点数）
  - 日志表（可选）: 开门记录（时间、用户、方式）
  - 密码表（可选）: 传统开门密码

  关键点：特征向量存储为 BLOB 二进制（numpy.array.tobytes()）

---
  6. 技术细节理解

  GlobalCamera 单例模式

  class GlobalCamera:
      _instance = None

      def __new__(cls):
          if cls._instance is None:
              cls._instance = super().__new__(cls)
              cls._instance.cap = cv2.VideoCapture(0)
          return cls._instance
  为什么单例？ 避免多个地方同时打开 /dev/video0 导致冲突。

  MJPEG 流推送

  def generate_frames():
      while True:
          frame = global_camera.get_frame()
          _, buffer = cv2.imencode('.jpg', frame)
          yield (b'--frame\r\n'
                 b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

  后台线程伪代码

  def background_guard():
      while True:
          frame = global_camera.get_frame()
          if has_motion(frame):  # 移动侦测
              feature = face_engine.extract_feature(frame_to_bytes(frame))
              if feature:
                  similarity = compare_with_database(feature)
                  if similarity >= 0.6:
                      GPIO.output(LOCK_PIN, HIGH)  # 开锁
          time.sleep(0.1)  # 100ms

---

✅ 我理解的开发优先级

  基于架构文档，我认为开发顺序应该是：

  1. database/db_manager.py - 数据存储基础（先建表）
  2. core/camera.py - GlobalCamera 单例（摄像头访问）
  3. routers/stream.py - 视频流（验证摄像头是否正常）
  4. routers/face.py - 人脸管理 API（录入、查询）
  5. core/background_task.py - 后台守护线程（⭐️核心功能）
  6. routers/auth.py + routers/monitor.py - 认证和监控（次要）
  7. main.py - FastAPI 入口（集成所有模块）

---
  ❓ 我的疑问（需要你确认）

  1. 摄像头设备号：是 /dev/video0 吗？还是其他？
  2. GPIO 引脚：使用哪个引脚控制门锁？需要 GPIO 库吗？
  3. 相似度阈值：0.6 还是 0.5？严格模式还是宽松模式？
  4. 认证方式：简单密码登录？还是需要 JWT Token？
  5. 日志功能：一定要做吗？还是可选？

---
  总结：我理解这是一个智能门禁系统，核心是后台线程自动识别开门，FastAPI 只是提供管理界面。FaceEngine 已经完成，现在需要构建后端服务框架。

  你觉得我的理解是否正确？有需要补充或修正的地方吗？

  Todos
  [ ] 实现 database/db_manager.py（数据库管理）
  [ ] 实现 core/camera.py（GlobalCamera 单例）
  [ ] 实现 routers/stream.py（MJPEG 视频流）
  [ ] 实现 routers/face.py（人脸录入、列表、删除）
  [ ] 实现 core/background_task.py（自动开门线程）
  [ ] 实现 routers/auth.py（登录和密码管理）
  [ ] 实现 routers/monitor.py（日志查询和测试接口）
  [ ] 实现 main.py（FastAPI 入口和启动配置）
  [ ] 集成测试和部署到 RK3568