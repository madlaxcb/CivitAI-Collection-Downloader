# CivitAI Collection Downloader (CivitAI 收藏下载器)

一个强大且易于使用的工具，用于下载 CivitAI 的收藏夹、帖子和用户内容。该工具支持下载图片和视频，并具备智能过滤和元数据保存功能。

原始项目是一个 Python 工具，用于从 CivitAI 的收藏和帖子中下载媒体文件（图片和视频）以及元数据。

这个工具是在经历了大量调试和"学习经验"后诞生的。我以"现状"提供它，不做任何保证、维护或承诺。如果 CivitAI 明天导致它无法使用，我也不会提供任何帮助。话虽如此，它在我的系统上运行良好，已经成功下载了数千张图片和少量视频。

大部分原始代码是通过 Claude Sonnet 3.7 生成的。

这是基于原版 CivitAI Downloader 修改的版本。它在原始项目的图形用户界面（GUI）基础上进行了扩展，并添加了一些新功能。此版本是使用 TRAE 和 Gemini 3 pro 开发的，现在这个版本与其说是下载器，不如说是个收藏夹管理器。这个版本应该是最终版本了，后续我也没有什么想要的需求了。

https://civitai.com/articles/24054
问题反馈可到该贴回复。

## 功能特性

- **多线程模型下载**：模型文件使用多个并发 HTTP Range 连接下载（可配置 1-8 线程，默认 4 线程），大幅提升下载速度。各线程下载独立分块，完成后合并。服务器不支持 Range 时自动回退为单线程。
- **断点续传**：自动跳过已下载的文件，节省时间和带宽。模型下载支持基于 HTTP Range 的断点续传。
- **磁盘空间校验**：下载模型文件前校验剩余磁盘空间，避免磁盘空间不足导致下载失败。
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

## v1.4.2 更新内容

- **多线程模型下载**：模型文件现在使用多个并发 HTTP Range 连接下载（可配置 1-8 线程，默认 4 线程），大幅提升速度。每个线程下载独立分块，完成后合并。服务器不支持 Range 时自动回退单线程。断点续传和磁盘空间校验保留。

## v1.4.1 更新内容

- **下载崩溃修复（修复）**：修复 API 返回的媒体 `mimeType` 为 `null` 时出现的 `'NoneType' object has no attribute 'lower'` 错误。此类项目现在能正常下载，不再导致整批中止。
- **视频库打包修复（修复）**：修复启动时 `DLL load failed while importing _core` 错误。Windows 构建现在正确打包 `av`（PyAV）的所有子模块、扩展模块以及 `av.libs` 中的 FFmpeg DLL 依赖，视频播放/预览开箱即用。

## v1.4 更新内容

- **收藏集管理（修复）**：用官方 TRPC API（`collection.getAllUser`）替换失效的 HTML 抓取来列出用户收藏集。之前的 403 Forbidden 错误已解决。
- **收藏集文件列表（修复）**：修复获取收藏集文件时的 `'str' object has no attribute 'get'` 错误。`image.getInfinite` 端点返回 superjson devalue 序列化数据；新增解码器正确解析。现在能完整列出所有文件（图片+视频），支持完整分页。
- **全 API 架构**：所有功能均使用 CivitAI 官方 API（TRPC + REST）。移除了最后一个 HTML 抓取路径（CDN key 获取），改用 REST API。
- **模型下载断点续传**：加固模型文件的 HTTP Range 断点续传。处理 416 错误、服务器不支持 Range 的情况，保留 `.part` 文件供下次续传。根据 `Content-Length` / API 提供的 `sizeKB` 校验下载文件大小。
- **磁盘空间校验**：在开始和恢复模型下载前校验剩余磁盘空间（含 5% / 50MB 安全余量）。空间不足时提前中止并给出明确错误。
- **健壮的错误处理**：单个损坏的媒体文件不再导致整个收藏集/帖子/用户下载中断。错误按单条记录日志，批次继续执行。
- **SOCKS5 代理支持**：新增 `PySocks` 依赖，SOCKS5 代理开箱即用。
- **其他修复**：移除导致启动崩溃的无用 `import yaml`；移除无用的 `beautifulsoup4` 依赖。

## v1.3.0 更新内容

- **域名选择**：新增在设置中切换 `civitai.com` 和 `civitai.red` 的功能。API 请求将使用所选域名，CDN 下载始终使用 `image.civitai.com`。
- **设置页优先**：将设置标签页移至第一位，方便快速访问配置。
- **设置页滚动**：修复了设置页面鼠标滚轮无法滚动的问题。
- **单文件打包**：现在以单个 `CivitAI_Downloader.exe` 文件分发，取代之前的文件夹形式。

## 安装与使用

### 1. 安装
1.  **下载**：从 Releases 页面获取最新版本（`CivitAI_Downloader.exe`）。
2.  **运行**：双击 `CivitAI_Downloader.exe` 启动程序。
    *   *注意：由于程序未经代码签名，首次运行时 Windows SmartScreen 可能会提示"Windows 已保护你的电脑"。请点击 **"更多信息"** → **"仍要运行"** 即可继续。*

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
    *   `Model`（模型）：通过模型 ID 或 URL 下载模型文件、示例图和元数据（例如 `https://civitai.com/models/12345`）。支持多线程下载和版本选择。
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
- Python 3.9 或更高版本
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

项目包含 PyInstaller spec 文件（`CivitAI_Downloader.spec`），自动处理所有依赖的打包，包括 PyAV 的 `av.libs` 中的 FFmpeg DLL。

**在 Windows 上：**
```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller CivitAI_Downloader.spec --noconfirm --clean
```

**在 Linux 上交叉编译（通过 Docker + Wine）：**
```bash
docker run --rm -w /src -v $(pwd):/src tobix/pywine:3.9 \
  sh -c "wine pip install -r requirements.txt && wine python -m PyInstaller CivitAI_Downloader.spec --noconfirm --clean"
```

### 关于 `tkVideoPlayer` 的说明
本项目使用 `tkVideoPlayer` 的修补版本，以确保与较新版本的 `av` 库 (v15.0.0+) 兼容。修补后的库以 `tkVideoPlayer.py` 文件的形式包含在此仓库中。`requirements.txt` 中已将其排除，以优先使用本地修补版本。

## 许可证

MIT License
