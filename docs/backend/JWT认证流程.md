## JWT 认证实现完成

### 新增文件

1. backend/utils/auth.py - JWT 工具模块
- create_access_token(username) - 生成 JWT token（24小时有效期）
- verify_token(token) - 验证 JWT token，返回用户名
- extract_token_from_header(authorization) - 从 Header 中提取 token
- 使用 datetime.now(timezone.utc) 替代已弃用的 utcnow()

### 修改文件

2. backend/routers/auth.py
- /api/login 现在返回 {"status": "success", "token": "<jwt_token>"}
- 符合设计文档要求

3. backend/routers/unlock.py
- /api/unlock 现在验证 JWT token 而不是用户名密码
- 从 Header 中读取 Authorization: Bearer <token>
- 符合设计文档要求："Header: 需携带 Token (Authorization: Bearer ...)"

---
### 使用方式

前端调用流程：

1. 登录获取 token:
POST /api/login
Body: { username: "admin", password: "123456" }
Response: { status: "success", token: "eyJ0eXAiOiJKV1QiLCJhbGci..." }

2. 使用 token 开门:
POST /api/unlock
Headers: { Authorization: "Bearer eyJ0eXAiOiJKV1QiLCJhbGci..." }
Response: { status: "success", message: "Door unlock initiated" }

---
注意事项

- Token 有效期：24小时
- SECRET_KEY 目前是硬编码的，生产环境应该从环境变量读取
- 只有 /api/unlock 需要 token 认证，其他端点不需要


1. 新增文件：backend/utils/password.py
   - hash_password(password) - 对明文密码进行 bcrypt hash
   - verify_password(plain_password, hashed_password) - 验证密码是否正确
   - 使用 passlib + bcrypt
2. 修改：backend/database/manager.py
   - add_administrator() - 存储时自动 hash 密码
   - update_administrator_password() - 更新时自动 hash 新密码
3. 修改：backend/routers/auth.py
   - login() - 使用 verify_password() 验证密码
   - change_password() - 使用 verify_password() 验证旧密码

---
🔒 安全改进

之前（不安全）：
数据库存储: "123456" (明文)
登录验证: if db_pwd == password  (直接比较)

现在（安全）：
数据库存储: "$2b$12$KIXxOV..." (bcrypt hash)
登录验证: verify_password(password, hashed)  (hash 验证)

---
📝 使用方式

用户登录时：
- 输入：username="admin", password="123456"
- 系统自动验证 hash
- 返回：JWT token

用户体验没有任何变化，仍然输入明文密码 "123456"。

---
⚠️ 重要提示

首次运行需要重新初始化数据库！

因为现有数据库中的密码是明文，需要：

1. 删除旧数据库（如果存在）
2. 重新运行程序，会自动创建管理员并 hash 密码

