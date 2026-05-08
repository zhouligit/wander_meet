# WanderMeet × nomadtable 初次引导 — 全量拆分清单

参考：`~/data/doc/创业/wandermeet`（nomadtable 截图）。本文不再合并步骤、不设优先级；**每一项均为独立页面或独立能力单元**，便于逐条落地与排期。

---

## 1. 全量拆分：独立单元一览

下列序号表示「可与 nomadtable 类似的独立一屏/一步」；WanderMeet 可删减或合并交互，但**需求拆解以每条为原子单位**。

| 序号 | 独立单元 | nomadtable 参考 | WanderMeet 现状 | 后端 | 小程序 |
|------|----------|-----------------|-------------------|------|--------|
| N01 | 欢迎与产品价值（标题/副文案） | 欢迎页顶部 | 登录页仅有「手机号登录」文案 | 不需要 | `login.vue` 可增强 |
| N02 | 实时社会证明（在线人数等） | 在线用户数条 | 无 | 可选统计接口 | 无 |
| N03 | 主登录方式（Apple） | Continue with Apple | 无（生态不同） | — | 不适用或后续扩展 |
| N04 | 次级登录/找回（Google / 手机历史账号） | 两枚次级按钮 | 仅短信；无「曾用手机登录」分支 | — | 无 |
| N05 | 跨平台账号冲突说明文案 | 红字错误引导 | 无 | — | 无 |
| N06 | 渠道归因「如何听说我们」 | 整页单选列表 | 无 | 可选埋点 / 表单项 | 无独立页 |
| N07 | 昵称（展示名）单独一页 | First name | 与性别等同页 `profile-edit` | `nickname` 已有 | 宜拆独立页 |
| N08 | 昵称不可更改声明 | 页内灰色说明 | 未承诺昵称永久不可改 | 可选 DB 约束或产品规则 | 文案 + 规则 |
| N09 | 母国/地区（资料国旗）单独一页 | Home country | `users` 无国家字段 | **需扩展** | **需新页** |
| N10 | 旅行身份多选（≤2）单独一页 | Traveler type 卡片 | 无 | **需扩展** 或映射 `tags` | **需新页** |
| N11 | 当前所在位置单独一页 | Where are you | 无用户级位置资料 | **需扩展** | **需新页**（可与城市合并） |
| N12 | 停留时长/意图单独一页 | 常住 / 具体日期 | 无 | **需扩展** | **需新页** |
| N13 | 个人简介单独一页（可跳过） | Bio + Skip | 与昵称同页；保存时有默认句 | `bio` 已有 | 宜拆页并真正 Skip |
| N14 | 兴趣：品类「美食饮品」单独一页 | food & drink chips | 无独立页；`tags` 未在编辑页维护 | `tags` 已有 | **需新页** |
| N15 | 兴趣：品类「夜生活娱乐」单独一页 | nightlife | 同上 | 同上 | **需新页** |
| N16 | 兴趣：品类「文化艺术」单独一页 | culture & arts | 同上 | 同上 | **需新页** |
| N17 | 兴趣：品类「户外探险」单独一页 | outdoor & adventure | 同上 | 同上 | **需新页** |
| N18 | 兴趣上限与「用于附近推荐」说明 | 副标题文案 | 无等价说明 | 校验 `PATCH /me` | 文案 |
| N19 | 头像上传单独一页（真人可见提示） | add profile photo | 仅首字母；无上传 | `avatarUrl` 已有；**OSS 链未完** | **需新页 + 上传** |
| N20 | 创建账户/完成引导 CTA 文案 | create your account | 仅「保存」进首页 | — | 文案与流程节点 |
| N21 | 通知偏好：全部/分类单独一页 | what activities interest you | 无 | **需扩展** 或仅本地 | **需新页** |
| N22 | 通知可变更提示（Settings） | 页脚灰字 | 无 | — | 文案 |
| N23 | 定位权限：价值说明单独一页（系统弹窗前） | connect with nearby | 无专门引导页 | — | **需新页** |
| N24 | 定位权限：三条利益点 + 隐私表述 | 列表 + shield | 无 | — | 与设计稿 |
| N25 | 隐私设置单独一页（例：展示距离 km） | privacy settings toggle | 无对应字段 | **需扩展** | **需新页** |
| N26 | 隐私可随时修改提示 | 页脚灰字 | 无 | — | 文案 |

说明：nomadtable 兴趣若有更多品类滚动，每新增一个品类即对应 **新增一行 N14… 类条目**；上表按截图拆至户外品类为止。

---

## 2. 后端字段拆分（与页面对齐）

每条字段独立评估，不全则标「缺」。

| 字段维度 | 用途 | 现状 |
|----------|------|------|
| `phone` / 登录 | 账号 | 有 |
| `nickname` | 展示名 | 有 |
| `gender` | 性别锁定策略 | 有 |
| `bio` | 简介 | 有 |
| `avatar_url` | 头像 URL | 有；直传 OSS 未就绪 |
| `tags` | 兴趣字符串列表 | 有；上限与 PATCH 已有 |
| 国家/地区码（示例：`country_code`） | N09 | **缺** |
| 旅行身份（示例：`traveler_roles` 或标签子集） | N10 | **缺** |
| 用户当前城市/坐标文本（示例：`current_place`） | N11 | **缺** |
| 停留意图（示例：`stay_kind` + 可选日期） | N12 | **缺** |
| 归因渠道（示例：`acquisition_source`） | N06 | **缺**（可先只前端埋点） |
| 通知偏好（示例：`notify_prefs` JSON） | N21 | **缺** |
| 是否展示距离等隐私（示例：`show_distance`） | N25 | **缺** |

---

## 3. 当前小程序实际路径（未拆分版）

1. `login.vue`：短信登录。  
2. 若缺性别 → `profile-edit?first=1`。  
3. `profile-edit.vue`：**单页** 含性别 + 昵称 + 简介；头像字母；**不写 tags**。  
4. 保存 → 首页。

与第 1 节「全量拆分」对照：**现有实现 = 登录 + 一页资料**，其余 N02～N26 均未按独立页实现。

---

## 4. 路由串联示例（全拆分时的顺序参考）

仅作串联参考，上线可删减或合并：

`登录` → `N06 归因` → `N07 昵称` → `N09 母国` → `N10 旅行身份` → `N11 位置` → `N12 停留` → `N13 简介` → `N14～N17 兴趣分品类` → `性别`（或提前）→ `N19 头像` → `N20 完成` → `N21 通知` → `N23～N24 定位说明` → `N25 隐私` → `首页`

性别（WanderMeet 强规则）可插在昵称后或简介前，以产品为准。

---

## 5. 接口与数据库变动草案（待评审后开发）

以下为 **全量引导** 落地时，相对当前代码的典型增量；字段名、类型可评审调整。**未写入代码前以本文档为需求草案**。对外接口说明同步维护于 **`doc/API_WanderMeet_v0.1.md`**（「`GET/PATCH /me` 规划扩展」小节）。

### 5.1 `users` 表（Alembic 迁移）

| 列名（草案） | 类型（草案） | 说明 |
|--------------|--------------|------|
| `country_code` | `String(8)` nullable | ISO 3166-1 alpha-2，如 `CN`；对应 N09 |
| `traveler_roles` | `JSON` nullable | 字符串数组，最多 2 条；或改用固定枚举存库 |
| `current_place` | `String(256)` nullable | 用户填写的当前城市/地点文案；精确定位可后续扩展 |
| `stay_kind` | `String(32)` nullable | 如 `indefinite` / `fixed_dates`；对应 N12 |
| `stay_end_at` | `DateTime` nullable | 若选择固定停留，可选结束时间 |
| `acquisition_source` | `String(64)` nullable | 归因渠道枚举值；对应 N06 |
| `notify_prefs` | `JSON` nullable | 通知偏好结构体；对应 N21 |
| `show_distance` | `Boolean` default true | 是否向他人展示距离类信息；对应 N25 |

说明：`nickname` 是否禁止二次修改属产品规则，可用 DB 列 `nickname_locked` 或仅服务端校验首次 PATCH。

### 5.2 `GET /api/v1/wm/me`（`MeData`）扩展草案

在现有 `userId`、`phoneMasked`、`nickname`、`avatarUrl`、`gender`、`bio`、`tags`、`status`、`verification` 基础上，可增加（全部为 camelCase 输出）：

- `countryCode`、`travelerRoles`、`currentPlace`、`stayKind`、`stayEndAt`、`acquisitionSource`、`notifyPrefs`、`showDistance`（无则 `null` 或默认值与产品一致）。

### 5.3 `PATCH /api/v1/wm/me`（`UpdateMeRequest`）扩展草案

上述新建列中，凡允许用户修改的，均在 `UpdateMeRequest` 增加可选字段；校验规则建议：

- `travelerRoles`：最多 2 项；  
- `tags`：维持现有最多 20；  
- `stayEndAt`：仅当 `stayKind` 为需要日期时接受。

### 5.4 可选新接口（非必须）

| 接口草案 | 用途 |
|----------|------|
| `GET /api/v1/wm/meta/onboarding` | 返回兴趣词表、归因枚举、旅行身份枚举等，供小程序渲染 Chip |
| `GET /api/v1/wm/meta/stats` | 在线人数等（若做 N02），需定义统计口径 |

---

## 6. 文档维护

- 不以「第几步」合并表述；新增品类/新权限页即在 **§1** 增行、 **§2** 增字段；**接口/表结构以 §5 为准迭代**。  
- 合规与大陆备案要求单独评估，本文仅拆功能单元。  
- **后端执行清单**同步见 `doc/TODO_Backend_NextSteps.md` §「资料与引导」。
