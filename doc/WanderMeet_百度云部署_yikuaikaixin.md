# WanderMeet 后端 — 百度云 Ubuntu 部署（yikuaikaixin.cn）

更新时间：2026-05-20  
适用：百度云 BCC（Ubuntu 22.04/24.04），对外 API 域名 **`yikuaikaixin.cn`**

---

## 1. 目标架构

```text
小程序 / H5
    │  HTTPS
    ▼
yikuaikaixin.cn:443  ──►  Nginx (SSL 终结)
                            │
                            └──► 127.0.0.1:8000  uvicorn (systemd: wandermeet)
                                      ├── MySQL (本机或 RDS)
                                      └── Redis (本机)
```

- **对外基路径**（与小程序 `API_BASE_URL` 一致）：  
  `https://yikuaikaixin.cn/api/v1/wm`
- **健康检查**：`GET https://yikuaikaixin.cn/api/v1/wm/health`  
- **依赖检查**：`GET https://yikuaikaixin.cn/api/v1/wm/health/deps`

可选：单独子域 `api.yikuaikaixin.cn` 只反代 API（下文以**根域名 + 路径**为例，与现有 `wang-hao-hao.cn` 写法一致）。

---

## 2. 部署前准备清单

| 项 | 说明 |
|----|------|
| 百度云 BCC 公网 IP | 记下，用于 DNS A 记录 |
| 安全组 | 入站：**22**（SSH）、**80**、**443**；**不要**对公网开放 3306/6379/8000 |
| 域名解析 | `yikuaikaixin.cn`、`www.yikuaikaixin.cn` → 服务器公网 IP（百度云 DNS 或域名服务商） |
| 代码仓库 | 服务器能 `git clone` / `git pull`（SSH key 或 HTTPS token） |
| 数据 | **新库**：在百度云装 MySQL 并 `alembic upgrade head`；**迁数据**：从阿里云 `mysqldump` 再导入 |
| 微信 | 小程序后台「服务器域名」增加 `https://yikuaikaixin.cn`；支付回调 URL 改为新域名（若启用支付） |

若阿里云 **`wang-hao-hao.cn` 仍在跑**：先决定是**切流量**（只留百度云）还是**双机并行**（小程序只改 `API_BASE_URL` 指向其一）。不要两台同时写同一库除非明确做主从/共享库。

---

## 3. 服务器初始化（Ubuntu）

SSH 登录后执行（root 或 sudo 用户）：

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip \
  nginx mysql-server redis-server certbot python3-certbot-nginx
```

### 3.1 MySQL

```bash
sudo mysql -e "CREATE DATABASE wandermeet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'wandermeet'@'localhost' IDENTIFIED BY '你的强密码';"
sudo mysql -e "GRANT ALL PRIVILEGES ON wandermeet.* TO 'wandermeet'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

### 3.2 Redis

默认本机 `127.0.0.1:6379` 即可。若设了 `requirepass`，`.env` 里填 `REDIS_PASSWORD`。

### 3.3 应用目录

```bash
sudo mkdir -p /opt/wander_meet
sudo chown "$USER":"$USER" /opt/wander_meet
cd /opt/wander_meet
git clone <你的仓库地址> .
# 或已有目录则 git pull
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
cp .env.example .env
# 编辑 .env（见 §5）
alembic upgrade head
```

---

## 4. systemd 服务（wandermeet）

创建 `/etc/systemd/system/wandermeet.service`：

```ini
[Unit]
Description=WanderMeet FastAPI
After=network.target mysql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/wander_meet
EnvironmentFile=/opt/wander_meet/.env
ExecStart=/opt/wander_meet/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

若代码目录属主是你自己的账号，可把 `User=` 改成该用户，并保证 `.env` 可读：

```bash
sudo chown -R www-data:www-data /opt/wander_meet
# 或保持你的用户，则 User=你的用户名
sudo systemctl daemon-reload
sudo systemctl enable wandermeet
sudo systemctl start wandermeet
sudo systemctl status wandermeet
curl -sS http://127.0.0.1:8000/api/v1/wm/health
```

---

## 5. 生产 `.env` 要点（yikuaikaixin.cn）

在 `/opt/wander_meet/.env` 中至少修改：

```bash
APP_ENV=prod
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

# 小程序/H5 来源（按实际前端域名补全，逗号分隔）
APP_CORS_ORIGINS=https://servicewechat.com,https://yikuaikaixin.cn

JWT_SECRET=<openssl rand -hex 32 生成>

MYSQL_HOST=127.0.0.1
MYSQL_USER=wandermeet
MYSQL_PASSWORD=<强密码>
MYSQL_DB=wandermeet

REDIS_HOST=127.0.0.1

# 上线务必 false
SMS_USE_MOCK=false
WX_MP_USE_MOCK=false

# 微信小程序（与公众平台一致）
WX_MP_APPID=<你的 AppID>
WX_MP_APPSECRET=<你的 Secret>

# 若启用微信支付，回调必须是公网 HTTPS 且已在商户平台配置
WECHAT_PAY_NOTIFY_URL=https://yikuaikaixin.cn/api/v1/wm/pay/wechat/notify
# 或沿用 YunGouOS：
# YUNGOU_NOTIFY_URL=https://yikuaikaixin.cn/api/v1/wm/pay/yungou/notify
```

**不要**把 `.env` 提交进 git。JWT、数据库密码与阿里云环境若共用同一业务，应使用**不同** `JWT_SECRET` 或接受换机后全员重新登录。

---

## 6. Nginx + HTTPS

创建 `/etc/nginx/sites-available/yikuaikaixin.cn`：

```nginx
server {
    listen 80;
    server_name yikuaikaixin.cn www.yikuaikaixin.cn;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yikuaikaixin.cn www.yikuaikaixin.cn;

    # certbot 会自动写入 ssl_certificate 行；首次可先只 listen 80 申请证书
    ssl_certificate     /etc/letsencrypt/live/yikuaikaixin.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yikuaikaixin.cn/privkey.pem;

    client_max_body_size 20m;

    location /api/v1/wm/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # 可选：根路径简单探活
    location = / {
        return 200 'WanderMeet API OK\n';
        add_header Content-Type text/plain;
    }
}
```

启用并重载：

```bash
sudo ln -sf /etc/nginx/sites-available/yikuaikaixin.cn /etc/nginx/sites-enabled/
sudo nginx -t
```

**首次申请证书**（域名已解析到本机且 80 可访问）：

```bash
sudo certbot --nginx -d yikuaikaixin.cn -d www.yikuaikaixin.cn
sudo systemctl reload nginx
```

验证：

```bash
curl -sS https://yikuaikaixin.cn/api/v1/wm/health
curl -sS https://yikuaikaixin.cn/api/v1/wm/health/deps
```

---

## 7. 日常发布

代码更新后在服务器：

```bash
cd /opt/wander_meet
APP_DIR=/opt/wander_meet SERVICE_NAME=wandermeet BRANCH=main bash scripts/deploy.sh
```

---

## 8. 小程序前端改 API 地址

`lv_ju/travel-together/src/api/config.js`（仓库已默认）：

```javascript
export const API_BASE_URL = 'https://yikuaikaixin.cn/api/v1/wm'
```

重新编译上传微信开发者工具 / 发版。

微信公众平台 → 开发 → 开发管理 → 开发设置 → **服务器域名**：

- request 合法域名：`https://yikuaikaixin.cn`
- 若用 uploadFile / downloadFile / socket，按实际接口一并配置

---

## 9. 百度云控制台注意点

| 项 | 建议 |
|----|------|
| 安全组 | 仅 22/80/443；源地址可限制 SSH 为你的办公 IP |
| 备案 | 大陆服务器 + `.cn` 域名通常需 **ICP 备案** 后才能稳定解析与 HTTPS 业务 |
| 快照 | 上线前对系统盘做快照；MySQL 用 `scripts/backup_mysql.sh` 定时备份 |
| 监控 | `systemctl status wandermeet`、Nginx error.log、`/api/v1/wm/health/deps` |

---

## 10. 与阿里云并存 / 迁移

| 场景 | 做法 |
|------|------|
| 只迁到百度云 | 阿里云停服前 `mysqldump` → 百度云 `mysql < dump.sql`；DNS 切到百度云 IP；小程序改 `API_BASE_URL` |
| 短期双机 | 两台各自 MySQL（数据不同步）或共用一台 RDS（`.env` 同 `MYSQL_HOST`） |
| 域名切换 | `yikuaikaixin.cn` 专用于百度云；旧域 `wang-hao-hao.cn` 可做 301 或保留并行 |

---

## 11. 故障排查

```bash
# 服务是否在听
ss -lntp | grep 8000
sudo journalctl -u wandermeet -n 80 --no-pager

# Nginx
sudo nginx -t
sudo tail -f /var/log/nginx/error.log

# 本机绕过 Nginx
curl -v http://127.0.0.1:8000/api/v1/wm/health/deps
```

常见错误：

- **502**：uvicorn 未启动或 `proxy_pass` 路径错误（应用路由前缀已是 `/api/v1/wm`，`proxy_pass` 用 `http://127.0.0.1:8000` 即可，不要多写一层路径）。
- **证书失败**：域名未解析、80 被占用、备案未通过导致外网访问异常。
- **微信登录失败**：`WX_MP_APPID/SECRET` 错误或小程序未配置新 request 域名。

---

## 12. 相关文件

- 一键部署：`scripts/deploy.sh`
- 环境变量模板：`.env.example`
- MySQL 备份：`scripts/backup_mysql.sh`
- 抖音小程序发布（分阶段，API 同域）：`doc/WanderMeet_抖音小程序发布步骤.md`
