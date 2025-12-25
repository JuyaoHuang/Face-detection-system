"""
智能门禁系统 - 统一配置文件

说明：
- 所有配置项都提供了合理的默认值
- 敏感配置（JWT_SECRET_KEY）支持通过环境变量覆盖
- 部署到 RK3568 后，可以直接修改此文件调整参数
"""

import os
from pathlib import Path

# ==================== 项目路径配置 ====================
# 获取项目根目录（backend/文件夹）
BASE_DIR = Path(__file__).resolve().parent

# ==================== JWT 认证配置 ====================
# JWT 密钥（用于签名和验证 Token）
# 生产环境建议：使用环境变量设置，或者修改为随机生成的强密钥
# 设置方法：export JWT_SECRET_KEY="your-random-secret-key-here"
JWT_SECRET_KEY = os.getenv("`JWT_SECRET_KEY`", "123456")

# JWT 加密算法（推荐使用 HS256）
JWT_ALGORITHM = "HS256"

# Token 有效期（小时）
JWT_EXPIRE_HOURS = 24

# ==================== 数据库配置 ====================
# SQLite 数据库文件路径
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "database" / "database.db"))

# 默认管理员账号（首次启动时自动创建）
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "123456"

# ==================== 摄像头配置 ====================
# 摄像头设备索引
# - 9: USB 摄像头（晟悦 SY011HD-V1, 1080P@60fps, UVC协议）
# - 测试结果：/dev/video9, uvcvideo驱动, 30 FPS @ 640x480
# - 如果有多个摄像头，可以设置为 1, 2, 3...
# - RK3568 上可能需要尝试不同索引（0, 1, 11, 21）
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "9"))

# 摄像头初始化模式（重要配置）
# - 'auto': 自动模式（推荐）- 优先尝试 gstreamer，失败则降级到 opencv
# - 'gstreamer': 强制使用 GStreamer 硬件加速管道（RK3568 专用，仅支持 MIPI CSI 摄像头）
# - 'opencv': 强制使用标准 OpenCV V4L2（通用模式，兼容性最好，支持 USB 摄像头）
# - USB 摄像头必须使用 'opencv' 模式（不支持 rkisp 硬件加速）
CAMERA_MODE = "opencv"  # 可选值: 'auto', 'gstreamer', 'opencv'

# GStreamer 管道配置（仅在 gstreamer 模式下使用）
# - 适用于 RK3568 + OV5695 硬件加速
# - 管道说明：rkisp(ISP处理) -> NV12(YUV格式) -> videoconvert(格式转换) -> BGR(OpenCV格式)
GSTREAMER_PIPELINE = (
    "rkisp device=/dev/video{index} io-mode=1 ! "
    "video/x-raw,format=NV12,width={width},height={height},framerate={fps}/1 ! "
    "videoconvert ! "
    "video/x-raw,format=BGR ! appsink"
)

# OpenCV 模式下尝试的设备索引列表
# - USB 摄像头：通常占用两个设备节点（video9=图像捕获, video10=元数据）
# - RK3568 上可能有多个 video 设备（ISP、编码器、实际摄像头）
# - 按顺序尝试，找到第一个能读取帧的设备
CAMERA_FALLBACK_INDICES = [9, 10, 0, 1, 11, 21]

# 摄像头分辨率配置
# - 推荐配置：640x480 (VGA) - 性能最佳，门禁场景足够
# - 可选配置：1280x720 (HD) - 更清晰，但占用更多资源
# - GStreamer 模式：支持 1920x1080（硬件加速，CPU占用低）
# - OpenCV 模式：建议 640x480（软解码，降低CPU负担）
CAMERA_WIDTH = 640  # 宽度（像素）
CAMERA_HEIGHT = 480  # 高度（像素）

# 摄像头帧率配置
# - 推荐值：30 FPS（平衡性能和流畅度）
# - 可选值：15-60 FPS
CAMERA_FPS = 30

# 移动检测 - 轮廓面积阈值（像素面积）
# - 作用：过滤掉小幅度运动（如树叶晃动、光线变化）
# - 取值范围：100-2000（推荐：500-1000）
# - 数值越大，越不容易触发移动检测（越不敏感）
MOTION_CONTOUR_THRESHOLD = 500

# ==================== 人脸识别配置 ====================
# 后台线程检查间隔（秒）
# - 作用：控制后台线程多久读取一次摄像头帧
# - 推荐值：0.1（即每秒检查10次，约10 FPS）
# - 数值越小，反应越灵敏，但 CPU 占用越高
CHECK_INTERVAL = 0.1

# 移动检测 - 二值化阈值（0-255）
# - 作用：帧差法中，像素差异超过此值才认为是"变化"
# - 取值范围：10-50（推荐：20-30）
# - 数值越小，对细微运动越敏感
BINARY_THRESHOLD = 25

# 移动检测 - 轮廓面积阈值（像素面积）
# - 同 MOTION_CONTOUR_THRESHOLD（在 Camera 类中使用）
# - 这里定义是为了传递给 BackgroundThread
CONTOUR_THRESHOLD = 500

# 人脸识别 - 相似度阈值（0.0 - 1.0）
# - 作用：人脸特征向量余弦相似度超过此值才认为是"同一人"
# - 推荐值：0.6-0.7（平衡安全性和便利性）
# - 0.5：较宽松（误识别风险高）
# - 0.7：较严格（可能需要多次尝试）
# - 0.8+：非常严格（可能无法识别）
SIMILARITY_THRESHOLD = 0.3  # 从原来的 0.5 提高到 0.6，增强安全性

# ==================== 门锁控制配置 ====================
# 开门持续时间（秒）
# - 作用：GPIO 高电平持续时长，控制电磁锁/继电器断电时间
# - 推荐值：2-5 秒
DOOR_OPEN_DURATION = 3

# GPIO 引脚配置（TODO: 根据实际硬件接线设置）
# - 示例：如果门锁继电器接在 GPIO17，则设置为 17
# - None 表示未配置（当前使用日志模拟开门）
GPIO_DOOR_PIN = None  # 实际部署时需要修改为真实引脚号，例如：17

# 蜂鸣器 GPIO 引脚（可选）
GPIO_BUZZER_PIN = None  # 示例：18

# LED 指示灯 GPIO 引脚（可选，仅用于传统GPIO控制）
GPIO_LED_PIN = None  # 示例：27

# LED 指示灯 sysfs 路径（RK3568 开发板使用）
# - RK3568 开发板使用 sysfs LED 控制接口
# - 可用LED：work (/sys/class/leds/work/brightness)
# - 亮度范围：0-255（0=关闭，255=最亮）
LED_SYSFS_PATH = "/sys/class/leds/work/brightness"

# ==================== FastAPI 服务器配置 ====================
# 监听地址
# - '0.0.0.0'：允许外部访问（手机通过 Wi-Fi 连接）
# - '127.0.0.1'：仅本机访问
SERVER_HOST = "0.0.0.0"

# 监听端口
SERVER_PORT = 8000

# 是否启用调试模式
# - True：自动重载代码，显示详细错误信息
# - False：生产模式，性能更好
DEBUG_MODE = False

# ==================== 开发模式配置 ====================
# 开发模式（用于 PC 开发调试，跳过硬件依赖）
# - True：使用 Mock 模拟摄像头和人脸引擎，不初始化真实硬件
# - False：正常加载硬件模块（RK3568 生产环境）
# - 当前已部署到 RK3568 开发板，使用真实 USB 摄像头
DEV_MODE = False  # PC 开发时设置为 True，部署到 RK3568 时改为 False

# ==================== 日志配置 ====================
# 日志级别
# - DEBUG：详细日志（开发调试用）
# - INFO：一般信息（推荐）
# - WARNING：警告信息
# - ERROR：错误信息
LOG_LEVEL = "INFO"

# 是否输出到文件
LOG_TO_FILE = False
LOG_FILE_PATH = str(BASE_DIR / "logs" / "smart_door.log")

# ==================== 性能优化配置 ====================
# 视频流编码质量（JPEG 压缩质量：1-100）
# - 数值越大，画质越好，但流量越大
# - 推荐值：50-80
VIDEO_STREAM_QUALITY = 70

# 视频流分辨率（宽, 高）
# - None：使用摄像头实际分辨率（由 CAMERA_WIDTH/CAMERA_HEIGHT 决定）
# - (width, height)：如果需要视频流与摄像头分辨率不同，可以在这里设置
# - 通常保持 None 即可
VIDEO_STREAM_RESOLUTION = None


# ==================== 配置验证 ====================
def validate_config():
    """验证配置的合理性，启动时调用"""
    issues = []

    # 检查 JWT 密钥是否修改
    if JWT_SECRET_KEY == "smart-door-rk3568-secret-key-change-me-in-production":
        issues.append("[WARN] JWT_SECRET_KEY 使用默认值，生产环境建议修改")

    # 检查相似度阈值范围
    if not (0.0 <= SIMILARITY_THRESHOLD <= 1.0):
        issues.append(
            f"[ERROR] SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD} 超出范围 [0.0, 1.0]"
        )

    # 检查相似度阈值是否过低（安全风险）
    if SIMILARITY_THRESHOLD < 0.5:
        issues.append(
            f"[WARN] SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD} 过低，可能导致误识别"
        )

    # 检查数据库路径
    db_dir = Path(DATABASE_PATH).parent
    if not db_dir.exists():
        issues.append(f"[INFO] 数据库目录不存在，将自动创建：{db_dir}")
        db_dir.mkdir(parents=True, exist_ok=True)

    # 输出验证结果
    if issues:
        print("\n" + "=" * 60)
        print("配置验证结果：")
        for issue in issues:
            print(f"  {issue}")
        print("=" * 60 + "\n")

    return len([i for i in issues if i.startswith("[ERROR]")]) == 0  # 返回是否有错误


# ==================== 配置摘要 ====================
def print_config_summary():
    """打印配置摘要（启动时调用，便于调试）"""
    print("\n" + "=" * 60)
    print("智能门禁系统配置摘要：")
    print("=" * 60)
    print(
        f"运行模式：            {'开发模式 (Mock)' if DEV_MODE else '生产模式 (硬件)'}"
    )
    print(f"摄像头模式：          {CAMERA_MODE}")
    print(f"摄像头索引：          {CAMERA_INDEX}")
    print(f"摄像头分辨率：        {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {CAMERA_FPS}fps")
    print(f"人脸相似度阈值：      {SIMILARITY_THRESHOLD}")
    print(f"移动检测阈值：        {CONTOUR_THRESHOLD} 像素")
    print(f"开门持续时间：        {DOOR_OPEN_DURATION} 秒")
    print(f"服务器地址：          http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"访问地址：            http://localhost:{SERVER_PORT}")
    print(f"数据库路径：          {DATABASE_PATH}")
    print(f"GPIO 门锁引脚：       {GPIO_DOOR_PIN or '未配置（日志模拟）'}")
    if DEV_MODE:
        print("\n[警告] 当前为开发模式，硬件功能将被 Mock 模拟")
        print("[警告] 部署到 RK3568 前请将 DEV_MODE 改为 False")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    """测试配置文件"""
    print("测试配置文件加载...\n")

    # 验证配置
    is_valid = validate_config()

    # 打印配置摘要
    print_config_summary()

    # 测试环境变量覆盖
    print("测试环境变量覆盖：")
    print(f"  JWT_SECRET_KEY: {JWT_SECRET_KEY[:20]}...")
    print(f"  CAMERA_INDEX: {CAMERA_INDEX}")
    print(f"  SIMILARITY_THRESHOLD: {SIMILARITY_THRESHOLD}")

    if is_valid:
        print("\n[OK] 配置验证通过")
    else:
        print("\n[ERROR] 配置存在错误，请检查")
