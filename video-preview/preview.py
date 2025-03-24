import ffmpeg

def calculate_sample_seconds(video_duration, samples, sample_duration):
    """
    Calculate the starting points for each sample based on the video duration,
    number of samples, and sample duration.
    """
    if video_duration <= samples * sample_duration:
        # If the video is shorter than the total sample time,
        # take samples at regular intervals
        interval = video_duration / samples
        return [i * interval for i in range(samples)]
    else:
        # Otherwise, distribute samples evenly throughout the video
        available_duration = video_duration - sample_duration
        interval = available_duration / (samples - 1)
        return [i * interval for i in range(samples)]

def sample_video(stream, sample_duration, sample_seconds=[]):
    samples = []
    for t in sample_seconds:
        sample = stream.video.trim(start=t, duration=sample_duration).setpts('PTS-STARTPTS')
        samples.append(sample)
    return samples

def generate_video_preview(in_filename, out_filename, sample_duration, sample_seconds, scale, format, quiet):
    stream = ffmpeg.input(in_filename)

    samples = sample_video(stream, sample_duration=sample_duration, sample_seconds=sample_seconds)
    stream = ffmpeg.concat(*samples)

    if scale is not None:
        width, height = scale.split(':')
        stream = ffmpeg.filter(stream, 'scale', width=width, height=height, force_original_aspect_ratio='decrease')

    (
        ffmpeg
        .output(stream, out_filename, format=format)
        .overwrite_output()
        .run(quiet=quiet)
    ) 