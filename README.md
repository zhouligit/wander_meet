# WanderMeet Backend (FastAPI)

## 前端（旅聚小程序）

微信小程序 **uni-app** 工程与本仓库分离，本地常见路径为：

**`/Users/zhouli/data/code/chuangye/lv_ju/travel-together`**

（全局样式与设计变量：`src/uni.scss`。）

## Tech Stack

- Python + FastAPI
- MySQL (SQLAlchemy async + `asyncmy`)
- Redis (`redis-py` asyncio client)

## Quick Start

1. Create and activate virtual env:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install deps:
   - `pip install -r requirements.txt`
3. Copy env:
   - `cp .env.example .env`
4. Run:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Database Migration

- Create database first (example): `CREATE DATABASE wandermeet CHARACTER SET utf8mb4;`
- Run migration:
  - `alembic upgrade head`
  - includes `20260416_0001` + `20260416_0002` revisions

## Health Endpoints

- `GET /api/v1/wm/health`
- `GET /api/v1/wm/health/deps` (checks MySQL + Redis)

## Implemented APIs (v0 skeleton)

- `POST /api/v1/wm/auth/sms/send`
- `POST /api/v1/wm/auth/sms/login`
- `POST /api/v1/wm/auth/wechat/login`（小程序 `wx.login` 的 code）
- `POST /api/v1/wm/auth/email/register`（H5 邮箱注册，见 `doc/mail_login.md`）
- `POST /api/v1/wm/auth/email/login`（H5 邮箱登录）
- `POST /api/v1/wm/auth/token/refresh`
- `POST /api/v1/wm/auth/logout`
- `GET /api/v1/wm/activities?cityCode=110000&page=1&pageSize=20`
- `GET /api/v1/wm/activities/{activityId}` (requires Bearer token)
- `POST /api/v1/wm/activities` (requires Bearer token)
- `PATCH /api/v1/wm/activities/{activityId}` (organizer only)
- `POST /api/v1/wm/activities/{activityId}/enrollments` (requires Bearer token)
- `DELETE /api/v1/wm/activities/{activityId}/enrollments/me`
- `POST /api/v1/wm/activities/{activityId}/cancel` (organizer only, requires Bearer token)
- `GET /api/v1/wm/activities/{activityId}/members`
- `GET /api/v1/wm/activities/{activityId}/messages`
- `POST /api/v1/wm/activities/{activityId}/messages`
- `GET /api/v1/wm/meta/activity-categories`
- `GET /api/v1/wm/me`（含 `phoneBound`、`emailMasked`、`emailBound`）
- `PATCH /api/v1/wm/me`
- `POST /api/v1/wm/me/phone/bind-wechat`
- `POST /api/v1/wm/me/phone/bind-sms`
- `GET /api/v1/wm/me/activities?role=organized|joined`
- `GET /api/v1/wm/me/chats?page=1&pageSize=20`
- `PATCH /api/v1/wm/me/chats/{activityId}/read`
- `GET /api/v1/wm/me/premium`
- `POST /api/v1/wm/me/avatar/upload-url`
- `GET /api/v1/wm/me/verification`
- `POST /api/v1/wm/me/verification`
- `POST /api/v1/wm/reports`
- `GET /api/v1/wm/me/reports`
- `POST /api/v1/wm/blocks`
- `DELETE /api/v1/wm/blocks/{blockedUserId}`
- `GET /api/v1/wm/blocks`
- `GET /api/v1/wm/notifications`
- `PATCH /api/v1/wm/notifications/{notificationId}/read`
- `POST /api/v1/wm/notifications/read-all`
- `GET /api/v1/wm/admin/activities`
- `POST /api/v1/wm/admin/activities/{activityId}/approve`
- `POST /api/v1/wm/admin/activities/{activityId}/reject`
- `GET /api/v1/wm/admin/reports`
- `PATCH /api/v1/wm/admin/reports/{reportId}`
- `POST /api/v1/wm/admin/users/{userId}/ban`
- `POST /api/v1/wm/admin/users/{userId}/unban`
- `GET /api/v1/wm/admin/users/search`（运维：重复账号排查）
- `POST /api/v1/wm/admin/users/merge`（运维：合并微信/短信重复账号）

## Next Milestones

- Implement create activity, enroll/cancel, and activity detail APIs.
- Add verification and report/block modules.
- SMS 验证码：生产环境 `SMS_USE_MOCK=false`，通过 **`SMS_PROVIDER`** 选择 **`ihuyi`**（互亿无线，默认）或 **`aliyun`**（阿里云 SendSms）；变量见 `.env.example`。

## Ops Scripts

- Deploy script: `scripts/deploy.sh`
  - Example:
    - `APP_DIR=/opt/wander_meet SERVICE_NAME=wandermeet BRANCH=main bash scripts/deploy.sh`
- MySQL backup script: `scripts/backup_mysql.sh`
  - Example:
    - `MYSQL_USER=wm_user MYSQL_PASSWORD='your_password' MYSQL_DB=wandermeet bash scripts/backup_mysql.sh`

