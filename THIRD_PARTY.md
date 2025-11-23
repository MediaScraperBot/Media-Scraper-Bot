# Media Scraper Bot - Third Party Tools

## OnlyFans Downloader (OF-DL)

This application integrates with **OF-DL** for downloading OnlyFans content.

### Download OF-DL

OF-DL is an external tool that must be downloaded separately due to licensing.

**Official Repository:**
https://git.ofdl.tools/sim0n00ps/OF-DL

**Download Link:**
https://git.ofdl.tools/sim0n00ps/OF-DL/releases

### Installation Steps

1. Download the latest `OF-DL.exe` from the releases page
2. Place it in a dedicated folder (e.g., `C:\Tools\OF-DL\`)
3. Open Media Scraper Bot
4. Go to **OnlyFans** tab
5. Click **Browse** to select `OF-DL.exe`
6. Configure download options in **Settings** tab
7. Click **Launch OF-DL** to start downloading

### Why Not Bundled?

OF-DL is:
- Independently developed and maintained
- Under separate license terms
- Frequently updated with new features
- Large binary file (~50MB+)

By downloading it separately, you always get the latest version with bug fixes and new features.

### OF-DL Features

- Browser-based authentication (more reliable than API)
- Download posts, messages, stories, highlights, streams
- Support for images, videos, and audio
- Incremental downloads (resume support)
- Expired subscription support
- Configurable download filters

### Configuration

The Media Scraper Bot automatically generates OF-DL config files based on your settings in the **Settings** tab:

- Content types to download
- Media types (images/videos/audio)
- Organization (folder per post/message)
- Advanced filters (skip ads, include expired subs, etc.)

### Support

For OF-DL specific issues:
- Visit: https://git.ofdl.tools/sim0n00ps/OF-DL
- Check their documentation and issues

For integration issues with Media Scraper Bot:
- Open an issue in this repository
