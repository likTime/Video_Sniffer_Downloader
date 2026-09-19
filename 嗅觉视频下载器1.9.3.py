# 视频嗅探下载器 v1.9.3
# 作者：李健辉
# 功能：通过监控网络请求，分析视频流，提取URL并下载

import requests
from requests.adapters import HTTPAdapter
import re
import os
import subprocess
import shutil
import json
import zipfile
import io
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import threading
import time

# 视频流协议的正则表达式（优化版，支持国内主流视频平台）
# 支持的平台：B站、抖音、优酷、爱奇艺、腾讯视频、芒果TV、西瓜视频、快手
VIDEO_PATTERNS = [
    r'\.(mp4|mkv|avi|flv|wmv|mov|webm)(\?.*)?$',  # 常见视频格式
    r'\.m3u8(\?.*)?$',  # M3U8播放列表
    r'(?i)(video|mp4|stream)\.(php|asp|aspx|jsp)(\?.*)?$',  # 视频播放页面
    r'(?i)/video/.*\.(mp4|mkv|avi|flv|wmv|mov|webm)(\?.*)?$',  # 视频路径
    r'(?i)/stream/.*\.(mp4|mkv|avi|flv|wmv|mov|webm)(\?.*)?$',  # 流路径
    # B站视频
    r'(?i)bilibili\.com.*\.flv(\?.*)?$',  # B站FLV格式
    r'(?i)bilibili\.com.*\.mp4(\?.*)?$',  # B站MP4格式
    r'(?i)api\.bilibili\.com.*playurl.*$',  # B站播放API
    r'(?i)upos-hz-mirrorks3\.bilivideo\.com.*$',  # B站视频存储服务器
    r'(?i)upos-sz-mirrorks3\.bilivideo\.com.*$',  # B站视频存储服务器
    # 抖音视频
    r'(?i)douyin\.com.*video/.*$',  # 抖音视频页面
    r'(?i)v\.douyin\.com/.*$',  # 抖音短链接
    r'(?i)aweme\.snsvideocdn\.com.*$',  # 抖音视频CDN
    r'(?i)douyin\.tiktokcdn-us\.com.*$',  # 抖音国际版CDN
    r'(?i)music\.douyin\.com.*$',  # 抖音音乐
    # 优酷视频
    r'(?i)youku\.com.*id_.*\.html$',  # 优酷视频页面
    r'(?i)player\.youku\.com/embed/.*$',  # 优酷播放器
    r'(?i)vali\.youku\.com/.*$',  # 优酷视频CDN
    r'(?i)ups\.youku\.com/.*$',  # 优酷视频存储
    # 爱奇艺视频
    r'(?i)iqiyi\.com/v_.*\.html$',  # 爱奇艺视频页面
    r'(?i)www\.iqiyi\.com/.*\.html$',  # 爱奇艺其他页面
    r'(?i)cache\.m\.iqiyi\.com/.*$',  # 爱奇艺缓存
    r'(?i)data\.m\.iqiyi\.com/.*$',  # 爱奇艺数据
    # 腾讯视频
    r'(?i)v\.qq\.com/.*\.html$',  # 腾讯视频页面
    r'(?i)film\.qq\.com/.*$',  # 腾讯电影页面
    r'(?i)imgcache\.qq\.com/.*$',  # 腾讯视频CDN
    r'(?i)vd\.qq\.com/.*$',  # 腾讯视频播放
    # 芒果TV
    r'(?i)mgtv\.com/b/.*\.html$',  # 芒果TV视频页面
    r'(?i)www\.mgtv\.com/.*$',  # 芒果TV其他页面
    r'(?i)gslb\.mgtv\.com/.*$',  # 芒果TV CDN
    r'(?i)video\.mgtv\.com/.*$',  # 芒果TV视频
    # 西瓜视频
    r'(?i)ixigua\.com/.*$',  # 西瓜视频页面
    r'(?i)v\.ixigua\.com/.*$',  # 西瓜视频短链接
    r'(?i)snssdk\.com/.*$',  # 西瓜视频CDN
    # 快手视频
    r'(?i)kuaishou\.com/f/.*$',  # 快手视频页面
    r'(?i)v\.kuaishou\.com/.*$',  # 快手短链接
    r'(?i)aweme\.kuaishoucdn\.com/.*$'  # 快手视频CDN
]

# 提前把 VIDEO_PATTERNS 编译成正则对象，避免 check_clipboard 每 500ms 一轮轮 re.search 重新编译
_COMPILED_VIDEO_PATTERNS = [re.compile(p, re.IGNORECASE) for p in VIDEO_PATTERNS]
_COMPILED_BILIBILI_PAGE = re.compile(r'bilibili\.com/video/(BV|bv|av|AV)', re.IGNORECASE)
_COMPILED_M4S_QN = re.compile(r'-1-(\d+)\.m4s')

# ========== 配置文件记忆功能 ==========
# 配置文件路径（与脚本同目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'downloader_config.json')

def load_config():
    """加载配置文件，返回下载路径和历史日志"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(download_path=None, recent_logs=None):
    """保存配置到文件"""
    try:
        existing = load_config()
        if download_path is not None:
            existing['download_path'] = download_path
        if recent_logs is not None:
            existing['recent_logs'] = recent_logs
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 已捕获的视频URL列表
captured_urls = set()

# 下载目录（优先从配置文件加载，否则使用默认值）
_config = load_config()
DOWNLOAD_DIR = _config.get('download_path', os.path.join("D:", "视频下载"))
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# 全局变量
running = False
stop_event = threading.Event()
last_clipboard_content = ""  # 上一次剪贴板内容

# 当前下载任务
current_download = None

# 下载线程列表
download_threads = []
MAX_THREADS = 3

# 当前B站视频的元数据（标题、封面等）
current_video_metadata = {}

# 全局浏览器Session
session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
})

# B站Cookie管理：运行时自动生成buvid3设备指纹，不硬编码任何私人Cookie
# buvid3 是B站的设备标识Cookie，缺失时B站风控会返回412错误
# 此处仅生成随机的buvid3（不含任何登录信息），确保请求不被风控拦截
#
# ★★★ 如何解锁1080P/4K高清画质 ★★★
# 不登录时B站最高只返回720P。要下载1080P及以上画质，需要填入你浏览器里的真实登录Cookie：
# 1. 在浏览器登录 bilibili.com
# 2. 按 F12 打开开发者工具 → Application/存储 → Cookies → bilibili.com
# 3. 找到 SESSDATA 的值，复制下来
# 4. 在下面的 USER_SESSDATA 变量里填入你的 SESSDATA 值
# 例如: USER_SESSDATA = "你复制的SESSDATA值"
USER_SESSDATA = ""  # 留空=不登录(最高720P)；填入SESSDATA=解锁1080P/4K

def _generate_buvid3():
    """生成随机 buvid3 设备指纹（B站格式：大写UUID + infoc后缀），避免412风控"""
    import uuid
    return str(uuid.uuid4()).upper() + 'infoc'

def ensure_bilibili_cookies():
    """确保 session 中有 B站所需的 Cookie（buvid3 等），避免412风控。
    如果 buvid3 缺失则随机生成；同时主动访问B站首页让服务器下发更多Cookie。"""
    # 检查并设置 buvid3
    buvid3 = session.cookies.get('buvid3', domain='.bilibili.com')
    if not buvid3:
        buvid3 = _generate_buvid3()
        session.cookies.set('buvid3', buvid3, domain='.bilibili.com')
    # 如果用户填入了SESSDATA，也设置到session
    if USER_SESSDATA:
        session.cookies.set('SESSDATA', USER_SESSDATA, domain='.bilibili.com')
    return True

def refresh_bilibili_cookies():
    """访问B站首页刷新Cookie（让服务器下发buvid3/b_nut等），用于412重试。
    返回 True 成功，False 失败。"""
    try:
        resp = session.get('https://www.bilibili.com/', timeout=10, headers={
            'User-Agent': session.headers.get('User-Agent', ''),
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        # 确保buvid3存在（服务器可能已下发，若没有则手动生成）
        ensure_bilibili_cookies()
        return resp.status_code == 200
    except Exception:
        return False

# 初始化B站Cookie（生成buvid3）
try:
    ensure_bilibili_cookies()
except Exception as e:
    print(f"[-] 初始化B站Cookie失败: {str(e)}")

adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=2
)

session.mount("http://", adapter)
session.mount("https://", adapter)

# ========== FFmpeg 自动下载与管理 ==========
# ffmpeg.exe 本地路径（与脚本同目录）
LOCAL_FFMPEG = os.path.join(SCRIPT_DIR, 'ffmpeg.exe')

def get_ffmpeg_path():
    """
    获取 ffmpeg 可执行文件路径。
    优先级：系统PATH > 脚本目录/ffmpeg.exe > imageio_ffmpeg包
    返回路径字符串，找不到则返回 None。
    """
    # 1. 检查系统 PATH
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            return 'ffmpeg'  # 使用系统PATH中的ffmpeg
    except Exception:
        pass

    # 2. 检查脚本目录
    if os.path.exists(LOCAL_FFMPEG):
        return LOCAL_FFMPEG

    # 3. 检查 imageio_ffmpeg 包（pip install imageio-ffmpeg）
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except ImportError:
        pass
    except Exception:
        pass

    return None

def download_ffmpeg_automatically():
    """
    自动下载 ffmpeg.exe 到脚本目录。
    下载源：BtbN/FFmpeg-Builds (GitHub Release) + 国内镜像
    返回 True 成功，False 失败。
    """
    import tempfile

    # 下载URL（多个源，含国内镜像，按优先级排序）
    github_url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
    download_urls = [
        github_url,
        # GitHub 国内代理镜像
        f'https://ghfast.top/{github_url}',
        f'https://gh-proxy.com/{github_url}',
        f'https://mirror.ghproxy.com/{github_url}',
    ]

    for idx, download_url in enumerate(download_urls):
        source_name = 'GitHub' if idx == 0 else f'镜像{idx}'
        try:
            log_message(f"[+] 正在从{source_name}下载 ffmpeg（约80MB）...")

            # 下载到临时文件（避免大文件占内存）
            temp_zip = os.path.join(SCRIPT_DIR, 'ffmpeg_download.zip')
            response = session.get(download_url, stream=True, timeout=(15, 60), allow_redirects=True)
            if response.status_code != 200:
                log_message(f"[-] {source_name}返回状态码 {response.status_code}，尝试下一个源", is_detailed=True)
                continue

            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            last_log_time = time.time()
            chunk_size = 1024 * 1024  # 1MB

            with open(temp_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if stop_event.is_set():
                        log_message(f"[-] ffmpeg下载被中止")
                        try: os.remove(temp_zip)
                        except: pass
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_log_time >= 3:
                            if total_size > 0:
                                pct = downloaded / total_size * 100
                                log_message(f"[+] ffmpeg下载进度: {pct:.0f}% ({downloaded//1024//1024}MB/{total_size//1024//1024}MB)", is_detailed=True)
                            else:
                                log_message(f"[+] ffmpeg下载进度: {downloaded//1024//1024}MB", is_detailed=True)
                            last_log_time = now

            log_message(f"[+] 下载完成，正在解压 ffmpeg.exe...")

            # 从zip中提取 ffmpeg.exe
            with zipfile.ZipFile(temp_zip) as zf:
                for name in zf.namelist():
                    if name.endswith('ffmpeg.exe'):
                        with zf.open(name) as src, open(LOCAL_FFMPEG, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                        log_message(f"[+] ffmpeg.exe 已保存到: {LOCAL_FFMPEG}")
                        try: os.remove(temp_zip)
                        except: pass
                        return True

            log_message(f"[-] zip中未找到 ffmpeg.exe", is_detailed=True)
            try: os.remove(temp_zip)
            except: pass
        except Exception as e:
            log_message(f"[-] {source_name}下载失败: {str(e)}", is_detailed=True)
            # 清理临时文件
            temp_zip = os.path.join(SCRIPT_DIR, 'ffmpeg_download.zip')
            try: os.remove(temp_zip)
            except: pass
            continue

    return False

def ensure_ffmpeg_available():
    """
    确保ffmpeg可用。如果不存在，尝试多种方式获取。
    返回 ffmpeg 路径（字符串），或 None（不可用）。
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        return ffmpeg_path

    # 方式1：从GitHub/镜像下载 ffmpeg.exe
    log_message(f"[+] 未检测到 ffmpeg，正在自动下载（首次使用约需80MB）...")
    if download_ffmpeg_automatically():
        return LOCAL_FFMPEG

    # 方式2：通过 pip 安装 imageio-ffmpeg（自带ffmpeg二进制，国内镜像可用）
    log_message(f"[+] GitHub下载失败，尝试通过 pip 安装 imageio-ffmpeg...")
    try:
        import sys
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'imageio-ffmpeg',
             '-i', 'https://mirrors.aliyun.com/pypi/simple/'],
            capture_output=True, timeout=120
        )
        if result.returncode == 0:
            log_message(f"[+] imageio-ffmpeg 安装成功")
            ffmpeg_path = get_ffmpeg_path()
            if ffmpeg_path:
                return ffmpeg_path
        else:
            error = result.stderr.decode('utf-8', errors='ignore')[-200:]
            log_message(f"[-] pip安装失败: {error}", is_detailed=True)
    except Exception as e:
        log_message(f"[-] pip安装异常: {str(e)}", is_detailed=True)

    log_message(f"[-] ffmpeg所有获取方式均失败，视频和音频将分别下载（不合并）")
    log_message(f"[-] 请手动运行: pip install imageio-ffmpeg -i https://mirrors.aliyun.com/pypi/simple/")
    return None

# 活动下载窗口列表
active_download_windows = []
windows_lock = threading.Lock()


class DownloadProgressWindow:
    def __init__(self, url, filename):
        self.url = url
        self.filename = filename
        self.window = None
        self.progress_var = None
        self.progress_bar = None
        self.speed_label = None
        self.status_label = None
        self.downloaded_mb = 0
        self.total_mb = 0
        self.speed_mb = 0
        self.cancelled = False
        self.completed = False

    def create_window(self):
        self.window = tk.Toplevel()
        self.window.title(f"正在下载: {self.filename}")
        self.window.geometry("450x180")
        self.window.resizable(False, False)

        main_frame = tk.Frame(self.window, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = tk.Label(main_frame, text=f"文件名: {self.filename}", font=("微软雅黑", 9, "bold"), wraplength=420)
        title_label.pack(pady=(0, 5))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, length=410)
        self.progress_bar.pack(pady=5)

        self.speed_label = tk.Label(main_frame, text="总大小: 0 MB | 已下载: 0 MB | 速度: 0 MB/s", font=("微软雅黑", 9))
        self.speed_label.pack(pady=2)

        self.status_label = tk.Label(main_frame, text="正在连接服务器...", font=("微软雅黑", 9), fg="blue")
        self.status_label.pack(pady=2)

        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=5)

        cancel_button = tk.Button(button_frame, text="取消下载", command=self.cancel_download, width=15, font=("微软雅黑", 9))
        cancel_button.pack(side=tk.LEFT, padx=5)

    def update_progress(self, downloaded_mb, total_mb, speed_mb):
        """线程安全地更新进度：通过 window.after 回到创建进度窗口的主线程再写控件。"""
        if not self.window or self.cancelled or self.completed:
            return
        try:
            def _apply():
                if not self.window or self.cancelled or self.completed:
                    return
                self.downloaded_mb = downloaded_mb
                self.total_mb = total_mb
                self.speed_mb = speed_mb
                if total_mb > 0:
                    progress = (downloaded_mb / total_mb) * 100
                    self.progress_var.set(progress)
                    self.speed_label.config(text=f"总大小: {total_mb:.2f} MB | 已下载: {downloaded_mb:.2f} MB | 速度: {speed_mb:.2f} MB/s")
                    self.status_label.config(text=f"下载进度: {progress:.1f}%")
            self.window.after(0, _apply)
        except Exception:
            pass

    def set_status(self, status, color="blue"):
        """线程安全地更新状态文本。"""
        if not self.window or self.cancelled:
            return
        try:
            def _apply():
                if self.window and not self.cancelled:
                    self.status_label.config(text=status, fg=color)
            self.window.after(0, _apply)
        except Exception:
            pass

    def set_combined_progress(self, progress, phase_text, info_text="", color="blue"):
        """线程安全地设置合并进度（跨多个阶段），progress为0-100。"""
        if not self.window or self.cancelled or self.completed:
            return
        try:
            def _apply():
                if not self.window or self.cancelled or self.completed:
                    return
                self.progress_var.set(progress)
                self.status_label.config(text=phase_text, fg=color)
                if info_text:
                    self.speed_label.config(text=info_text)
            self.window.after(0, _apply)
        except Exception:
            pass

    def close_window(self):
        if self.window:
            try:
                self.window.destroy()
            except Exception as e:
                pass

    def cancel_download(self):
        self.cancelled = True
        self.close_window()

# 检查系统是否安装了 ffmpeg（兼容系统PATH和脚本目录）
def is_ffmpeg_available():
    """检查 ffmpeg 是否可用"""
    return get_ffmpeg_path() is not None

# B站 DASH 专用下载：下载视频流+音频流，用 ffmpeg 合并为完整 mp4
def download_bilibili_dash(video_url, audio_url, title, show_progress_window, cover_path=''):
    """
    下载B站DASH视频流和音频流，用ffmpeg合并为完整的mp4文件。
    如果ffmpeg不可用，则回退为分别下载两个文件。
    """
    import tempfile

    # 清理标题作为文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title) if title else 'bilibili_video'
    safe_title = safe_title.strip().rstrip('.')
    if not safe_title:
        safe_title = 'bilibili_video'

    download_dir = DOWNLOAD_DIR
    final_path = os.path.join(download_dir, f"{safe_title}.mp4")

    # 如果最终文件已存在，先跳过
    if os.path.exists(final_path):
        log_message(f"[+] 文件已存在，跳过: {safe_title}.mp4")
        return

    # 获取 ffmpeg 路径（如果不存在会自动下载）
    ffmpeg_path = get_ffmpeg_path()

    if not ffmpeg_path:
        log_message("[+] 未检测到 ffmpeg，正在自动下载（首次使用约需80MB）...", )
        ffmpeg_path = ensure_ffmpeg_available()

    if not ffmpeg_path:
        log_message("[-] ffmpeg自动下载失败，视频和音频将分别下载（不合并）")
        # 回退：分别下载
        if video_url and video_url not in captured_urls:
            download_video(video_url, show_progress_window=show_progress_window, custom_filename=title)
        if audio_url and audio_url not in captured_urls:
            download_video(audio_url, show_progress_window=show_progress_window, custom_filename=(title + "_音频") if title else None)
        return

    # 有 ffmpeg：下载到临时文件，合并后删除临时文件
    log_message(f"[+] 检测到 ffmpeg，将下载并合并视频+音频为完整文件")

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix='bilibili_dash_')
    temp_video = os.path.join(temp_dir, 'video.m4s')
    temp_audio = os.path.join(temp_dir, 'audio.m4s')

    # 创建进度窗口（仅剪贴板自动下载时）
    progress_window = None
    if show_progress_window:
        progress_window = DownloadProgressWindow(video_url, safe_title)
        progress_window.create_window()

    # 统一进度更新函数（兼容主窗口和独立窗口）
    def _update_progress(progress, phase_text, info_text="", color="blue"):
        if progress_window and not progress_window.cancelled:
            progress_window.set_combined_progress(progress, phase_text, info_text, color)
        else:
            try:
                def _apply():
                    progress_var.set(progress)
                    if info_text:
                        download_info_label.config(text=info_text)
                    status_var.set(phase_text)
                root.after(0, _apply)
            except Exception:
                pass

    # 下载单个流的内部函数（带进度回调）
    def _download_stream(url, filepath, stream_type, progress_base, progress_range):
        """
        stream_type: '视频' 或 '音频'
        progress_base: 该阶段起始进度（如视频=0, 音频=45）
        progress_range: 该阶段进度跨度（如视频=45, 音频=45）
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Range': 'bytes=0-',
        }
        try:
            resp = session.get(url, headers=headers, stream=True, timeout=30)
            if resp.status_code not in [200, 206]:
                log_message(f"[-] {stream_type}流下载失败，状态码: {resp.status_code}", is_detailed=True)
                return False

            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            start_time = time.time()
            last_log_time = start_time
            chunk_size = 1024 * 1024 * 4  # 4MB

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if stop_event.is_set():
                        log_message(f"[-] {stream_type}流下载被中止")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        # 更新进度（每次chunk都更新，保证平滑）
                        speed = downloaded / (now - start_time) / 1024 / 1024 if now > start_time else 0
                        if total > 0:
                            stream_pct = downloaded / total
                            combined = progress_base + stream_pct * progress_range
                            info = f"正在下载{stream_type}流: {downloaded/1024/1024:.1f}/{total/1024/1024:.1f}MB | {speed:.1f}MB/s"
                            _update_progress(combined, f"正在下载{stream_type}流", info)
                        else:
                            info = f"正在下载{stream_type}流: {downloaded/1024/1024:.1f}MB | {speed:.1f}MB/s"
                            _update_progress(progress_base + progress_range * 0.5, f"正在下载{stream_type}流", info)
                        # 每2秒输出一次日志
                        if now - last_log_time >= 2:
                            if total > 0:
                                pct = downloaded / total * 100
                                log_message(f"[+] {stream_type}流下载: {pct:.1f}% ({downloaded/1024/1024:.1f}/{total/1024/1024:.1f}MB, {speed:.1f}MB/s)", is_detailed=True)
                            else:
                                log_message(f"[+] {stream_type}流下载: {downloaded/1024/1024:.1f}MB ({speed:.1f}MB/s)", is_detailed=True)
                            last_log_time = now

            log_message(f"[+] {stream_type}流下载完成 ({downloaded/1024/1024:.1f}MB)")
            _update_progress(progress_base + progress_range, f"{stream_type}流下载完成", f"{stream_type}流: {downloaded/1024/1024:.1f}MB 下载完成")
            return True
        except Exception as e:
            log_message(f"[-] {stream_type}流下载异常: {str(e)}", is_detailed=True)
            return False

    # 1. 下载视频流 (0% → 45%)
    log_message(f"[+] 开始下载视频流...")
    _update_progress(0, "正在下载视频流", "准备下载视频流...")
    if not _download_stream(video_url, temp_video, '视频', 0, 45):
        log_message(f"[-] 视频流下载失败，无法合并")
        if progress_window:
            progress_window.set_status("视频流下载失败", "red")
            progress_window.window.after(2000, progress_window.close_window)
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return

    # 2. 下载音频流 (45% → 90%)
    log_message(f"[+] 开始下载音频流...")
    _update_progress(45, "正在下载音频流", "准备下载音频流...")
    if audio_url and not _download_stream(audio_url, temp_audio, '音频', 45, 45):
        log_message(f"[-] 音频流下载失败，将只保留视频流（无声）", is_detailed=True)
        # 没有音频，只复制视频流
        try:
            shutil.move(temp_video, final_path)
            log_message(f"[+] 下载完成（仅视频，无声）: {safe_title}.mp4")
            _update_progress(100, "下载完成（仅视频）", f"文件: {safe_title}.mp4 (无声)", "green")
            if progress_window:
                progress_window.window.after(2000, progress_window.close_window)
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
        except Exception as e:
            log_message(f"[-] 文件保存失败: {str(e)}", is_detailed=True)
        return

    # 3. 用 ffmpeg 合并 (90% → 100%)
    log_message(f"[+] 正在合并视频和音频...")
    _update_progress(90, "正在合并音视频", "正在用 ffmpeg 合并视频和音频...", "blue")
    try:
        # 构建ffmpeg命令：合并视频+音频，并嵌入封面（如果有）
        cmd = [ffmpeg_path, '-i', temp_video, '-i', temp_audio]

        has_cover = cover_path and os.path.exists(cover_path)
        if has_cover:
            cmd.extend(['-i', cover_path])
            log_message(f"[+] 将嵌入视频封面到文件中", is_detailed=True)

        # 映射流：视频=0, 音频=1, 封面=2
        if has_cover:
            cmd.extend(['-map', '0', '-map', '1', '-map', '2',
                        '-c', 'copy', '-disposition:v:1', 'attached_pic'])
        else:
            cmd.extend(['-c', 'copy'])

        cmd.extend(['-y', final_path])

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0:
            file_size = os.path.getsize(final_path) / 1024 / 1024
            cover_msg = "，已嵌入封面" if has_cover else ""
            log_message(f"[+] 下载完成（视频+音频已合并{cover_msg}）: {safe_title}.mp4 ({file_size:.1f}MB)")
            _update_progress(100, "下载完成", f"文件: {safe_title}.mp4 ({file_size:.1f}MB{cover_msg})", "green")
            # 合并成功后删除独立的封面JPG（已嵌入到MP4中）
            if has_cover:
                try:
                    os.remove(cover_path)
                    log_message(f"[+] 已清理封面文件", is_detailed=True)
                except Exception:
                    pass
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')[-200:]
            log_message(f"[-] ffmpeg合并失败: {error_msg}", is_detailed=True)
            # 合并失败，保留视频流
            shutil.move(temp_video, final_path)
            log_message(f"[+] 已保留视频流（无声）: {safe_title}.mp4")
            _update_progress(100, "合并失败，已保留视频", f"文件: {safe_title}.mp4 (无声)", "orange")
    except Exception as e:
        log_message(f"[-] 合并过程异常: {str(e)}", is_detailed=True)
        try:
            shutil.move(temp_video, final_path)
        except Exception:
            pass
        _update_progress(100, "合并异常", f"异常: {str(e)[:50]}", "red")
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        # 延迟关闭进度窗口
        if progress_window:
            progress_window.completed = True
            progress_window.window.after(2000, progress_window.close_window)
        # 重置主窗口进度条
        try:
            root.after(2000, lambda: progress_var.set(0))
        except Exception:
            pass

# 下载视频
def download_video(url, show_progress_window=False, custom_filename=None):
    """
    将下载任务添加到队列中，由专门的下载线程处理
    show_progress_window: 是否显示下载进度窗口（仅自动下载时显示）
    custom_filename: 自定义文件名（如B站视频标题）
    """
    global captured_urls

    # 跳过已处理的URL
    if url in captured_urls:
        return

    captured_urls.add(url)
    log_message(f"[+] 开始处理视频URL: {url}", is_detailed=True)

    # 为这个下载任务创建一个独立的线程
    download_thread = threading.Thread(target=_download_video, args=(url, show_progress_window, custom_filename))
    download_thread.daemon = True
    download_thread.start()
    download_threads.append(download_thread)

# 扫描指定网站的视频链接
def _download_video(url, show_progress_window=False, custom_filename=None):
    """
    实际执行视频下载操作
    show_progress_window: 是否显示下载进度窗口
    custom_filename: 自定义文件名（如B站视频标题）
    """
    # 仅当需要显示窗口时创建进度窗口
    progress_window = None

    try:
        # 添加请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com'
        }

        # 对于B站视频流，添加额外的请求头
        if 'bilivideo.com' in url or 'bilivideo.cn' in url:
            headers.update({
                'Cookie': f'buvid3={session.cookies.get("buvid3", _generate_buvid3())}',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于抖音视频流，添加额外的请求头
        elif 'snsvideocdn.com' in url or 'tiktokcdn-us.com' in url:
            headers.update({
                'Cookie': 'tt_webid=1234567890abcdef; tt_webid_v2=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.douyin.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于优酷视频流，添加额外的请求头
        elif 'youku.com' in url or 'vali.youku.com' in url:
            headers.update({
                'Cookie': 'cna=1234567890abcdef; l=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.youku.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于爱奇艺视频流，添加额外的请求头
        elif 'iqiyi.com' in url or 'cache.m.iqiyi.com' in url:
            headers.update({
                'Cookie': 'QED=1234567890abcdef; P00001=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.iqiyi.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于腾讯视频流，添加额外的请求头
        elif 'qq.com' in url:
            headers.update({
                'Cookie': 'pgv_pvid=1234567890; pgv_info=1234567890;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://v.qq.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于芒果TV视频流，添加额外的请求头
        elif 'mgtv.com' in url:
            headers.update({
                'Cookie': '芒果TV_COOKIE=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.mgtv.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于西瓜视频流，添加额外的请求头
        elif 'ixigua.com' in url or 'snssdk.com' in url:
            headers.update({
                'Cookie': 'tt_webid=1234567890abcdef; tt_webid_v2=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.ixigua.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于快手视频流，添加额外的请求头
        elif 'kuaishou.com' in url or 'kuaishoucdn.com' in url:
            headers.update({
                'Cookie': 'kuaishou_webid=1234567890abcdef;',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.kuaishou.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 对于B站视频流（第二个匹配分支，处理 .cn 域名等其他情况）
        elif 'bilivideo.cn' in url:
            headers.update({
                'Cookie': f'buvid3={session.cookies.get("buvid3", _generate_buvid3())}',
                'Host': url.split('/')[2],
                'Range': 'bytes=0-',
                'Referer': 'https://www.bilibili.com/',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            })

        # 检查URL是否为真实视频链接
        response = None
        try:
            # 仅当需要显示窗口时创建进度窗口
            if show_progress_window:
                progress_window = DownloadProgressWindow(url, "正在获取文件名...")
                progress_window.create_window()

            response = session.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)

            # 处理常见的HTTP状态码
            if response.status_code == 200:
                log_message(f"[+] 成功连接到视频服务器")
                if progress_window:
                    progress_window.set_status("连接成功")
            elif response.status_code == 206:
                log_message(f"[+] 成功连接到视频服务器 (部分内容)")
                if progress_window:
                    progress_window.set_status("连接成功")
            elif response.status_code == 403:
                log_message(f"[-] 下载失败，状态码: 403 Forbidden (可能需要登录)", is_detailed=True)
                log_message(f"[+] 尝试使用不同的请求头重试...", is_detailed=True)
                if progress_window:
                    progress_window.set_status("403错误，重试中...")
                # 尝试简化请求头
                simple_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'Referer': 'https://www.bilibili.com/',
                    'Range': 'bytes=0-'
                }
                response = session.get(url, headers=simple_headers, stream=True, timeout=30, allow_redirects=True)
                if response.status_code not in [200, 206]:
                    log_message(f"[-] 重试失败，状态码: {response.status_code}", is_detailed=True)
                    if progress_window:
                        progress_window.set_status("下载失败", "red")
                        progress_window.window.after(2000, progress_window.close_window)
                    return
            elif response.status_code == 404:
                log_message(f"[-] 下载失败，状态码: 404 Not Found", is_detailed=True)
                if progress_window:
                    progress_window.set_status("文件不存在", "red")
                    progress_window.window.after(2000, progress_window.close_window)
                return
            elif response.status_code >= 500:
                log_message(f"[-] 下载失败，状态码: {response.status_code} (服务器错误)", is_detailed=True)
                if progress_window:
                    progress_window.set_status("服务器错误", "red")
                    progress_window.window.after(2000, progress_window.close_window)
                return
            else:
                log_message(f"[-] 下载失败，状态码: {response.status_code}", is_detailed=True)
                if progress_window:
                    progress_window.set_status(f"下载失败: {response.status_code}", "red")
                    progress_window.window.after(2000, progress_window.close_window)
                return
        except requests.RequestException as e:
            log_message(f"[-] 网络请求错误: {str(e)}", is_detailed=True)
            if progress_window:
                progress_window.set_status(f"网络错误: {str(e)}", "red")
                progress_window.window.after(2000, progress_window.close_window)
            return

        # 确保response对象有效且状态码正确
        if not response or response.status_code not in [200, 206]:
            log_message(f"[-] 无效的响应，状态码: {response.status_code if response else '无'}", is_detailed=True)
            if progress_window:
                progress_window.set_status("无效响应", "red")
                progress_window.window.after(2000, progress_window.close_window)
            return

        # 检查内容类型
        content_type = response.headers.get('Content-Type', '')
        is_valid = False

        # 1. Content-Type里直接包含音频/视频特征
        if any(mark in content_type for mark in ['video', 'audio', 'mp4', 'flv', 'webm', 'mov', 'octet-stream', 'mp2t', 'mp4a', 'mp4v']):
            is_valid = True
        # 2. URL扩展名匹配（包括B站DASH专用的 .m4s 格式）
        elif any(ext in url.lower() for ext in ['.mp4', '.mkv', '.avi', '.flv', '.wmv', '.mov', '.webm', '.m4s', '.m4a', '.ts']):
            is_valid = True
        # 3. B站视频CDN域名（新老域名均放行：bilivideo.com 及 bilivideo.cn）
        elif any(domain in url for domain in ['bilivideo.com', 'bilivideo.cn', 'upos-sz', 'akamaized.net']):
            is_valid = True

        if not is_valid:
            log_message(f"[-] 跳过非视频文件: {url}", is_detailed=True)
            if progress_window:
                progress_window.set_status("非视频文件", "orange")
                progress_window.window.after(2000, progress_window.close_window)
            return

        # 生成文件名（优化版）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 优先使用自定义文件名（如B站视频标题）
        if custom_filename:
            # 清理标题中的非法文件名字符
            base_name = re.sub(r'[\\/:*?"<>|]', '_', custom_filename)
            base_name = base_name.strip().rstrip('.')
            if not base_name:
                base_name = f"video_{timestamp}"
            # 根据URL判断扩展名
            if '.mp4' in url.lower() or 'video' in content_type.lower():
                ext = 'mp4'
            elif '.flv' in url.lower():
                ext = 'flv'
            elif '.m4s' in url.lower():
                # B站DASH的.m4s文件：根据URL中的流ID判断是视频还是音频
                # URL格式: xxx-1-XXXXX.m4s，其中XXXXX是流ID
                # 30xxx=视频流(AVC/HEVC/AV1)，302xx=音频流
                m4s_match = re.search(r'-1-(\d+)\.m4s', url)
                if m4s_match:
                    stream_id = int(m4s_match.group(1))
                    if 30200 <= stream_id <= 30299:
                        ext = 'm4a'  # 音频流
                    else:
                        ext = 'mp4'  # 视频流
                else:
                    # 无法从URL判断，默认用mp4
                    ext = 'mp4'
            else:
                ext = 'mp4'
        else:
            # 尝试从URL中提取有意义的文件名
            filename_match = re.search(r'/([^/]+)\.(mp4|mkv|avi|flv|wmv|mov|webm)(\?.*)?$', url)
            if filename_match:
                base_name = filename_match.group(1)
                # 清理文件名中的特殊字符
                base_name = re.sub(r'[^a-zA-Z0-9_一-龥]', '_', base_name)
                ext = filename_match.group(2)
            else:
                # 从Content-Disposition中提取文件名
                content_disposition = response.headers.get('Content-Disposition', '')
                disp_match = re.search(r'filename="?([^"]+)"?', content_disposition)
                if disp_match:
                    base_name = disp_match.group(1)
                    # 清理文件名
                    base_name = re.sub(r'[^a-zA-Z0-9_一-龥]', '_', base_name)
                    ext = 'mp4'  # 默认扩展名
                else:
                    # 使用时间戳作为文件名
                    base_name = f"video_{timestamp}"
                    ext = 'mp4'

        # 更新进度窗口的文件名
        if progress_window:
            progress_window.filename = f"{base_name}.{ext}"
            progress_window.window.title(f"正在下载: {progress_window.filename}")

        # 确保文件名唯一
        filename = f"{base_name}.{ext}"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        # 如果文件已存在，添加序号
        counter = 1
        while os.path.exists(filepath):
            filename = f"{base_name}_{counter}.{ext}"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            counter += 1

        # 在GUI中显示消息
        log_message(f"[+] 发现视频URL")
        log_message(f"[+] 开始下载视频")
        log_message(f"[+] 保存路径: {filepath}")
        # 详细日志
        log_message(f"[+] 视频URL: {url}", is_detailed=True)
        log_message(f"[+] 完整保存路径: {filepath}", is_detailed=True)

        if progress_window:
            progress_window.set_status("正在下载...")

        # 下载视频
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded_size = 0
        start_time = time.time()
        last_time = start_time
        last_downloaded = 0

        # 打开文件进行写入（使用大缓冲区提升写入性能）
        with open(filepath, 'wb', buffering=8*1024*1024) as f:  # 8MB写缓冲区
            for chunk in response.iter_content(chunk_size=4*1024*1024):  # 4MB chunks，减少IO次数
                if progress_window and progress_window.cancelled:
                    # 用户取消了下载
                    f.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    log_message(f"[-] 用户取消了下载", is_detailed=True)
                    if progress_window:
                        progress_window.window.after(100, progress_window.close_window)
                    return

                if not chunk:
                    continue

                # 写入数据
                f.write(chunk)
                downloaded_size += len(chunk)

                # 更新进度条和下载信息
                if total_size > 0:
                    # 计算下载速度
                    current_time = time.time()
                    time_elapsed = current_time - last_time
                    if time_elapsed > 0.5:  # 每0.5秒更新一次速度
                        # 转换为MB
                        total_mb = total_size / (1024 * 1024)
                        downloaded_mb = downloaded_size / (1024 * 1024)
                        # 计算速度
                        speed_mb = (downloaded_size - last_downloaded) / (1024 * 1024) / time_elapsed

                        # 更新进度
                        if progress_window:
                            # 使用独立窗口显示进度
                            progress_window.update_progress(downloaded_mb, total_mb, speed_mb)
                        else:
                            # 更新主窗口进度条
                            try:
                                progress = (downloaded_size / total_size) * 100
                                if 'progress_var' in globals():
                                    progress_var.set(progress)
                                if 'download_info_label' in globals():
                                    download_info_label.config(text=f"总大小: {total_mb:.2f} MB | 已下载: {downloaded_mb:.2f} MB | 速度: {speed_mb:.2f} MB/s")
                                # 强制更新GUI
                                root = tk._default_root
                                if root:
                                    root.update_idletasks()
                            except:
                                pass

                        last_time = current_time
                        last_downloaded = downloaded_size

        # 检查文件大小，过滤空文件或过小的文件
        file_size = os.path.getsize(filepath)
        if file_size < 1024 * 1024:  # 小于1MB的文件可能不是完整视频
            os.remove(filepath)
            log_message(f"[-] 移除过小文件: {filename} (可能不是完整视频)", is_detailed=True)
            if progress_window:
                progress_window.set_status("文件过小，已取消", "orange")
                progress_window.window.after(2000, progress_window.close_window)
            return

        # 检查文件是否完整（如果有Content-Length头）
        if total_size > 0 and file_size < total_size * 0.9:  # 文件大小小于预期的90%，可能不完整
            os.remove(filepath)
            log_message(f"[-] 移除不完整文件: {filename} (仅下载了 {file_size/total_size*100:.1f}%)", is_detailed=True)
            if progress_window:
                progress_window.set_status("文件不完整，已取消", "orange")
                progress_window.window.after(2000, progress_window.close_window)
            return

        # 下载完成
        if progress_window:
            progress_window.completed = True
            progress_window.set_status("下载完成!", "green")
            progress_window.window.after(2000, progress_window.close_window)
        else:
            # 手动扫描模式，重置主窗口进度条
            try:
                if 'progress_var' in globals():
                    progress_var.set(0)
                if 'download_info_label' in globals():
                    download_info_label.config(text="总大小: 0 MB | 已下载: 0 MB | 速度: 0 MB/s")
                root = tk._default_root
                if root:
                    root.update_idletasks()
            except:
                pass

        # 下载完成，添加可点击的日志
        log_message(f"[+] 下载完成: {filename}")
        # 添加可点击的打开链接
        log_message(f"[+] 点击查看: {filepath}")

    except Exception as e:
        log_message(f"[-] 下载错误: {str(e)}", is_detailed=True)
        # 清理可能的不完整文件
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
                log_message(f"[-] 清理不完整文件: {filename}", is_detailed=True)
        except:
            pass

        # 重置主窗口进度条（手动扫描模式）
        if not progress_window:
            try:
                if 'progress_var' in globals():
                    progress_var.set(0)
                if 'download_info_label' in globals():
                    download_info_label.config(text="总大小: 0 MB | 已下载: 0 MB | 速度: 0 MB/s")
                root = tk._default_root
                if root:
                    root.update_idletasks()
            except:
                pass

        if progress_window:
            progress_window.set_status(f"错误: {str(e)}", "red")
            progress_window.window.after(3000, progress_window.close_window)

# 从剪贴板获取URL并检查是否是视频链接
def check_clipboard():
    """
    使用 tkinter 的 after() 方法在主线程中定期检查剪贴板
    """
    global running, last_clipboard_content

    if not running:
        return

    try:
        # 使用 tkinter 获取剪贴板内容（必须在主线程）
        clipboard_content = ""
        try:
            clipboard_content = root.clipboard_get().strip()
        except Exception:
            try:
                import pyperclip
                clipboard_content = pyperclip.paste().strip()
            except:
                pass

        # 检查剪贴板内容是否有效
        if clipboard_content and clipboard_content != last_clipboard_content:
            last_clipboard_content = clipboard_content

            # 检查是否是有效的URL（必须以http开头）
            if clipboard_content.startswith('http://') or clipboard_content.startswith('https://'):
                # 先检查是否是B站视频页面链接（特殊处理）
                is_bilibili_page = bool(_COMPILED_BILIBILI_PAGE.search(clipboard_content))

                if is_bilibili_page:
                    # B站视频页面链接：通过扫描网站方式提取视频流
                    if clipboard_content not in captured_urls:
                        captured_urls.add(clipboard_content)
                        log_message(f"[+] 从剪贴板检测到B站视频链接: {clipboard_content}")
                        # 在新线程中执行扫描，避免阻塞剪贴板监控
                        threading.Thread(
                            target=scan_website,
                            args=(clipboard_content, True),
                            daemon=True,
                        ).start()
                else:
                    # 检查是否是普通视频流URL（使用预编译正则，省掉每次 re.compile）
                    is_video_url = False
                    for compiled in _COMPILED_VIDEO_PATTERNS:
                        if compiled.search(clipboard_content):
                            is_video_url = True
                            break

                    # 如果是视频URL，添加到下载队列
                    if is_video_url and clipboard_content not in captured_urls:
                        log_message(f"[+] 从剪贴板检测到视频链接: {clipboard_content}")
                        download_video(clipboard_content, show_progress_window=True)

    except Exception as e:
        log_message(f"[-] 剪贴板检查错误: {str(e)}", is_detailed=True)

    # 继续定时检查剪贴板。500ms一次足够捕捉复制操作，且显著降低CPU抢用。
    if running:
        root.after(500, check_clipboard)

# ========== B站视频提取辅助函数 ==========

def extract_bilibili_playinfo(html_text):
    """
    从window.__playinfo__中提取B站视频播放链接
    使用花括号计数法稳健提取JSON，避免嵌套结构问题
    """
    import json
    video_urls = []
    
    # 方法1: 用花括号计数法提取 __playinfo__ 
    json_strs = []
    start_patterns = [
        'window.__playinfo__=',
        'window.__playinfo__ =',
    ]
    
    for pattern in start_patterns:
        idx = html_text.find(pattern)
        if idx >= 0:
            json_start = idx + len(pattern)
            # 跳过空格
            while json_start < len(html_text) and html_text[json_start] in ' \t\r\n':
                json_start += 1
            
            if json_start < len(html_text) and html_text[json_start] == '{':
                brace_count = 0
                json_end = json_start
                for i in range(json_start, min(json_start + 100000, len(html_text))):
                    if html_text[i] == '{':
                        brace_count += 1
                    elif html_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    json_str = html_text[json_start:json_end]
                    json_strs.append(json_str)
    
    for json_str in json_strs:
        try:
            playinfo = json.loads(json_str)
            
            # 从durl中提取（旧格式）
            durl = playinfo.get('durl', [])
            if durl:
                for item in durl:
                    url = item.get('url', '')
                    if url:
                        video_urls.append(url)
                        backup_url = item.get('backup_url', '')
                        if backup_url:
                            video_urls.append(backup_url)
                if video_urls:
                    log_message(f"[+] 从playinfo的durl中提取到 {len(video_urls)} 个视频链接", is_detailed=True)
                    return video_urls
            
            # 从dash中提取（DASH格式，现代B站）
            dash = playinfo.get('dash', {})
            if dash:
                video_list = dash.get('video', [])
                audio_list = dash.get('audio', [])
                
                for v in video_list:
                    base_url = v.get('baseUrl', '') or v.get('url', '')
                    if base_url:
                        video_urls.append(base_url)
                    backup_urls = v.get('backupUrl', [])
                    if backup_urls:
                        for bu in backup_urls:
                            video_urls.append(bu)
                
                for a in audio_list:
                    base_url = a.get('baseUrl', '') or a.get('url', '')
                    if base_url:
                        video_urls.append(base_url)
                    backup_urls = a.get('backupUrl', [])
                    if backup_urls:
                        for bu in backup_urls:
                            video_urls.append(bu)
                
                if video_urls:
                    log_message("[+] 从playinfo的dash中提取到视频/音频链接", is_detailed=True)
                    return video_urls
                    
        except json.JSONDecodeError:
            continue
    
    # 方法2: 直接在HTML中搜索B站视频CDN链接
    bilibili_url_pattern = r'https?://[^"\'\s]*?\.bilivideo\.com[^"\'\s]*'
    found_urls = re.findall(bilibili_url_pattern, html_text)
    if found_urls:
        video_urls = list(set(found_urls))
        log_message(f"[+] 从HTML中直接提取到 {len(video_urls)} 个B站视频链接", is_detailed=True)
        return video_urls
    
    # 方法3: 从INITIAL_STATE中递归查找视频URL
    # 使用稳健的花括号计数法提取
    init_json = extract_json_object(html_text, 'window.__INITIAL_STATE__')
    if init_json:
        try:
            init_data = json.loads(init_json)
            found = find_video_urls_in_json(init_data)
            if found:
                video_urls.extend(found)
                log_message(f"[+] 从INITIAL_STATE中递归查找到 {len(found)} 个视频链接", is_detailed=True)
        except json.JSONDecodeError:
            pass
    
    return list(set(video_urls))


def extract_json_object(html_text, var_name):
    """
    从HTML中提取指定JavaScript变量的完整JSON对象值
    使用花括号计数法确保正确处理嵌套结构
    """
    import json
    
    patterns = [
        f'{var_name}=',
        f'{var_name} =',
    ]
    
    json_start = -1
    for pattern in patterns:
        idx = html_text.find(pattern)
        if idx >= 0:
            json_start = idx + len(pattern)
            break
    
    if json_start < 0:
        return None
    
    # 跳过空格
    while json_start < len(html_text) and html_text[json_start] in ' \t\r\n':
        json_start += 1
    
    if json_start >= len(html_text):
        return None
    
    # 处理可能的 undefined 或其他非JSON值
    if html_text[json_start] != '{':
        return None
    
    # 花括号计数
    brace_count = 0
    for i in range(json_start, min(json_start + 500000, len(html_text))):
        if html_text[i] == '{':
            brace_count += 1
        elif html_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = html_text[json_start:i + 1]
                try:
                    # 验证JSON有效性
                    json.loads(json_str)
                    return json_str
                except json.JSONDecodeError:
                    # 可能不是我们要的JSON，跳过
                    return None
    
    return None


def find_video_urls_in_json(obj, depth=0, max_depth=5):
    """递归在JSON对象中查找视频URL"""
    if depth > max_depth:
        return []
    
    urls = []
    if isinstance(obj, str):
        # 检查是否是视频URL
        if ('bilivideo.com' in obj or 'bilibili.com' in obj) and any(
            ext in obj for ext in ['.mp4', '.flv', '.m4s', '.wav', '.aac']
        ):
            urls.append(obj)
        # 也检查长URL（可能没有扩展名但包含token参数）
        elif 'bilivideo.com' in obj and len(obj) > 50 and 'token' in obj.lower():
            urls.append(obj)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            urls.extend(find_video_urls_in_json(value, depth + 1, max_depth))
    elif isinstance(obj, list):
        for item in obj:
            urls.extend(find_video_urls_in_json(item, depth + 1, max_depth))
    
    return urls


def extract_bilibili_initial_state(html_text, target_bvid=''):
    """
    从window.__INITIAL_STATE__中准确提取当前视频的cid、aid、bvid、标题和封面
    关键改进：找到videoData部分，而不是简单匹配第一个cid
    """
    import json
    result = {}

    # 使用统一的JSON提取函数
    json_str = extract_json_object(html_text, 'window.__INITIAL_STATE__')
    if not json_str:
        return result

    try:
        initial_state = json.loads(json_str)
    except json.JSONDecodeError:
        return result

    # 从videoData中提取（这是最可靠的位置）
    video_data = initial_state.get('videoData', {})
    if isinstance(video_data, dict):
        video_bvid = video_data.get('bvid', '')

        if video_data.get('cid'):
            result['cid'] = str(video_data['cid'])
        if video_data.get('aid'):
            result['aid'] = str(video_data['aid'])
        if video_bvid:
            result['bvid'] = video_bvid
        # 提取视频标题
        if video_data.get('title'):
            result['title'] = video_data['title']
        # 提取视频封面
        if video_data.get('pic'):
            result['cover'] = video_data['pic']

    # 如果videoData没有找到，尝试从其他位置提取
    if not result.get('cid'):
        for key in ['videoPage', 'view', 'videoInfo']:
            sub_data = initial_state.get(key, {})
            if isinstance(sub_data, dict):
                if sub_data.get('cid'):
                    result['cid'] = str(sub_data['cid'])
                if sub_data.get('aid'):
                    result['aid'] = str(sub_data['aid'])
                if sub_data.get('bvid') and not result.get('bvid'):
                    result['bvid'] = sub_data['bvid']
                if sub_data.get('title') and not result.get('title'):
                    result['title'] = sub_data['title']
                if sub_data.get('pic') and not result.get('cover'):
                    result['cover'] = sub_data['pic']
                if result.get('cid') and result.get('aid'):
                    break

    # 如果还是没有，递归查找
    if not result.get('cid'):
        found = find_in_json(initial_state, 'cid', target_bvid)
        if found:
            result['cid'] = found

    if not result.get('aid'):
        found = find_in_json(initial_state, 'aid', target_bvid)
        if found:
            result['aid'] = found

    return result


def find_in_json(obj, target_key, hint_bvid='', depth=0, max_depth=8):
    """
    在JSON对象中查找指定key的值
    如果提供了hint_bvid，优先查找bvid匹配的对象中的值
    """
    if depth > max_depth:
        return None
    
    if isinstance(obj, dict):
        # 先检查当前层级是否有bvid
        if hint_bvid and obj.get('bvid', '').lower() == hint_bvid.lower():
            # bvid匹配，直接返回目标key
            if target_key in obj:
                return str(obj[target_key])
        
        # 继续递归查找
        for key, value in obj.items():
            if key == target_key and not hint_bvid:
                return str(value)
            if key == target_key and hint_bvid and obj.get('bvid', '').lower() == hint_bvid.lower():
                return str(value)
            
            result = find_in_json(value, target_key, hint_bvid, depth + 1, max_depth)
            if result is not None:
                return result
                
    elif isinstance(obj, list):
        for item in obj:
            result = find_in_json(item, target_key, hint_bvid, depth + 1, max_depth)
            if result is not None:
                return result
    
    return None


# ========== B站视频提取辅助函数结束 ==========

# 扫描指定网站的视频链接
def scan_website(scan_url=None, from_clipboard=False):
    """
    from_clipboard: 是否由剪贴板监控自动触发（True=弹出独立小进度窗；False=手动扫描，用主窗口进度条）
    """
    # 如果传入了URL参数（如剪贴板监控触发），直接使用；否则从输入框获取
    if scan_url:
        url = scan_url
    else:
        url = url_entry.get()
        if not url:
            messagebox.showerror("错误", "请输入网站URL")
            return
    
    # 确保URL有正确的协议前缀
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    
    # 修复域名格式错误（确保域名包含必要的点）
    domain_match = re.search(r'https?://([^/]+)', url)
    if domain_match:
        domain = domain_match.group(1)
        # 检查域名是否缺少点或格式不正确
        # 第三个条件：www.xxxcom 这种 www. 后面的部分缺少点的情况
        if '.' not in domain or ('www' in domain and not domain.startswith('www.')) or \
           (domain.startswith('www.') and '.' not in domain[4:]):
            # 尝试修复常见的域名格式错误
            # 例如：wwwbilibilicom -> www.bilibili.com
            fixed_domain = domain
            
            # 首先处理www前缀
            if fixed_domain.startswith('www') and not fixed_domain.startswith('www.'):
                fixed_domain = 'www.' + fixed_domain[3:]
            
            # 检查是否包含常见的域名后缀
            suffixes = ['.com', '.net', '.org', '.cn', '.io', '.dev']
            for suffix in suffixes:
                suffix_no_dot = suffix[1:]  # 移除点
                if suffix_no_dot in fixed_domain and not fixed_domain.endswith(suffix):
                    # 在后缀前添加点
                    pos = fixed_domain.find(suffix_no_dot)
                    if pos > 0:
                        fixed_domain = fixed_domain[:pos] + '.' + fixed_domain[pos:]
                        break
            
            # 特殊处理：如果域名中仍然没有点，尝试在中间添加点
            if '.' not in fixed_domain and len(fixed_domain) > 6:
                # 尝试在合适的位置添加点
                # 例如：bilibilicom -> bilibili.com
                for i in range(3, len(fixed_domain) - 2):
                    if fixed_domain[i:].startswith('com') or fixed_domain[i:].startswith('net') or fixed_domain[i:].startswith('org'):
                        fixed_domain = fixed_domain[:i] + '.' + fixed_domain[i:]
                        break
            
            # 如果域名已修复，更新链接
            if fixed_domain != domain:
                old_url = url
                url = url.replace(domain, fixed_domain)
                log_message(f"[+] 修复域名格式错误: {old_url} -> {url}")
    
    log_message(f"[+] 正在连接: {url}", is_detailed=True)
    
    try:
        # 添加请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

        # B站页面请求前确保有 buvid3 Cookie，避免412风控
        if 'bilibili.com' in url:
            ensure_bilibili_cookies()

        # 发送请求获取网页内容 (使用 session 来保持 Cookie)
        response = session.get(url, headers=headers, timeout=10)

        # B站412风控处理：刷新Cookie后重试一次
        if response.status_code == 412:
            log_message("[+] 遇到B站412风控(Precondition Failed)，刷新Cookie后重试...")
            refresh_bilibili_cookies()
            response = session.get(url, headers=headers, timeout=10)

        response.raise_for_status()
        
        # 提取所有链接
        links = re.findall(r'href=["\'](.*?)["\']', response.text)
        
        # 检查每个链接是否是视频URL
        for link in links:
            # 处理相对路径
            if not link.startswith('http'):
                if link.startswith('/'):
                    # 绝对路径，基于域名
                    domain_match = re.search(r'https?://([^/]+)', url)
                    if domain_match:
                        domain = domain_match.group(0)
                        link = domain + link
                else:
                    # 相对路径，基于当前URL
                    link = url.rstrip('/') + '/' + link
            
            # 修复域名格式错误（确保域名包含必要的点）
            domain_match = re.search(r'https?://([^/]+)', link)
            if domain_match:
                domain = domain_match.group(1)
                # 检查域名是否缺少点或格式不正确
                if '.' not in domain or ('www' in domain and not domain.startswith('www.')):
                    # 尝试修复常见的域名格式错误
                    # 例如：wwwbilibilicom -> www.bilibili.com
                    fixed_domain = domain
                    
                    # 首先处理www前缀
                    if fixed_domain.startswith('www') and not fixed_domain.startswith('www.'):
                        fixed_domain = 'www.' + fixed_domain[3:]
                    
                    # 检查是否包含常见的域名后缀
                    suffixes = ['.com', '.net', '.org', '.cn', '.io', '.dev']
                    for suffix in suffixes:
                        suffix_no_dot = suffix[1:]  # 移除点
                        if suffix_no_dot in fixed_domain and not fixed_domain.endswith(suffix):
                            # 在后缀前添加点
                            pos = fixed_domain.find(suffix_no_dot)
                            if pos > 0:
                                fixed_domain = fixed_domain[:pos] + '.' + fixed_domain[pos:]
                                break
                    
                    # 特殊处理：如果域名中仍然没有点，尝试在中间添加点
                    if '.' not in fixed_domain and len(fixed_domain) > 6:
                        # 尝试在合适的位置添加点
                        # 例如：bilibilicom -> bilibili.com
                        for i in range(3, len(fixed_domain) - 2):
                            if fixed_domain[i:].startswith('com') or fixed_domain[i:].startswith('net') or fixed_domain[i:].startswith('org'):
                                fixed_domain = fixed_domain[:i] + '.' + fixed_domain[i:]
                                break
                    
                    # 如果域名已修复，更新链接
                    if fixed_domain != domain:
                        # 使用更可靠的方式更新链接，确保只替换域名部分
                        old_domain_part = domain_match.group(0)
                        new_domain_part = old_domain_part.replace(domain, fixed_domain)
                        link = link.replace(old_domain_part, new_domain_part)
                        log_message(f"[+] 修复域名格式", is_detailed=True)
                        log_message(f"[+] 修复前: {domain} -> 修复后: {fixed_domain}", is_detailed=True)
            
            # 检查是否是视频URL
            for pattern in VIDEO_PATTERNS:
                if re.search(pattern, link, re.IGNORECASE):
                    if link not in captured_urls:
                        download_video(link)
                        break
        
        # 特殊处理B站视频页面
        if 'bilibili.com/video/' in url:
            log_message("[+] 检测到B站视频页面，尝试提取视频流...")
            
            # 方法1: 直接从URL中提取bvid
            bvid_from_url = re.search(r'B[Vv][0-9A-Za-z]+', url)
            if bvid_from_url:
                bvid = bvid_from_url.group(0)
                log_message(f"[+] 从URL提取到bvid: {bvid}", is_detailed=True)
            else:
                bvid = ''
            
            cid = ''
            aid = ''
            video_title = ''
            video_cover = ''

            # 方法2: 从window.__playinfo__中直接提取视频链接（最可靠的方式）
            playinfo_urls = extract_bilibili_playinfo(response.text)

            # 方法3: 从window.__INITIAL_STATE__中正确提取cid、aid、标题、封面
            extracted = extract_bilibili_initial_state(response.text, bvid)
            if extracted:
                if extracted.get('cid'):
                    cid = extracted['cid']
                    log_message(f"[+] 从INITIAL_STATE提取到cid: {cid}", is_detailed=True)
                if extracted.get('aid'):
                    aid = extracted['aid']
                    log_message(f"[+] 从INITIAL_STATE提取到aid: {aid}", is_detailed=True)
                if extracted.get('bvid') and not bvid:
                    bvid = extracted['bvid']
                    log_message(f"[+] 从INITIAL_STATE提取到bvid: {bvid}", is_detailed=True)
                if extracted.get('title'):
                    video_title = extracted['title']
                    log_message(f"[+] 提取到视频标题: {video_title}")
                if extracted.get('cover'):
                    video_cover = extracted['cover']
                    log_message(f"[+] 提取到视频封面: {video_cover}", is_detailed=True)

            # 备选：如果INITIAL_STATE没有标题，从 <title> 标签提取
            if not video_title:
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text)
                if title_match:
                    raw_title = title_match.group(1).strip()
                    # B站标题格式: "视频标题_哔哩哔哩_bilibili" 或 "视频标题 - 哔哩哔哩"
                    for sep in ['_哔哩哔哩_bilibili', '_哔哩哔哩', ' - 哔哩哔哩', '_bilibili']:
                        if sep in raw_title:
                            raw_title = raw_title.split(sep)[0].strip()
                            break
                    if raw_title:
                        video_title = raw_title
                        log_message(f"[+] 从<title>标签提取到视频标题: {video_title}")

            # 提前下载封面图片（供 ffmpeg 嵌入到视频文件中）
            cover_file_path = ''
            if video_cover:
                try:
                    cover_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                        'Referer': 'https://www.bilibili.com/',
                    }
                    cover_response = session.get(video_cover, headers=cover_headers, timeout=10)
                    if cover_response.status_code == 200:
                        cover_base = re.sub(r'[\\/:*?"<>|]', '_', video_title) if video_title else f"cover_{bvid}"
                        cover_base = cover_base.strip().rstrip('.')
                        cover_file_path = os.path.join(DOWNLOAD_DIR, f"{cover_base}.jpg")
                        with open(cover_file_path, 'wb') as f:
                            f.write(cover_response.content)
                        log_message(f"[+] 视频封面已保存: {cover_file_path}")
                except Exception as cover_e:
                    log_message(f"[-] 封面下载失败: {str(cover_e)}", is_detailed=True)

            # playinfo方案作为备用（当API方式失败时才使用），
            # 且只选最高画质的视频流 + 最高码率的音频流，避免下载9个冗余文件
            def pick_best_playinfo_streams(urls):
                """从一组playinfo链接中挑选最佳视频流+最佳音频流"""
                vid_candidates = []  # (编码优先级, 画质码, URL)
                aud_candidates = []  # (码率码, URL)
                for u in urls:
                    if not u:
                        continue
                    m = _COMPILED_M4S_QN.search(u)
                    if not m:
                        continue
                    code = int(m.group(1))
                    # 音频码一般在30200~30299之间
                    if 30200 <= code <= 30299:
                        aud_candidates.append((code, u))
                    else:
                        # 视频流：AVC(30xxx)优先级3 > HEVC(12xxx)优先级2 > AV1(10xxx)优先级1
                        if 30000 <= code <= 30999:
                            vid_candidates.append((3, code, u))
                        elif 12000 <= code <= 12999:
                            vid_candidates.append((2, code, u))
                        elif 10000 <= code <= 10999:
                            vid_candidates.append((1, code, u))
                        else:
                            vid_candidates.append((0, code, u))
                picked = []
                if vid_candidates:
                    # 先按编码优先级，再按画质码取最大
                    picked.append(max(vid_candidates, key=lambda x: (x[0], x[1]))[2])
                if aud_candidates:
                    picked.append(max(aud_candidates, key=lambda x: x[0])[1])
                return picked

            # playinfo先不下载（等API失败时再走这个分支），
            # 但先把URL按画质选择好，避免后面重复处理
            playinfo_picked = pick_best_playinfo_streams(playinfo_urls) if playinfo_urls else []
            
            # 方法4: 从HTML中尝试提取
            if not cid:
                cid_match = re.search(r'"cid"\s*:\s*(\d+)', response.text)
                if cid_match:
                    cid = cid_match.group(1)
                    log_message(f"[+] 从HTML提取到cid: {cid}", is_detailed=True)
            
            if not aid:
                aid_match = re.search(r'"aid"\s*:\s*(\d+)', response.text)
                if aid_match:
                    aid = aid_match.group(1)
                    log_message(f"[+] 从HTML提取到aid: {aid}", is_detailed=True)
            
            api_processed = False  # 标记API是否成功处理了下载

            if cid and (aid or bvid):
                log_message(f"[+] 提取到B站视频参数: cid={cid}, aid={aid}, bvid={bvid}", is_detailed=True)
                
                # 构造B站视频API请求
                # qn=127 请求最高画质(8K/4K/1080P60等，B站会自动返回账号能访问的最高规格)
                # fnval=4048 请求DASH格式(支持4K/HDR/杜比/1080P60等高规格)
                params = f"cid={cid}"
                if aid:
                    params += f"&aid={aid}"
                if bvid:
                    params += f"&bvid={bvid}"
                params += "&qn=127&type=&otype=json&fnval=4048&fourk=1"
                api_url = f"https://api.bilibili.com/x/player/playurl?{params}"
                log_message(f"[+] 尝试访问B站API（请求最高画质）: {api_url}", is_detailed=True)
                
                try:
                    # 构造API请求头，模拟浏览器行为
                    api_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                        'Referer': f'https://www.bilibili.com/video/{bvid}' if bvid else 'https://www.bilibili.com/',
                        'Origin': 'https://www.bilibili.com',
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'zh-CN,zh;q=0.9',
                        'Connection': 'keep-alive',
                        'Sec-Fetch-Dest': 'empty',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'same-site',
                    }
                    
                    # 关键：显式传递Cookie（从session中获取，含buvid3等）
                    ensure_bilibili_cookies()
                    cookie_str = '; '.join([f'{k}={v}' for k, v in session.cookies.get_dict().items()])
                    api_headers['Cookie'] = cookie_str

                    log_message(f"[+] 传递的Cookie: {cookie_str[:100]}...", is_detailed=True)

                    api_response = session.get(api_url, headers=api_headers, timeout=10)

                    # B站API 412风控处理：刷新Cookie后重试一次
                    if api_response.status_code == 412:
                        log_message("[+] B站API遇到412风控，刷新Cookie后重试...", is_detailed=True)
                        refresh_bilibili_cookies()
                        # 重新构建Cookie字符串
                        cookie_str = '; '.join([f'{k}={v}' for k, v in session.cookies.get_dict().items()])
                        api_headers['Cookie'] = cookie_str
                        api_response = session.get(api_url, headers=api_headers, timeout=10)

                    if api_response.status_code == 200:
                        log_message("[+] B站API访问成功，尝试解析视频流链接...", is_detailed=True)
                        log_message(api_response.headers.get("Content-Type", ""), is_detailed=True)
                        log_message(api_response.text[:500], is_detailed=True)
                        
                        if not api_response.text or not api_response.text.strip():
                            log_message("[-] B站API返回空响应", is_detailed=True)
                        else:
                            import json
                            try:
                                api_data = json.loads(api_response.text)
                                if api_data.get('code') == 0:
                                    data = api_data.get('data', {})
                                    # 显示可用画质信息
                                    accept_quality = data.get('accept_quality', [])
                                    if accept_quality:
                                        log_message(f"[+] 可用画质列表: {accept_quality}", is_detailed=True)
                                    quality_desc = data.get('quality', 0)
                                    # 画质映射表
                                    qn_names = {16: '360P', 32: '480P', 64: '720P', 80: '1080P',
                                                112: '1080P+', 116: '1080P60', 120: '4K', 125: 'HDR', 126: '杜比视界', 127: '8K'}
                                    qn_name = qn_names.get(quality_desc, f'qn={quality_desc}')
                                    log_message(f"[+] 当前画质等级: {qn_name}")

                                    # 未登录时提示
                                    if quality_desc <= 64 and 120 in accept_quality:
                                        log_message("[-] 当前未登录，最高仅720P。在代码 USER_SESSDATA 变量中填入 SESSDATA 可解锁1080P/4K")

                                    # 优先处理DASH格式（高清视频使用DASH，视频和音频分离）
                                    dash = data.get('dash', None)
                                    streams_added = 0
                                    if dash:
                                        video_dash = dash.get('video', [])
                                        audio_dash = dash.get('audio', [])

                                        # 从URL中提取真实画质码（格式：XXX-1-XXXXX.m4s 中的 XXXXX 段）
                                        # 例如 39796738280-1-30032.m4s 中的 30032
                                        def qn_from_url(stream_item):
                                            purl = stream_item.get('baseUrl', '') or stream_item.get('url', '')
                                            qnm = _COMPILED_M4S_QN.search(purl)
                                            return int(qnm.group(1)) if qnm else stream_item.get('id', 0)

                                        # B站DASH视频流有三种编码：
                                        #   30xxx = AVC(H.264) — 兼容性最好，所有播放器都支持
                                        #   12xxx = HEVC(H.265) — 部分播放器支持
                                        #   10xxx = AV1 — 数字最大但大部分播放器打不开
                                        # 优先选AVC编码，在AVC里按 bandwidth（码率）选最高的
                                        def sort_key_video(stream_item):
                                            code = qn_from_url(stream_item)
                                            # AVC(30xxx)优先级=3, HEVC(12xxx)=2, AV1(10xxx)=1, 其他=0
                                            if 30000 <= code <= 30999:
                                                priority = 3
                                            elif 12000 <= code <= 12999:
                                                priority = 2
                                            elif 10000 <= code <= 10999:
                                                priority = 1
                                            else:
                                                priority = 0
                                            # 用bandwidth（码率）作为次要排序键，bandwidth越大画质越好
                                            bandwidth = stream_item.get('bandwidth', 0)
                                            return (priority, bandwidth)

                                        # 视频流按编码优先级+码率排序：先选AVC，再在AVC里选码率最高的
                                        if video_dash:
                                            best_video = max(video_dash, key=sort_key_video)
                                            video_url = best_video.get('baseUrl', '') or best_video.get('base_url', '') or best_video.get('url', '')
                                            if video_url:
                                                v_qn = qn_from_url(best_video)
                                                v_bw = best_video.get('bandwidth', 0)
                                                v_w = best_video.get('width', 0)
                                                v_h = best_video.get('height', 0)
                                                v_codec = best_video.get('codecs', '')
                                                v_frame = best_video.get('frameRate', '')
                                                log_message(f"[+] 选择最高画质DASH视频流: 画质码={v_qn}, 分辨率={v_w}x{v_h}, 码率={v_bw//1000}kbps, 编码={v_codec}, 帧率={v_frame}", is_detailed=True)

                                                # 选最佳音频流（按bandwidth码率排序）
                                                audio_url = None
                                                if audio_dash:
                                                    best_audio = max(audio_dash, key=lambda a: a.get('bandwidth', 0))
                                                    audio_url = best_audio.get('baseUrl', '') or best_audio.get('base_url', '') or best_audio.get('url', '')
                                                    if audio_url:
                                                        a_bw = best_audio.get('bandwidth', 0)
                                                        log_message(f"[+] 选择最高码率DASH音频流: 码率={a_bw//1000}kbps", is_detailed=True)

                                                # 用专用函数下载并合并（需要ffmpeg）
                                                # 注意：不要在此处 captured_urls.add，否则 download_bilibili_dash 内部
                                                # 回退分支的 download_video 会被去重跳过，导致视频不下载
                                                if video_url not in captured_urls:
                                                    # 在新线程中执行下载+合并
                                                    threading.Thread(
                                                        target=download_bilibili_dash,
                                                        args=(video_url, audio_url, video_title if video_title else None, from_clipboard, cover_file_path),
                                                        daemon=True
                                                    ).start()
                                                    streams_added += 1
                                    else:
                                        # 非DASH格式，使用durl（旧格式FLV/MP4）
                                        durl = data.get('durl', [])
                                        for video_info in durl:
                                            video_url = video_info.get('url')
                                            if video_url and video_url not in captured_urls:
                                                log_message(f"[+] 发现B站视频流链接: {video_url}", is_detailed=True)
                                                download_video(video_url, show_progress_window=from_clipboard, custom_filename=video_title if video_title else None)
                                                streams_added += 1

                                    if streams_added > 0:
                                        api_processed = True
                                else:
                                    log_message(f"[-] B站API返回错误: code={api_data.get('code')}, message={api_data.get('message', '未知错误')}", is_detailed=True)
                                    if api_data.get('code') == -403:
                                        log_message("[-] B站API返回-403，需要登录Cookie", is_detailed=True)
                                    elif api_data.get('code') == -404:
                                        log_message("[-] B站API返回-404，可能是cid/bvid参数不匹配", is_detailed=True)
                                    elif api_data.get('code') == -400:
                                        log_message("[-] B站API返回-400，请求参数错误", is_detailed=True)
                            except json.JSONDecodeError as je:
                                log_message(f"[-] JSON解析失败: {str(je)}", is_detailed=True)
                                log_message(f"[-] API原始响应: {api_response.text[:200]}", is_detailed=True)
                    else:
                        log_message(f"[-] B站API请求返回状态码: {api_response.status_code}", is_detailed=True)
                except Exception as api_e:
                    log_message(f"[-] B站API访问错误: {str(api_e)}", is_detailed=True)
            else:
                log_message("[-] 未能提取到B站视频参数，尝试直接从HTML中搜索视频链接...")
                # 尝试直接从HTML中搜索视频链接
                video_links = re.findall(r'https?://[^"\']*\.(mp4|flv)(\?.*)?', response.text)
                for link_tuple in video_links:
                    video_url = link_tuple[0]
                    if video_url and video_url not in captured_urls:
                        download_video(video_url, show_progress_window=from_clipboard, custom_filename=video_title if video_title else None)

            # 回退：如果API方式未成功处理流（返回-404/参数错误等），且playinfo有候选，则用playinfo下载
            if not api_processed and playinfo_picked:
                log_message(f"[+] API方式未成功，使用playinfo回退方案（已筛掉冗余文件，剩 {len(playinfo_picked)} 个流）", is_detailed=True)
                for idx, pu in enumerate(playinfo_picked):
                    if pu and pu not in captured_urls:
                        log_message(f"[+] playinfo回退下载: {pu}", is_detailed=True)
                        fn = video_title if video_title else None
                        if idx == 1 and video_title:  # 第二个一般是音频
                            fn = f"{video_title}_音频"
                        download_video(pu, show_progress_window=from_clipboard, custom_filename=fn)

        # 特殊处理抖音视频页面
        if 'douyin.com/video/' in url or 'v.douyin.com/' in url:
            log_message("[+] 检测到抖音视频页面，尝试提取视频流...")
            
            # 方法1: 从URL中提取视频ID
            video_id_match = re.search(r'douyin\.com/video/(\d+)', url)
            short_code_match = re.search(r'v\.douyin\.com/([^/]+)', url)
            
            video_id = ''
            short_code = ''
            
            if video_id_match:
                video_id = video_id_match.group(1)
                log_message(f"[+] 从URL提取到视频ID: {video_id}")
            elif short_code_match:
                short_code = short_code_match.group(1)
                log_message(f"[+] 从URL提取到短链接代码: {short_code}")
            
            # 方法2: 从HTML中提取视频参数
            sec_uid_match = re.search(r'sec_uid=["\']([^"\']+)["\']', response.text)
            item_id_match = re.search(r'item_id=["\']([^"\']+)["\']', response.text)
            
            sec_uid = ''
            item_id = ''
            
            if sec_uid_match:
                sec_uid = sec_uid_match.group(1)
                log_message(f"[+] 从HTML提取到sec_uid: {sec_uid}")
            
            if item_id_match:
                item_id = item_id_match.group(1)
                log_message(f"[+] 从HTML提取到item_id: {item_id}")
            elif not video_id:
                item_id = video_id
            
            # 尝试从window.__INITIAL_STATE__中提取参数
            initial_state_match = re.search(r'window\.__INITIAL_STATE__=(\{.*?\});', response.text, re.DOTALL)
            if initial_state_match:
                initial_state = initial_state_match.group(1)
                item_id_match2 = re.search(r'item_id=["\']([^"\']+)["\']', initial_state)
                if item_id_match2 and not item_id:
                    item_id = item_id_match2.group(1)
                    log_message(f"[+] 从INITIAL_STATE提取到item_id: {item_id}")
            
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索抖音视频流链接...")
            # 抖音视频CDN链接格式
            douyin_video_patterns = [
                r'https?://aweme\.snsvideocdn\.com/[^"\']+',
                r'https?://douyin\.tiktokcdn-us\.com/[^"\']+',
                r'https?://[^"\']+\.mp4(\?.*)?'
            ]
            
            for pattern in douyin_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and 'mp4' in video_link:
                        log_message(f"[+] 发现抖音视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理优酷视频页面
        elif 'youku.com' in url:
            log_message("[+] 检测到优酷视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索优酷视频流链接...")
            # 优酷视频链接格式
            youku_video_patterns = [
                r'https?://vali\.youku\.com/[^"\']+',
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.flv(\?.*)?'
            ]
            
            for pattern in youku_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.flv' in video_link):
                        log_message(f"[+] 发现优酷视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理爱奇艺视频页面
        elif 'iqiyi.com' in url:
            log_message("[+] 检测到爱奇艺视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索爱奇艺视频流链接...")
            # 爱奇艺视频链接格式
            iqiyi_video_patterns = [
                r'https?://cache\.m\.iqiyi\.com/[^"\']+',
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.m3u8(\?.*)?'
            ]
            
            for pattern in iqiyi_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.m3u8' in video_link):
                        log_message(f"[+] 发现爱奇艺视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理腾讯视频页面
        elif 'v.qq.com' in url:
            log_message("[+] 检测到腾讯视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索腾讯视频流链接...")
            # 腾讯视频链接格式
            tencent_video_patterns = [
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.m3u8(\?.*)?',
                r'https?://[^"\']+\.ts(\?.*)?'
            ]
            
            for pattern in tencent_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.m3u8' in video_link or '.ts' in video_link):
                        log_message(f"[+] 发现腾讯视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理芒果TV视频页面
        elif 'mgtv.com' in url:
            log_message("[+] 检测到芒果TV视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索芒果TV视频流链接...")
            # 芒果TV视频链接格式
            mgtv_video_patterns = [
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.m3u8(\?.*)?'
            ]
            
            for pattern in mgtv_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.m3u8' in video_link):
                        log_message(f"[+] 发现芒果TV视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理西瓜视频页面
        elif 'ixigua.com' in url:
            log_message("[+] 检测到西瓜视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索西瓜视频流链接...")
            # 西瓜视频链接格式
            ixigua_video_patterns = [
                r'https?://[^"\']+\.snssdk\.com/[^"\']+',
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.m3u8(\?.*)?'
            ]
            
            for pattern in ixigua_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.m3u8' in video_link):
                        log_message(f"[+] 发现西瓜视频流链接: {video_link}")
                        download_video(video_link)
        
        # 特殊处理快手视频页面
        elif 'kuaishou.com' in url:
            log_message("[+] 检测到快手视频页面，尝试提取视频流...")
            # 尝试直接从HTML中搜索视频流链接
            log_message("[+] 尝试直接从HTML中搜索快手视频流链接...")
            # 快手视频链接格式
            kuaishou_video_patterns = [
                r'https?://[^"\']+\.kuaishoucdn\.com/[^"\']+',
                r'https?://[^"\']+\.mp4(\?.*)?',
                r'https?://[^"\']+\.m3u8(\?.*)?'
            ]
            
            for pattern in kuaishou_video_patterns:
                video_links = re.findall(pattern, response.text)
                for video_link in video_links:
                    if video_link and ('.mp4' in video_link or '.m3u8' in video_link):
                        log_message(f"[+] 发现快手视频流链接: {video_link}")
                        download_video(video_link)
        
        log_message(f"[+] 网站扫描完成")
    except Exception as e:
        log_message(f"[-] 扫描错误: {str(e)}")



# 开始监控
def start_monitoring():
    global running, stop_event, last_clipboard_content
    if not running:
        running = True
        stop_event.clear()
        start_button.config(state=tk.DISABLED)
        stop_button.config(state=tk.NORMAL)

        # 启动时先记录当前剪贴板内容，避免把启动之前的内容误判为"新复制"的链接
        try:
            last_clipboard_content = root.clipboard_get()
        except Exception:
            last_clipboard_content = ''

        log_message("[+] 开始监控剪贴板...（从现在开始复制的新链接才会触发自动下载）")
        log_message("[+] 请复制视频链接到剪贴板")
        # 用 after() 在主线程做轮询。tkinter 控件禁止跨线程访问，
        # 之前用线程调用 window.clipboard_get/window.after 容易造成"未响应"和崩溃
        root.after(400, check_clipboard)

# 停止监控
def stop_monitoring():
    global running, stop_event
    if running:
        running = False
        stop_event.set()
        start_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        log_message("[+] 停止监控")
        log_message(f"[+] 共捕获 {len(captured_urls)} 个视频URL")

# 选择下载路径
def select_download_path():
    global DOWNLOAD_DIR
    global path_label

    # 打开文件夹选择对话框
    new_path = filedialog.askdirectory(title="选择下载路径")

    if new_path:
        DOWNLOAD_DIR = new_path
        # 更新路径标签
        path_label.config(text=f"当前下载路径: {DOWNLOAD_DIR}")
        # 确保路径存在
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        log_message(f"[+] 下载路径已更改为: {DOWNLOAD_DIR}")
        # 保存到配置文件
        save_config(download_path=DOWNLOAD_DIR)



# 打开文件
def open_file(file_path):
    try:
        if os.path.exists(file_path):
            # 使用系统默认程序打开文件
            os.startfile(file_path)
            log_message(f"[+] 正在打开文件: {file_path}")
        else:
            log_message(f"[-] 文件不存在: {file_path}")
    except Exception as e:
        log_message(f"[-] 打开文件错误: {str(e)}")

# 显示更新日志
def show_update_log():
    # 创建更新日志窗口
    log_window = tk.Toplevel()
    log_window.title("更新日志")
    log_window.geometry("600x400")
    
    # 创建文本框显示更新日志
    log_text = scrolledtext.ScrolledText(log_window, width=70, height=20)
    log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 更新日志内容
    update_log = """=====================================
视频嗅探下载器 - 更新日志
=====================================

[2026-9-12] v1.9.3 （412风控修复 + 私人Cookie移除 + DASH三阶段进度条）
- 修复B站返回412 Client Error: Precondition Failed的问题：B站风控检测到旧版Chrome/91 User-Agent和缺失buvid3 Cookie时返回412。统一升级所有请求头User-Agent至Chrome/138，新增Sec-Fetch-*浏览器标准请求头
- 新增 ensure_bilibili_cookies() 函数：运行时自动生成随机buvid3设备指纹（UUID格式+infoc后缀），不再硬编码任何私人Cookie。请求B站页面前自动确保buvid3存在
- 新增 refresh_bilibili_cookies() 函数：412错误时自动访问B站首页刷新Cookie后重试，避免风控拦截
- scan_website 页面请求和API请求均新增412重试逻辑：检测到412状态码后刷新Cookie并重发请求
- 移除硬编码的私人Cookie（SESSDATA等登录凭据），改为运行时生成buvid3；解锁高清画质改为通过 USER_SESSDATA 变量填入
- _download_video 中B站CDN请求头的buvid3 Cookie fallback改为运行时生成，不再硬编码设备指纹
- DASH下载三阶段平滑进度条：重写 download_bilibili_dash 进度逻辑，将整个下载过程分为三阶段 — 视频流下载(0%-45%)、音频流下载(45%-90%)、ffmpeg合并(90%-100%)，进度条平滑递增不再跳跃
- 每个chunk都更新进度，确保进度条丝滑流畅；进度条附近实时显示当前阶段标签
- DownloadProgressWindow 新增 set_combined_progress() 方法，支持跨阶段进度和阶段文字
- 合并完成/失败/异常均有对应的进度条终态和2秒后自动关闭窗口

[2026-8-10] v1.9.2 （FFmpeg下载增强 + 已有文件合并功能）
- 修复FFmpeg自动下载在国内失败的问题：添加4个下载源（GitHub直连 + 3个国内镜像 ghfast.top/gh-proxy.com/mirror.ghproxy.com），依次尝试直到成功
- 修复FFmpeg下载进度不可见的问题：所有 print() 改为 log_message()，用户可在GUI日志区实时看到下载进度和错误信息
- 修复大文件下载到内存导致失败的问题：改为下载到临时文件 ffmpeg_download.zip，解压后自动清理
- 新增"合并已有文件"按钮：扫描下载目录中文件名含"_音频"的文件，自动匹配对应视频文件并用ffmpeg合并（同时嵌入封面），合并成功后删除原始分片文件
- ensure_ffmpeg_available() 失败时显示手动下载提示

[2026-8-10] v1.9.1 （标题提取增强 + 封面嵌入修复）
- 修复视频标题获取失败导致文件名用数字编码的问题：新增从HTML <title>标签提取标题的备选方案（INITIAL_STATE提取失败时自动回退），自动去除"_哔哩哔哩_bilibili"等后缀
- 修复封面图片未嵌入视频文件的问题：封面下载提前到download_bilibili_dash调用之前执行，封面路径作为参数传入；ffmpeg合并命令增加第三个输入(-i cover.jpg)和-map/-disposition参数，将封面作为attached_pic嵌入MP4文件
- 移除重复的封面下载代码（之前在下载流程结束后又下载了一次封面，现已合并为一次）

[2026-8-10] v1.9.0 （记忆功能 + FFmpeg自动下载 + 路径BUG修复）
- 新增配置文件记忆功能：程序退出时自动保存下载路径和最近200条日志到 downloader_config.json，下次启动自动恢复下载路径并显示上次历史日志（最近30条）
- 新增FFmpeg自动下载：首次使用B站DASH下载时如果未检测到ffmpeg，自动从GitHub下载ffmpeg.exe到脚本目录（约80MB，仅需一次），下载后自动用于视频+音频合并，无需用户手动安装
- 修复致命BUG：download_bilibili_dash中使用未定义的 download_path_var.get()，导致B站DASH视频下载到错误的"下载的视频"目录而非用户选择的下载路径。改为直接使用全局 DOWNLOAD_DIR
- is_ffmpeg_available() 改为优先检查系统PATH、其次检查脚本目录/ffmpeg.exe，兼容两种安装方式
- ffmpeg合并命令改用获取到的完整路径，确保本地下载的ffmpeg.exe能被正确调用

[2026-7-31] v1.8.2 （captured_urls BUG再次修复 + URL修复增强）
- 修复captured_urls提前add导致download_bilibili_dash回退分支的download_video被跳过的BUG（第三次出现同类问题）。在scan_website调用download_bilibili_dash前不再captured_urls.add，让download_video内部自行管理去重
- 修复URL域名修复逻辑：www.bilibilicom（www.后面缺少点）不会被修复。新增第三个判断条件：domain.startswith('www.') 且 domain[4:] 不含点时也进入修复分支

[2026-7-31] v1.8.1 （DeepSeek建议优化）
- DASH流选择改用 bandwidth（码率）字段排序，替代之前的URL画质码排序。bandwidth是B站API返回的真实码率值，比URL中提取的画质码更准确
- 视频流选择日志增强：现在显示分辨率、码率、编码格式、帧率等完整信息
- 音频流选择也改用 bandwidth 排序
- 添加画质等级中文显示（720P/1080P/4K等），替代原来的纯数字qn=64
- 未登录时自动提示"最高仅720P，填入SESSDATA可解锁1080P/4K"
- Cookie配置处添加详细注释，指导用户如何获取并填入SESSDATA以解锁高清画质

[2026-7-31] v1.8.0 （DASH合并+扩展名修复）
- 修复"下载全是模糊的m4a"的致命BUG：B站CDN返回的Content-Type是application/octet-stream，不含"video"也不含"mp4"，导致所有.m4s视频流被误判为音频保存成.m4a。现在根据URL中的流ID判断：30xxx=视频流→.mp4，302xx=音频流→.m4a
- 新增 ffmpeg 自动合并功能：B站DASH格式视频和音频是分离的两个.m4s文件，之前分别下载导致用户拿到一个无声视频+一个音频文件。现在新增download_bilibili_dash()函数，先下载视频流和音频流到临时目录，再用ffmpeg合并为完整的.mp4文件（-c copy 无损无重编码），合并后自动删除临时文件
- ffmpeg不可用时自动回退：检测系统是否安装ffmpeg，若未安装则回退为分别下载两个文件（和之前行为一致），并提示用户安装ffmpeg
- 合并失败容错：ffmpeg合并失败时保留视频流文件（无声），确保用户至少能拿到画面
- 修复B站请求头中的假Cookie：移除SESSDATA=1234567890abcdef等伪造值，改为从session.cookies中获取真实的buvid3
- 新增B站CDN域名bilivideo.cn的支持（之前的请求头匹配只匹配了bilivideo.com，遗漏了.cn域名）

[2026-7-31] v1.7.0 （日志体验优化）
- 修复点击"扫描网站"按钮后无即时反馈的问题：现在点击后立即在日志区显示"[+] 开始扫描网站: xxx"（蓝色高亮），状态栏同步显示"正在扫描网站..."，用户不再因以为没反应而重复点击导致批量下载
- 日志系统从队列批量消费改回 root.after(0) 逐条渲染：每条日志立即显示，不再有批量延迟
- 日志颜色分级显示：成功信息（下载完成/扫描完成/封面保存）=绿色、错误信息（失败/错误）=红色、警告信息（跳过/非视频）=橙色、关键操作（开始扫描/检测到/提取到/开始监控）=蓝色、其他=默认色
- scan_website 内部原来的"开始扫描网站"改为"正在连接"（详细日志），避免与按钮点击时的即时提示重复

[2026-7-31] v1.6.2 （致命BUG修复）
- 修复"只下载了封面，视频下不了"的致命BUG：在调用download_video之前就执行了captured_urls.add(url)，导致download_video内部第227行"if url in captured_urls: return"直接跳过，视频和音频永远不会下载。已移除所有调用前的captured_urls.add，由download_video内部统一管理去重
- 修复DASH画质选择选到AV1编码(10xxx)的问题：B站DASH有三种编码(AVC=30xxx/HEVC=12xxx/AV1=10xxx)，之前用画质码数字大小排序，100023(AV1)>30116(1080P60)，导致选了AV1编码——大部分播放器打不开。新增sort_key_video()按(编码优先级, 画质码)排序，AVC(H.264)优先级最高，确保下载的视频所有播放器都能播放
- pick_best_playinfo_streams同步修复：视频流候选也按AVC>HEVC>AV1优先级排序

[2026-7-31] v1.6.1 （性能与稳定性优化版，不阉割任何现有功能）
- 修复「扫描网站」按钮点击后界面"未响应"/直接崩的根因：按钮直接在主线程跑 requests.get + HTML解析，阻塞Tk事件循环；改为点击后立即把 scan_website 投入后台线程执行，主线程立刻回到消息循环
- 修复「剪贴板监控」跨线程访问Tk导致的偶发崩溃：之前用 threading.Thread 启动 check_clipboard，子线程里直接调 window.clipboard_get / window.after 会触发 Tk 内部锁死；现在 start_monitoring 直接通过 root.after(400) 在主线程轮询，完全符合 Tkinter 线程模型
- 修复 log_message() 在下载/扫描线程里直接写 Text/Status 控件导致的随机卡死：引入生产者-消费者队列(log_queue + after(0, drain))，工作线程只把消息塞入队列，渲染统一回到主线程做
- 修复 DownloadProgressWindow.update_progress/set_status 在工作线程直接 .config() 导致的偶发白屏/未响应：进度/状态写入也通过 window.after(0, apply) 切回主线程执行
- 移除 check_clipboard 内部的重复 import threading（顶层已经 import），并把轮询间隔从 300ms 放宽到 500ms，CPU抢用率显著下降
- 把 VIDEO_PATTERNS/B站页面匹配/m4s画质码匹配 三个高频正则提前编译为 _COMPILED_* 对象，check_clipboard/qn_from_url/pick_best_playinfo 直接复用，去掉每次调用的 re.compile 开销
- 其他：去掉 DownloadProgressWindow 的 update_idletasks() 同步刷新（改由 after 异步自然刷新，避免忙等拉慢主线程）

[2026-7-31] v1.6.0
- 修复DASH m4s格式被误判为"非视频文件"的问题，新增白名单：扩展名(.m4s/.m4a/.ts)、CDN域名(bilivideo.cn/bilivideo.com/upos-sz/akamaized.net)、Content-Type(audio/octet-stream/mp2t/mp4a/mp4v)
- 修复DASH画质选择BUG：之前用接口返回的id字段排序（32=360P最差画质被误选为"最高"），现在用URL中的真实画质码（30080=1080P/30116=1080P60/30120=4K）排序
- 修复__playinfo__提取9个冗余链接全部下载的问题：新增pick_best_playinfo_streams()只挑最佳视频+最佳音频；playinfo变为API失败后的回退方案，API成功时不重复下载
- 剪贴板监控逻辑修正：start_monitoring()时先记录当前剪贴板内容为基准，只有监控启动之后新复制的链接才自动触发下载（避免"一开启监控就把之前复制的内容下了"）
- 进度窗口显示逻辑与触发来源绑定：scan_website新增from_clipboard参数，只有剪贴板监控自动触发的下载才弹出独立小窗口；手动点"扫描网站"按钮时继续使用主界面进度条
- URL输入框支持回车键直接触发扫描网站，无需再点击按钮

[2026-7-28] v1.5.0
- 新增B站视频标题自动提取功能，从INITIAL_STATE的videoData中获取
- 下载的视频文件自动以B站原视频标题命名（自动清理非法文件名字符）
- DASH音频流文件名自动追加"_音频"后缀以区分
- 新增B站视频封面自动下载功能，封面保存为JPG格式
- 封面文件名与视频标题一致，方便对应管理
- download_video新增custom_filename参数支持自定义文件名

[2026-7-28] v1.4.0
- 新增B站最高画质提取功能，支持1080P60/4K/8K/HDR/杜比视界
- API请求参数升级: qn=127(最高画质) + fnval=4048(DASH全格式) + fourk=1
- DASH视频流智能选择: 自动挑选id最大的最高画质视频流
- DASH音频流智能选择: 自动挑选最高质量音频流
- 不再下载所有画质，只下载最佳视频+最佳音频，避免冗余文件
- 新增画质信息日志输出，显示可用画质列表和当前画质等级

[2026-7-28] v1.3.0
- 新增剪贴板监控支持B站视频页面链接（含BV号/AV号）
- 复制B站视频页面URL后自动触发下载，无需手动扫描
- B站视频下载时自动弹出独立进度窗口
- 优化scan_website支持外部URL参数传入
- 所有B站视频流下载均显示进度窗口和实时网速

[2026-1-30] v1.2.0
- 新增下载进度条功能，实时显示下载进度
- 新增下载信息显示，包括总大小(MB)、已下载量(MB)和下载速度(MB/s)
- 优化进度条重置机制，下载完成或失败时自动重置
- 优化下载信息标签重置机制，确保下载状态正确显示
- 修复B站视频处理时详细信息显示问题，将详细参数隐藏到详细日志
- 改进B站视频流链接提取逻辑，提高视频识别率
- 增强下载速度计算精度，使用更准确的时间间隔计算

[2025-12-27] v1.1.0
- 优化UI界面布局，窗口大小调整为800x400
- 新增状态栏显示关键操作信息
- 新增详细日志按钮，点击查看完整日志
- 优化日志显示逻辑，区分关键信息和详细参数
- 修复B站视频下载403错误问题
- 增强响应内容验证和错误处理

[2025-12-25] v1.0.5
- 优化了视频URL检测逻辑
- 改进了文件名生成算法
- 添加了文件大小检查，过滤无效文件
- 优化了日志显示，支持点击打开文件
- 优化了GUI界面布局
- 改进了错误处理机制
- 重写为GUI界面
- 添加了模拟浏览器请求头
- 基于Scapy库的网络数据包捕获
- 支持视频流URL提取和下载

[2025-12-01] v1.0.0
- 新增B站视频下载功能
- 新增快手视频下载功能
- 新增剪贴板监控功能
- 新增网站扫描功能
- 新增多线程下载功能
- 新增文件完整性检查功能
- 新增自定义下载路径功能
- 新增更新日志功能

=====================================
"""
    
    # 插入更新日志
    log_text.insert(tk.END, update_log)
    log_text.config(state=tk.DISABLED)  # 设置为只读

# 详细日志存储
detailed_logs = []

# 显示详细日志
def show_detailed_logs():
    # 创建详细日志窗口
    log_window = tk.Toplevel()
    log_window.title("详细日志")
    log_window.geometry("800x600")
    
    # 创建文本框显示详细日志
    log_text_widget = scrolledtext.ScrolledText(log_window, width=100, height=30)
    log_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 插入详细日志
    for log in detailed_logs:
        # 检查是否包含文件路径
        path_match = re.search(r'\[\+\] 点击查看: (.*)$', log)
        if path_match:
            # 插入普通文本
            log_text_widget.insert(tk.END, "[+] 点击查看: ")
            # 插入可点击的文件路径
            file_path = path_match.group(1)
            log_text_widget.insert(tk.END, file_path)
            # 为文件路径添加标签
            log_text_widget.tag_add("file_path", "end - %dc" % len(file_path), "end")
            # 设置标签样式
            log_text_widget.tag_config("file_path", foreground="blue", underline=1)
            # 绑定点击事件
            log_text_widget.tag_bind("file_path", "<Button-1>", lambda e, fp=file_path: open_file(fp))
            log_text_widget.insert(tk.END, "\n")
        else:
            log_text_widget.insert(tk.END, log + "\n")
    
    log_text_widget.see(tk.END)
    log_text_widget.config(state=tk.DISABLED)  # 设置为只读

# 日志颜色配置：根据消息前缀自动着色
_LOG_COLORS = {
    'success': '#008000',  # 绿色 — [+] 下载完成/扫描完成/成功
    'error': '#CC0000',    # 红色 — [-] 错误/失败
    'warn': '#CC6600',     # 橙色 — [-] 警告/跳过
    'info': '#0066CC',     # 蓝色 — [+] 开始扫描/检测到/提取到
    'default': None,        # 默认色
}

def _get_log_color(message):
    """根据消息内容返回对应颜色的tag名"""
    if '[-]' in message and ('错误' in message or '失败' in message or '崩溃' in message):
        return 'error'
    elif '[-]' in message:
        return 'warn'
    elif '[+] 下载完成' in message or '[+] 网站扫描完成' in message or '[+] 视频封面已保存' in message:
        return 'success'
    elif '[+] 开始扫描' in message or '[+] 检测到' in message or '[+] 提取到' in message or '[+] 开始监控' in message or '[+] 从剪贴板检测到' in message:
        return 'info'
    return 'default'

def _render_log_message(message, show_in_status, is_detailed):
    """只在主线程中调用：实际写 Text 控件、写状态栏。"""
    if not is_detailed and 'log_text' in globals():
        try:
            log_text.config(state=tk.NORMAL)
            color_tag = _get_log_color(message)

            # 检查是否包含文件路径（可点击）
            path_match = re.search(r'\[\+\] 点击查看: (.*)$', message)
            if path_match:
                log_text.insert(tk.END, "[+] 点击查看: ", color_tag)
                file_path = path_match.group(1)
                log_text.insert(tk.END, file_path)
                log_text.tag_add("file_path", "end - %dc" % len(file_path), "end")
                log_text.tag_config("file_path", foreground="blue", underline=1)
                log_text.tag_bind("file_path", "<Button-1>", lambda e, fp=file_path: open_file(fp))
                log_text.insert(tk.END, "\n")
            else:
                log_text.insert(tk.END, message + "\n", color_tag)
            log_text.see(tk.END)
            log_text.config(state=tk.DISABLED)
        except Exception:
            pass

    if show_in_status and not is_detailed and 'status_var' in globals():
        try:
            path_match = re.search(r'\[\+\] 点击查看: (.*)$', message)
            if path_match:
                status_var.set("[+] 视频下载完成，点击查看详细日志")
            else:
                if "[+] 下载完成:" in message:
                    status_var.set(f"[+] 下载完成: {message.split(': ')[1]}")
                elif "[+] 开始下载:" in message:
                    status_var.set("[+] 开始下载视频...")
                elif "[-] 下载失败" in message or "[-] 网络请求错误" in message:
                    status_var.set("[-] 下载失败，请查看详细日志")
                elif "[+] 开始监控剪贴板" in message:
                    status_var.set("[+] 开始监控剪贴板")
                elif "[+] 停止监控" in message:
                    status_var.set("[+] 停止监控")
                elif "[+] 网站扫描完成" in message:
                    status_var.set("[+] 网站扫描完成")
                elif "[+] 下载路径已更改为:" in message:
                    status_var.set(f"[+] 下载路径已更改")
                elif "[+] 成功连接到视频服务器" in message:
                    status_var.set("[+] 正在下载视频...")
                elif "[+] 发现视频URL:" in message or ("[+] 发现" in message and "视频流链接" in message):
                    status_var.set("[+] 发现视频链接")
                elif "[+] 检测到" in message and "视频页面" in message:
                    status_var.set(f"[+] 检测到视频页面")
                elif "[+] 扫描错误" in message:
                    status_var.set("[-] 扫描错误，请查看详细日志")
                elif "[+] 开始扫描" in message:
                    status_var.set("[+] 正在扫描网站...")
        except Exception:
            pass

# 在日志中显示消息
def log_message(message, show_in_status=True, is_detailed=False):
    # 先保存到详细日志（纯内存列表操作，线程安全由GIL保证）
    detailed_logs.append(message)

    # is_detailed 且不显示在状态栏的，完全不需要碰UI，直接返回
    if is_detailed and not show_in_status:
        return

    # 通过 root.after(0) 切回主线程渲染，避免跨线程操作Tk控件
    try:
        root.after(0, lambda: _render_log_message(message, show_in_status, is_detailed))
    except Exception:
        pass  # 主窗口销毁时忽略

# 按钮点击效果函数
def button_click_effect(button, original_bg):
    """为按钮添加点击效果"""
    # 点击时的效果
    button.config(bg="#d0d0d0")
    # 模拟点击后恢复
    button.after(100, lambda: button.config(bg=original_bg))

# 合并已有文件：扫描下载目录中的未合并视频+音频对
def merge_existing_files():
    """扫描下载目录，将未合并的视频+音频文件对用ffmpeg合并"""
    def _merge_task():
        # 确保ffmpeg可用
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            log_message(f"[+] 未检测到 ffmpeg，正在自动下载...")
            ffmpeg_path = ensure_ffmpeg_available()
        if not ffmpeg_path:
            log_message(f"[-] ffmpeg不可用，无法合并。请先确保ffmpeg下载成功")
            return

        # 扫描下载目录
        if not os.path.exists(DOWNLOAD_DIR):
            log_message(f"[-] 下载目录不存在: {DOWNLOAD_DIR}")
            return

        log_message(f"[+] 开始扫描下载目录: {DOWNLOAD_DIR}")

        # 收集所有视频和音频文件
        all_files = os.listdir(DOWNLOAD_DIR)
        video_files = [f for f in all_files if f.lower().endswith('.mp4') and '_音频' not in f]
        audio_files = [f for f in all_files if '_音频' in f and (f.lower().endswith('.m4a') or f.lower().endswith('.mp4'))]
        cover_files = [f for f in all_files if f.lower().endswith('.jpg')]

        if not audio_files:
            log_message(f"[+] 未发现需要合并的音频文件（文件名含'_音频'）")
            log_message(f"[+] 所有视频文件可能已经合并完成")
            return

        log_message(f"[+] 发现 {len(audio_files)} 个音频文件，开始匹配和合并...")

        merged_count = 0
        for audio_file in audio_files:
            # 从音频文件名推导视频文件名: "标题_音频.m4a" → "标题.mp4"
            base_name = audio_file.replace('_音频', '').rsplit('.', 1)[0]
            video_file = f"{base_name}.mp4"
            video_path = os.path.join(DOWNLOAD_DIR, video_file)
            audio_path = os.path.join(DOWNLOAD_DIR, audio_file)

            if not os.path.exists(video_path):
                log_message(f"[-] 未找到匹配的视频文件: {video_file}", is_detailed=True)
                continue

            # 检查是否已有合并后的文件（避免重复）
            merged_path = os.path.join(DOWNLOAD_DIR, f"{base_name}_merged.mp4")
            if os.path.exists(merged_path):
                log_message(f"[+] 已存在合并文件，跳过: {base_name}_merged.mp4", is_detailed=True)
                continue

            # 查找封面
            cover_path = ''
            for cover_file in cover_files:
                if cover_file.rsplit('.', 1)[0] == base_name:
                    cover_path = os.path.join(DOWNLOAD_DIR, cover_file)
                    break

            # 构建ffmpeg命令
            cmd = [ffmpeg_path, '-i', video_path, '-i', audio_path]
            has_cover = cover_path and os.path.exists(cover_path)
            if has_cover:
                cmd.extend(['-i', cover_path])

            if has_cover:
                cmd.extend(['-map', '0', '-map', '1', '-map', '2',
                            '-c', 'copy', '-disposition:v:1', 'attached_pic'])
            else:
                cmd.extend(['-map', '0', '-map', '1', '-c', 'copy'])

            cmd.extend(['-y', merged_path])

            log_message(f"[+] 正在合并: {video_file} + {audio_file}")
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=300)
                if result.returncode == 0:
                    file_size = os.path.getsize(merged_path) / 1024 / 1024
                    cover_msg = "，已嵌入封面" if has_cover else ""
                    log_message(f"[+] 合并成功: {base_name}_merged.mp4 ({file_size:.1f}MB{cover_msg})")
                    # 删除原始文件和封面（封面已嵌入MP4）
                    try:
                        os.remove(video_path)
                        os.remove(audio_path)
                        if has_cover:
                            os.remove(cover_path)
                        log_message(f"[+] 已清理原始文件和封面", is_detailed=True)
                    except Exception:
                        pass
                    merged_count += 1
                else:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')[-200:]
                    log_message(f"[-] 合并失败: {base_name} - {error_msg}", is_detailed=True)
            except Exception as e:
                log_message(f"[-] 合并异常: {base_name} - {str(e)}", is_detailed=True)

        log_message(f"[+] 合并完成：成功 {merged_count}/{len(audio_files)} 个")

    # 在后台线程执行
    threading.Thread(target=_merge_task, daemon=True).start()

# 主函数
def main():
    global start_button, stop_button, url_entry, status_var, window, root

    # 创建GUI窗口
    window = tk.Tk()
    root = window  # 全局别名，供 log_message / check_clipboard 等函数通过 root.after() 调用
    window.title("视频嗅探下载器 v1.9.3")
    window.geometry("800x400")
    window.resizable(True, True)
    
    # 创建主框架
    main_frame = tk.Frame(window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 移除标题标签
    
    # 创建URL输入框
    url_frame = tk.Frame(main_frame)
    url_frame.pack(pady=5, fill=tk.X)
    
    url_label = tk.Label(url_frame, text="网站URL:", font=("微软雅黑", 9))
    url_label.pack(side=tk.LEFT, padx=(0, 5))
    
    # 按钮点击后，在后台线程执行扫描，避免 requests.get 阻塞主线程导致"未响应"
    def _scan_safe():
        button_click_effect(scan_button, "#f0f0f0")
        # 立即在主线程显示"开始扫描"提示，让用户知道按钮已响应
        scan_url = url_entry.get().strip()
        if scan_url:
            log_message(f"[+] 开始扫描网站: {scan_url}")
        # 立即返回主线程控制权，再启动线程
        threading.Thread(target=scan_website, args=(None, False), daemon=True).start()

    url_entry = tk.Entry(url_frame, width=60, font=("微软雅黑", 9))
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    # 支持回车键直接触发扫描网站
    url_entry.bind('<Return>', lambda e: _scan_safe())

    # 创建扫描按钮并添加点击效果
    scan_button = tk.Button(url_frame, text="扫描网站", command=_scan_safe, font=("微软雅黑", 9))
    scan_button.pack(side=tk.LEFT, padx=5)
    
    # 创建控制按钮
    button_frame = tk.Frame(main_frame)
    button_frame.pack(pady=10)
    
    # 按钮原始背景色
    original_bg = "#f0f0f0"
    
    # 创建开始监控按钮并添加点击效果
    start_button = tk.Button(button_frame, text="开始监控剪贴板", command=lambda: [button_click_effect(start_button, original_bg), start_monitoring()], width=15, font=("微软雅黑", 9))
    start_button.pack(side=tk.LEFT, padx=5)
    
    # 创建停止监控按钮并添加点击效果
    stop_button = tk.Button(button_frame, text="停止监控", command=lambda: [button_click_effect(stop_button, original_bg), stop_monitoring()], state=tk.DISABLED, width=15, font=("微软雅黑", 9))
    stop_button.pack(side=tk.LEFT, padx=5)
    
    # 添加选择下载路径按钮并添加点击效果
    path_button = tk.Button(button_frame, text="选择下载路径", command=lambda: [button_click_effect(path_button, original_bg), select_download_path()], width=15, font=("微软雅黑", 9))
    path_button.pack(side=tk.LEFT, padx=5)

    # 添加合并已有文件按钮并添加点击效果
    merge_button = tk.Button(button_frame, text="合并已有文件", command=lambda: [button_click_effect(merge_button, original_bg), merge_existing_files()], width=15, font=("微软雅黑", 9))
    merge_button.pack(side=tk.LEFT, padx=5)
    
    # 添加详细日志按钮并添加点击效果
    log_button = tk.Button(button_frame, text="详细日志", command=lambda: [button_click_effect(log_button, original_bg), show_detailed_logs()], width=15, font=("微软雅黑", 9))
    log_button.pack(side=tk.LEFT, padx=5)
    
    # 添加更新日志按钮并添加点击效果
    update_log_button = tk.Button(button_frame, text="更新日志", command=lambda: [button_click_effect(update_log_button, original_bg), show_update_log()], width=15, font=("微软雅黑", 9))
    update_log_button.pack(side=tk.LEFT, padx=5)
    
    # 显示当前下载路径
    global path_label
    path_label = tk.Label(main_frame, text=f"当前下载路径: {DOWNLOAD_DIR}", anchor=tk.W, font=("微软雅黑", 9))
    path_label.pack(pady=5, fill=tk.X)
    
    # 创建进度条
    global progress_var, progress_bar, download_info_label
    progress_var = tk.DoubleVar()
    # 从ttk模块导入Progressbar
    from tkinter import ttk
    
    progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100, length=750)
    progress_bar.pack(pady=5, fill=tk.X)
    progress_var.set(0)  # 初始进度为0
    
    # 创建下载信息标签
    download_info_label = tk.Label(main_frame, text="总大小: 0 MB | 已下载: 0 MB | 速度: 0 MB/s", anchor=tk.W, font=("微软雅黑", 9))
    download_info_label.pack(pady=2, fill=tk.X)
    
    # 创建日志显示区域
    global log_text
    log_frame = tk.Frame(main_frame, bd=1, relief=tk.GROOVE)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    # 创建日志标题
    log_title = tk.Label(log_frame, text="日志信息", font=("微软雅黑", 10, "bold"), anchor=tk.W)
    log_title.pack(fill=tk.X, padx=5, pady=2)
    
    log_text = scrolledtext.ScrolledText(log_frame, width=100, height=12, font=("微软雅黑", 9))
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
    # 配置日志颜色标签
    log_text.tag_config('success', foreground='#008000')  # 绿色
    log_text.tag_config('error', foreground='#CC0000')    # 红色
    log_text.tag_config('warn', foreground='#CC6600')     # 橙色
    log_text.tag_config('info', foreground='#0066CC')     # 蓝色
    log_text.config(state=tk.DISABLED)  # 设置为只读
    
    # 创建状态栏
    status_frame = tk.Frame(window, relief=tk.SUNKEN, bd=1)
    status_frame.pack(side=tk.BOTTOM, fill=tk.X)
    
    status_var = tk.StringVar()
    status_var.set("就绪")
    
    status_label = tk.Label(status_frame, textvariable=status_var, bd=1, relief=tk.FLAT, anchor=tk.W, font=("微软雅黑", 9))
    status_label.pack(fill=tk.X, padx=5, pady=2)

    # 加载并显示上一次的历史日志
    _saved_logs = _config.get('recent_logs', [])
    if _saved_logs:
        log_message("=========== 上次历史日志 ===========", show_in_status=False)
        # 只显示最近30条，避免太多
        for old_log in _saved_logs[-30:]:
            log_message(old_log, show_in_status=False)
        log_message("=========== 历史日志结束 ===========", show_in_status=False)

    # 退出时保存日志
    def _on_exit():
        save_config(download_path=DOWNLOAD_DIR, recent_logs=detailed_logs[-200:])
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", _on_exit)

    # 显示欢迎消息
    log_message("=====================================", show_in_status=False)
    log_message("视频嗅探下载器 v1.9.3", show_in_status=False)
    log_message("作者：李健辉", show_in_status=False)
    log_message("=====================================", show_in_status=False)
    log_message("使用说明：", show_in_status=False)
    log_message("1. 点击'开始监控剪贴板'，然后复制视频链接到剪贴板", show_in_status=False)
    log_message("   - 自动下载时会弹出独立的下载进度窗口", show_in_status=False)
    log_message("2. 或在URL输入框中输入网站地址，点击'扫描网站'提取视频链接", show_in_status=False)
    log_message("   - 手动扫描时使用主窗口的进度条显示下载进度", show_in_status=False)
    log_message("3. 下载的视频保存在设置的下载目录中", show_in_status=False)
    log_message("=====================================", show_in_status=False)
    
    # 在状态栏显示欢迎信息
    status_var.set("就绪 - 请开始使用视频嗅探下载器")
    
    # 运行GUI
    window.mainloop()

if __name__ == "__main__":
    main()
