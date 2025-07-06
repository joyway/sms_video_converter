import os
import re
import time
import json
import shutil
from pathlib import Path
from subprocess import Popen, PIPE

VERSION = '1.0'
WELCOME_MSG = f'## Welcome to SMS Video Converter v{VERSION}! ##'
VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.rmvb', '.rm', '.mov', '.flv', '.mpg', '.mpeg', '.wmv')
SUBTITLE_EXTS = ('.ass', '.srt')
RESOLUTION_4BY3 = '640x480'
RESOLUTION_16BY9 = '854x480'
VIDEO_BITRATE = '3000k'
AUDIO_BITRATE = '192k'


def get_options():
    """
    Interacts with the user to collect preferences.

    Returns:
        tuple: Options for video cropping, subtitle burning and overwrite existing files
    """
    # Should we crop the video to 4 by 3?
    should_crop = False
    while True:
        user_input_crop = str(input('Crop the widescreen video to 4:3? (y/N)\n'))
        if user_input_crop.strip().lower() == 'y':
            should_crop = True
            break
        elif user_input_crop.strip().lower() in ('', 'n'):
            break
        else:
            print('Invalid input!')
    # Should we burn the subtitle to the video?
    subtitle_choice = None
    while True:
        user_input_subtitle_burn = str(input('Burn the text subtitles to the video? (Y/n)\n'))
        if user_input_subtitle_burn.strip().lower() in ('', 'y'):
            while True:
                user_input_int_or_ext_subtitle = str(input(
                    'Burn internal or external subtitles? \n  1. Internal\n  2. External\n'
                    ))
                if user_input_int_or_ext_subtitle.strip() == '2':
                    subtitle_choice = 'ext'
                    break
                elif user_input_int_or_ext_subtitle.strip() == '1':
                    while True:
                        user_input_int_subtitle_index = str(input(
                        'Enter the number of subtitle track, the first track will be 0:\n'
                        ))
                        try:
                            subtitle_choice = int(user_input_int_subtitle_index.strip())
                            break
                        except Exception as e:
                            print(e)
                            print('Invalid input!')
                else:
                    print('Invalid input!')
                if subtitle_choice is not None:
                    break
            break
        elif user_input_subtitle_burn.strip().lower() == 'n':
            break
        else:
            print('Invalid input!')
    # Overwrite existing files in the output directory?
    overwrite_output = False
    while True:
        user_input_overwrite = str(input('Overwrite existing files in the output directory? (y/N)\n'))
        if user_input_overwrite.strip().lower() == 'y':
            overwrite_output = True
            break
        elif user_input_overwrite.strip().lower() in ('', 'n'):
            break
        else:
            print('Invalid input!')
    return should_crop, subtitle_choice, overwrite_output

def probe_source(source):
    """
    Probes a video file to extract resolution and subtitle stream info.

    Args:
        source (str): Filename of the source video.

    Returns:
        tuple:
            - resolution (dict): A dictionary containing the 'width' and 'height' of the first video stream
            - subtitles (list): A list of subtitle streams
    """
    # Probing the resolution
    probe_resolution_cmd = [
        'ffprobe', 
        '-v',
        'error',
        '-select_streams',
        'v:0',
        '-show_entries',
        'stream=width,height',
        '-of',
        'json',
        source
        ]
    probe_proc = Popen(probe_resolution_cmd, stdout=PIPE)
    resolution = json.loads(probe_proc.communicate()[0].decode("utf-8"))['streams'][0]
    # Probing subtitle streams
    probe_subtitle_cmd = [
        'ffprobe',
        '-v',
        'error',
        '-select_streams',
        's',
        '-show_entries',
        'stream=index',
        '-of',
        'json',
        source
        ]
    probe_proc = Popen(probe_subtitle_cmd, stdout=PIPE)
    subtitles = json.loads(probe_proc.communicate()[0].decode("utf-8"))['streams']
    return resolution, subtitles
    
def has_external_subtitle(base_dir, source):
    """
    Checks if an external subtitle file exists in the given directory that matches the source video name.

    Args:
        base_dir (str): Path to the directory to search for subtitle files.
        source (str): Filename of the source video.

    Returns:
        str or None: A subtitle command string for ffmpeg video filter (e.g., 'subtitles=example.srt') if a matching subtitle file is found;
        otherwise, returns None.
    """
    subtitle_cmd = None
    # Checking for external subtitle
    for each_file in os.listdir(base_dir):
        each_name, each_ext = os.path.splitext(each_file)
        each_ext = each_ext.lower()
        source_name = os.path.splitext(source)[0]
        if (each_ext in SUBTITLE_EXTS) and (source_name in each_name):
            subtitle_cmd = f'subtitles={os.path.basename(each_file)}'
            break
    return subtitle_cmd

def has_internal_subtitle(source, subtitle_streams, subtitle_choice):
    """
    Check if an internal subtitle stream exists that matches the index from the user preferences.

    Args:
        source (str): Filename of the source video.
        subtitle_streams (list): A list of available subtitle streams.
        subtitle_choice (int): The index of the internal subtitle stream to use.

    Returns:
        str or None: A formatted subtitle command string for ffmpeg video filter (e.g., 'subtitles=video.mkv:si=0') if the specified
        subtitle stream index exists. Returns None if the index is out of range.
    """
    subtitle_cmd = None
    try:
        subtitle_streams[subtitle_choice]
        subtitle_cmd = f'subtitles={source}:si={subtitle_choice}'
    except IndexError:
        print(f'Subtitle stream {subtitle_choice} not found')
    return subtitle_cmd

def calculate_cropping(resolution):
    """
    Calculate and generate the cropping command for ffmpeg video filter based on the given resolution.

    Args:
        resolution (dict): A dictionary containing the 'width' and 'height' of the video.

    Returns:
        str: A formatted crop command string for ffmpeg video filter (e.g. 'crop=1440:1080:240:0').
    """
    output_width = int((resolution['height'] / 3) * 4)
    cropped_width = int((resolution['width'] - output_width) / 2)
    return f'crop={output_width}:{resolution['height']}:{cropped_width}:0'
    

def get_sources():
    """
    Prompts the user to enter the path to a video file or directory and gathers information about video files found.

    The function:
        - Accepts a path input from the user (file or directory).
        - Validates the path and ensures it exists.
        - Scans for video files.
        - For each video file found, probes its resolution and subtitle streams.
        - Calculates the cropping command based on the video resolution.

    Returns:
        tuple:
            - base_dir (Path): The base directory containing the video files.
            - source_list (list): A list of dictionaries, each containing:
                - 'video' (str): The video filename.
                - 'ratio' (float): The aspect ratio (height / width).
                - 'crop_cmd' (str): The crop command string.
                - 'subtitles' (list): Subtitle stream information from ffprobe.
    """

    while True:
        base_dir = str(input('Enter the path of the source video file or directory:\n'))
        if not os.path.exists(base_dir):
            print('Path doesn\'t exist, try again.')
            continue
        else:
            print('\rScanning...', end='')
            if os.path.isdir(base_dir):
                files_list = os.listdir(base_dir)
            else:
                files_list = [base_dir]
                base_dir = Path(base_dir).parent.absolute()
        os.chdir(base_dir)

        # Verify the given path has video files
        source_list = []
        subtitle_list = []
        for each_file in files_list:
            each_name, each_ext = os.path.splitext(each_file)
            each_ext = each_ext.lower()
            if each_ext in VIDEO_EXTS:
                resolution, subtitles = probe_source(each_file)
                source_list.append({
                    'video': os.path.basename(each_file),
                    'ratio': resolution['height'] / resolution['width'],
                    'crop_cmd': calculate_cropping(resolution),
                    'subtitles': subtitles
                    })
        print('\rScanning... Done')
        if not source_list:
            print('No video found in the given path.')
        else:
            return base_dir, source_list
    
def get_output_dir():
    """
    Prompts the user to enter a valid output directory path.

    Returns:
        str: The validated output directory path.
    """
    while True:
        output_dir = str(input('Enter the path of the output directory:\n'))
        output_path = Path(output_dir.strip())
        if output_path.is_dir():
            return output_path
        else:
            try:
                output_path.mkdir(parents=False, exist_ok=True)
                return output_path
            except:
                print('Path doesn\'t exist, try again.')

def convert(source, crop, subtitle, resolution, output, progress_msg):
    """
    Converts a video file using ffmpeg with optional cropping and subtitle burning.

    Args:
        source (str): Filename of the source video..
        crop (str or None): FFmpeg crop filter string, or None if no cropping is needed.
        subtitle (str or None): FFmpeg subtitle filter string, or None if no subtitles are to be burned.
        resolution (str): Output video resolution in format 'widthxheight' (e.g., '640x480').
        output (str): Path for the output video file.
        progress_msg (str): Messages that writes to the console to display progress

    Returns:
        None
    """
    filters = [] # Videos filter command such as crop and subtitle
    convert_cmd = [
        'ffmpeg', 
        '-i',
        source,
        '-vcodec',
        'mpeg4',
        '-vtag',
        'xvid', # Xvid video codec
        '-acodec',
        'libmp3lame', # MP3 Lame audio codec
        '-b:v',
        VIDEO_BITRATE,# Constant video bitrate
        '-b:a',
        AUDIO_BITRATE, # Constant audio bitrate
        '-s',
        resolution,
        ]
    if crop:
        filters.append(crop)
    if subtitle:
        filters.append(subtitle)
    if filters:
        vf_command = ','.join(filters)
        convert_cmd += ['-vf', vf_command]
    convert_cmd.append(output)
    
    ffmpeg_process = Popen(convert_cmd, stderr=PIPE)
    
    # Read progress
    duration = None
    time_pattern = re.compile(r'time=(\d+:\d+:\d+\.\d+)')
    ftr = [3600, 60, 1]
    buffer = b''
    all_stderr = ''
    while True:
        # Reading from stderr
        chunk = ffmpeg_process.stderr.read(1)
        if not chunk:
            break # EOF
        buffer += chunk
        
        if chunk == b'\r':  # FFmpeg progress lines end with \r
            try:
                line = buffer.decode("utf-8", errors="ignore").strip()
                buffer = b""  # Reset for next line
                all_stderr += line + '\n'

                if 'Duration' in line and duration is None:
                    duration_match = re.search(r'Duration: (\d+:\d+:\d+\.\d+)', line)
                    if duration_match:
                        duration = duration_match.group(1).split('.')[0]
                        # Convert duration to seconds
                        duration = sum([a * b for a, b in zip(ftr, map(int, duration.split(':')))])
                
                time_match = time_pattern.search(line)
                if time_match:
                    current_time = time_match.group(1).split('.')[0]
                    # Convert current progress time to seconds
                    current_time = sum([a * b for a, b in zip(ftr, map(int, current_time.split(':')))])
                    progress_percentage = int(current_time / duration * 100)
                    print(f'{progress_msg} {progress_percentage}%', end='')
            except:
                pass
    
    ffmpeg_process.wait()
    if ffmpeg_process.returncode != 0:
        print(f'{progress_msg} Failed')
        raise Exception(all_stderr)
    
    
def main():
    print(WELCOME_MSG)
    base_dir, source_list = get_sources()
    output_dir = get_output_dir()
    should_crop, subtitle_choice, overwrite_output = get_options()

    count = 1
    count_padding = len(str(len(source_list)))
    for each_source in source_list:
        progress_msg = f"\r {str(count).rjust(count_padding, ' ')}/{len(source_list)}: Converting {each_source['video']}..."
        print(progress_msg, end="")
        
        output = os.path.join(output_dir, f'{os.path.splitext(each_source['video'])[0]}.avi')
        if os.path.exists(output):
            if not overwrite_output:
                print(f'{progress_msg} Skipped, file already existed!')
                continue
            else:
                os.remove(output)

        crop = None
        resolution = RESOLUTION_16BY9
        if should_crop and (each_source['ratio'] < 0.65):
            crop = each_source['crop_cmd']
            resolution = RESOLUTION_4BY3 # Force resolution to 4:3 when enable cropping
        if each_source['ratio'] >= 0.7:
            resolution = RESOLUTION_4BY3

        subtitle = None
        if subtitle_choice is not None:
            if subtitle_choice == 'ext':
                ext_sub_cmd = has_external_subtitle(base_dir, each_source['video'])
                if ext_sub_cmd:
                    subtitle = ext_sub_cmd
            else:
                int_sub_cmd = has_internal_subtitle(each_source['video'], each_source['subtitles'], subtitle_choice)
                if int_sub_cmd:
                    subtitle = int_sub_cmd

        convert(each_source['video'], crop, subtitle, resolution, output, progress_msg)
        print(f'{progress_msg} Completed')
        count += 1

if __name__ == '__main__':
    main()