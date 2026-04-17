# CivitAI Collection Downloader (CivitAI 收藏下载器)

一个强大且易于使用的工具，用于下载 CivitAI 的收藏夹、帖子和用户内容。该工具支持下载图片和视频，并具备智能过滤和元数据保存功能。

原始项目是一个 Python 工具，用于从 CivitAI 的收藏和帖子中下载媒体文件（图片和视频）以及元数据。

这个工具是在经历了大量调试和"学习经验"后诞生的。我以"现状"提供它，不做任何保证、维护或承诺。如果 CivitAI 明天导致它无法使用，我也不会提供任何帮助。话虽如此，它在我的系统上运行良好，已经成功下载了数千张图片和少量视频。

大部分原始代码是通过 Claude Sonnet 3.7 生成的。

这是基于原版 CivitAI Downloader 修改的版本。它在原始项目的图形用户界面（GUI）基础上进行了扩展，并添加了一些新功能。此版本是使用 TRAE 和 Gemini 3 pro 开发的，现在这个版本与其说是下载器，不如说是个收藏夹管理器。这个版本应该是最终版本了，后续我也没有什么想要的需求了。

https://civitai.com/articles/24054
问题反馈可到该贴回复。

## 功能特性

- **多线程下载**：支持并发连接，实现高速下载。
- **断点续传**：自动跳过已下载的文件，节省时间和带宽。
- **智能过滤**：可选择下载图片、视频或两者都下载。
- **元数据支持**：保存图片元数据和生成信息（兼容 Stable Diffusion WebUI）。
- **域名选择**：支持在 `civitai.com` 和 `civitai.red` 之间切换下载源。
- **代理支持**：完全支持 HTTP/SOCKS 代理及身份验证，适合受限网络环境。
- **多语言支持**：双语界面（英语和简体中文,可自行新增语言文件以支持更多语言）。
- **用户友好的 UI**：界面整洁，提供进度跟踪、日志记录和预览功能。
- **优化的视频处理**：
    - **正确的视频下载**：自动处理 CivitAI CDN 参数，确保下载的是有效的 MP4 视频文件，而不是 WebP 预览图。
    - **高效的预览**：在 UI 中使用轻量级的 WebP 预览图，减少内存占用并防止程序崩溃。
- **便携式**：提供独立的单文件可执行程序，无需安装。
- **可定制**：可编辑语言文件和配置。

## v1.3.0 更新内容

- **域名选择**：新增在设置中切换 `civitai.com` 和 `civitai.red` 的功能。API 请求将使用所选域名，CDN 下载始终使用 `image.civitai.com`。
- **设置页优先**：将设置标签页移至第一位，方便快速访问配置。
- **设置页滚动**：修复了设置页面鼠标滚轮无法滚动的问题。
- **单文件打包**：现在以单个 `CivitAI_Downloader.exe` 文件分发，取代之前的文件夹形式。

## 安装与使用

### 1. 安装
1.  **下载**：从 Releases 页面获取最新版本（`CivitAI_Downloader.exe`）。
2.  **运行**：双击 `CivitAI_Downloader.exe` 启动程序。

### 2. 配置
1.  **域名选择**（新增）：
    *   进入 `Settings`（设置）标签页。
    *   从下拉菜单中选择域名（`civitai.com` 或 `civitai.red`）。
    *   点击 `Save Settings`（保存设置）。

2.  **API Key 设置**（可选但推荐）：
    *   进入 `Settings`（设置）标签页。
    *   输入你的 CivitAI API Key。你可以在 CivitAI Settings -> API Key 生成。
    *   点击 `Save Settings`（保存设置）。
    *   *注意：下载 NSFW 内容或访问私有收藏夹需要 API Key。*

3.  **语言设置**：
    *   进入 `Settings`（设置）标签页。
    *   从下拉菜单中选择首选语言（例如 `zh_CN` 或 `en`）。
    *   点击 `Save Settings`（保存设置）。界面将立即更新。

4.  **代理设置**（如果需要）：
    *   进入 `Settings`（设置）标签页。
    *   勾选 `Enable Proxy`（启用代理）。
    *   选择协议（`HTTP` 或 `SOCKS5`）。
    *   输入主机（例如 `127.0.0.1`）和端口（例如 `7890`）。
    *   点击 `Save Settings`（保存设置）。

### 3. 下载内容
1.  **选择任务类型**：
    *   `Collection`（收藏夹）：下载特定收藏夹（例如 `https://civitai.com/collections/12345`）。
    *   `Post`（帖子）：下载特定帖子中的图片/视频。
    *   `User`（用户）：下载特定用户发布的所有图片。
2.  **输入 ID**：
    *   对于 URL `https://civitai.com/collections/12345`，ID 为 `12345`。
    *   对于 URL `https://civitai.com/user/username`，ID 为 `username`。
3.  **开始下载**：
    *   点击 `Start`（开始）。
    *   在日志窗口中监控进度。
    *   文件默认保存到 `Pictures/CivitAI`（可在设置中更改）。

## 开发 / 从源码运行

如果您希望从源码运行代码或参与贡献：

### 前提条件
- Python 3.11 或更高版本
- Windows 10/11（推荐）

### 设置
1.  克隆此仓库或下载源代码。
2.  安装依赖：
    ```bash
    pip install -r requirements.txt
    ```
3.  运行应用程序：
    ```bash
    python main.py
    ```

### 从源码构建
```bash
pip install pyinstaller
pyinstaller --name "CivitAI_Downloader" --windowed --onefile --add-data "locales;locales" --add-data "user_agreement.py;." main.py
```

### 关于 `tkVideoPlayer` 的说明
本项目使用 `tkVideoPlayer` 的修补版本，以确保与较新版本的 `av` 库 (v16.0.0+) 兼容。修补后的库以 `tkVideoPlayer.py` 文件的形式包含在此仓库中。`requirements.txt` 中已将其排除，以优先使用本地修补版本。

## 许可证

MIT License
