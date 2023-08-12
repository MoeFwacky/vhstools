import ffmpeg
import os
from moviepy.editor import VideoFileClip
from moviepy.audio.fx.all import audio_normalize

def normalize_audio(video_path, output_path=None):
    
    originals_path = os.path.join(os.path.dirname(video_path)+"/_originals",os.path.basename(video_path))
    os.makedirs(os.path.dirname(originals_path), exist_ok=True)
    os.rename(video_path,originals_path)
    print("[ACTION] Loading the video file")
    video_clip = VideoFileClip(originals_path)

    print("[ACTION] Extracting the audio from the video file")
    audio_clip = video_clip.audio

    print("[ACTION] Normalizing the audio level")
    normalized_audio = audio_normalize(audio_clip)

    print("[ACTION] Combining the normalized audio with the video clip")
    normalized_clip = video_clip.set_audio(normalized_audio)

    # Retrieve existing metadata
    existing_metadata = video_clip.reader.infos

    # Define the output file path
    if output_path == None:
        output_path = os.path.dirname(video_path)
    os.makedirs(output_path, exist_ok=True)
    print("[ACTION] Writing video to file")
    # Export the normalized clip to a temporary file
    temp_file = os.path.join(output_path, os.path.basename(video_path)).replace('.mp4', "_temp.mp4")
    normalized_clip.write_videofile(temp_file, codec="libx264", audio_codec="aac")

    # Use ffmpeg-python to copy the metadata from the original video to the new video
    input_stream = ffmpeg.input(originals_path)
    input_audio = input_stream.audio
    input_video = input_stream.video
    output_stream = ffmpeg.output(input_audio, input_video, os.path.join(output_path, os.path.basename(video_path)), codec="copy", map_metadata="0", loglevel="quiet")
    ffmpeg.run(output_stream, overwrite_output=True)

    # Remove the temporary file
    os.remove(temp_file)

    # Close the video clip
    video_clip.close()
