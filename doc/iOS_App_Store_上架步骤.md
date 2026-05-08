# iOS App 上架（App Store）步骤

面向 **原生 iOS 工程（Xcode）** 首次上架的通用流程。若产品仅为**微信小程序**，则不需要走 App Store，只需在微信公众平台完成小程序提审与发布。

---

## 一、前置条件

1. **Mac + 最新版 Xcode**（与目标 iOS 版本匹配）。
2. **Apple ID**，并加入 **Apple Developer Program**（[developer.apple.com](https://developer.apple.com) 付费会员，按年续费）。
3. 应用已完成开发与自测；上架包须符合 **App Store 审核指南**（内容、隐私、账号登录说明等）。

---

## 二、开发者后台准备

1. 登录 [App Store Connect](https://appstoreconnect.apple.com)。
2. **创建 App**
   - 「我的 App」→「+」→ 填写名称、主要语言、Bundle ID（须先在开发者网站的 **Identifiers** 里创建并与 Xcode 一致）、SKU（内部编号，可自拟）。
3. **Certificates, Identifiers & Profiles**（[developer.apple.com/account](https://developer.apple.com/account)）
   - 确认 **App ID**、**推送/Associated Domains** 等能力与工程勾选一致。
   - 通常在 Xcode **Automatically manage signing** 下由 Xcode 自动维护证书与描述文件；若手动签名再导出分发证书。

---

## 三、工程内配置（Xcode）

1. 选中 Project → **Signing & Capabilities**
   - 勾选 **Automatically manage signing**，Team 选你的开发团队；**Bundle Identifier** 与 App Store Connect 中一致。
2. **Version**（用户可见版本号，如 1.0.0）与 **Build**（每次提交递增的构建号，如 1、2、3…）。
3. 配置 **Info.plist** 中各类 **Usage Description**（相机、相册、定位、蓝牙等，缺了会在审核或运行期被拒/崩溃）。
4. 若需 **App 加密出口合规**：在 App Store Connect 或提交时按实际情况回答（多数仅 HTTPS 的 App 选「否」或按向导填写）。

---

## 四、Archive 与上传

1. 在 Xcode 顶部将运行目标选为 **Any iOS Device (arm64)** 或真机，勿选模拟器进行 Archive。
2. 菜单 **Product → Archive**，等待完成。
3. 在 **Organizer** 中选中该 Archive → **Distribute App** → **App Store Connect** → 按向导上传（可勾选 **Upload** 后由 App Store Connect 处理符号表等选项）。
4. 上传完成后，在 **App Store Connect** → 该 App → **TestFlight** 中等待处理（约数分钟到数十分钟），出现可测构建即表示处理成功。

---

## 五、TestFlight（建议）

1. 在 TestFlight 添加**内部测试员**（同组织成员）或**外部测试员**（需简单审核）。
2. 安装 **TestFlight** App，用邀请链接或邮件安装，做最后一轮真机验证。

---

## 六、填写商店信息与送审

在 App Store Connect 中进入该 App 的 **App 信息 / 价格与销售范围**：

1. **截屏与预览视频**：按各机型尺寸要求上传（可参阅苹果当期文档）。
2. **描述、关键词、支持 URL、营销 URL**（可选）、**隐私政策 URL**（涉及收集数据时通常必填）。
3. **App 隐私**：按清单申报收集的数据类型与用途（须与真实行为一致）。
4. **分类、年龄分级、版权** 等按提示填写。
5. **构建版本**：在「版本」页选择已通过处理的 **构建记录**，保存。
6. 点击 **提交以供审核**；若有 **出口合规、广告标识符（IDFA）、内容版权** 等问题，按表单如实作答。

---

## 七、审核与发布

1. 状态会经历「等待审核」→「正在审核」→「待开发者发布」或「被拒绝」。
2. **通过**后可在 App Store Connect 选择 **手动发布**或**自动发布**。
3. **被拒**：阅读 Resolution Center 说明，修改工程或元数据，必要时提升 Build 号重新 Archive 上传，再次提交。

---

## 八、常见注意点

- 每次重新上传商店构建，**Build 号必须递增**，Version 可按产品节奏调整。
- **登录方式**：若提供第三方登录，通常需同时提供苹果要求的同等替代方案（如 **Sign in with Apple**，在一定条件下强制）。
- **元数据与二进制一致**：截图、描述勿夸大或与 App 实际功能不符。
- 涉及 **用户生成内容（UGC）** 的 App，审核常关注举报、屏蔽、审核机制说明。

---

## 九、官方文档入口（备查）

- [App Store Connect 帮助](https://developer.apple.com/help/app-store-connect/)
- [App 审核指南](https://developer.apple.com/app-store/review/guidelines/)
- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)

---

*文档用于团队内部备忘；具体表单与规则以 Apple 当时官网为准。*
