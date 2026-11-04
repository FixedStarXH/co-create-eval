# 后端服务基础

本模块使用 FastAPI、SQLModel 和 Alembic。当前提供健康检查、版本化任务、参与者凭证登录、演示版知情同意和两场任务分配；创作保存、真实 AI 与教师评分尚未实现。

## 本地运行

在 `backend` 目录下，使用 Python 3.11 或更新版本建立虚拟环境并安装锁定依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

默认数据库位于 `backend/data/app.sqlite3`，不会提交至仓库。可通过环境变量 `DATABASE_URL` 指定 SQLite 数据库地址；迁移和服务必须使用同一地址。

- `GET /api/v1/health`：进程存活。
- `GET /api/v1/ready`：数据库可连接且迁移版本符合预期；未迁移时返回 503。
- `/docs`：FastAPI 接口文档。

运行测试：`.\.venv\Scripts\python.exe -m pytest`。测试使用临时数据库，不访问本地开发数据。后续数据表应通过 Alembic 新增迁移，不应改写已应用的迁移文件。

## 创建本地演示参与者

迁移完成后，在 `backend` 目录运行以下命令，按提示输入至少 8 位的访问凭证。凭证不会保存在命令行历史，数据库只保存摘要：

```powershell
$env:APP_MODE = 'demo'
.\.venv\Scripts\python.exe -m app.provision --code DEMO001 --sequence S1
```

支持 S1—S4，创建时固定分配两场任务。此工具只用于本地演示：任务版本为 `demo-1`，同意说明版本为 `demo-1`，正式采集前仍需正式的配置、同意文本与管理功能。重复编号不会覆盖已有记录。

参与者登录使用 `POST /api/v1/auth/participant-login`；同意说明后可通过 `GET /api/v1/participant/sessions` 读取本人分配。服务端使用 HttpOnly 会话 Cookie、CSRF 校验和来源校验。生产环境须配置 HTTPS、`COOKIE_SECURE=true` 与实际 `FRONTEND_ORIGINS`，并在真实部署前完善账号管理和持久化限流。
