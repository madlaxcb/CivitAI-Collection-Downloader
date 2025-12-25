# CivitAI Collection Downloader v1.1.0

The original project is a Python tool designed to download media (images and videos) and metadata from CivitAI collections and posts.

This tool came into existence after extensive debugging and "learning experiences." I provide it as-is, with no guarantees, maintenance, or commitments. If CivitAI breaks it tomorrow, I won’t be offering any assistance. That said, it works well on my system and has successfully downloaded thousands of images and a few videos.

The post functionality is completely untested, but as mentioned above, if anyone encounters issues and submits a fix or a pull request, I’ll approve it. However, to be honest, I’ve already used this tool to download the content I needed and may not use it again.

Most of the original code was generated using Claude Sonnet 3.7.

This is a modified version based on the original CivitAI Downloader. It builds upon the original project’s GUI and adds some new features. This version was developed using Antigravity and Gemini 3.

## To-do:

1. Package the files after download.

2. Enable downloading content from a user’s albums or videos (e.g., https://civitai.com/user/username/images or https://civitai.com/user/username/videos).

## Overview

This application allows you to easily download content from the CivitAI platform, including:

- Images and videos from collections
- Images and videos from posts
- Associated metadata (prompts, models used, tags, etc.)
- Complete collection/post information

All content is organized into a structured directory hierarchy for easy browsing and management.

## Features

- **Collection and Post Support**: Download from individual CivitAI collections and posts, or process multiple IDs in a single run
- **Complete Metadata**: Automatically retrieves and saves generation prompts, models used, tags, and other details
- **Proxy Support**: Support for HTTP and SOCKS5 proxies containing authentication
- **Post-Download Actions**: Automatically close, shutdown, sleep or hibernate after download completes
- **Reliable Downloads**: Built-in retry logic for handling network errors and interruptions
- **Flexible Configuration**: Customizable download locations and behavior
- **Dry Run Mode**: Preview what would be downloaded without actually downloading files
- **Verbose Logging**: Detailed information about the download process when needed

## Installation

### Prerequisites

- Python 3.6 or higher
- The pyyaml Library

### Setup

1. Clone this repository or download the source code:

```bash
git clone https://github.com/madlaxcb/CivitAI-Collection-Downloader
cd CivitAI-Collection-Downloader
```

2. Install the required dependencies:

```bash
pip install requests pyyaml
```

## Configuration

On first run, the application will prompt you for:

1. Your CivitAI API key
2. A download directory (defaults to `~/Pictures/CivitAI`)
3. Proxy settings (HTTP/SOCKS5) if required
4. Post-download actions (System shutdown, sleep, etc.)

These settings are saved to a configuration file at `~/.civitai_downloader/config.json`.

**New in v1.1:**
- Proxy settings are now hidden by default and only show when "Enable Proxy" is checked.
- Post-download actions are now selected via a dropdown menu.

### Getting a CivitAI API Key

To use this tool, you need a CivitAI API key:

1. Create an account or log in at [CivitAI](https://civitai.com/)
2. Navigate to your user settings and find the API section
3. Generate a new API key

## Usage
1. Run `CivitAI_Downloader.exe`.
2. Go to the **Settings** tab to configure your [API Key](https://civitai.com/user/settings) and Download Directory.
   - You can also configure Proxy settings and Post-download actions here.
3. Switch to the **Download** tab.
4. Select the download type (**Collection** or **Post**).
5. Enter the ID(s) you wish to download (comma-separated for multiple).
6. Click **Start Download**.

### Configuration
All settings can be configured directly in the **Settings** tab of the application.
- **API Key**: Required for downloading age-restricted content or private collections.
- **Download Directory**: Where files will be saved.
- **Proxy**: Support for HTTP and SOCKS5 proxies.
- **Post-Download Action**: Choose to Close, Sleep, Hibernate, or Shutdown after tasks complete.

## Output Structure

For a collection with ID 12345 and name "Example Collection":

```
~/Pictures/CivitAI/12345-Example_Collection/
├── collection_metadata.json
├── image1.jpg
├── image1_metadata.json
├── image2.png
├── image2_metadata.json
└── ...
```

For a post with ID 67890 and title "Example Post":

```
~/Pictures/CivitAI/67890-Example_Post/
├── post_metadata.json
├── image1.jpg
├── image1_metadata.json
├── image2.png
├── image2_metadata.json
└── ...
```

## Metadata Format

The tool saves detailed metadata for each downloaded item, including:

- Basic information (dimensions, MIME type, creation date, etc.)
- Generation data (prompts, negative prompts)
- Models used in creation
- Tags and other metadata

## Troubleshooting

### Download Failures

The tool has built-in retry logic, but persistent failures might indicate:
- Network connectivity issues
- CivitAI server problems
- Invalid or deleted content IDs

Try using the `--verbose` flag to get more detailed error information.

### Changing Configuration

You can manually edit the configuration file at `~/.civitai_downloader/config.json` or delete it to be prompted again on the next run.
