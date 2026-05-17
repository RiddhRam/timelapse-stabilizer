#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FPS = 5
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_FILTER = "format=yuv420p"


def write_status(status_path, status, progress, message):
    Path(status_path).write_text(json.dumps({
        "status": status,
        "progress": progress,
        "message": message,
    }))


def image_sort_key(path, metadata_by_name):
    metadata = metadata_by_name.get(path.name)
    if metadata:
        return metadata.get("lastModified", 0)

    return os.path.getmtime(path)


def run_command(command):
    process = subprocess.run(command, capture_output=True, text=True)

    if process.returncode != 0:
        raise RuntimeError(process.stderr[-1200:] or "ffmpeg failed.")


def image_dimensions(image_path):
    process = subprocess.run([
        "/opt/homebrew/bin/ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(image_path),
    ], capture_output=True, text=True)

    if process.returncode != 0:
        raise RuntimeError(process.stderr[-1200:] or "Could not read image dimensions.")

    stream = json.loads(process.stdout)["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])

    return width - (width % 2), height - (height % 2)


def frame_filter(width, height):
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        "format=rgb24"
    )


def main():
    input_dir, metadata_path, output_path, status_path = sys.argv[1:5]
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    frames_dir = output_path.parent / "frames"

    write_status(status_path, "running", 5, "Reading image timestamps...")

    metadata = json.loads(Path(metadata_path).read_text()) if Path(metadata_path).exists() else []
    metadata_by_name = {
        Path(item.get("name", "")).name: item
        for item in metadata
        if item.get("name")
    }

    images = sorted(
        [path for path in input_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: image_sort_key(path, metadata_by_name),
    )

    if not images:
        write_status(status_path, "error", 0, "No supported images were uploaded.")
        return 1

    write_status(status_path, "running", 20, "Normalizing frames...")

    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    try:
        target_width, target_height = image_dimensions(images[0])
        normalize_filter = frame_filter(target_width, target_height)

        for index, image in enumerate(images):
            frame_path = frames_dir / f"frame_{index:06d}.png"
            run_command([
                "/opt/homebrew/bin/ffmpeg",
                "-y",
                "-i",
                str(image),
                "-vf",
                normalize_filter,
                "-frames:v",
                "1",
                str(frame_path),
            ])

            progress = 20 + round(((index + 1) / len(images)) * 30)
            write_status(status_path, "running", progress, "Normalizing frames...")
    except RuntimeError as error:
        write_status(status_path, "error", 0, str(error))
        return 1

    write_status(status_path, "running", 35, "Rendering MP4...")

    total_seconds = max(len(images) / FPS, 1 / FPS)
    command = [
        "/opt/homebrew/bin/ffmpeg",
        "-y",
        "-nostats",
        "-framerate",
        str(FPS),
        "-i",
        str(frames_dir / "frame_%06d.png"),
        "-vf",
        VIDEO_FILTER,
        "-frames:v",
        str(len(images)),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "12",
        "-tune",
        "stillimage",
        "-x264-params",
        "keyint=1:min-keyint=1:scenecut=0:bframes=0:colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        str(output_path),
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    for line in process.stdout:
        key, _, value = line.strip().partition("=")
        if key == "out_time_ms":
            if not value.isdigit():
                continue

            seconds = int(value) / 1_000_000
            progress = min(95, 35 + round((seconds / total_seconds) * 60))
            write_status(status_path, "running", progress, "Rendering MP4...")

    stderr = process.stderr.read()
    return_code = process.wait()

    if return_code != 0:
        write_status(status_path, "error", 0, stderr[-1200:] or "ffmpeg failed.")
        return return_code

    write_status(status_path, "complete", 100, "Video ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
