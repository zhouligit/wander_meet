# 照片验证 — 运营审核说明

用户提交后，`photo_verifications.status = pending`。需对比 **用户头像** 与 **现场自拍**（`selfieUrl`）是否为同一人、是否为现场拍摄。

---

## 一、小程序手机审核（推荐）

### 1. 开通管理员

在 MySQL 将运营账号设为 admin（`users.id` 与登录账号一致）：

```sql
UPDATE users SET role = 'admin' WHERE id = 1;
```

### 2. 管理员入口

- 用该账号登录微信小程序
- 打开底部 **「我的」**
- 菜单顶部会出现 **「照片验证审核」**（仅 `isAdmin=true` 可见）
- 副标题显示待审数量，如 `3 待审`

### 3. 审核操作

审核页每条申请展示：

| 区域 | 说明 |
|------|------|
| 头像 | 用户资料头像，点击可放大 |
| 现场自拍 | BOS 上传的自拍，点击可放大 |

- **通过**：确认后用户获得「照片已验证」、信任分 +150
- **拒绝**：选择预设原因，用户可在照片验证页看到并重新提交

### 4. 发布要求

- **后端**：含 `GET /me` 的 `isAdmin` 字段 + `/admin/photo-verifications/*` 接口，并已 `alembic upgrade head`
- **前端**：含 `pages/admin-photo-review` 与「我的」入口，需 **重新编译并上传** 小程序（新增页面必须重新构建，否则会白屏）

### 5. 白屏排查

| 现象 | 处理 |
|------|------|
| 整页空白 | 重新编译上传小程序；确认 `pages.json` 已注册 `admin-photo-review` |
| 「加载失败」 | 后端未部署 `/admin/photo-verifications` 或未执行迁移 |
| 「无管理员权限」 | 执行 `UPDATE users SET role='admin'` 后完全退出再登录 |
| 有菜单但进页空白 | 多为旧包未含审核页，或接口 500，看页面是否显示错误文案 |

---

## 二、管理 API（Postman / 脚本）

使用 **`role = admin`** 账号的 access token：

```http
GET /api/v1/wm/admin/photo-verifications?status=pending&page=1&pageSize=20
Authorization: Bearer <admin_access_token>
```

```http
POST /api/v1/wm/admin/photo-verifications/pv_123/approve
Authorization: Bearer <admin_access_token>
```

```http
POST /api/v1/wm/admin/photo-verifications/pv_123/reject
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{"reason": "自拍与头像不一致，请重新拍摄"}
```

---

## 三、无后台时手工 SQL（应急）

```sql
UPDATE photo_verifications
SET status = 'approved', reviewed_at = UTC_TIMESTAMP()
WHERE id = PV_ID AND status = 'pending';

UPDATE user_trust_profiles
SET photo_verified = 1, trust_score = LEAST(1000, trust_score + 150)
WHERE user_id = USER_ID;
```

拒绝：

```sql
UPDATE photo_verifications
SET status = 'rejected', reject_reason = '请重新拍摄', reviewed_at = UTC_TIMESTAMP()
WHERE id = PV_ID AND status = 'pending';
```

---

## 四、本地 Mock 调试

1. 开发者工具 Storage 将 `wm_use_mock` 设为 `true`
2. 在 `wandermeet-db.js` 的 `profile` 上设 `isAdmin: true`
3. 用户先走「照片验证」提交一条 pending
4. 「我的」→「照片验证审核」里操作

H5 照片验证页的「开发：模拟通过」仅 Mock 自用，与审核页无关。
