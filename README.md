# WanderMeet Backend (FastAPI)

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
- `POST /api/v1/wm/auth/token/refresh`
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
- `GET /api/v1/wm/me`
- `PATCH /api/v1/wm/me`
- `GET /api/v1/wm/me/activities?role=organized|joined`
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

## Next Milestones

- Implement create activity, enroll/cancel, and activity detail APIs.
- Add verification and report/block modules.
- Integrate real SMS provider and JWT refresh token flow.

## Ops Scripts

- Deploy script: `scripts/deploy.sh`
  - Example:
    - `APP_DIR=/opt/wander_meet SERVICE_NAME=wandermeet BRANCH=main bash scripts/deploy.sh`
- MySQL backup script: `scripts/backup_mysql.sh`
  - Example:
    - `MYSQL_USER=wm_user MYSQL_PASSWORD='your_password' MYSQL_DB=wandermeet bash scripts/backup_mysql.sh`

