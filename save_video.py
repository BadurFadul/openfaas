# save_video.py
import requests
import os
import json
import base64
import sys

def save_video_preview(video_url, output_path=None):
    """
    Call the video-preview function and save the result to the local filesystem
    
    Args:
        video_url: URL of the video to process
        output_path: Path where to save the output file (default: current directory)
    """
    if output_path is None:
        output_path = os.getcwd()
    
    # Call the OpenFaaS function
    print(f"Calling video-preview function for URL: {video_url}")
    response = requests.post(
        "http://127.0.0.1:8080/function/video-preview",
        headers={"Content-Type": "application/json"},
        json={"url": video_url}
    )
    
    if response.status_code != 200:
        print(f"Error: Function returned status code {response.status_code}")
        print(response.text)
        return False
    
    # Parse the response
    result = response.json()
    if "content" not in result:
        print("Error: Function did not return file content")
        print(result)
        return False
    
    # Get the file content and metadata
    filename = result.get("filename", "preview.mp4")
    content = base64.b64decode(result["content"])
    
    # Save the file
    output_file = os.path.join(output_path, filename)
    with open(output_file, 'wb') as f:
        f.write(content)
    
    print(f"Video preview saved to: {output_file}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python save_video.py <video_url> [output_path]")
        sys.exit(1)
    
    video_url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    save_video_preview(video_url, output_path)