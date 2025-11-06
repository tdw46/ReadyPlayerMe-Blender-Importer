# ReadyPlayerMe Blender Importer

Import ReadyPlayerMe avatars directly into Blender with a modern webview-based UI.

## Installation

**Get the extension from Blender Extensions:** [ReadyPlayerMe Blender Importer](https://extensions.blender.org/approval-queue/readyplayerme-blender-importer/)

## Demo

![ReadyPlayerMe Blender Importer Demo](resources/RPM%20Blender%20Importer%20Demo.gif)

## Video Tutorial

<video width="100%" controls>
  <source src="https://extensions.blender.org/media/videos/9c/9c0ceac85f2135631b48df1364033d29de15403c9eada83e6e91728ff299315f.mp4" type="video/mp4">
  Your browser does not support the video tag. <a href="https://extensions.blender.org/media/videos/9c/9c0ceac85f2135631b48df1364033d29de15403c9eada83e6e91728ff299315f.mp4">Watch the tutorial video here</a>.
</video>

## Features

- 🎨 Modern webview UI for browsing and importing avatars
- 🔐 Login to your ReadyPlayerMe account to access your avatars
- ⚙️ Customizable import options (quality, T-pose, ARKit shapes, texture atlas)
- 🔄 Automatic avatar refresh and synchronization
- 💾 Persistent preferences and avatar cache

## Requirements

- **Blender 4.5.0 or later**
  
pywebview is bundled with the extension; no separate installation is required.

## Installation

### Blender 4.2+ Extensions Platform

1. Download the addon as a ZIP file
2. Open Blender 4.2+
3. Go to **Edit > Preferences > Get Extensions**
4. Click the dropdown menu (⋮) and select **Install from Disk**
5. Navigate to the downloaded ZIP file and select it
6. The extension will be installed and enabled automatically

### Alternative: Manual Installation

1. Copy the entire `ReadyPlayerMe-Blender-Importer` folder to:
   - **Windows:** `%APPDATA%\Blender Foundation\Blender\4.5\extensions\user_default\`
   - **macOS:** `~/Library/Application Support/Blender/4.5/extensions/user_default/`
   - **Linux:** `~/.config/blender/4.5/extensions/user_default/`

2. Restart Blender or refresh extensions

## Setup

No additional setup is required. The webview runtime is provided by the extension.

## Usage

### Importing Avatars

1. Go to **File > Import > Ready Player Me**
2. A webview window will open with the ReadyPlayerMe interface
3. Log in with your ReadyPlayerMe account credentials
4. Click **Refresh Avatars** to load your avatar library
5. Select an avatar and configure import options:
   - **Quality:** High, Medium, or Low
   - **T-Pose:** Import in T-pose for easier rigging
   - **ARKit Shapes:** Include facial blend shapes for animation
   - **Texture Atlas:** Combine textures into a single atlas
6. Click **Import to Blender** to download and import the avatar

### Developer Mode

Enable Developer Mode in addon preferences to keep the webview window visible during avatar refresh operations. This is useful for debugging or seeing the login process.

## Preferences

The addon stores the following preferences:

- **Login Email:** Your ReadyPlayerMe account email
- **Login Password:** Your ReadyPlayerMe account password (stored in Blender preferences)
- **Avatar Cache:** List of your avatars with URLs and thumbnails
- **Developer Mode:** Toggle webview visibility during operations

Preferences are automatically saved to Blender's config directory and persist across sessions.

## Permissions

This extension requires:

- **File Access:** To download and import GLB files
- **Network Access:** To communicate with ReadyPlayerMe API

## Troubleshooting

### Webview window not opening

- pywebview is bundled with this extension; try restarting Blender
- On Windows, Edge WebView2 runtime may be required
- Check Blender console for error messages

### Avatars not loading

- Ensure you're logged into your ReadyPlayerMe account
- Click **Refresh Avatars** to reload the list
- Check your internet connection
- Verify credentials in addon preferences

### Import fails

- Some quality/size combinations are not supported by ReadyPlayerMe
- Try different quality settings or texture atlas sizes
- Check Blender console for detailed error messages

## Technical Details

### Blender 4.2+ Extensions

This addon is built for the new Blender 4.2+ extensions platform:

- Uses `blender_manifest.toml` instead of `bl_info` dict
- Compatible with extension sandboxing
- Follows extension naming conventions
- Proper permission declarations


## Support

For issues, feature requests, or contributions: GitHub

## Credits

- **Author:** BeyondDev (Tyler Walker)
- **ReadyPlayerMe:** https://readyplayer.me/
- **pywebview:** https://pywebview.flowrl.com/

---

Made with ❤️ for the Blender community
