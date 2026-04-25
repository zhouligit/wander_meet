# 旅聚 WanderMeet API 清单 v0.1

对应 PRD：`PRD_WanderMeet_v0.1_Beijing.md`。  
基路径示例：`https://api.wandermeet.example.com/api/v1/wm`  
鉴权：`Authorization: Bearer <accessToken>`（除登录、发送验证码、部分 meta 外均需携带）

统一响应外层：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| code | number | 0 表示成功，非 0 为业务/错误码 |
| message | string | 提示文案 |
| data | object \| null | 业务数据 |

---

## 通用约定

- 时间与日期：请求/响应 ISO 8601 字符串，如 `2026-04-16T18:30:00+08:00`。
- 分页列表：`query` 带 `page`（从 1 起）、`pageSize`（默认 20，最大 50）；列表响应在 `data` 内含 `list`、`total`、`page`、`pageSize`。
- 游标分页（消息）：`cursor`（可选）、`limit`（默认 20，最大 50）。
- 用户可见字段中的 `userId` 为字符串（UUID 或雪花 ID），示例用短 ID 便于阅读。

---

## 1. 发送短信验证码

### `POST /api/v1/wm/auth/sms/send`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| phone | body | string | 是 | 中国大陆手机号，如 `13800138000` |
| scene | body | string | 否 | `login`（默认） |

### 请求参数示例（JSON）

```json
{
  "phone": "13800138000",
  "scene": "login"
}
```

### 请求示例

```
POST /api/v1/wm/auth/sms/send HTTP/1.1
Host: api.wandermeet.example.com
Content-Type: application/json

{"phone":"13800138000","scene":"login"}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| expireInSeconds | number | 验证码有效秒数（展示用） |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "expireInSeconds": 300
  }
}
```

---

## 2. 短信验证码登录（换 token）

### `POST /api/v1/wm/auth/sms/login`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| phone | body | string | 是 | 手机号 |
| code | body | string | 是 | 短信验证码 |

### 请求参数示例（JSON）

```json
{
  "phone": "13800138000",
  "code": "123456"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| accessToken | string | 访问令牌 |
| expiresIn | number | accessToken 有效秒数 |
| refreshToken | string | 刷新用（可选，v0.1 可简化为长有效期 accessToken） |
| user | object | 当前用户摘要 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "accessToken": "wm_at_xxx",
    "expiresIn": 7200,
    "refreshToken": "wm_rt_xxx",
    "user": {
      "userId": "u_10001",
      "nickname": "旅人小王",
      "avatarUrl": "https://cdn.example.com/a.png",
      "status": "active"
    }
  }
}
```

---

## 3. 刷新令牌（可选）

### `POST /api/v1/wm/auth/token/refresh`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| refreshToken | body | string | 是 | 登录返回的 refreshToken |

### 请求参数示例（JSON）

```json
{
  "refreshToken": "wm_rt_xxx"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| accessToken | string | 新 accessToken |
| expiresIn | number | 有效秒数 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "accessToken": "wm_at_yyy",
    "expiresIn": 7200
  }
}
```

---

## 4. 当前用户资料

### `GET /api/v1/wm/me`

### 请求参数

无（鉴权即当前用户）

### 请求示例

```
GET /api/v1/wm/me HTTP/1.1
Host: api.wandermeet.example.com
Authorization: Bearer wm_at_xxx
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | string | 用户 ID |
| phoneMasked | string | 脱敏手机号，如 `138****8000` |
| nickname | string | 昵称 |
| avatarUrl | string \| null | 头像 URL |
| tags | array | 标签，如 `["digital_nomad","weekend"]` |
| status | string | `active` \| `banned` \| `restricted` |
| verification | object | 认证状态摘要（见下方） |

### `verification` 对象

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | `none` \| `pending` \| `approved` \| `rejected` |
| canCreateActivity | boolean | 是否允许创建活动（PRD：发活动需认证通过） |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "userId": "u_10001",
    "phoneMasked": "138****8000",
    "nickname": "旅人小王",
    "avatarUrl": "https://cdn.example.com/a.png",
    "tags": ["digital_nomad", "weekend"],
    "status": "active",
    "verification": {
      "status": "approved",
      "canCreateActivity": true
    }
  }
}
```

---

## 5. 更新当前用户资料

### `PATCH /api/v1/wm/me`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| nickname | body | string | 否 | 昵称 |
| avatarUrl | body | string | 否 | 头像 URL（若先直传 OSS，可为上传后 URL） |
| tags | body | array | 否 | 标签 ID 或枚举值列表 |

### 请求参数示例（JSON）

```json
{
  "nickname": "小王在北京",
  "tags": ["digital_nomad", "solo_travel"]
}
```

### 响应 `data`

同「当前用户资料」结构（`GET /me`）

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "userId": "u_10001",
    "phoneMasked": "138****8000",
    "nickname": "小王在北京",
    "avatarUrl": "https://cdn.example.com/a.png",
    "tags": ["digital_nomad", "solo_travel"],
    "status": "active",
    "verification": {
      "status": "approved",
      "canCreateActivity": true
    }
  }
}
```

---

## 6. 头像上传凭证（可选，OSS 直传）

### `POST /api/v1/wm/me/avatar/upload-url`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| contentType | body | string | 是 | 如 `image/jpeg` |
| fileExt | body | string | 是 | `jpg` \| `png` \| `webp` |

### 请求参数示例（JSON）

```json
{
  "contentType": "image/jpeg",
  "fileExt": "jpg"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| uploadUrl | string | 直传 PUT URL |
| objectKey | string | 对象键，成功后拼接访问域名或再调 CDN |
| headers | object | 上传时需携带的额外头 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "uploadUrl": "https://oss.example.com/...",
    "objectKey": "wm/avatar/u_10001/xxx.jpg",
    "headers": {
      "Content-Type": "image/jpeg"
    }
  }
}
```

---

## 7. 认证状态详情

### `GET /api/v1/wm/me/verification`

### 请求参数

无

### 请求示例

```
GET /api/v1/wm/me/verification HTTP/1.1
Host: api.wandermeet.example.com
Authorization: Bearer wm_at_xxx
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | `none` \| `pending` \| `approved` \| `rejected` |
| rejectReason | string \| null | 审核拒绝原因 |
| submittedAt | string \| null | 提交时间 |
| reviewedAt | string \| null | 审核时间 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "pending",
    "rejectReason": null,
    "submittedAt": "2026-04-16T10:00:00+08:00",
    "reviewedAt": null
  }
}
```

---

## 8. 提交组织者认证（实名 / 人脸由对接厂商决定）

### `POST /api/v1/wm/me/verification`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| realName | body | string | 是 | 真实姓名 |
| idCardNumber | body | string | 是 | 身份证号（传输 HTTPS，服务端加密存储） |
| faceVerifyToken | body | string | 否 | 人脸核验完成后第三方回传的 token（若走小程序人脸） |

### 请求参数示例（JSON）

```json
{
  "realName": "张三",
  "idCardNumber": "110101199001011234",
  "faceVerifyToken": "face_token_xxx"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 提交后多为 `pending` 或三方实时返回 `approved` |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "pending"
  }
}
```

---

## 9. 活动类目与配置（发现页、筛选）

### `GET /api/v1/wm/meta/activity-categories`

### 请求参数

无

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| categories | array | 类目列表 |

### `categories[]` 元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| categoryId | string | 如 `coffee` |
| name | string | 展示名 |
| icon | string \| null | 图标 URL 或 key |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "categories": [
      { "categoryId": "coffee", "name": "咖啡", "icon": null },
      { "categoryId": "citywalk", "name": "Citywalk", "icon": null },
      { "categoryId": "hiking", "name": "徒步", "icon": null },
      { "categoryId": "boardgame", "name": "桌游", "icon": null }
    ]
  }
}
```

---

## 10. 同城活动列表（北京首站）

### `GET /api/v1/wm/activities`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| cityCode | query | string | 是 | 首站固定 `110000`（北京）或 `beijing` |
| dateRange | query | string | 否 | `today` \| `tomorrow` \| `all` |
| categoryId | query | string | 否 | 筛选类目 |
| maxDistanceKm | query | number | 否 | 需要用户 lat/lng 时与距离联合使用 |
| lat | query | number | 否 | 用户纬度，算距离 |
| lng | query | number | 否 | 用户经度 |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

### 请求示例

```
GET /api/v1/wm/activities?cityCode=110000&dateRange=today&lat=39.9&lng=116.4&page=1&pageSize=20 HTTP/1.1
Host: api.wandermeet.example.com
Authorization: Bearer wm_at_xxx
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 活动卡片列表 |
| total | number | 总条数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

### `list[]` 元素（卡片）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |
| title | string | 标题 |
| startAt | string | 开始时间 |
| locationName | string | 地点名称 |
| lat | number | 纬度 |
| lng | number | 经度 |
| distanceMeters | number \| null | 有用户坐标时返回 |
| enrolledCount | number | 已报名人数（不含 organizer 可产品与 PRD 对齐） |
| maxMembers | number | 人数上限 |
| categoryId | string | 类目 |
| organizer | object | 组织者摘要 |
| activityStatus | string | `published` 等 |
| enrollmentStatus | string \| null | 当前用户报名状态：`joined` \| null（未登录可为 null） |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "activityId": "act_20001",
        "title": "周末奥森轻徒步",
        "startAt": "2026-04-17T09:00:00+08:00",
        "locationName": "奥林匹克森林公园南园",
        "lat": 40.01,
        "lng": 116.39,
        "distanceMeters": 2300,
        "enrolledCount": 4,
        "maxMembers": 8,
        "categoryId": "hiking",
        "organizer": {
          "userId": "u_10002",
          "nickname": "领队阿李",
          "avatarUrl": null
        },
        "activityStatus": "published",
        "enrollmentStatus": null
      }
    ],
    "total": 42,
    "page": 1,
    "pageSize": 20
  }
}
```

---

## 11. 活动详情

### `GET /api/v1/wm/activities/:activityId`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| lat | query | number | 否 | 用于展示距离 |
| lng | query | number | 否 | 用于展示距离 |

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |
| title | string | 标题 |
| description | string | 活动说明 |
| categoryId | string | 类目 |
| startAt | string | 开始时间 |
| endAt | string \| null | 结束时间（可选） |
| cityCode | string | 城市 |
| locationName | string | 地点名称 |
| addressDetail | string \| null | 详细地址（到点后可展示或由群聊同步） |
| lat | number | 纬度 |
| lng | number | 经度 |
| distanceMeters | number \| null | 可选 |
| maxMembers | number | 人数上限 |
| feeType | string | `free` \| `aa` \| `fixed` |
| feeAmount | number \| null | 固定金额（分）或展示用 |
| rulesAccepted | object | PRD 规则勾选留痕 |
| activityStatus | string | 见数据库说明 |
| organizer | object | 组织者信息 |
| enrolledCount | number | 已报名人数 |
| myEnrollment | object \| null | 当前用户报名态 |

### `rulesAccepted` 示例字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| noHarassment | boolean | 禁止骚扰 |
| noPromotion | boolean | 禁止引流 |
| noInappropriate | boolean | 禁止不当内容 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "activityId": "act_20001",
    "title": "周末奥森轻徒步",
    "description": "休闲节奏，自备饮水。",
    "categoryId": "hiking",
    "startAt": "2026-04-17T09:00:00+08:00",
    "endAt": "2026-04-17T12:00:00+08:00",
    "cityCode": "110000",
    "locationName": "奥林匹克森林公园南园",
    "addressDetail": "南门集合",
    "lat": 40.01,
    "lng": 116.39,
    "distanceMeters": 2300,
    "maxMembers": 8,
    "feeType": "free",
    "feeAmount": null,
    "rulesAccepted": {
      "noHarassment": true,
      "noPromotion": true,
      "noInappropriate": true
    },
    "activityStatus": "published",
    "organizer": {
      "userId": "u_10002",
      "nickname": "领队阿李",
      "avatarUrl": null,
      "verificationBadge": true
    },
    "enrolledCount": 4,
    "myEnrollment": null
  }
}
```

---

## 12. 创建活动（需认证通过）

### `POST /api/v1/wm/activities`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| title | body | string | 是 | 标题 |
| description | body | string | 是 | 活动说明 |
| categoryId | body | string | 是 | 类目 |
| startAt | body | string | 是 | 开始时间 |
| endAt | body | string | 否 | 结束时间 |
| cityCode | body | string | 是 | 首站 `110000` |
| locationName | body | string | 是 | 地点名称 |
| addressDetail | body | string | 否 | 详细地址 |
| lat | body | number | 是 | 纬度 |
| lng | body | number | 是 | 经度 |
| maxMembers | body | number | 是 | 人数上限 |
| feeType | body | string | 是 | `free` \| `aa` \| `fixed` |
| feeAmount | body | number | 否 | 分（feeType 为 fixed 时） |
| rulesAccepted | body | object | 是 | 必须与 PRD 勾选一致 |

### 请求参数示例（JSON）

```json
{
  "title": "周五晚国贸咖啡局",
  "description": "随意聊天，不限话题。",
  "categoryId": "coffee",
  "startAt": "2026-04-18T19:30:00+08:00",
  "endAt": "2026-04-18T21:30:00+08:00",
  "cityCode": "110000",
  "locationName": "某咖啡厅",
  "addressDetail": "国贸桥下某门牌",
  "lat": 39.91,
  "lng": 116.46,
  "maxMembers": 8,
  "feeType": "aa",
  "feeAmount": null,
  "rulesAccepted": {
    "noHarassment": true,
    "noPromotion": true,
    "noInappropriate": true
  }
}
```

### 响应 `data`

活动详情结构（同「活动详情」核心字段），含 `activityStatus`（新建可能为 `pending_review` 或直接进入 `published`，以运营策略为准）。

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "activityId": "act_20002",
    "title": "周五晚国贸咖啡局",
    "activityStatus": "pending_review",
    "organizer": {
      "userId": "u_10001",
      "nickname": "旅人小王",
      "avatarUrl": null,
      "verificationBadge": true
    }
  }
}
```

---

## 13. 修改活动（组织者）

### `PATCH /api/v1/wm/activities/:activityId`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

与创建类似，均为可选字段；若活动已开始或已结束，服务端拒绝或限制修改（业务码另行定义）。

### 响应 `data`

同活动详情。

---

## 14. 取消活动（组织者）

### `POST /api/v1/wm/activities/:activityId/cancel`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| reason | body | string | 否 | 取消原因（通知参与者） |

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |
| activityStatus | string | `cancelled` |

---

## 15. 报名参加活动

### `POST /api/v1/wm/activities/:activityId/enrollments`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

无 body 或空对象 `{}`（v0.1 无问卷）

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| enrollmentId | string | 报名记录 ID |
| status | string | `joined` |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "enrollmentId": "enr_30001",
    "status": "joined"
  }
}
```

---

## 16. 取消报名

### `DELETE /api/v1/wm/activities/:activityId/enrollments/me`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | `cancelled` |

---

## 17. 活动成员列表（群聊成员 / 组织者选人）

### `GET /api/v1/wm/activities/:activityId/members`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 说明

仅已报名者/组织者可访问；被拉黑用户不应出现在对方视图中（服务端过滤）。

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 成员列表 |

### `list[]` 元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | string | 用户 ID |
| nickname | string | 昵称 |
| avatarUrl | string \| null | 头像 |
| role | string | `organizer` \| `member` |
| joinedAt | string | 加入时间 |

---

## 18. 活动群聊：拉取消息

### `GET /api/v1/wm/activities/:activityId/messages`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| cursor | query | string | 否 | 上一页最后一条 messageId 或时间游标 |
| limit | query | number | 否 | 默认 20 |
| direction | query | string | 否 | `older`（默认，向上翻） \| `newer` |

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 消息列表（时间正序或逆序与前端约定，建议时间正序） |
| nextCursor | string \| null | 下一页游标 |

### `list[]` 元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| messageId | string | 消息 ID |
| activityId | string | 活动 ID |
| sender | object | 发送者摘要 |
| msgType | string | `text` \| `image` |
| text | string \| null | 文本 |
| imageUrl | string \| null | 图片 URL |
| createdAt | string | 发送时间 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "messageId": "msg_40001",
        "activityId": "act_20001",
        "sender": {
          "userId": "u_10002",
          "nickname": "领队阿李",
          "avatarUrl": null
        },
        "msgType": "text",
        "text": "大家好，明天南门见。",
        "imageUrl": null,
        "createdAt": "2026-04-16T12:00:00+08:00"
      }
    ],
    "nextCursor": "msg_40001"
  }
}
```

---

## 19. 活动群聊：发送消息

### `POST /api/v1/wm/activities/:activityId/messages`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| msgType | body | string | 是 | `text` \| `image` |
| text | body | string | 条件 | msgType 为 text 时必填 |
| imageUrl | body | string | 条件 | msgType 为 image 时必填（先走上传凭证） |

### 请求参数示例（JSON）

```json
{
  "msgType": "text",
  "text": "我准时到。"
}
```

### 响应 `data`

单条消息对象（同 `list[]` 元素）。

---

## 20. 举报

### `POST /api/v1/wm/reports`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| targetType | body | string | 是 | `user` \| `activity` \| `message` |
| targetId | body | string | 是 | 对应用户 ID、活动 ID、消息 ID |
| activityId | body | string | 否 | 消息/用户上下文建议传 |
| reasonCode | body | string | 是 | 如 `harassment` \| `spam` \| `fraud` \| `inappropriate` \| `other` |
| detail | body | string | 否 | 补充说明 |

### 请求参数示例（JSON）

```json
{
  "targetType": "message",
  "targetId": "msg_40001",
  "activityId": "act_20001",
  "reasonCode": "harassment",
  "detail": "重复私信骚扰"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| reportId | string | 举报单 ID |
| status | string | `pending` |

---

## 21. 我的举报记录

### `GET /api/v1/wm/me/reports`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

### 响应 `data`

分页结构，`list[]` 含 `reportId`、`targetType`、`reasonCode`、`status`、`createdAt`、`handledResult`（可选）。

---

## 22. 拉黑用户

### `POST /api/v1/wm/blocks`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| blockedUserId | body | string | 是 | 被拉黑用户 ID |

### 请求参数示例（JSON）

```json
{
  "blockedUserId": "u_10999"
}
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| blockedUserId | string | 被拉黑用户 ID |

---

## 23. 取消拉黑

### `DELETE /api/v1/wm/blocks/:blockedUserId`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| blockedUserId | string | 用户 ID |

### 响应 `data`

```json
{ "ok": true }
```

---

## 24. 拉黑列表

### `GET /api/v1/wm/blocks`

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 被拉黑用户简要信息 + createdAt |

---

## 25. 通知列表

### `GET /api/v1/wm/notifications`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| read | query | string | 否 | `all` \| `unread` |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

### 响应 `data` 中 `list[]` 元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| notificationId | string | 通知 ID |
| type | string | `enrollment_ok` \| `activity_changed` \| `report_result` \| `verification_result` 等 |
| title | string | 标题 |
| body | string | 正文 |
| payload | object | 跳转参数（如 activityId） |
| readAt | string \| null | 已读时间 |
| createdAt | string | 创建时间 |

---

## 26. 单条通知已读

### `PATCH /api/v1/wm/notifications/:notificationId/read`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| notificationId | string | 通知 ID |

### 响应 `data`

```json
{ "notificationId": "ntf_50001", "readAt": "2026-04-16T15:00:00+08:00" }
```

---

## 27. 全部已读

### `POST /api/v1/wm/notifications/read-all`

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| updatedCount | number | 更新条数 |

---

## 28. 我的活动（我发起的 / 我报名的）

### `GET /api/v1/wm/me/activities`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| role | query | string | 是 | `organized` \| `joined` |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

### 响应 `data`

分页 + 活动卡片列表（可简化为与活动列表一致字段）。

---

## 29. 付费能力预埋（可选）

### `GET /api/v1/wm/me/premium`

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| enabled | boolean | 是否开通付费（v0.1 恒为 false） |
| sku | array | 商品占位 |

---

## 29.1 我加入的群聊列表

### `GET /api/v1/wm/me/chats`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| page | query | number | 否 | 页码，默认 1 |
| pageSize | query | number | 否 | 每页条数，默认 20，最大 50 |

### 请求示例

```
curl "http://127.0.0.1:8001/api/v1/wm/me/chats?page=1&pageSize=20" \
  -H "Authorization: Bearer <TOKEN>"
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 群聊列表（按最近消息时间倒序） |
| total | number | 总条数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

### `list[]` 元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID（群 ID） |
| title | string | 活动标题 |
| activityStatus | string | 活动状态 |
| memberCount | number | 当前成员数（joined） |
| lastMessage | string \| null | 最后一条消息摘要（图片为 `[图片]`） |
| lastMessageAt | string \| null | 最后一条消息时间 |
| unreadCount | number | 未读消息数 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "activityId": "act_20001",
        "title": "周五晚国贸咖啡局",
        "activityStatus": "published",
        "memberCount": 6,
        "lastMessage": "我准时到。",
        "lastMessageAt": "2026-04-22T10:30:00+08:00",
        "unreadCount": 2
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 20
  }
}
```

---

## 29.2 标记群聊已读

### `PATCH /api/v1/wm/me/chats/:activityId/read`

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID（如 `act_1`） |

### 请求示例

```
curl -X PATCH "http://127.0.0.1:8001/api/v1/wm/me/chats/act_1/read" \
  -H "Authorization: Bearer <TOKEN>"
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| updatedCount | number | 更新条数，正常为 1 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "updatedCount": 1
  }
}
```

---

## 管理端 API（运营 / 审核，独立鉴权）

管理端建议使用独立 `Admin-Token` 或服务端账号，以下为示例路径。

---

## 30. 待审核活动列表

### `GET /api/v1/wm/admin/activities`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| activityStatus | query | string | 否 | 默认 `pending_review` |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

---

## 31. 审核通过活动

### `POST /api/v1/wm/admin/activities/:activityId/approve`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| comment | body | string | 否 | 内部备注 |

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |
| activityStatus | string | `published` |

---

## 32. 审核拒绝活动

### `POST /api/v1/wm/admin/activities/:activityId/reject`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| reason | body | string | 是 | 给组织者可见的拒绝原因（可选是否展示） |

---

## 33. 举报处理列表

### `GET /api/v1/wm/admin/reports`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| status | query | string | 否 | `pending` \| `handled` |
| page | query | number | 否 | 页码 |
| pageSize | query | number | 否 | 每页条数 |

---

## 34. 处理举报

### `PATCH /api/v1/wm/admin/reports/:reportId`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| action | body | string | 是 | `dismiss` \| `warn_user` \| `ban_user` \| `delete_message` 等 |
| note | body | string | 否 | 内部备注 |
| notifyUser | body | boolean | 否 | 是否通知举报人结果 |

---

## 35. 封禁用户

### `POST /api/v1/wm/admin/users/:userId/ban`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| reason | body | string | 是 | 原因 |
| scope | body | string | 否 | `full`（默认） \| `no_create_activity` 等 |

---

## 36. 解封用户

### `POST /api/v1/wm/admin/users/:userId/unban`

---

## 37. 周边活动列表（按距离）

### `GET /api/v1/wm/activities/nearby`

### 请求参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| lat | query | number | 是 | 用户当前纬度（WGS84） |
| lng | query | number | 是 | 用户当前经度（WGS84） |
| radiusKm | query | number | 否 | 搜索半径（公里），默认 `5`，可选 `1` \| `3` \| `5` \| `10` \| `20` |
| cityCode | query | string | 否 | 城市编码；不传时由坐标反查城市或不过滤 |
| dateRange | query | string | 否 | `today` \| `tomorrow` \| `weekend` \| `all`（默认） |
| categoryId | query | string | 否 | 活动类目 |
| sortBy | query | string | 否 | `distance`（默认）\| `startAt` |
| page | query | number | 否 | 页码，默认 `1` |
| pageSize | query | number | 否 | 每页条数，默认 `20`，最大 `50` |

### 请求参数示例（JSON）

```json
{
  "lat": 39.9087,
  "lng": 116.3975,
  "radiusKm": 5,
  "cityCode": "110000",
  "dateRange": "all",
  "categoryId": "citywalk",
  "sortBy": "distance",
  "page": 1,
  "pageSize": 20
}
```

### 请求示例

```
GET /api/v1/wm/activities/nearby?lat=39.9087&lng=116.3975&radiusKm=5&cityCode=110000&page=1&pageSize=20 HTTP/1.1
Host: api.wandermeet.example.com
Authorization: Bearer wm_at_xxx
```

### cURL 示例

```bash
curl "http://127.0.0.1:8001/api/v1/wm/activities/nearby?lat=39.9087&lng=116.3975&radiusKm=5&cityCode=110000&page=1&pageSize=20" \
  -H "Authorization: Bearer <TOKEN>"
```

### 响应 `data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| list | array | 周边活动卡片列表 |
| total | number | 命中总条数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |
| searchCenter | object | 查询中心点 |
| radiusKm | number | 本次查询半径（公里） |

### `list[]` 元素（卡片）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| activityId | string | 活动 ID |
| title | string | 标题 |
| startAt | string | 开始时间 |
| locationName | string | 地点名称 |
| lat | number | 活动纬度 |
| lng | number | 活动经度 |
| distanceMeters | number | 与用户中心点的距离（米） |
| enrolledCount | number | 已报名人数 |
| maxMembers | number | 人数上限 |
| categoryId | string | 类目 |
| activityStatus | string | `published` 等 |

### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "activityId": "act_20001",
        "title": "晚饭后亮马河散步局",
        "startAt": "2026-04-26T19:30:00+08:00",
        "locationName": "亮马河国际风情水岸",
        "lat": 39.9498,
        "lng": 116.4603,
        "distanceMeters": 2840,
        "enrolledCount": 6,
        "maxMembers": 10,
        "categoryId": "citywalk",
        "activityStatus": "published"
      }
    ],
    "total": 18,
    "page": 1,
    "pageSize": 20,
    "searchCenter": {
      "lat": 39.9087,
      "lng": 116.3975
    },
    "radiusKm": 5
  }
}
```

### SQL 方案（MySQL 8+，先粗筛再精算）

#### 1) 索引建议

```sql
CREATE INDEX idx_activities_city_status_start
ON activities (city_code, activity_status, start_at);

CREATE INDEX idx_activities_lat_lng
ON activities (lat, lng);
```

#### 2) 先做经纬度包围框（Bounding Box）粗筛

```sql
-- 输入参数:
-- :lat, :lng, :radius_km
-- :lat_delta = :radius_km / 111.32
-- :lng_delta = :radius_km / (111.32 * COS(RADIANS(:lat)))
-- :min_lat = :lat - :lat_delta
-- :max_lat = :lat + :lat_delta
-- :min_lng = :lng - :lng_delta
-- :max_lng = :lng + :lng_delta
```

#### 3) 再用 Haversine 精确距离过滤和排序

```sql
SELECT
  a.id,
  a.title,
  a.start_at,
  a.location_name,
  a.lat,
  a.lng,
  ROUND(
    6371000 * 2 * ASIN(
      SQRT(
        POW(SIN(RADIANS((a.lat - :lat) / 2)), 2) +
        COS(RADIANS(:lat)) * COS(RADIANS(a.lat)) *
        POW(SIN(RADIANS((a.lng - :lng) / 2)), 2)
      )
    )
  ) AS distance_meters
FROM activities a
WHERE a.activity_status = 'published'
  AND (:city_code IS NULL OR a.city_code = :city_code)
  AND a.lat BETWEEN :min_lat AND :max_lat
  AND a.lng BETWEEN :min_lng AND :max_lng
HAVING distance_meters <= :radius_km * 1000
ORDER BY distance_meters ASC, a.start_at ASC
LIMIT :limit OFFSET :offset;
```

#### 4) 分页 total 统计（同样过滤条件）

```sql
SELECT COUNT(1) AS total
FROM (
  SELECT a.id
  FROM activities a
  WHERE a.activity_status = 'published'
    AND (:city_code IS NULL OR a.city_code = :city_code)
    AND a.lat BETWEEN :min_lat AND :max_lat
    AND a.lng BETWEEN :min_lng AND :max_lng
    AND (
      6371000 * 2 * ASIN(
        SQRT(
          POW(SIN(RADIANS((a.lat - :lat) / 2)), 2) +
          COS(RADIANS(:lat)) * COS(RADIANS(a.lat)) *
          POW(SIN(RADIANS((a.lng - :lng) / 2)), 2)
        )
      )
    ) <= :radius_km * 1000
) t;
```

### 5 公里 / 10 公里算法说明（服务端）

1. 将用户坐标记为 `(lat, lng)`，地球半径取 `R = 6371000m`。  
2. 根据半径 `radiusKm` 先计算包围框，减少参与精算的候选点。  
3. 对候选活动计算 Haversine 距离：  
   `d = 2R * asin(sqrt(sin^2((lat2-lat1)/2) + cos(lat1)*cos(lat2)*sin^2((lng2-lng1)/2)))`。  
4. `radiusKm=5` 时过滤 `d <= 5000`；`radiusKm=10` 时过滤 `d <= 10000`。  
5. 默认按 `distance_meters ASC` 排序；同距离再按 `start_at ASC`。  

### 实现建议（与现有接口兼容）

- 发现页保持现有 `GET /api/v1/wm/activities`（城市维度）。  
- 新增 `GET /api/v1/wm/activities/nearby` 作为“附近”tab 专用。  
- 前端距离筛选按钮可直接传 `radiusKm=1/3/5/10/20`，后端统一处理。  

---

## 附录：常用错误码（示例）

| code | 说明 |
| --- | --- |
| 0 | 成功 |
| 40001 | 参数错误 |
| 40101 | 未登录或 token 无效 |
| 40301 | 无权限（非组织者、非成员） |
| 40901 | 重复报名 |
| 40902 | 人数已满 |
| 42201 | 未通过认证，无法创建活动 |
| 42202 | 账号已被封禁或限制 |

---

文档版本：v0.1  
对齐 PRD：`PRD_WanderMeet_v0.1_Beijing.md`
