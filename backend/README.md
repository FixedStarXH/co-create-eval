# 后端服务基础

本模块使用 FastAPI、SQLModel 和 Alembic。当前提供服务健康检查、数据库就绪检查及任务版本表的第一版迁移；参与者身份、业务流程、AI 与评分接口尚未实现。

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
