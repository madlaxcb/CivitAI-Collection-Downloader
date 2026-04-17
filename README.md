# CivitAI Collection Downloader（[中文版说明](https://github.com/madlaxcb/CivitAI-Collection-Downloader/blob/main/README_CN.md)）

A powerful, user-friendly tool to download collections, posts, and user content from CivitAI. This tool supports downloading both images and videos, with smart filtering and metadata preservation.

The original project is a Python tool designed to download media (images and videos) and metadata from CivitAI collections and posts.

This tool came into existence after extensive debugging and "learning experiences." I provide it as-is, with no guarantees, maintenance, or commitments. If CivitAI breaks it tomorrow, I won't be offering any assistance. That said, it works well on my system and has successfully downloaded thousands of images and a few videos.

Most of the original code was generated using Claude Sonnet 3.7.

This is a modified version based on the original CivitAI Downloader. It builds upon the original project's GUI and adds some new features. This version was developed using TRAE and Gemini 3 pro,This version is more of a Collection manager than a downloader. It should be the final version, as I don't have any further needs or features in mind..

https://civitai.com/articles/24054 
You can provide feedback by replying to this post.

## Features

- **Multi-threaded Downloading**: Fast downloads with concurrent connections.
- **Resume Capability**: Skips already downloaded files to save time and bandwidth.
- **Smart Filtering**: Options to download images, videos, or both.
- **Metadata Support**: Saves image metadata and generation info (compatible with Stable Diffusion WebUI).
- **Domain Selection**: Choose between `civitai.com` and `civitai.red` as the download source.
- **Proxy Support**: Full HTTP/SOCKS proxy support with authentication for users in restricted network environments.
- **Language Support**: Bilingual interface (English and Simplified Chinese / 简体中文,with the option to add language files to support more languages).
- **User Friendly UI**: Clean interface with progress tracking, logs, and preview.
- **Optimized Video Handling**:
    - **Correct Video Downloads**: Automatically handles CivitAI CDN parameters to ensure valid MP4 files are downloaded instead of WebP previews.
    - **Efficient Previews**: Uses lightweight WebP previews in the UI to reduce memory usage and prevent crashes.
- **Portable**: Available as a standalone single-file executable, no installation required.
- **Customizable**: Editable language files and configuration.

## What's New in v1.3.0

- **Domain Selection**: Added the ability to switch between `civitai.com` and `civitai.red` in Settings. The API requests will use the selected domain, while CDN downloads remain on `image.civitai.com`.
- **Settings Tab First**: Moved the Settings tab to the first position for quicker access to configuration.
- **Scrollable Settings**: Fixed mouse wheel scrolling on the Settings page for better usability.
- **Single-File Build**: Now distributed as a single `CivitAI_Downloader.exe` file instead of a folder.

## Installation & Usage

### 1. Installation
1.  **Download**: Get the latest release (`CivitAI_Downloader.exe`) from the Releases page.
2.  **Run**: Double-click `CivitAI_Downloader.exe` to launch the application.

### 2. Configuration
1.  **Domain Selection** (New):
    *   Go to the `Settings` tab.
    *   Select your preferred domain (`civitai.com` or `civitai.red`) from the dropdown.
    *   Click `Save Settings`.

2.  **API Key Setup** (Optional but Recommended):
    *   Go to the `Settings` tab.
    *   Enter your CivitAI API Key. You can generate one at CivitAI Settings -> API Key.
    *   Click `Save Settings`.
    *   *Note: An API Key is required for downloading NSFW content or accessing private collections.*

3.  **Language Settings**:
    *   Go to the `Settings` tab.
    *   Select your preferred language (e.g., `zh_CN` or `en`) from the dropdown menu.
    *   Click `Save Settings`. The interface will update immediately.

4.  **Proxy Setup** (If needed):
    *   Go to the `Settings` tab.
    *   Check `Enable Proxy`.
    *   Select Protocol (`HTTP` or `SOCKS5`).
    *   Enter Host (e.g., `127.0.0.1`) and Port (e.g., `7890`).
    *   Click `Save Settings`.

### 3. Downloading Content
1.  **Select Task Type**:
    *   `Collection`: Download a specific collection (e.g., `https://civitai.com/collections/12345`).
    *   `Post`: Download images/videos from a specific post.
    *   `User`: Download all images posted by a specific user.
2.  **Enter ID**:
    *   For URL `https://civitai.com/collections/12345`, the ID is `12345`.
    *   For URL `https://civitai.com/user/username`, the ID is `username`.
3.  **Start Download**:
    *   Click `Start`.
    *   Monitor progress in the log window.
    *   Files are saved to `Pictures/CivitAI` by default (changeable in Settings).

## Development / Running from Source

If you wish to run the code from source or contribute:

### Prerequisites
- Python 3.11 or higher
- Windows 10/11 (Recommended)

### Setup
1.  Clone this repository or download the source code.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python main.py
    ```

### Building from Source
```bash
pip install pyinstaller
pyinstaller --name "CivitAI_Downloader" --windowed --onefile --add-data "locales;locales" --add-data "user_agreement.py;." main.py
```

### Note on `tkVideoPlayer`
This project uses a patched version of `tkVideoPlayer` to ensure compatibility with newer versions of the `av` library (v16.0.0+). The patched library is included as `tkVideoPlayer.py` in this repository. The `requirements.txt` excludes it to prioritize the local patched version.

## License

MIT License
