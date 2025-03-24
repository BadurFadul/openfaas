import os
import json
import logging
import tempfile
import ffmpeg
import boto3
from botocore.config import Config
import requests
import subprocess
import shutil
import base64

from .preview import generate_video_preview, calculate_sample_seconds, sample_video

s3_client = None

samples = int(os.getenv("samples", "4"))
sample_duration = int(os.getenv("sample_duration", "2"))
scale = os.getenv("scale")
format = os.getenv("format", "mp4")

s3_output_prefix = os.getenv("s3_output_prefix", "output")
s3_bucket_name = os.getenv('s3_bucket')
debug = os.getenv("debug", "false").lower() == "true"

def init_s3():
    with open('/var/openfaas/secrets/video-preview-s3-key', 'r') as s:
        s3Key = s.read().strip()
    with open('/var/openfaas/secrets/video-preview-s3-secret', 'r') as s:
        s3Secret = s.read().strip()

    s3_endpoint_url = os.getenv("s3_endpoint_url")

    session = boto3.Session(
        aws_access_key_id=s3Key,
        aws_secret_access_key=s3Secret,
    )
    
    return session.client('s3', config=Config(signature_version='s3v4'), endpoint_url=s3_endpoint_url)

def verify_url(url):
    try:
        response = requests.head(url, timeout=10)
        if response.status_code >= 400:
            return False, f"URL returned status code {response.status_code}"
        return True, "URL is accessible"
    except Exception as e:
        return False, f"Error accessing URL: {str(e)}"

def get_presigned_url(object_key):
    """Generate a pre-signed URL for an object in the bucket"""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': s3_bucket_name,
                'Key': object_key
            },
            ExpiresIn=3600  # URL valid for 1 hour
        )
        return url
    except Exception as e:
        logging.error(f"Failed to generate presigned URL: {str(e)}")
        return None

def handle(event, context):
    # Check if FFmpeg is installed
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        logging.info(f"FFmpeg version: {result.stdout.split('\\n')[0]}")
    except Exception as e:
        logging.error(f"FFmpeg check failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": {"error": "FFmpeg not properly installed"}
        }

    global s3_client

    # Initialize an S3 client upon first invocation
    if s3_client is None:
        s3_client = init_s3()

    data = json.loads(event.body)
    
    # Handle both full URLs and object keys
    if "url" in data:
        input_url = data["url"]
    elif "key" in data:
        # Generate a pre-signed URL for the object in our bucket
        object_key = data["key"]
        input_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': s3_bucket_name,
                'Key': object_key
            },
            ExpiresIn=3600
        )
        logging.info(f"Generated presigned URL for {object_key}")
    else:
        return {
            "statusCode": 400,
            "body": {"error": "Request must contain either 'url' or 'key' field"}
        }
    
    # Verify URL is accessible
    url_accessible, message = verify_url(input_url)
    if not url_accessible:
        logging.error(f"URL verification failed: {message}")
        return {
            "statusCode": 400,
            "body": {"error": f"Cannot access video URL: {message}"}
        }

    file_name, _ = os.path.basename(input_url).split(".")
    output_key = os.path.join(s3_output_prefix, file_name + "." + format)
    out_file = tempfile.NamedTemporaryFile(delete=True)

    try:
        probe = ffmpeg.probe(input_url)
        video_duration = float(probe["format"]["duration"])
    except ffmpeg.Error as e:
        logging.error("failed to get video info")
        logging.error(f"FFmpeg stderr: {e.stderr.decode() if hasattr(e, 'stderr') else 'No stderr'}")
        logging.error(f"Input URL: {input_url}")
        return {
            "statusCode": 500,
            "body": {"error": f"Failed to get video info: {str(e)}"}
        }

    # Calculate sample_seconds based on the video duration, sample_duration and number of samples
    sample_seconds = calculate_sample_seconds(video_duration, samples, sample_duration)

    # Generate video preview
    try:
        generate_video_preview(input_url, out_file.name, sample_duration, sample_seconds, scale, format, quiet=not debug)
    except Exception as e:
        logging.error("failed to generate video preview")
        logging.error(str(e))
        return {
            "statusCode": 500,
            "body": {"error": "Failed to generate video preview"}
        }

    # Upload video file to S3 bucket
    try:
        # Instead of uploading to S3, return the file content
        local_file_path = out_file.name
        
        # Read the file content
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
        
        # Encode the content as base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        return {
            "statusCode": 200,
            "body": {
                "message": "Video preview generated successfully",
                "filename": f"{file_name}.{format}",
                "content_type": f"video/{format}",
                "content": encoded_content
            }
        }
    except Exception as e:
        logging.error("failed to save video preview locally")
        logging.error(str(e))
        return {
            "statusCode": 500,
            "body": {"error": f"Failed to save video preview: {str(e)}"}
        }
