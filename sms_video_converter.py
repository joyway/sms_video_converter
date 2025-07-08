import os
import re
import time
import json
import shutil
from pathlib import Path
from subprocess import Popen, PIPE

VERSION = '1.0.1'
WELCOME_MSG = f'## Welcome to SMS Video Converter v{VERSION}! ##'
VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.rmvb', '.rm', '.mov', '.flv', '.mpg', '.mpeg', '.wmv')
SUBTITLE_EXTS = ('.ass', '.ssa', '.srt')
RESOLUTION_4BY3 = '640x480'
RESOLUTION_16BY9 = '854x480'
VIDEO_BITRATE_RANGE = [1000, 9000]
AUDIO_BITRATE = '192k'


def _prompt_input(prompt, validate_func):
    """
    Interact with the user to collect and validate user input.

    Args:
        prompt (str): The message to be displayed to the user.
        validate_func (function): The function to validate the input, should return True when it's valid.

    Raises:
        Exception: When user input is invalid.

    Returns:
        str: The user input.
    """
    while True:
        user_input = str(input(f'# {prompt}\n')).strip()
        try:
            validated_input = validate_func(user_input)
            if validated_input:
                break
            else:
                raise Exception(f'Invalid input: {user_input}')
        except Exception as e:
            print(f'# {e}')
    return user_input

def _prompt_yes_no(prompt, default=True):
    """
    Interact with the user to choose yes and no.

    Args:
        prompt (str): The message to be displayed to the user.
        default (bool, optional): Default to yes(True) or no(False) when user hits return without typing anything. Defaults to True.

    Returns:
        bool: yes(True) or no(False).
    """
    result = default
    prompt += ' (Y/n)' if default else ' (y/N)'
    while True:
        user_input = str(input(f'# {prompt}\n'))
        if not user_input:
            break
        elif user_input.strip().lower() == 'y':
            result = True
            break
        elif user_input.strip().lower() == 'n':
            result = False
            break
        else:
            print('# Invalid input!')
    return result

def _prompt_choice(prompt, options):
    """
    Interact with the user to choose from a list of options.

    Args:
        prompt (str): The message to be displayed to the user.
        options (list): The list of options.

    Returns:
        int: The index of the chosen option.
    """
    while True:
        options_text = ''
        for i, option in enumerate(options):
            options_text += f'\n  {i + 1}. {option}'
        user_input = str(input(f'# {prompt}{options_text} \n'))
        try:
            chosen_index = int(user_input.strip())
            return options[chosen_index - 1]
        except:
            print('# Invalid input!')

def get_options():
    """
    Interacts with the user to collect preferences.

    Returns:
        tuple: Options for bitrate, video cropping, subtitle burning and overwrite existing files
    """
    # What's the target video bitrate?
    validate_vbitrate = lambda x: VIDEO_BITRATE_RANGE[0] <= int(x) <= VIDEO_BITRATE_RANGE[1]
    v_bitrate = _prompt_input(
        'Set the video bitrate, numbers only: (1000-9000 kbps)',
        validate_vbitrate
        )
    v_bitrate = f'{v_bitrate}k'

    # Should we crop the video to 4 by 3?
    should_crop = _prompt_yes_no('Crop the widescreen video to 4:3?', default=False)

    # Should we burn the subtitle to the video?
    should_burn_subtitle = _prompt_yes_no('Burn the text subtitles to the video?')
    if should_burn_subtitle:
        subtitle_choice = 'ext' if _prompt_choice(
            'Burn internal or external subtitles?',
            ('Internal', 'External')
            ) == 'External' else 'int'
        if subtitle_choice == 'int':
            subtitle_choice = int(
                _prompt_input(
                    'Enter the number of subtitle track, the first track will be 0:',
                    lambda x:  x.isdigit()
                    )
                )
    else:
        subtitle_choice = None

    # Overwrite existing files in the output directory?
    overwrite_output = _prompt_yes_no('Overwrite existing files in the output directory?', default=False)

    return v_bitrate, should_crop, subtitle_choice, overwrite_output

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
        print(f'# Subtitle stream {subtitle_choice} not found')
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
        base_dir = str(input('# Enter the path of the source video file or directory:\n'))
        if not os.path.exists(base_dir):
            print('# Path doesn\'t exist, try again.')
            continue
        else:
            print('\r# Scanning...', end='')
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
        print('\r# Scanning... Done')
        if not source_list:
            print('# No video found in the given path.')
        else:
            return base_dir, source_list
    
def get_output_dir():
    """
    Prompts the user to enter a valid output directory path.

    Returns:
        str: The validated output directory path.
    """
    def validate_output_path(output_path):
        """
        Validate the output path. Will create the folder if the output path doesn't exist but its parent does.

        Args:
            output_path (str): The output path

        Raises:
            Exception: When neither given path and the parent of the given path exists

        Returns:
            bool: True for valid path.
        """
        output_path = Path(output_path)
        if output_path.is_dir():
            return True
        else:
            try:
                output_path.mkdir(parents=False, exist_ok=True)
                return True
            except:
                raise Exception("Path doesn\'t exist, try again!")
        
    return _prompt_input('Enter the path of the output directory:', validate_output_path)

def convert(source, v_bitrate, crop, subtitle, resolution, output, progress_msg):
    """
    Converts a video file using ffmpeg with optional cropping and subtitle burning.

    Args:
        source (str): Filename of the source video.
        v_bitrate (str): Video bitrate.
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
        v_bitrate, # Constant video bitrate
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
    ftr = [3600, 60, 1] # Convert time to second https://stackoverflow.com/a/12739542
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
    v_bitrate, should_crop, subtitle_choice, overwrite_output = get_options()

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

        convert(each_source['video'], v_bitrate, crop, subtitle, resolution, output, progress_msg)
        print(f'{progress_msg} Completed')
        count += 1

if __name__ == '__main__':
    main()