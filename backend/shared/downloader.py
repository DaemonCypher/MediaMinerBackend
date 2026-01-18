
import os
import platform
from typing import Callable, Optional, Dict, Any
from yt_dlp import YoutubeDL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default to sibling 'downloads' folder of backend; allow override.
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", os.path.join(os.path.dirname(BASE_DIR), "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_ffmpeg_path() -> Optional[str]:
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        return env_path

    project_root = os.path.dirname(BASE_DIR)
    ffmpeg_bin = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    bundled = os.path.join(project_root, "ffmpeg", "bin", ffmpeg_bin)
    if os.path.exists(bundled):
        return bundled

    return None

def make_progress_hook(on_progress: Optional[Callable[[Dict[str, Any]], None]]):
    def hook(d: Dict[str, Any]):
        if on_progress:
            on_progress(d)
    return hook

def build_outtmpl(download_dir: str, media_type: str) -> str:
    if media_type == "audio":
        return os.path.join(download_dir, "%(title)s [%(id)s].%(ext)s")
    if media_type == "video":
        return os.path.join(download_dir, "%(title)s [%(id)s] [%(height)sp %(vcodec)s].%(ext)s")
    raise ValueError("media_type must be 'audio' or 'video'")

def audio_metadata_postprocessors(audio_format: str, bitrate: str):
    return [
        {"key": "FFmpegExtractAudio", "preferredcodec": audio_format, "preferredquality": bitrate},
        {"key": "EmbedThumbnail"},
        {"key": "FFmpegMetadata"},
    ]

def video_metadata_options():
    return {"writethumbnail": True, "embedthumbnail": True, "addmetadata": True}

def playlist_options(allow_playlist: bool = True, playlist_items: Optional[str] = None):
    opts = {"noplaylist": not allow_playlist}
    if playlist_items:
        opts["playlist_items"] = playlist_items
    return opts

def cookies_options(cookie_file: Optional[str]):
    if cookie_file and os.path.exists(cookie_file):
        return {"cookiefile": cookie_file}
    return {}

def network_resilience_options(retries: int = 5, fragment_retries: int = 5, timeout: int = 30, resume: bool = True):
    return {
        "retries": retries,
        "fragment_retries": fragment_retries,
        "socket_timeout": timeout,
        "continuedl": resume,
    }

def build_video_format_selector(container: str, max_height: Optional[int], prefer_codec: Optional[str]) -> str:
    height_part = f"[height<={max_height}]" if max_height is not None else ""

    if container == "mp4":
        base = f"bv*{height_part}[ext=mp4]+ba[ext=m4a]/b{height_part}[ext=mp4]/best"
    elif container == "webm":
        base = f"bv*{height_part}[ext=webm]+ba[ext=webm]/b{height_part}[ext=webm]/best"
    else:
        base = f"bv*{height_part}+ba/best"

    if prefer_codec:
        base = f"{base}[vcodec~={prefer_codec}]"

    return base

def download_audio(
    url: str,
    audio_format: str = "mp3",
    bitrate: str = "192",
    allow_playlist: bool = True,
    playlist_items: Optional[str] = None,
    cookie_file: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
):
    ffmpeg_path = get_ffmpeg_path()
    ydl_opts = {
        "ffmpeg_location": ffmpeg_path,
        "format": "bestaudio/best",
        "outtmpl": build_outtmpl(DOWNLOAD_DIR, "audio"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "progress_hooks": [make_progress_hook(on_progress)],
        "writethumbnail": True,
        "postprocessors": audio_metadata_postprocessors(audio_format, bitrate),
        **playlist_options(allow_playlist, playlist_items),
        **cookies_options(cookie_file),
        **network_resilience_options(),
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_video(
    url: str,
    container: str = "mp4",
    max_height: Optional[int] = 1080,
    prefer_codec: Optional[str] = None,
    allow_playlist: bool = True,
    playlist_items: Optional[str] = None,
    cookie_file: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
):
    ffmpeg_path = get_ffmpeg_path()
    fmt = build_video_format_selector(container, max_height, prefer_codec)

    ydl_opts = {
        "ffmpeg_location": ffmpeg_path,
        "format": fmt,
        "merge_output_format": container,
        "outtmpl": build_outtmpl(DOWNLOAD_DIR, "video"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "progress_hooks": [make_progress_hook(on_progress)],
        **video_metadata_options(),
        **playlist_options(allow_playlist, playlist_items),
        **cookies_options(cookie_file),
        **network_resilience_options(),
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
