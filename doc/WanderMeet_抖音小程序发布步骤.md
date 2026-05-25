# WanderMeet 抖音小程序发布步骤

更新时间：2026-05-23  
适用范围：前端 `lv_ju/travel-together`（uni-app）+ 后端 `wander_meet`（`https://yikuaikaixin.cn/api/v1/wm`）

---

## 进度总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| **一** | 平台与账号（抖音开放平台、小程序 AppID 等） | **已完成** |
| **二** | 工程配置（manifest、本地编译、抖音开发者工具） | **已完成** |
| **三** | 抖音一键登录（前后端） | **已完成**（短信登录后端已有，抖音端未单独做登录页） |
| **四** | 分享 / 定位 / 绑手机等平台差异 | **部分完成**（支付二期） |
| **五** | 抖音后台域名与权限 | **已完成**（域名已配置） |
| **六** | 构建、提审、发布 | **待做** |

---

## 背景与约束

| 项目 | 说明 |
|------|------|
| uni-app 平台名 | **`mp-toutiao`** |
| 编译命令 | `npm run dev:mp-toutiao` / `npm run build:mp-toutiao` |
| 后端 API | `https://yikuaikaixin.cn/api/v1/wm` |
| 抖音登录 | `tt.login` → `POST /auth/douyin/login`（见 `doc/dy_login.md`） |
| 绑手机 | 抖音端 **短信绑定** `POST /me/phone/bind-sms`（无授权取号） |
| 发布付费 | `PAY_PUBLISH_ENABLED=false`，**支付二期** |

---

## 第一阶段：平台与账号（已完成）

1. 抖音开放平台注册、小程序创建、主体认证  
2. AppID 已写入 `manifest.json` → `mp-toutiao.appid`  
3. 抖音开发者工具已安装  

AppSecret **仅配置在服务器** `.env`：

```bash
DY_MP_APPID=你的AppID
DY_MP_APPSECRET=你的Secret
DY_MP_USE_MOCK=false
```

部署后执行：`alembic upgrade head`（迁移 `20260523_0021` 增加 `users.dy_openid`）。

---

## 第二阶段：工程配置（已完成）

- `src/manifest.json`：`mp-toutiao.appid`、`urlCheck`、定位 `permission`  
- 编译：`npm run dev:mp-toutiao` → `dist/dev/mp-toutiao`  
- 抖音开发者工具导入上述目录  

---

## 第三阶段：抖音登录（已完成）

### 后端

- `POST /api/v1/wm/auth/douyin/login`  
- `app/services/douyin_miniapp.py`（code2session）  
- 用户字段 `dy_openid`  

### 前端

- `src/utils/douyinAuth.js`：`getTtLoginCode`、`trySilentDouyinLogin`  
- `src/pages/login/login.vue`：`MP-TOUTIAO` →「抖音一键登录」  
- `src/App.vue`：抖音静默登录  
- `src/api/wandermeet.js`：`loginByDouyin`  

登录后跳转与微信相同：`navigateAfterLogin` → 极简资料页或首页。

---

## 第四阶段：平台差异（部分完成）

| 能力 | 状态 |
|------|------|
| 抖音登录 | ✅ |
| 绑手机（短信） | ✅ `bind-phone.vue`；抖音无微信授权按钮 |
| 分享 | ✅ `onShareAppMessage`；朋友圈分享仅微信 |
| 定位 | ✅ `manifest` 已声明；业务仍用 `uni.getLocation` |
| 支付 | ⏳ 二期 |

---

## 第五阶段：抖音后台（已完成）

- request 合法域名：`https://yikuaikaixin.cn`  
- 隐私协议 / 用户协议与小程序内页面一致  

---

## 第六阶段：提审发布（待做）

1. 服务器配置 `DY_MP_*` 并 `alembic upgrade head`、`systemctl restart wandermeet`  
2. `npm run build:mp-toutiao`  
3. 抖音开发者工具上传 → 体验版内测（登录、绑手机、发活动、群聊）  
4. 提交审核 → 发布  

**MVP 自测清单**

- [ ] 抖音一键登录 → 完善资料 → 首页  
- [ ] 我的 → 绑定手机号（短信）  
- [ ] 浏览活动 / 进群聊 / 发布活动（无付费）  
- [ ] 分享活动卡片  

---

## 关联文档

- 抖音登录 API：`doc/dy_login.md`  
- 微信登录对照：`doc/wx_login.md`  
- 后端部署：`doc/WanderMeet_百度云部署_yikuaikaixin.md`  
- 前端说明：`../lv_ju/travel-together/README.md`
