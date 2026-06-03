# WanderMeet 同城动态（V0.5 / V1 / V2）

更新时间：2026-05-26  
对标语境：NomadTable 类「同城状态 / 广场」；本版为旅聚 MVP 三阶段交付说明。

---

## 1. 阶段定义

| 阶段 | 范围 | 说明 |
|------|------|------|
| **V0.5 活动态** | 活动参与者、开始后至结束 72h 内 | 图文动态挂在活动下，不进入全城广场 |
| **V1 同城广场** | 同城公开流 | 列表、发布、点赞、评论、图片上传、举报 |
| **V2 关系与话题** | 关注流 + 话题 + 个人主页动态 | `scope=following`、预设话题、`GET /users/{id}/posts` |
| **再议（未做）** | 视频、@、转发、算法推荐、仅好友圈 | 产品后续单独立项 |

### 1.1 动态位置（2026-05-26 结论）

| 决策点 | 结论 |
|--------|------|
| 是否必填 | **可选**（A）：发布页可添加/清除位置，不带位置也可发 |
| 坐标存储 | **存 lat/lng**（B）：GCJ-02；有坐标时必须同时有 `locationName`；仅文字位置名也允许（无坐标时仅展示文案） |
| 覆盖范围 | **同城广场 + 活动态** 均支持；活动详情「发一条」预填活动地点，用户可改 |

交互：发布页选点 → `location-picker?from=feed`；列表/详情卡片展示位置；有坐标时点击打开地图（`uni.openLocation`）。V1 **不做**按距离筛流（坐标已落库供后续）。

---

## 2. 后端实现状态（`wander_meet`）

迁移：`alembic/versions/20260525_0023_city_feed.py`（`posts`、`post_likes`、`post_comments`、`user_follows`）；`20260526_0024_post_lat_lng.py`（动态可选坐标）。

| 能力 | API | 状态 |
|------|-----|------|
| 话题元数据 | `GET /feed/topics` | ✅ |
| 同城列表 | `GET /feed?cityCode&scope=city&topic&page` | ✅ |
| 关注列表 | `GET /feed?scope=following` | ✅ |
| 发布同城动态 | `POST /feed/posts` | ✅ |
| 动态可选位置 | `locationName` + `lat`/`lng`（可选；有坐标须有名） | ✅ |
| 动态详情 | `GET /feed/posts/{id}` | ✅ |
| 删除自己的动态 | `DELETE /me/feed/posts/{id}` | ✅（接口有，小程序未接删除入口） |
| 点赞 | `POST /feed/posts/{id}/like` | ✅ |
| 评论列表/发表 | `GET/POST /feed/posts/{id}/comments` | ✅ |
| 动态图片上传 | `POST /me/feed/images`（BOS `wm/feed/`） | ✅ |
| 活动态列表/发布 | `GET/POST /activities/{id}/posts` | ✅ |
| 关注/取关/状态 | `POST/DELETE/GET /users/{id}/follow` | ✅ |
| 用户动态列表 | `GET /users/{id}/posts` | ✅ |
| 举报动态 | 复用 `POST /reports`，`targetType=post`，`targetId=post_{id}` | ✅ |
| 内容审核后台 | 动态专审队列 | ❌ 再议（目前仅用户举报 + 管理端举报处理） |
| 视频 / @ / 转发 | — | ❌ 再议 |

业务规则（已实现，见 `app/services/feed.py`）：

- 活动态：须 `joined` 报名；非城市大群活动；取消活动不可发；时间窗为**开始后**至结束 +72h（无 `end_at` 则从 start 起 72h）。
- 同城：须 `cityCode`；每日发帖上限；联系方式过滤；拉黑用户内容对 viewer 不可见。
- **位置（可选）**：发布时可附带 POI 名称 + GCJ-02 坐标；列表/详情展示；有坐标可点开地图。同城列表仍按 `cityCode` 聚合（V1 不做按距离筛流）。
- 活动态：发布接口同样支持 `locationName`/`lat`/`lng`；从活动详情进入发布页时**预填活动地点**（可改、可清除）。
- 图片：须为本服务 BOS 已存 URL（`validate_stored_feed_image_url`）。

部署：新环境需 `alembic upgrade head`（含 `0022` 增长信任 + `0023` feed + `0024` 动态坐标）。

---

## 3. 小程序实现状态（`lv_ju/travel-together`）

| 能力 | 路径 / 模块 | 状态 |
|------|-------------|------|
| API + Mock | `src/api/wandermeet.js`、`src/mock/feed-mock.js` | ✅ |
| 图片上传 | `src/api/feedImageUpload.js` | ✅ |
| 动态卡片 | `src/components/FeedPostCard/FeedPostCard.vue` | ✅ |
| 同城列表（同城/关注 Tab） | `src/pages/feed/feed.vue` | ✅ |
| 发布（同城 / 活动态） | `src/pages/feed-publish/feed-publish.vue` | ✅ |
| 发布选位置 | 复用 `location-picker?from=feed` | ✅ |
| 动态卡片/详情展示位置 | `FeedPostCard`、点开地图 | ✅ |
| 详情 + 评论 + 举报 | `src/pages/feed-detail/feed-detail.vue` | ✅ |
| 发现页入口 | `src/pages/discover/discover.vue` | ✅ |
| 活动详情 · 活动动态区 | `src/pages/activity-detail/activity-detail.vue` | ✅ |
| 用户资料 · 关注 + Ta 的动态 | `src/pages/user-public/user-public.vue` | ✅ |
| 路由注册 | `src/pages.json` | ✅ |
| 城市大群页入口 | `city-hall` | ❌ 未单独加（可从发现页进同城动态） |
| 删除自己的动态 | — | ❌ 未接 UI |
| 话题筛选 UI | 列表页按 topic 筛选 | ❌ 未做（后端与发布页话题已支持） |
| 按距离筛同城动态 / 附近流 | — | ❌ 再议（已存 lat/lng 供后续） |
| 视频 / @ / 转发 | — | ❌ 再议 |

Mock：存储键逻辑与其它模块一致；`getUserFeedPosts` Mock 已按 `userId` 过滤。

---

## 4. 联调检查清单

1. 登录后 Storage 有 `wm_access_token` / `wm_refresh_token`。
2. 发布同城动态：选图 → `POST /me/feed/images` → 可选选位置 → `POST /feed/posts`（含 `locationName`/`lat`/`lng`）。
3. 活动态：已报名活动 → 活动详情「发一条」→ 默认带活动地点 → `POST /activities/{id}/posts`（注意时间窗）。
4. 关注：用户资料页关注 → 同城动态 Tab「关注」有内容。
5. 举报：动态详情「举报」→ `POST /reports`，`targetType=post`。
6. 生产：确认 BOS 配置与 `wm/feed/` 前缀可访问。

---

## 5. 相关文档

- 后端总待办：`doc/TODO_Backend_NextSteps.md` §8 同城动态
- 裂变与信任（独立模块）：`doc/PRD_WanderMeet_裂变与信任_v1.md`
- 照片验证审核：`doc/WanderMeet_照片验证审核.md`
