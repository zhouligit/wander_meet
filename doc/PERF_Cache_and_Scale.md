# WanderMeet 性能与缓存

更新时间：2026-05-21（P2 已落地，读写分离/压测除外）  
适用范围：FastAPI + MySQL + Redis 后端

---

## 1. 已实现

| 项 | 说明 | 配置 / 代码 |
|----|------|-------------|
| **活动同城列表短缓存** | `GET /activities`，Redis JSON，默认 **60s**；写操作按 `city_code` 删 key | `CACHE_ACTIVITY_LIST_*`，`app/services/response_cache.py` |
| **活动附近短缓存** | `GET /activities/nearby`，坐标四舍五入到 3 位小数；同城写操作失效 | 同上 `response_cache.py` |
| **活动详情短缓存** | `GET /activities/{id}`，不含 `myEnrollment`；命中后仅补查报名状态 | 同上 |
| **群聊未读优化** | 普通活动：发消息 Redis `INCR`、已读 `SET 0`；城群：bounded COUNT（最多扫 100 行，展示 cap 99） | `app/services/chat_unread.py` |
| **元数据进程内缓存** | `GET /meta/activity-categories`、`/meta/onboarding`、`/meta/city-groups` | `@lru_cache`，`app/services/meta_cache.py` |
| **元数据 HTTP 缓存** | 上述静态 meta 响应头 `Cache-Control: public, max-age=…` | `META_HTTP_CACHE_MAX_AGE_SECONDS` |
| **鉴权用户行缓存** | `get_current_user` / `get_optional_user` 优先 Redis 用户快照 | `CACHE_USER_AUTH_*`，`app/services/user_cache.py` |
| **`GET /me`、`/me/stats`** | Redis 短缓存；`PATCH /me`、绑手机、封禁等失效 | `CACHE_ME_*` |
| **历史活动 `ended_at`** | 取消时写入；迁移回填；`timeScope=past` 按 `ended_at` 排序 | 迁移 `20260521_0019`，`app/services/activity_lifecycle.py` |
| **列表过滤索引** | `(activity_kind, activity_status, end_at, start_at)` | 迁移 `20260520_0018` |
| **既有** | 报名/消息/通知索引、`20260429_0004`；refresh/验证码/限流 Redis | 见 `alembic/versions/20260429_0004_add_perf_indexes.py` |

### 列表缓存说明

- 缓存内容**不含**登录用户的 `enrollmentStatus`；命中后若已登录，仅补查当前页活动的「是否已报名」。
- **失效**：创建活动、更新活动、取消活动、报名/取消报名后，对该活动 `city_code` 执行 `SCAN` 删除 `wm:cache:act:list:{city}:*`。
- 关闭：`.env` 中 `CACHE_ACTIVITY_LIST_ENABLED=false` 或 `CACHE_ACTIVITY_LIST_TTL_SECONDS=0`（同时关闭列表 / 附近 / 详情读缓存）。

### 未读数说明

- **普通活动**：`POST .../messages` 对成员 `INCR wm:unread:{userId}:{activityId}`；`PATCH /me/chats/{id}/read` 置 0；列表 `MGET`。
- **城群**：不发消息时全员 Redis 扩散（成员可达 20 万）；列表用 **最多 100 行** bounded COUNT，展示仍 cap **99**。
- **报名 >500 人的活动**：与城群相同，发消息不做 Redis 扩散，列表走 bounded COUNT。

### `ended_at` 说明

- **`end_at`**：计划结束时间（发布时填写）。
- **`ended_at`**：实际结束/取消时刻；取消活动时写入；历史数据由迁移回填。
- 自然到期（`published` 且 `end_at` 已过）仍由查询条件兼容；后续可加定时任务批量写 `ended_at`（当前未做）。

---

## 2. 待办

### 暂不实施（按产品决策）

- [ ] **读写分离**、**压测基线**（`wrk` / `locust`）。

### 运维 / 后续

- [ ] **定时任务**：`published` 过期活动批量写 `ended_at`、活动自动 `ended` 状态。
- [ ] **Redis** `maxmemory-policy` 与 key 监控（列表缓存 key 随城市×分页增长）。
- [ ] Nginx 层对 `/meta/*` 再叠加 CDN（应用已发 `Cache-Control`，可与边缘缓存叠加）。

---

## 3. 相关文档

- 城市大群与 `/me/chats` 性能：`doc/WanderMeet_城市大群_需求与接口规划.md` §9  
- 后端总待办：`doc/TODO_Backend_NextSteps.md` §7  
