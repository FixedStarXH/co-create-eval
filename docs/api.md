# API 接口与业务状态规则

版本：V1.0（2026-11-02）  
状态：实施合同草案；编码时以生成的 OpenAPI 文档核对  
上位需求：[requirements.md](requirements.md)；数据字段：[data-model.md](data-model.md)

## 1. 协议与通用约定

- 前缀 `/api/v1`。普通响应为 JSON；导出 ZIP 和打印页例外。时间使用 ISO 8601 UTC 字符串，如 `2026-11-02T08:30:00Z`。
- 浏览器使用同源、`HttpOnly`、`SameSite=Lax` 的会话 Cookie；写接口携带服务端下发的 CSRF token。前端仅持有 token，不持有用户密码或模型密钥。研究模式应通过 HTTPS 或受控局域网访问。
- 每个响应带 `request_id`，错误结构为 `{ "error": { "code": "...", "message": "...", "details": {} }, "request_id": "..." }`。错误文案面向用户，调试细节只进服务端日志。
- 普通成功结构为 `{ "data": ..., "request_id": "..." }`。分页列表另带 `page`、`page_size`、`total`。涉及等待模型的接口可返回 `202 Accepted` 与请求状态地址。
- 修改型 `POST` 请求提供 `Idempotency-Key`；服务端按“操作者 + 路径 + 会话 + 键”去重。草稿 `PUT` 使用修订号乐观锁，不用幂等键替代冲突检查。
- 所有接口先鉴权、再校验对象归属和状态。对无权访问的会话不暴露其存在；教师接口只使用匿名作品码和专用响应 DTO。

## 2. 角色与状态矩阵

| 动作 | 参与者 | 教师 | 管理员 | 状态条件 |
| --- | --- | --- | --- | --- |
| 查看本人任务、草稿、报告 | 本人 | 否 | 管理视图 | 对应批次有效 |
| 保存初始构思 | 本人 | 否 | 否 | IDEATION 且截止前/统一收尾窗口 |
| 保存五字段作品 | 本人 | 否 | 否 | DEVELOPMENT 且截止前/统一收尾窗口 |
| 调用创作 AI | 本人 | 否 | 只测配置 | AI 条件、DEVELOPMENT、未超轮次 |
| 建议采纳或忽略 | 本人 | 否 | 否 | AI 条件、DEVELOPMENT、消息属本场 |
| 提交终稿 | 本人 | 否 | 只记录异常，不代提交 | DEVELOPMENT，草稿保存成功 |
| 查看匿名终稿 | 否 | 已分配作品 | 管理视图 | 有 FINAL 版本 |
| 提交正式教师评分 | 否 | 已分配作品 | 否 | 本人评分未提交，终稿存在 |
| 导出匿名数据 | 否 | 否 | 是 | 批次与权限有效 |

教师响应不得出现 `participant_id`、`study_code`、`condition`、`sequence`、`chat_message`、`ai_assessment` 或其他教师评分；必须用接口测试验证字段集合。

## 3. 接口清单

### 3.1 身份和当前用户

| 方法与路径 | 角色 | 请求重点 | 响应与关键校验 |
| --- | --- | --- | --- |
| `POST /auth/participant-login` | 未登录 | `study_code, credential` | 设置 Cookie；返回同意状态与本人场次摘要；凭证错误统一提示 |
| `POST /auth/staff-login` | 未登录 | `username, password` | 设置教师/管理员 Cookie；失败限速 |
| `POST /auth/logout` | 已登录 | 无 | 撤销服务端会话、清 Cookie；幂等 |
| `GET /auth/me` | 已登录 | 无 | 返回角色、显示名、CSRF token；不返回密码摘要 |
| `POST /participant/consent` | 参与者 | `consent_version, agreed=true` | 保存服务端时间；版本与当前批次一致；重复请求返回原同意记录 |

### 3.2 参与者任务与阶段

| 方法与路径 | 角色 | 请求重点 | 响应与关键校验 |
| --- | --- | --- | --- |
| `GET /participant/sessions` | 参与者 | 无 | 返回本人两场的任务代码、次序、状态和可进入链接；不提前显示第二场详细题干 |
| `GET /sessions/{id}` | 本人 | 无 | 返回任务版本、条件、状态、服务端时间、阶段截止时间、可执行动作 |
| `POST /sessions/{id}/start` | 本人 | 幂等键 | 从 CREATED 进入 IDEATION，固定开始与截止时间；第二场须在第一场完成后 |
| `PUT /sessions/{id}/idea-draft` | 本人 | 三个想法字段、`expected_revision` | 保存未锁定草稿，返回新修订号与时间；冲突为 409 |
| `POST /sessions/{id}/initial` | 本人 | 幂等键、`expected_revision` | 锁定 INITIAL 快照；早交可进入等待状态，5 分钟截止后进入 DEVELOPMENT |
| `GET /sessions/{id}/draft` | 本人 | 无 | 返回五字段、修订号、最后成功保存时间；只返回本人数据 |
| `PUT /sessions/{id}/draft` | 本人 | `sections`, `expected_revision` | 成功递增修订号；旧号返回 409 和服务器稿摘要，不静默覆盖 |
| `GET /sessions/{id}/versions` | 本人 | 分页 | 返回初始/过程/终稿的只读元数据及内容；终稿前不返回不存在版本 |
| `POST /sessions/{id}/versions` | 本人 | `expected_revision, reason` | 保存过程关键快照；不得伪造 INITIAL/FINAL |
| `POST /sessions/{id}/submit` | 本人 | 幂等键、`expected_revision` | 在同一事务生成 FINAL、锁稿、返回报告链接；重复提交返回同一版本 |
| `GET /sessions/{id}/questionnaire` | 本人 | 无 | 返回批次问卷与条件适用题项 |
| `PUT /sessions/{id}/survey` | 本人 | 逐题值与问卷版本 | 保存草稿；只接收本条件题项且值为 1—5 |
| `POST /sessions/{id}/survey/submit` | 本人 | 幂等键 | 完整校验后锁定问卷；不改变终稿 |
| `GET /sessions/{id}/report` | 本人 | 无 | 返回分层报告、评价状态、证据与时间线；缺失为 `null + status` |

### 3.3 AI 对话与评分

| 方法与路径 | 角色 | 请求重点 | 响应与关键校验 |
| --- | --- | --- | --- |
| `POST /sessions/{id}/chat` | 本人 | `client_request_id, message` | AI 条件且 DEVELOPMENT；保存 USER 消息后调用模型；返回 `request_id/status`，不直接插入作品 |
| `GET /sessions/{id}/chat` | 本人 | 分页 | 返回本场消息和请求状态；独立条件返回空列表但不可发起调用 |
| `GET /sessions/{id}/chat-requests/{requestId}` | 本人 | 无 | 查询等待/成功/超时/失败；重复请求号得到原结果 |
| `POST /sessions/{id}/suggestion-actions` | 本人 | `assistant_message_id, action, target_section, inserted_text, expected_revision` | 验证消息归属；采纳时原子写入动作与新草稿修订号；忽略不改草稿 |
| `GET /sessions/{id}/ai-assessment` | 本人 | 无 | 只读最新有效辅助评价或失败/待生成状态；教师接口不提供此路由 |
| `POST /admin/sessions/{id}/ai-assessment/retry` | 管理员 | 幂等键、原因 | 只对已有 FINAL 的失败尝试重试；保留旧尝试与审计 |

### 3.4 教师评分与研究管理

| 方法与路径 | 角色 | 请求重点 | 响应与关键校验 |
| --- | --- | --- | --- |
| `GET /teacher/works` | 教师 | `status,page` | 只列已分配匿名作品；每人顺序随机化且稳定 |
| `GET /teacher/works/{workCode}` | 教师 | 无 | 只返回匿名终稿、任务版本、量规和本人评分草稿 |
| `PUT /teacher/works/{workCode}/rating-draft` | 教师 | 三维分数与评语，可不完整 | 暂存本人草稿；不影响报告 |
| `POST /teacher/works/{workCode}/rating-submit` | 教师 | 幂等键、三维分数、优点、改进意见 | 校验 1—5、非空评语；正式提交锁定；重复返回原评分 |
| `POST /teacher/works/{workCode}/invalid-review` | 教师 | 原因 | 标记待复核，不填 0 分 |
| `GET /admin/batches`、`POST /admin/batches` | 管理员 | 批次配置 | 创建/查看演示或研究批次；正式批次校验 AI 配置 |
| `POST /admin/batches/{id}/freeze` | 管理员 | 幂等键 | 检查 A/B、量规、问卷、提示词、模型配置后冻结 |
| `POST /admin/participants` | 管理员 | 研究编号或数量 | 发放编号、凭证与 S1—S4；明文凭证仅首次显示一次 |
| `GET /admin/progress` | 管理员 | 批次、筛选 | 完成/缺失/失败列表；可按会话展开原始状态 |
| `GET /admin/export-preview` | 管理员 | 批次 | 显示将导出的文件、字段、记录数与排除项 |
| `POST /admin/exports` | 管理员 | 批次、导出原因、幂等键 | 生成匿名 ZIP、manifest 与审计；默认只允许研究模式 |
| `GET /admin/exports/{id}/download` | 管理员 | 无 | 有效期内下载本人/管理员授权导出文件 |

任务、量规、提示词和问卷的创建、发布接口由管理员模块按资源分别提供；若第一版只需固定两题，也须保留版本化配置的读写和冻结能力，不以修改源代码替代正式研究配置。

## 4. 核心请求示例

### 4.1 草稿保存与修订冲突

```http
PUT /api/v1/sessions/6e.../draft
X-CSRF-Token: <from-auth-me>
Content-Type: application/json

{
  "expected_revision": 7,
  "sections": {
    "goal": "学生能指出待核验说法……",
    "student_task": "小组核验资料……",
    "flow": "5 分钟引入；20 分钟核验……",
    "resources": "任务单与公开资料……",
    "evaluation": "依据核验卡与反思卡……"
  }
}
```

成功：`200`，返回 `revision_no: 8`、`saved_at`。冲突：`409 REVISION_CONFLICT`，响应包含服务器修订号和服务器稿摘要；前端保留本地文本并提供比较/重试，不自动覆盖。正式内容格式若允许富文本，则字段值为经服务端约束的结构化文档或安全 HTML，不能接受任意脚本标签。

### 4.2 AI 请求与建议处理

```json
{
  "client_request_id": "3a91e4b8-2edb-41f5-b33b-3bc7fa83270b",
  "message": "怎样让学生提出可核验的问题，而不是只听教师讲解？"
}
```

成功请求返回 `202` 与 `request_id`、`status=PENDING`；完成后 `chat-requests/{requestId}` 返回模型回复与版本。建议动作需携带该回复的 `assistant_message_id`、动作、目标章节和用户确认的文字；后端在同一事务更新草稿与动作日志。`IGNORE` 不要求目标章节，也不修改作品。

### 4.3 评分提交

```json
{
  "novelty": 4,
  "fit": 5,
  "feasibility": 3,
  "strength": "学生确实需要比较来源并修订资料。",
  "improvement": "应补充每组核验材料的数量与汇报时间。"
}
```

提交后返回匿名作品码、三维原始评分、`submitted_at`；该教师再次提交同一幂等键返回原记录，用不同键重复提交返回 `409 RATING_LOCKED`。

## 5. 状态迁移和超时规则

| 当前状态 | 触发 | 下一状态 | 服务端动作 |
| --- | --- | --- | --- |
| CREATED | 本人开始且已同意 | IDEATION | 写入开始/截止时间与审计 |
| IDEATION | 早交初始稿 | IDEATION（已交标志） | 锁定 INITIAL；到 5 分钟截止前仅显示等待，不开放 AI |
| IDEATION | 5 分钟截止 | DEVELOPMENT | 未早交则以最后成功保存的构思生成 INITIAL；若内容缺失，标记缺失，不编造；写入新的 20 分钟窗口 |
| DEVELOPMENT | 本人提前提交终稿 | SUBMITTED | 强制保存成功后生成 FINAL；锁定编辑；安排 AI 辅助评价 |
| DEVELOPMENT | 20 分钟截止 | SUBMITTED 或 EXPIRED | 统一收尾窗口内接受最后一次保存；有有效草稿则生成 FINAL，否则标记 EXPIRED 与缺稿原因 |
| SUBMITTED | 两名教师正式评分完成 | RATED | 计算派生均分与分歧标记，保留原始评分 |
| 任意可退出状态 | 参与者退出研究 | WITHDRAWN | 依学校要求删除或排除，写审计 |

**统一收尾窗口：**建议在截止后保留 30 秒，仅用于传输已编辑内容和处理网络延迟；前端立即停止输入，后端记录是否在窗口内到达。试测后可调整，但正式研究前必须冻结该值，两条件相同。阶段服务在每次读写时执行到期检查，并由后台定时任务补齐长时间不访问的会话状态；二者调用同一状态机。AI 回复若在截止后才完成，保留请求与回复记录，但不再允许将其采纳到锁定作品。

## 6. 错误码与前端处理

| HTTP / 代码 | 场景 | 前端处理 |
| --- | --- | --- |
| `400 VALIDATION_ERROR` | 字段、题项、分数格式不合规 | 在对应字段显示原因，保留输入 |
| `401 AUTH_REQUIRED` | 未登录或会话过期 | 提示重新登录，保留本地未提交文本 |
| `403 ROLE_FORBIDDEN` | 角色或条件不允许 | 返回无权操作，不展示受限数据 |
| `404 NOT_FOUND` | 不存在或无权访问的对象 | 统一“未找到或无权查看”，避免探测编号 |
| `409 REVISION_CONFLICT` | 旧修订号保存 | 显示服务器稿与本地稿选择，不静默覆盖 |
| `409 STAGE_CLOSED` | 阶段已结束 | 重新读取会话状态，保留本地未传输文本供异常记录 |
| `409 ALREADY_SUBMITTED` | 终稿或评分已锁定 | 跳转到只读结果，不重复生成记录 |
| `429 AI_LIMIT_REACHED` | 模型轮次或频率超限 | 显示剩余限制，不影响编辑 |
| `502/504 AI_UNAVAILABLE` | 模型出错或超时 | 对话区提示失败与重试；草稿不回滚；管理员见错误码 |
| `503 STUDY_NOT_READY` | 研究模式配置不完整 | 阻断正式批次启动，告知管理员缺项 |

## 7. 接口验收门槛

通过 OpenAPI 自动生成接口说明，并用测试逐条验证：401/403/404 隔离、四序列分配、5+20 分钟状态、草稿 409 冲突、AI 独立场禁止、对话幂等、终稿幂等、教师互盲、评分锁定、报告来源和匿名导出。测试数据库使用独立内存或临时库，不连接研究库；SQLModel 官方测试示例可参考 [SQLModel 测试指南](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/)。
