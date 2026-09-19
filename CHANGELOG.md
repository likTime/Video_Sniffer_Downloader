# 更新日志

本项目所有值得记录的版本变更。版本号遵循 `主版本.次版本.修订号` 格式。

> 程序内「更新日志」按钮展示的内容与此文件保持同步。

---

## [v1.9.3] - 2026-09-12

### 主题：412 风控修复 + 私人 Cookie 移除 + DASH 三阶段进度条

#### 修复
- **修复 B 站返回 `412 Client Error: Precondition Failed`**：B 站风控检测到旧版 Chrome/91 User-Agent 与缺失 `buvid3` Cookie 时返回 412。统一升级所有请求头 User-Agent 至 Chrome/138，并新增 `Sec-Fetch-*` 浏览器标准请求头
- `_download_video` 中 B 站 CDN 请求头的 `buvid3` fallback 改为运行时生成，不再硬编码设备指纹

#### 安全
- **移除硬编码的私人 Cookie**（SESSDATA 等登录凭据），改为运行时生成 `buvid3`；解锁高清画质改为通过 `USER_SESSDATA` 变量填入

#### 新增
- `ensure_bilibili_cookies()`：运行时自动生成随机 `buvid3` 设备指纹（UUID 格式 + `infoc` 后缀），请求 B 站页面前自动确保其存在
- `refresh_bilibili_cookies()`：412 错误时自动访问 B 站首页刷新 Cookie 后重试
- `scan_website` 页面请求与 API 请求均新增 412 重试逻辑
- `DownloadProgressWindow.set_combined_progress()`：支持跨阶段进度与阶段文字

#### 优化
- **DASH 下载三阶段平滑进度条**：重写 `download_bilibili_dash` 进度逻辑，划分为视频流下载（0%–45%）、音频流下载（45%–90%）、ffmpeg 合并（90%–100%）三阶段，进度条平滑递增不再跳跃
- 每个 chunk 都更新进度，进度条附近实时显示当前阶段标签
- 合并完成 / 失败 / 异常均有对应的进度条终态，窗口 2 秒后自动关闭

---

## [v1.9.2] - 2026-08-10

### 主题：FFmpeg 下载增强 + 已有文件合并功能

#### 修复
- 修复 FFmpeg 自动下载在国内失败：添加 4 个下载源（GitHub 直连 + 3 个国内镜像 `ghfast.top` / `gh-proxy.com` / `mirror.ghproxy.com`），依次尝试直到成功
- 修复 FFmpeg 下载进度不可见：所有 `print()` 改为 `log_message()`，可在 GUI 日志区实时看到进度与错误
- 修复大文件下载到内存导致失败：改为下载到临时文件 `ffmpeg_download.zip`，解压后自动清理

#### 新增
- 新增「合并已有文件」按钮：扫描下载目录中文件名含 `_音频` 的文件，自动匹配对应视频文件并用 ffmpeg 合并（同时嵌入封面），合并成功后删除原始分片文件
- `ensure_ffmpeg_available()` 失败时显示手动下载提示

---

## [v1.9.1] - 2026-08-10

### 主题：标题提取增强 + 封面嵌入修复

#### 修复
- 修复视频标题获取失败导致文件名用数字编码：新增从 HTML `<title>` 标签提取标题的备选方案（INITIAL_STATE 提取失败时自动回退），自动去除 `_哔哩哔哩_bilibili` 等后缀
- 修复封面图片未嵌入视频文件：封面下载提前到 `download_bilibili_dash` 调用之前执行，封面路径作为参数传入；ffmpeg 合并命令增加第三个输入（`-i cover.jpg`）与 `-map` / `-disposition` 参数，将封面作为 `attached_pic` 嵌入 MP4

#### 优化
- 移除重复的封面下载代码，合并为一次

---

## [v1.9.0] - 2026-08-10

### 主题：记忆功能 + FFmpeg 自动下载 + 路径 BUG 修复

#### 新增
- **配置文件记忆功能**：程序退出时自动保存下载路径与最近 200 条日志到 `downloader_config.json`，下次启动自动恢复下载路径并显示上次历史日志（最近 30 条）
- **FFmpeg 自动下载**：首次使用 B 站 DASH 下载时若未检测到 ffmpeg，自动下载 `ffmpeg.exe` 到脚本目录（约 80MB，仅需一次）

#### 修复
- **修复致命 BUG**：`download_bilibili_dash` 中使用未定义的 `download_path_var.get()`，导致 B 站 DASH 视频下载到错误的「下载的视频」目录而非用户选择的路径。改为直接使用全局 `DOWNLOAD_DIR`
- `is_ffmpeg_available()` 改为优先检查系统 PATH、其次检查脚本目录 `ffmpeg.exe`，兼容两种安装方式
- ffmpeg 合并命令改用获取到的完整路径，确保本地下载的 `ffmpeg.exe` 能被正确调用

---

## [v1.8.2] - 2026-07-31

### 主题：captured_urls BUG 再次修复 + URL 修复增强

#### 修复
- 修复 `captured_urls` 提前 add 导致 `download_bilibili_dash` 回退分支的 `download_video` 被跳过的 BUG（第三次出现同类问题）。在 `scan_website` 调用 `download_bilibili_dash` 前不再 `captured_urls.add`，让 `download_video` 内部自行管理去重
- 修复 URL 域名修复逻辑：`www.bilibilicom`（`www.` 后面缺少点）不会被修复。新增第三个判断条件：`domain.startswith('www.')` 且 `domain[4:]` 不含点时也进入修复分支

---

## [v1.8.1] - 2026-07-31

### 主题：流选择精度优化

#### 优化
- DASH 流选择改用 `bandwidth`（码率）字段排序，替代之前的 URL 画质码排序。`bandwidth` 是 B 站 API 返回的真实码率值，比 URL 中提取的画质码更准确
- 视频流选择日志增强：显示分辨率、码率、编码格式、帧率等完整信息
- 音频流选择也改用 `bandwidth` 排序
- 添加画质等级中文显示（720P / 1080P / 4K 等），替代原来的纯数字 `qn=64`
- 未登录时自动提示「最高仅 720P，填入 SESSDATA 可解锁 1080P/4K」
- Cookie 配置处添加详细注释，指导用户获取并填入 SESSDATA

---

## [v1.8.0] - 2026-07-31

### 主题：DASH 合并 + 扩展名修复

#### 修复
- **修复「下载全是模糊的 m4a」的致命 BUG**：B 站 CDN 返回的 Content-Type 是 `application/octet-stream`，不含 `video` 也不含 `mp4`，导致所有 `.m4s` 视频流被误判为音频存成 `.m4a`。现在根据 URL 中的流 ID 判断：`30xxx`=视频流→`.mp4`，`302xx`=音频流→`.m4a`
- 修复 B 站请求头中的假 Cookie：移除 `SESSDATA=1234567890abcdef` 等伪造值，改为从 `session.cookies` 获取真实的 `buvid3`
- 新增 B 站 CDN 域名 `bilivideo.cn` 支持（此前只匹配了 `bilivideo.com`）

#### 新增
- **ffmpeg 自动合并功能**：B 站 DASH 格式视频与音频是分离的两个 `.m4s` 文件，此前分别下载导致用户拿到无声视频 + 独立音频。新增 `download_bilibili_dash()`，先下载视频流与音频流到临时目录，再用 ffmpeg 合并为完整 `.mp4`（`-c copy` 无损无重编码），合并后自动删除临时文件
- ffmpeg 不可用时自动回退为分别下载两个文件，并提示用户安装
- 合并失败容错：ffmpeg 合并失败时保留视频流文件（无声），确保至少能拿到画面

---

## [v1.7.0] - 2026-07-31

### 主题：日志体验优化

#### 修复
- 修复点击「扫描网站」按钮后无即时反馈：现在点击后立即在日志区显示 `[+] 开始扫描网站: xxx`（蓝色高亮），状态栏同步显示「正在扫描网站...」，避免用户误以为没反应而重复点击导致批量下载

#### 优化
- 日志系统从队列批量消费改回 `root.after(0)` 逐条渲染，每条日志立即显示
- **日志颜色分级**：成功信息（下载完成 / 扫描完成 / 封面保存）=绿色、错误信息（失败 / 错误）=红色、警告信息（跳过 / 非视频）=橙色、关键操作（开始扫描 / 检测到 / 提取到 / 开始监控）=蓝色
- `scan_website` 内部的「开始扫描网站」改为「正在连接」（详细日志），避免与按钮点击的即时提示重复

---

## [v1.6.2] - 2026-07-31

### 主题：致命 BUG 修复

#### 修复
- **修复「只下载了封面，视频下不了」的致命 BUG**：在调用 `download_video` 之前就执行了 `captured_urls.add(url)`，导致其内部 `if url in captured_urls: return` 直接跳过。已移除所有调用前的 `captured_urls.add`，由 `download_video` 内部统一管理去重
- **修复 DASH 画质选到 AV1 编码（10xxx）**：B 站 DASH 有三种编码（AVC=30xxx / HEVC=12xxx / AV1=10xxx），此前按画质码数字大小排序，`100023`(AV1) > `30116`(1080P60)，导致选了大部分播放器打不开的 AV1。新增 `sort_key_video()` 按（编码优先级, 画质码）排序，AVC(H.264) 优先级最高
- `pick_best_playinfo_streams` 同步修复：视频流候选也按 AVC > HEVC > AV1 优先级排序

---

## [v1.6.1] - 2026-07-31

### 主题：性能与稳定性优化版（不阉割任何现有功能）

#### 修复
- 修复「扫描网站」按钮点击后界面「未响应」/崩溃的根因：按钮直接在主线程跑 `requests.get` + HTML 解析，阻塞 Tk 事件循环；改为投入后台线程执行
- 修复「剪贴板监控」跨线程访问 Tk 导致的偶发崩溃：`start_monitoring` 改为通过 `root.after(400)` 在主线程轮询，完全符合 Tkinter 线程模型
- 修复 `log_message()` 在下载/扫描线程直接写 Text/Status 控件导致的随机卡死：引入生产者-消费者队列，渲染统一回到主线程
- 修复 `DownloadProgressWindow.update_progress/set_status` 在工作线程直接 `.config()` 导致的偶发白屏：进度/状态写入也通过 `window.after(0, apply)` 切回主线程

#### 优化
- 移除 `check_clipboard` 内部重复的 `import threading`，轮询间隔从 300ms 放宽到 500ms，CPU 占用显著下降
- 把 `VIDEO_PATTERNS` / B 站页面匹配 / m4s 画质码匹配三个高频正则提前编译为 `_COMPILED_*` 对象，去掉每次调用的 `re.compile` 开销
- 去掉 `DownloadProgressWindow` 的 `update_idletasks()` 同步刷新，改由 `after` 异步刷新，避免忙等拉慢主线程

---

## [v1.6.0] - 2026-07-31

#### 修复
- 修复 DASH m4s 格式被误判为「非视频文件」：新增白名单——扩展名（`.m4s`/`.m4a`/`.ts`）、CDN 域名（`bilivideo.cn`/`bilivideo.com`/`upos-sz`/`akamaized.net`）、Content-Type（`audio`/`octet-stream`/`mp2t`/`mp4a`/`mp4v`）
- 修复 DASH 画质选择 BUG：此前用接口返回的 `id` 字段排序（32=360P 最差画质被误选为「最高」），现在用 URL 中的真实画质码（30080=1080P / 30116=1080P60 / 30120=4K）排序
- 修复 `__playinfo__` 提取 9 个冗余链接全部下载：新增 `pick_best_playinfo_streams()` 只挑最佳视频 + 最佳音频；`playinfo` 变为 API 失败后的回退方案
- 剪贴板监控逻辑修正：`start_monitoring()` 时先记录当前剪贴板内容为基准，只有监控启动后新复制的链接才自动触发下载

#### 新增
- 进度窗口显示逻辑与触发来源绑定：`scan_website` 新增 `from_clipboard` 参数，只有剪贴板监控触发的下载才弹出独立小窗口；手动扫描时使用主界面进度条
- URL 输入框支持回车键直接触发扫描网站

---

## [v1.5.0] - 2026-07-28

#### 新增
- B 站视频标题自动提取（从 `INITIAL_STATE` 的 `videoData` 中获取）
- 下载的视频文件自动以 B 站原视频标题命名（自动清理非法文件名字符）
- DASH 音频流文件名自动追加 `_音频` 后缀以区分
- B 站视频封面自动下载，保存为 JPG 格式，文件名与视频标题一致
- `download_video` 新增 `custom_filename` 参数支持自定义文件名

---

## [v1.4.0] - 2026-07-28

#### 新增
- B 站最高画质提取，支持 1080P60 / 4K / 8K / HDR / 杜比视界
- API 请求参数升级：`qn=127`（最高画质）+ `fnval=4048`（DASH 全格式）+ `fourk=1`
- DASH 视频流智能选择：自动挑选最高画质视频流
- DASH 音频流智能选择：自动挑选最高质量音频流
- 不再下载所有画质，只下载最佳视频 + 最佳音频，避免冗余文件
- 新增画质信息日志输出，显示可用画质列表与当前画质等级

---

## [v1.3.0] - 2026-07-28

#### 新增
- 剪贴板监控支持 B 站视频页面链接（含 BV 号 / AV 号）
- 复制 B 站视频页面 URL 后自动触发下载，无需手动扫描
- B 站视频下载时自动弹出独立进度窗口
- `scan_website` 支持外部 URL 参数传入
- 所有 B 站视频流下载均显示进度窗口和实时网速

---

## [v1.2.0] - 2026-01-30

#### 新增
- 下载进度条功能，实时显示下载进度
- 下载信息显示，包括总大小（MB）、已下载量（MB）和下载速度（MB/s）

#### 优化
- 进度条重置机制：下载完成或失败时自动重置
- 下载信息标签重置机制，确保下载状态正确显示
- 改进 B 站视频流链接提取逻辑，提高视频识别率
- 增强下载速度计算精度

#### 修复
- 修复 B 站视频处理时详细信息显示问题，将详细参数隐藏到详细日志

---

## [v1.1.0] - 2025-12-27

#### 新增
- 状态栏显示关键操作信息
- 详细日志按钮，点击查看完整日志

#### 优化
- UI 界面布局优化，窗口大小调整为 800x400
- 日志显示逻辑优化，区分关键信息和详细参数
- 增强响应内容验证和错误处理

#### 修复
- 修复 B 站视频下载 403 错误问题

---

## [v1.0.5] - 2025-12-25

- 重写为 GUI 界面
- 添加模拟浏览器请求头
- 基于 Scapy 库的网络数据包捕获
- 支持视频流 URL 提取和下载
- 优化视频 URL 检测逻辑
- 改进文件名生成算法
- 添加文件大小检查，过滤无效文件
- 优化日志显示，支持点击打开文件
- 改进错误处理机制

---

## [v1.0.0] - 2025-12-01

首个版本发布

- B 站视频下载功能
- 快手视频下载功能
- 剪贴板监控功能
- 网站扫描功能
- 多线程下载功能
- 文件完整性检查功能
- 自定义下载路径功能
- 更新日志功能

---

[Unreleased]: https://github.com/likTime/Video_Sniffer_Downloader/compare/main...HEAD
