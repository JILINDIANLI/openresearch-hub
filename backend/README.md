# OpenResearch Hub Backend V10

模块化 FastAPI 后端，默认使用本地 SQLite，设置 `DATABASE_URL` 后可切换 PostgreSQL。

## 本地启动

```powershell
cd D:\huggingface_hub-main\atlas-platform
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开 `http://127.0.0.1:8000/docs` 查看 Swagger。

首次启动会自动创建数据库并写入演示用户、模型、数据集、算法、项目、论文、Demo 和教程。

Docker Desktop 可用时，在项目根目录执行 `docker compose up --build`，会启动 PostgreSQL、Redis、MinIO 和后端。Docker 后端启动时会自动执行 `alembic upgrade head`。

已有的 V1-V5 数据库如果是在 Alembic 接入之前创建的，需要只执行一次：

```powershell
docker compose exec -T backend sh -c "cd backend && alembic stamp 0005_engagement_trending_v1"
docker compose exec -T backend sh -c "cd backend && alembic upgrade head"
```

升级 V10 后，执行 `alembic upgrade head`，当前迁移版本为 `0010_research_showcase_v1`。

## 核心接口

- `POST /api/users/register`
- `POST /api/users/login`
- `GET /api/users/{id}`
- `GET /api/resources?type=model`
- `GET /api/resources/{id}`
- `POST /api/resources`
- `PUT /api/resources/{id}`
- `DELETE /api/resources/{id}`
- `GET /api/search?q=transformer`
- `GET /api/search?q=transf&type=MODEL&framework=PyTorch&sort=stars&page=1&page_size=20`
- `GET /api/search/suggestions?q=trans`
- `GET /api/search/trending`
- `GET /api/tags`
- `GET /api/resources/stats`
- `GET /api/health`
- `POST /api/resources/{id}/repository`
- `GET /api/resources/{id}/repository`
- `DELETE /api/resources/{id}/repository`
- `POST /api/resources/{id}/repository/sync`
- `GET /api/resources/{id}/repository/commits`
- `GET /api/resources/{id}/repository/branches`
- `GET /api/resources/{id}/repository/tree?path=`
- `GET /api/resources/{id}/repository/file?path=README.md`
- `POST /api/resources/{id}/versions`
- `GET /api/resources/{id}/versions`
- `GET /api/resources/{id}/versions/latest`
- `GET /api/resources/{id}/versions/compare?from=1.0.0&to=1.1.0`
- `GET /api/resources/{id}/versions/{version}`
- `PATCH /api/resources/{id}/versions/{version}`
- `DELETE /api/resources/{id}/versions/{version}`
- `POST /api/resources/{id}/versions/{version}/publish`
- `POST /api/resources/{id}/versions/{version}/archive`
- `POST /api/resources/{id}/versions/{version}/files`
- `GET /api/resources/{id}/versions/{version}/files`
- `POST /api/resources/{id}/discussions`
- `GET /api/resources/{id}/discussions`
- `GET /api/discussions/{id}`
- `PATCH /api/discussions/{id}`
- `POST /api/discussions/{id}/close|reopen|lock|unlock`
- `POST|DELETE /api/discussions/{id}/pin`
- `POST /api/discussions/{id}/comments`
- `PATCH|DELETE /api/comments/{id}`
- `POST /api/resources/{id}/issues`
- `GET /api/resources/{id}/issues`
- `GET|PATCH /api/issues/{id}`
- `POST /api/issues/{id}/comments`
- `PATCH|DELETE /api/issue-comments/{id}`
- `POST|DELETE /api/users/{username}/follow`
- `GET /api/users/{username}/followers|following|follow-state`
- `GET /api/notifications`
- `GET /api/notifications/unread-count`
- `POST /api/notifications/{id}/read`
- `POST /api/notifications/read-all`
- `POST /api/resources/{id}/showcase`
- `GET|PATCH|DELETE /api/resources/{id}/showcase`
- `POST|GET /api/showcases/{showcase_id}/media`
- `DELETE /api/showcases/media/{media_id}`
- `POST|GET /api/showcases/{showcase_id}/results`
- `DELETE /api/showcase/results/{result_id}`

## V6 Search & Discovery

- 搜索标题、简介、标签、作者、模型框架/任务、论文、项目和算法字段。
- 支持不区分大小写的部分关键词、资源类型、标签（可多选）、研究方向、框架、许可证、作者和论文年份筛选。
- 支持相关度、最新、最早、Stars、下载量、浏览量和 Trending 排序。
- 结果返回分页、资源类型计数和筛选 Facets；`page_size` 最大生效值为 100。
- PostgreSQL 使用 `pg_trgm` GIN 索引加速部分关键词匹配；真实结果始终来自 PostgreSQL。
- 搜索日志只存关键词、可选用户 ID、结果数和时间，不存 IP、JWT 或其他敏感信息。

搜索页面位于 `http://127.0.0.1:8000/search`，首页 `Ctrl+K` 使用真实的搜索建议接口。

## Verification

```powershell
python backend/tests/search_v6_smoke.py
python backend/tests/regression_v5_v6.py
python backend/tests/repository_v7_smoke.py
python backend/tests/versioning_v8_smoke.py
python backend/tests/versioning_v8_persistence.py
python backend/tests/community_v9_smoke.py
python backend/tests/community_v9_persistence.py
python backend/tests/showcase_v10_smoke.py
python backend/tests/showcase_v10_persistence.py
```

第一条检查 V6 搜索接口；第二条创建并自动删除一个临时资源，覆盖 V5 的身份、发布、互动、文件、MinIO 和活动链路。

第三条会创建临时 User A/User B、真实 Gitea 仓库和私有仓库，验证作者权限、未登录 401、非作者 403、私有仓库 404、README、文件树、文件内容、Commit、Branch、同步、Redis 缓存以及本机 `git clone`，最后自动删除临时资源和仓库。

第四条会创建临时用户、资源、Gitea 仓库和两个正式版本，验证 SemVer 排序、草稿编辑限制、发布与归档、最新版本切换、版本文件上传及下载统计、Git 分支和 Commit 校验、版本对比、Redis 缓存失效，以及私有资源详情和活动记录的访问隔离；测试结束会自动清理临时资源与仓库。

第五条会创建并发布一个临时版本，重启 Docker 后端容器，确认版本和最新版本查询仍从 PostgreSQL 正确恢复，最后自动清理测试数据。

第六条创建临时 User A/B/C 与资源，覆盖 Discussion、评论权限、锁定、置顶、Issue 创建和管理、Issue 评论、关注去重、防止关注自己、通知未读数与已读操作；测试资源会自动清理。

第七条创建临时社区内容和关注关系，重启 Docker 后端容器，确认 Discussion、Issue、Follow 与 Notification 仍可读取，最后自动清理测试资源。

## Gitea

Docker Compose 会启动 Gitea：`http://127.0.0.1:3000`，SSH 端口为 `2222`，数据保存在 `openresearch-gitea` 卷中。后端通过 `.env` 中的系统服务账号 Token 调用 Gitea API；OpenResearch 用户密码不会同步到 Gitea。`.env` 已被 `.gitignore` 忽略，Token 不应提交到 Git。

Repository 的统计信息在 Redis 中缓存 5 分钟，Gitea 仍是代码仓库信息的最终来源；点击资源详情页的 `Code` 标签可以查看 README、文件树、代码文件、最近提交、分支和 HTTPS/SSH Clone 地址。

## V8 Resource Versioning

每个 Resource 可以拥有多个正式的语义化版本，例如 `1.0.0`、`1.1.0` 和 `2.0.0`。创建时均为 `DRAFT`；只有作者能编辑 Draft、上传版本文件、发布、归档和删除 Draft。公开资源的访客只能查看已发布或归档版本，私有资源则仅作者可见。

- 发布一个版本会自动撤销旧版本的 `is_latest`，并将新版本标记为最新版本。
- 归档最新版本时，系统按 SemVer 自动选择最高的其他已发布版本作为最新版本。
- 版本可选绑定 Gitea 的 branch 和 commit；关联仓库时，发布前会验证两者确实存在。
- 版本文件保存在 MinIO：`resources/{resource_id}/versions/{version}/{uuid}/{filename}`。下载会同时累计文件、资源和版本的下载次数。
- 公开版本列表及最新版本结果会在 Redis 缓存 5 分钟；创建、修改、发布、归档、删除、上传和下载后会清除对应缓存。
- 资源详情页有 `Versions` 标签；点击版本可进入 `/resources/{id}/versions/{version}`，查看发布说明、Git 绑定、版本文件和下载量。作者可在该页继续完成 Draft 的编辑、上传、发布、归档或删除。

## V9 Community & Collaboration

V9 新增 Discussion、带一层回复的软删除评论、Issue、用户关注与站内通知。Discussion 和 Issue 都沿用 Resource 可见性：私有资源的社区内容不会被非作者读取或创建。Discussion 作者可编辑和关闭自己的讨论；资源作者可置顶、锁定及重开讨论，并管理 Issue 状态、优先级和负责人。V1 的 Issue 负责人仅支持资源作者。

通知使用 PostgreSQL 持久化，未读数、关注数和匿名访问的 Discussion 列表使用短期 Redis 缓存。`COMMUNITY_CACHE_TTL`、`DISCUSSION_RATE_LIMIT`、`ISSUE_RATE_LIMIT`、`COMMENT_RATE_LIMIT` 与 `COMMUNITY_RATE_LIMIT_WINDOW_SECONDS` 都可在 `.env` 调整。前端资源详情页新增 Discussions 与 Issues 标签；用户主页显示关注数据，导航栏有通知铃铛及未读角标。

## V10 Research Showcase

每个资源最多拥有一个 Showcase，用于将研究背景、方法、创新点、实验设置、结果表、图片、视频、PDF 和引用信息组织成可公开浏览的科研成果页面。公开资源的 Showcase 可匿名查看；私有资源沿用资源可见性，只有作者可以创建、修改、删除和管理媒体或结果表。

- 页面入口：`http://127.0.0.1:8000/resources/{id}/showcase`。
- 展示媒体复用 MinIO 和 ResourceFile：`resources/{resource_id}/{uuid}/{filename}`，删除展示媒体时同时删除 MinIO 对象和对应文件记录。
- 详情与媒体列表使用 Redis 缓存五分钟；修改 Showcase、媒体或结果表会主动清理缓存。
- Markdown 在浏览器端先进行 HTML 转义，只解析标题、列表、代码块、行内代码与 `http(s)` 链接，原始 HTML 不会插入页面。
- Citation 同时支持纯文本和 BibTeX；展示页内置复制 BibTeX 按钮。
- 搜索与首页资源响应新增 `has_showcase`，前端以 Research Showcase / Featured Research 标识展示。
