# WanderMeet 活动图片（V0）

更新时间：2026-05-31  
对标语境：NomadTable 类活动封面/图集；本版 **仅图片、不接视频**。

---

## 1. 产品决策

| 决策点 | 结论 |
|--------|------|
| 数量上限 | 最多 **9 张**；**首张为封面** |
| 是否必填 | **非必填**；无图时沿用渐变头图 |
| 存储 | 百度 BOS `wm/activity/u_{userId}/`；发布时仅接受本服务已上传 URL |
| 审核 | 微信 `mediaCheckAsync`（scene=**论坛 3**）+ 服务端回调 |
| 审核状态 | `none` / `pending` / `pass` / `reject` |
| 公众可见 | **`pass` 前不展示图片**；活动文字、时间地点仍可见 |
| 发起人可见 | 真实 URL + `imagesAuditStatus`（含 pending/reject） |
| pending 超时 | **30 分钟**无回调 → 视为 `reject` |
| 编辑规则 | 与活动编辑一致：**进行中不可改图**；未开始可改 |
| 视频 | **不做**（后续单独立项） |

---

## 2. 后端实现（`wander_meet`）

迁移：`alembic/versions/20260531_0029_activity_images.py`

| 表/字段 | 说明 |
|---------|------|
| `activities.cover_image_url` | 封面 URL（首张） |
| `activities.images` | JSON 数组，顺序即展示顺序 |
| `activities.images_audit_status` | 见上 |
| `activities.images_audit_updated_at` | 审核状态变更时间 |
| `activity_media_audits` | 每次提交图集一条审核记录 + `trace_entries` |

| 能力 | API | 状态 |
|------|-----|------|
| 活动图片上传 | `POST /me/activity/images`（multipart） | ✅ |
| 发布带图 | `POST /activities` body `images: string[]` | ✅ |
| 编辑图集 | `PATCH /activities/{id}` body `images` | ✅ |
| 列表封面 | `GET /activities` card `coverImageUrl`（仅 pass） | ✅ |
| 详情图集 | `GET /activities/{id}` `coverImageUrl` / `images` / `imagesAuditStatus` | ✅ |
| 微信审核回调 | `POST /webhooks/wechat/media-check` | ✅ |

业务规则（`app/services/activity_images.py`）：

- URL 校验：`validate_stored_activity_image_url`，须为当前用户 `wm/activity/u_{id}/` 前缀。
- 提交后状态 `pending`，逐张调用 `media_check_async` 记录 `trace_id`。
- Mock / 未开内容安全 / 无 openid：本地 **自动 pass**。
- 回调 `suggest` 为 `risky`/`review` → `reject`；全部 `pass` → 活动可公开展示。
- 读详情/列表时若 pending 超时 → 自动 reject 并落库。

部署：新环境需 `alembic upgrade head`（含 `0029`）；微信后台配置 **消息推送** 指向 `…/api/v1/wm/webhooks/wechat/media-check`（与支付回调域名相同即可）。

环境变量：

- 复用 BOS 与 `wx_content_sec_enabled` / `wx_mp_*`。
- 可选 `BOS_ACTIVITY_IMAGE_MAX_BYTES`（默认 8MB，见 `app/core/config.py`）。

---

## 3. 小程序实现（`lv_ju/travel-together`）

| 能力 | 路径 / 模块 | 状态 |
|------|-------------|------|
| 图片上传 | `src/api/activityImageUpload.js` → `/me/activity/images` | ✅ |
| 发布/编辑选图 | `src/pages/publish/publish.vue` | ✅ |
| 详情轮播 | `src/pages/activity-detail/activity-detail.vue` | ✅ |
| 首页卡片封面 | `src/pages/home/home.vue` + `mapActivityCard` | ✅ |
| Mock | `wandermeet.js` create/update/detail | ✅ |

交互要点：

- 发布页：九宫格选图，首张标「封面」；编辑模式预填已有图；进行中编辑隐藏选图区。
- 详情：pass 后所有人可见轮播；发起人 pending 时可见图 + 「审核中」提示。
- 首页：列表卡片顶部展示 `coverImageUrl`（仅后端 pass 后下发）。

---

## 4. 自测清单

1. **上传**：登录 → 发布页选 1～9 张 → Network 见 `POST /me/activity/images` → 发布 body 含 BOS URL。
2. **公众不可见 pending**：用另一账号看详情/列表，pending 期间无图；发起人可见。
3. **pass 展示**：Mock 或真实回调后，列表/详情出现封面与轮播。
4. **编辑**：未开始可换图；开始后 PATCH `images` 应 400。
5. **清空**：PATCH `images: []` 恢复 `none`、无封面。
6. **仅 Mock**：`wm_use_mock=true` 时上传返回本地路径，create 后 mock 直接 pass。

---

## 5. 再议（未做）

- 视频、GIF、裁剪/压缩策略单独配置
- 人工复审后台、违规图替换占位图
- CDN 鉴权、私有桶 + 临时签名读
