# 嗅觉视频下载器 (Video Sniffer Downloader)

*Note: English version is available below. / 注意：下方有英文版本*

### 项目简介

视频嗅探下载器是一个功能强大的视频下载工具，能够通过监控剪贴板或扫描网站自动检测并下载视频。支持多种视频格式和主流视频平台，提供直观的GUI界面和实时下载进度显示

功能特点

***·自动剪贴板监控***：实时监控剪贴板，自动检测并下载复制的视频链接

***·智能网站扫描***：扫描指定网站，提取页面中的所有视频链接

***·多平台支持***：支持B站、抖音、优酷、爱奇艺、腾讯视频、芒果TV、西瓜视频、快手等主流平台

***·多种视频格式***：支持mp4、mkv、avi、flv、wmv、mov、webm、m3u8等格式

***·实时进度显示***：显示下载进度、文件大小和下载速度

***·智能反爬绕过***：模拟浏览器请求头，绕过部分网站的反爬机制

***·自定义下载路径***：支持选择自定义下载目录

***·友好GUI界面***：简洁直观的用户界面，操作便捷

## 安装说明

#### 系统要求

·Python 3.7+/普通用户（无需Python编译器，下载exe.版本）

·Windows 10/11 (推荐) 或 Linux/macOS

#### 依赖安装

```pip install -r requirements.txt```

### 快速开始

##### 1. 克隆项目到本地
```git clone https://github.com/likTime/Video_Sniffer_Downloader.git```

```cd Video_Sniffer_Downloader```


##### 2. 安装依赖
```pip install -r requirements.txt```

##### 3. 运行程序
```python 嗅觉视频下载器1.9.3.py```

### 使用方法

#### 方法一：剪贴板监控

1.点击"开始监控剪贴板"按钮

2.复制任意视频链接到剪贴板

3.程序自动检测并开始下载
#### 方法二：网站扫描

1.在URL输入框中输入网站地址

2.点击"扫描网站"按钮

3.程序自动提取页面中的视频链接并下载

### 自定义设置
***·下载路径***：点击"选择下载路径"按钮设置保存目录
***·查看日志***：点击"详细日志"查看完整操作记录
***·更新信息***：点击"更新日志"查看版本更新历史

### 技术架构
```视频嗅探下载器/
├── 核心功能模块
│   ├── 剪贴板监控 (pyperclip)
│   ├── 网络请求 (requests)
│   ├── 链接解析 (正则表达式)
│   └── 多线程下载
├── GUI界面
│   ├── tkinter主窗口
│   ├── 进度条显示
│   ├── 实时日志
│   └── 状态栏
└── 平台适配
    ├── 各视频平台解析器
    ├── 请求头模拟
    └── 错误处理机制
```
## 工作原理

1.  **链接捕获**：通过监控剪贴板或扫描网页HTML内容，利用预定义的正则表达式模式匹配视频流URL。
2.  **请求模拟**：添加完整的浏览器请求头（User-Agent, Referer, Cookie等），模拟真实浏览器行为，以绕过简单的反爬虫机制。
3.  **流媒体识别**：通过检查HTTP响应头中的`Content-Type`和URL文件扩展名，验证链接是否为有效的视频流。
4.  **分块下载**：使用HTTP流式下载，将大文件分割为多个块（Chunk）进行传输，支持断点续传（通过`Range`头）。
5.  **实时更新**：在主线程中通过Tkinter的变量（`DoubleVar`, `StringVar`）实时更新进度条和下载信息标签。
6.  **文件保存**：根据当前时间戳和源URL信息生成唯一文件名，并将数据写入本地文件系统。

## 常见问题 (FAQ)

**Q: 扫描网站时出现"412 Client Error"或"403 Forbidden"错误怎么办？**

**A:** 程序已内置模拟浏览器请求头，但某些网站的反爬策略较强。
*   v1.9.3 已针对性修复 B 站 412 风控问题：统一升级请求头至 Chrome/138 并自动生成 `buvid3` 设备指纹，命中 412 时会自动刷新 Cookie 重试。若仍遇到 412，建议升级到最新版。
*   确保输入的URL格式正确（包含`http://`或`https://`）。
*   程序会自动尝试修复常见的域名格式错误（如`wwwbilibilicom` -> `www.bilibili.com`）。
*   网络环境或目标网站暂时不可访问。

**Q: 下载的视频文件无法播放或文件大小异常小？**

**A:** 程序具备文件完整性检查功能。如果文件小于1MB或远小于预期大小，会自动将其识别为无效文件并删除。请确保源视频链接有效且可公开访问。

**Q: 如何下载B站、抖音等需要登录才能观看的视频？**

**A:** 当前版本主要针对公开可访问的视频内容。对于需要登录或会员的视频，程序内置的通用请求头可能权限不足。您可以尝试手动复制视频链接到剪贴板使用监控下载功能，有时可直接获取到视频流。

**Q: 下载 B 站视频时提示"最高仅 720P"？**

**A:** 这是 B 站对未登录用户的画质限制，并非程序缺陷。如需下载 1080P/4K，请在源码中 `USER_SESSDATA` 变量处填入你自己浏览器中的 `SESSDATA` 值（源码注释中有详细获取步骤）。

**Q: 首次下载 B 站视频时程序看起来卡住了？**

**A:** 程序正在自动下载 ffmpeg（约 80MB，仅需一次，用于合并 B 站 DASH 格式的分离视频流与音频流）。国内网络若直连 GitHub 失败，会自动切换 3 个国内镜像源重试，请在日志区查看实时进度。

**Q: 程序无法启动或缺少模块？**

**A:** 请确保已正确安装`requirements.txt`中的所有依赖（`requests`, `pyperclip`）。如果使用Linux系统，可能还需要安装Tkinter相关包（例如在Ubuntu上：`sudo apt-get install python3-tk`）。

## 更新日志

### 最新版本：v1.9.3 (2026-09-12)

**412风控修复 + 私人Cookie移除 + DASH三阶段进度条**

*   修复 B 站 `412 Client Error: Precondition Failed` 风控拦截：统一升级请求头至 Chrome/138，运行时自动生成 `buvid3` 设备指纹，412 时自动刷新 Cookie 重试
*   移除硬编码的私人 Cookie（SESSDATA 等登录凭据），如需高清画质改为在 `USER_SESSDATA` 变量中自行填入
*   DASH 下载三阶段平滑进度条：视频流(0%-45%) → 音频流(45%-90%) → ffmpeg合并(90%-100%)

### 历史版本

*   **v1.9.2 (2026-08-10)**: FFmpeg 下载增强（4 个下载源含国内镜像）；新增"合并已有文件"按钮
*   **v1.9.1 (2026-08-10)**: 修复标题提取失败（改用 `<title>` 备选方案）；修复封面未嵌入视频
*   **v1.9.0 (2026-08-10)**: 新增配置记忆功能与 FFmpeg 自动下载；修复下载路径 BUG
*   **v1.8.0 (2026-07-31)**: 新增 ffmpeg 自动合并，修复视频流被误存为 `.m4a` 的致命 BUG
*   **v1.7.0 (2026-07-31)**: 日志颜色分级显示；修复"扫描网站"按钮无即时反馈
*   **v1.6.x (2026-07-31)**: 修复界面卡死/崩溃（线程模型重构）；修复 AV1 编码选择问题
*   **v1.5.0 (2026-07-28)**: 新增 B 站视频标题与封面自动下载
*   **v1.4.0 (2026-07-28)**: 新增 B 站最高画质提取（1080P60/4K/8K/HDR）
*   **v1.3.0 (2026-07-28)**: 剪贴板监控支持 B 站视频页面链接
*   **v1.2.0 (2026-01-30)**: 新增下载进度条与实时速度显示；优化B站视频解析逻辑。
*   **v1.1.0 (2025-12-27)**: 优化UI布局；增强日志系统；修复B站403错误。
*   **v1.0.5 (2025-12-25)**: 重写为GUI界面；添加剪贴板监控与网站扫描功能。
*   **v1.0.0 (2025-12-01)**: 初始版本发布，支持基础视频流下载。

（完整更新内容请查看 [CHANGELOG.md](CHANGELOG.md)，或点击程序内的"更新日志"按钮。）

##下载

•如需查看或修改源码，可下载 `.py` 源码版本

•**最新源码为 `嗅觉视频下载器1.9.3.py`**，旧版 `嗅觉视频下载器 (Video Sniffer Downloader).py` 仅作版本对照

•普通用户请直接下载 `.exe` 版本（无需安装 Python 环境）

## 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目。对于新视频平台的支持或功能建议尤其欢迎。

## 免责声明

本工具仅供学习和研究目的使用。请尊重版权，仅下载您拥有合法权限或授权下载的视频内容。使用者应对其下载行为负责，作者不承担任何法律责任。

## 作者

*   **李健辉 (likTime)** - [GitHub主页](https://github.com/likTime)

    **邮箱**：3849730216@qq.com
---

**如果觉得这个项目对你有帮助，请给它一个Star！⭐**



# Video Sniffer Downloader

## Project Introduction

Video Sniffer Downloader is a powerful video downloading tool that can automatically detect and download videos by monitoring the clipboard or scanning websites. It supports multiple video formats and mainstream video platforms, providing an intuitive GUI interface and real-time download progress display.

## Features

• **Automatic Clipboard Monitoring**: Real-time clipboard monitoring, automatically detects and downloads copied video links

• **Intelligent Website Scanning**: Scans specified websites to extract all video links from the page

• **Multi-Platform Support**: Supports Bilibili, Douyin, Youku, iQiyi, Tencent Video, Mango TV, Xigua Video, Kuaishou and other mainstream platforms

• **Multiple Video Formats**: Supports mp4, mkv, avi, flv, wmv, mov, webm, m3u8 and other formats

• **Real-time Progress Display**: Shows download progress, file size and download speed

• **Smart Anti-Scraping Bypass**: Simulates browser headers to bypass anti-scraping mechanisms

• **Custom Download Path**: Supports selecting custom download directory

• **User-Friendly GUI**: Simple and intuitive user interface, easy to operate

## Installation Instructions

#### System Requirements
• Python 3.7/ For regular users (No Python compiler required, download the .exe version)
• Windows 10/11 (Recommended) or Linux/macOS

#### Dependency Installation

```pip install -r requirements.txt```

### Quick Start

#### 1. Clone the repository

```git clone https://github.com/likTime/Video_Sniffer_Downloader.git```

```cd Video_Sniffer_Downloader```

#### 2. Install dependencies

```pip install -r requirements.txt```

#### 3. Run the program

```python 嗅觉视频下载器1.9.3.py```

## Usage

#### Method 1: Clipboard Monitoring
1. Click "Start Monitoring Clipboard" button
2. Copy any video link to clipboard
3. Program automatically detects and starts downloading

#### Method 2: Website Scanning
1. Enter website URL in URL input box
2. Click "Scan Website" button
3. Program automatically extracts video links from page and downloads them

## Custom Settings
• **Download Path**: Click "Select Download Path" to set save directory
• **View Logs**: Click "Detailed Logs" to view complete operation history
• **Update Info**: Click "Update Log" to view version update history

## Technical Architecture

```Video-Sniffer-Downloader/

├── Core Modules

│   ├── Clipboard Monitoring (pyperclip)

│   ├── Network Requests (requests)

│   ├── Link Parsing (Regular Expressions)

│   └── Multi-threaded Downloading

├── GUI Interface

│   ├── tkinter Main Window

│   ├── Progress Bar Display

│   ├── Real-time Logs

│   └── Status Bar

└── Platform Adaptation

├── Video Platform Parsers

├── Request Header Simulation

└── Error Handling
```

## How It Works

1. **Link Capture**: Monitor clipboard or scan webpage HTML, use regex patterns to match video URLs
2. **Request Simulation**: Add browser headers to simulate real browser behavior
3. **Stream Identification**: Verify links by checking Content-Type and file extensions
4. **Chunked Downloading**: Download in chunks with resume support (Range header)
5. **Real-time Updates**: Update progress using Tkinter variables
6. **File Saving**: Generate unique filenames and save to local storage

## FAQ

**Q: Getting "412 Client Error" or "403 Forbidden" when scanning websites?**

**A:** The program has built-in browser headers, but some sites have strong anti-scraping.
• v1.9.3 specifically fixes Bilibili 412 errors: request headers upgraded to Chrome/138 and a random `buvid3` device fingerprint is generated at runtime, with automatic Cookie refresh and retry on 412. Please upgrade to the latest version.
• Ensure correct URL format (http:// or https://)
• Program auto-fixes common domain format errors
• Check network/target site accessibility

**Q: Downloaded video won't play or file is too small?**

**A:** Program checks file integrity. Files <1MB or significantly smaller than expected are auto-deleted.

**Q: How to download login-required videos?**

**A:** Current version targets publicly accessible content. For member-only videos, try copying direct video links to clipboard.

**Q: Why does it say "720P maximum" when downloading Bilibili videos?**

**A:** This is Bilibili's limitation for non-logged-in users, not a program defect. To download 1080P/4K, fill in your own `SESSDATA` value at the `USER_SESSDATA` variable in the source code (see the detailed instructions in the code comments).

**Q: The program appears frozen on the first Bilibili download?**

**A:** It is automatically downloading ffmpeg (~80MB, one-time only) to merge Bilibili's separated DASH video and audio streams. If GitHub is unreachable, it automatically retries via 3 domestic mirrors — check the log area for real-time progress.

**Q: Program won't start or missing modules?**

**A:** Ensure all dependencies in requirements.txt are installed. On Linux, may need: 
```sudo apt-get install python3-tk```

## Changelog

### Latest: v1.9.3 (2026-09-12)

**Bilibili 412 fix + private Cookie removal + 3-stage DASH progress bar**

• Fixed Bilibili `412 Client Error: Precondition Failed`: headers upgraded to Chrome/138, runtime-generated `buvid3` fingerprint, automatic Cookie refresh and retry on 412
• Removed hardcoded private Cookies (SESSDATA etc.); HD quality is now unlocked by filling in your own `USER_SESSDATA`
• Smooth 3-stage DASH progress bar: video stream (0%-45%) → audio stream (45%-90%) → ffmpeg merge (90%-100%)

### Previous versions

• **v1.9.2 (2026-08-10)**: Enhanced FFmpeg download (4 sources incl. mirrors); added "Merge Existing Files" button
• **v1.9.1 (2026-08-10)**: Fixed title extraction (fallback to `<title>`); fixed cover not embedded in video
• **v1.9.0 (2026-08-10)**: Added config memory and automatic FFmpeg download; fixed download path bug
• **v1.8.0 (2026-07-31)**: Added automatic ffmpeg merging; fixed critical bug where video streams were saved as `.m4a`
• **v1.7.0 (2026-07-31)**: Color-coded logs; fixed missing feedback on "Scan Website"
• **v1.6.x (2026-07-31)**: Fixed UI freeze/crash (threading model rewrite); fixed AV1 codec selection
• **v1.5.0 (2026-07-28)**: Added automatic Bilibili title and cover download
• **v1.4.0 (2026-07-28)**: Added Bilibili max quality extraction (1080P60/4K/8K/HDR)
• **v1.3.0 (2026-07-28)**: Clipboard monitoring supports Bilibili video page links
• **v1.2.0 (2026-01-30)**: Added progress bar and speed display; optimized Bilibili parsing

• **v1.1.0 (2025-12-27)**: Improved UI; enhanced logs; fixed Bilibili 403 errors

• **v1.0.5 (2025-12-25)**: GUI version; added clipboard monitoring and website scanning

• **v1.0.0 (2025-12-01)**: Initial release with basic video downloading

(For full details, see [CHANGELOG.md](CHANGELOG.md) or click the "Update Log" button in the program.)

##Download

•For source code viewing or modification, download the `.py` source version

•**The latest source is `嗅觉视频下载器1.9.3.py`**; the older `嗅觉视频下载器 (Video Sniffer Downloader).py` is kept for version reference only

•For regular users, please download the `.exe` version directly (no Python environment required)

## Disclaimer

This tool is for learning and research only. Respect copyrights and only download content you have rights to. Users are responsible for their activities.

Translated by DeepSeek. Please email me if you find any errors.

## Author

**Li Jianhui** ([likTime](https://github.com/likTime) on GitHub)  
**Email**: 3849730216@qq.com

---

**If this project helps you, please give it a Star! ⭐**
