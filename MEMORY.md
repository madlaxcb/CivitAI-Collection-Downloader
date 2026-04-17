# 用户信息
- 偏好：Windows 开发环境
- 技术栈：Python 3.11+, Tkinter GUI

# 项目上下文
- 当前项目：CivitAI-Collection-Downloader
- 架构：GUI + CLI 双入口，模块化设计
- 用途：从 CivitAI 下载图片/视频集合
- 版本：v1.3.0

# 技术架构
- **入口**：`main.py` (CLI), `gui.py` (GUI), `launcher.py` (启动器)
- **核心模块**：
  - `api.py` - CivitAI TRPC API 客户端（动态域名）
  - `downloader.py` - 媒体下载逻辑（动态CDN域名）
  - `config.py` - 配置管理 + 域名配置工具函数
  - `cache.py` - 缓存管理
  - `language_manager.py` - 国际化
- **依赖**：requests, beautifulsoup4, Pillow, av (视频处理)
- **GUI**：Tkinter + 自定义 tkVideoPlayer
- **域名配置**：支持 civitai.com / civitai.red 切换

# 已解决问题
- 项目克隆成功 (2026-04-16)
- v1.3.0：域名选择功能（civitai.com / civitai.red）、所有硬编码域名改为动态配置
- v1.3.0：PyInstaller 打包成功，产出 dist/CivitAI_Downloader_v1.3.0.zip (~57MB)

# 重要约定
- Python 3.11+ required
- Windows 10/11 recommended
- CDN Key 自动获取或配置
- 域名切换后 CDN Key 缓存自动清除
- config.py 提供 get_site_base_url/get_image_cdn_domain/get_image_cdn_base 工具函数
