# CivitAI Collection Downloader

A powerful, user-friendly tool to download collections, posts, and user content from CivitAI. This tool supports downloading both images and videos, with smart filtering and metadata preservation.

## Features

- **Multi-threaded Downloading**: Fast downloads with concurrent connections.
- **Resume Capability**: Skips already downloaded files to save time and bandwidth.
- **Smart Filtering**: Options to download images, videos, or both.
- **Metadata Support**: Saves image metadata and generation info (compatible with Stable Diffusion WebUI).
- **Proxy Support**: Full HTTP/SOCKS proxy support with authentication for users in restricted network environments.
- **Language Support**: Bilingual interface (English and Simplified Chinese / 简体中文).
- **User Friendly UI**: Clean interface with progress tracking, logs, and preview.
- **Customizable**: Editable language files and configuration.

## Installation & Usage

### 1. Installation
1.  **Download**: Get the latest release (`CivitAI_Downloader.zip`) from the Releases page.
2.  **Extract**: Unzip the folder to a location of your choice.
3.  **Run**: Double-click `CivitAI_Downloader.exe` to launch the application.

### 2. Configuration
1.  **API Key Setup** (Optional but Recommended):
    *   Go to the `Settings` tab.
    *   Enter your CivitAI API Key. You can generate one at [CivitAI Settings](https://civitai.com/user/settings) -> API Key.
    *   Click `Save Settings`.
    *   *Note: An API Key is required for downloading NSFW content or accessing private collections.*

2.  **Language Settings**:
    *   Go to the `Settings` tab.
    *   Select your preferred language (e.g., `zh_CN` or `en`) from the dropdown menu.
    *   Click `Save Settings`. The interface will update immediately.

3.  **Proxy Setup** (If needed):
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

### Note on `tkVideoPlayer`
This project uses a patched version of `tkVideoPlayer` to ensure compatibility with newer versions of the `av` library (v16.0.0+). The patched library is included as `tkVideoPlayer.py` in this repository. The `requirements.txt` excludes it to prioritize the local patched version.

## License

MIT License
