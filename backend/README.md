# 后端服务基础

本模块使用 FastAPI、SQLModel 和 Alembic。当前提供健康检查、参与者凭证登录、演示版同意、任务分配、服务端阶段计时、构思和作品草稿、初稿与终稿快照；真实 AI、问卷和教师评分尚未实现。

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

已登录的参与者可通过 `/api/v1/sessions/{id}/start` 启动首场，使用 `/progress` 读取服务端时间及草稿，通过 `/idea-draft`、`/initial`、`/draft`、`/submit` 保存和提交。草稿携带修订号，旧修订号返回 409。构思提前提交后等待阶段截止，作品截止后提供 30 秒传输宽限；阶段过期会在下次请求时推进，当前尚无独立后台定时任务。服务端清理作品富文本中的不安全标签。第二场须在第一场终稿提交后才能启动。

## AI 适配层（开发中）

已添加兼容 chat-completions 消息格式的服务端适配层。配置使用环境变量 `AI_CHAT_ENDPOINT`（服务商的完整 HTTPS 对话接口地址）、`AI_CHAT_MODEL`、`AI_API_KEY` 和可选的 `AI_TIMEOUT_SECONDS`（1—120 秒，默认 30）。密钥仅供后端读取，不要提交至仓库。适配层测试使用模拟传输，不产生实际模型调用。

该适配层尚未连接任何 HTTP 接口或前端，也未完成对话存储、场次权限控制和真实服务商联调；当前页面的 AI 内容仍是示例。配置变量本身不会开启 AI 功能。
