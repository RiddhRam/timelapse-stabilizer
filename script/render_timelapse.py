#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path

FPS = 5
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


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


def main():
    input_dir, metadata_path, output_path, status_path = sys.argv[1:5]
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    concat_path = output_path.with_suffix(".txt")

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

    write_status(status_path, "running", 20, "Ordering images...")

    with concat_path.open("w") as file_list:
        for image in images:
            file_list.write(f"file '{image.as_posix()}'\n")
            file_list.write(f"duration {1 / FPS}\n")

    write_status(status_path, "running", 35, "Rendering MP4...")

    total_seconds = max(len(images) / FPS, 1 / FPS)
    command = [
        "/opt/homebrew/bin/ffmpeg",
        "-y",
        "-nostats",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-r",
        str(FPS),
        "-frames:v",
        str(len(images)),
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
