# SMS Video Converter v1.0

A command-line Python utility that batch converts video files or single file into **DviX format** that [PS2 Simple Media System](https://github.com/ps2homebrew/SMS) supports, using `ffmpeg`, with optional cropping, subtitle burning (internal or external), and real-time progress monitoring.

This was inspired by following Reddit posts:
- [Converting videos for playback on PS2 using Simple Media System (SMS)](https://www.reddit.com/r/crtgaming/comments/17rfbk6/converting_videos_for_playback_on_ps2_using/)
- [TUTORIAL: convert any media file to one playable on your PlayStation 2 w/simple media system](https://www.reddit.com/r/ps2/comments/7uaslk/tutorial_convert_any_media_file_to_one_playable/)
- [How to convert videos to play on SMS (Simple Media System) [Tutorial]](https://www.reddit.com/r/ps2homebrew/comments/19aptns/how_to_convert_videos_to_play_on_sms_simple_media/)


## ✨ Features

- 🔍 Automatically detects video resolution and internal subtitle tracks
- ✂️ Optionally crops widescreen videos to 4:3
- 💬 Burn subtitles into video:
  - Internal (by subtitle stream index)
  - External (`.srt` / `.ass`) auto-detected from filename
- 📈 Displays live conversion progress


## ⚙️ Requirements

- Python 3.6+
- [`ffmpeg`](https://ffmpeg.org/) and `ffprobe` must be installed and available in your system's PATH


## 🧑‍💻 Usage

1. **Run the script:**

    ```bash
    python ps2_sms_converter.py
    ```

2. Follow the interactive prompts:
    - Enter the source video file or directory
    - Enter the output directory
    - Set the video bitrate
    - Choose cropping option (yes/no)
    - Choose subtitle burning option from:
        - None
        - Internal (by stream index)
        - External (auto-detected)
    - Decide whether to overwrite existing files (yes/no)
    - Wait patiently or impatiently (you do you)


## 📁 Supported Formats

- Input Video Extensions: `.mkv`, `.mp4`, `.avi`, `.rmvb`, `.rm`, `.mov`, `.flv`, `.mpg`, `.mpeg`, `.wmv`
- External Subtitle Extensions: `.srt`, `.ass`


## 📦 Output Details

- Resolution:
    - Widescreen (16:9): 854x480
    - Standard (4:3): 640x480

- Encoding:
    - Video: DviX (1000k - 9000k)
    - Audio: MP3Lame (192k)


## 📝 Example Output

```
## Welcome to SMS Video Converter v1.0! ##
# Enter the path of the source video file or directory:
D:\Videos\DEATH NOTE
# Scanning... Done
# Enter the path of the output directory:
D:\Videos\DEATH NOTE\output
# Please set the video bitrate, numbers only: (1000-9000 kbps):
2500
# Crop the widescreen video to 4:3? (y/N)
y
# Burn the text subtitles to the video? (Y/n)
y
# Burn internal or external subtitles?
  1. Internal
  2. External
1
# Enter the number of subtitle track, the first track will be 0:
0
# Overwrite existing files in the output directory? (y/N)
y
 1/3: Converting myvideo.S01E01.mkv... Completed
 2/3: Converting myvideo.S01E02.mkv... 42%
 ```


## ❗ Notes
- In my testing, a video bitrate of 2000–3000 kbps strikes a good balance between picture quality and smooth playback when playing from USB devices.
- Cropping is only applied if the original video is wider than standard 4:3 ratio.
- Subtitles can be burned only if a valid stream or external file is found.
