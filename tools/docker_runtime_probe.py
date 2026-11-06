"""Network-isolated, synthetic checks streamed into the built runtime image.

Run only through check_docker.py, without application data/media/key mounts.
No AppContext, browser profile, saved session or external platform is loaded.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

CHECKS = ("isolation", "dependencies", "javascript", "ffmpeg_merge", "thumbnail", "image_privacy", "optional_browser")


def require(condition):
    if not condition:
        raise RuntimeError("acceptance condition failed")


def command(arguments):
    result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=45, check=True)
    require(len(result.stdout) <= 128 * 1024 and len(result.stderr) <= 128 * 1024)
    return result.stdout


def main():
    receipt = os.environ.get("SSDL_DOCKER_ACCEPTANCE", "")
    result = {"format_version": 1, "receipt": receipt, "passed": False, "checks": [], "versions": {}}
    current = "isolation"
    try:
        require(re.fullmatch(r"[0-9a-f]{32}", receipt) is not None)
        require(sys.platform == "linux" and platform.machine() == "x86_64" and os.getuid() == 10001)
        require(sys.version_info[:2] == (3, 12) and Path(sys.prefix) == Path("/app/.venv"))
        require(os.path.ismount("/work") and Path.home() == Path("/work/home"))
        require(set(os.listdir("/sys/class/net")) == {"lo"})
        for directory in (Path("/app/data"), Path("/app/cache"), Path("/downloads")):
            require(not os.path.ismount(directory) and not any(directory.iterdir()))
        Path("/work/home").mkdir()
        Path("/work/cache").mkdir()
        os.chdir("/work")
        sys.path.insert(0, "/app")
        result["checks"].append(current)

        current = "dependencies"
        command([sys.executable, "-m", "pip", "check"])
        from ssdl.media_engines import engine_status, ffmpeg_path
        engines = engine_status()
        require(all(engines[name] for name in ("video", "images", "ffmpeg")))
        require(ffmpeg_path() == "/usr/bin/ffmpeg" and shutil.which("ffprobe") == "/usr/bin/ffprobe")
        require(platform.python_version() == os.environ["SSDL_EXPECT_PYTHON"])
        result["versions"]["python"] = platform.python_version()
        for package in ("yt-dlp", "gallery-dl", "yt-dlp-ejs", "imageio-ffmpeg", "pycryptodomex"):
            version = importlib.metadata.version(package)
            require(re.fullmatch(r"[A-Za-z0-9.+!_-]{1,80}", version) is not None)
            result["versions"][package] = version
        result["checks"].append(current)

        current = "javascript"
        node = command(["node", "--version"]).decode("ascii").strip().removeprefix("v")
        require(node == os.environ["SSDL_EXPECT_NODE"] and int(node.split(".")[0]) >= 22)
        from yt_dlp import YoutubeDL
        from yt_dlp.extractor.youtube.jsc._builtin.node import NodeJCP
        from yt_dlp.extractor.youtube.jsc._builtin.ejs import ScriptType

        class QuietLogger:
            def trace(self, *args, **kwargs): pass
            def debug(self, *args, **kwargs): pass
            def info(self, *args, **kwargs): pass
            def warning(self, *args, **kwargs): pass
            def error(self, *args, **kwargs): pass

        with YoutubeDL({"quiet": True, "no_warnings": True, "cachedir": False,
                        "js_runtimes": {"node": {}}, "remote_components": [], "logger": QuietLogger()}) as ydl:
            runtime = ydl._js_runtimes["node"].info
            require(runtime is not None and runtime.supported and runtime.version == node)
            provider = NodeJCP(ydl.get_info_extractor("Youtube"), QuietLogger(), {})
            try:
                require(provider.is_available())
                for kind in (ScriptType.CORE, ScriptType.LIB):
                    script = provider._pypackage_source(kind)
                    require(script is not None and script.hash == provider._ALLOWED_HASHES[kind][script.variant])
                output = provider._run_js_runtime('console.log(JSON.stringify({sum:[1,2,3].reduce((a,b)=>a+b,0),wide:9007199254740993n.toString()}));')
                require(json.loads(output) == {"sum": 6, "wide": "9007199254740993"})
            finally:
                provider.close()
        result["versions"]["node"] = node
        result["checks"].append(current)

        current = "ffmpeg_merge"
        version = command(["ffmpeg", "-version"]).decode("utf-8").splitlines()[0].split()[2]
        require(re.fullmatch(r"[A-Za-z0-9.+~_-]{1,100}", version) is not None)
        result["versions"]["ffmpeg"] = version
        ffmpeg = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "1", "-filter_threads", "1"]
        command(ffmpeg + ["-f", "lavfi", "-i", "color=c=blue:s=160x90:r=8", "-t", "1", "-an", "-c:v", "mpeg4", "video.mp4"])
        command(ffmpeg + ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1", "-vn", "-c:a", "aac", "audio.m4a"])
        command(ffmpeg + ["-i", "video.mp4", "-i", "audio.m4a", "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", "merged.mp4"])
        probe = json.loads(command(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height", "-show_entries", "format=duration", "-of", "json", "merged.mp4"]))
        streams = {item["codec_type"]: item for item in probe["streams"]}
        require(len(probe["streams"]) == 2 and streams["video"]["codec_name"] == "mpeg4" and streams["audio"]["codec_name"] == "aac")
        require((streams["video"]["width"], streams["video"]["height"]) == (160, 90))
        require(.8 <= float(probe["format"]["duration"]) <= 1.3)
        for source, stream in (("video.mp4", "v:0"), ("audio.m4a", "a:0")):
            def packet_hash(filename):
                return command(ffmpeg + ["-i", filename, "-map", f"0:{stream}", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"]).strip()
            require(packet_hash(source) == packet_hash("merged.mp4"))
        result["checks"].append(current)

        current = "thumbnail"
        command(ffmpeg + ["-i", "merged.mp4", "-frames:v", "1", "-vf", "scale=80:-2", "preview.jpg"])
        preview = Path("preview.jpg").read_bytes()
        require(preview.startswith(b"\xff\xd8") and preview.endswith(b"\xff\xd9") and len(preview) < 100_000)
        result["checks"].append(current)

        current = "image_privacy"
        expected_root = {".venv", "requirements.lock.txt", "app.py", "LICENSE", "THIRD_PARTY_NOTICES.md",
                         "ssdl", "static", "chrome-extension", "docker", "data", "cache"}
        require({path.name for path in Path("/app").iterdir()} == expected_root)
        marker = os.environ["SSDL_CONTEXT_CANARY"].encode("ascii")
        require(re.fullmatch(rb"ssdl-canary-[0-9a-f]{32}", marker) is not None)
        total = count = 0
        for path in Path("/app").rglob("*"):
            if path.is_symlink():
                # venv creates interpreter and lib64 links; source links are forbidden.
                require(path in {Path("/app/.venv/bin") / name for name in ("python", "python3", "python3.12")}
                        or path == Path("/app/.venv/lib64"))
                require(path.resolve().is_relative_to("/app/.venv")
                        or path.resolve() == Path(sys.base_prefix) / "bin/python3.12")
                continue
            if not path.is_file():
                continue
            count += 1
            require(count <= 40_000)
            with path.open("rb") as source:
                overlap = b""
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    require(total <= 512 * 1024 * 1024 and marker not in overlap + chunk)
                    overlap = chunk[-(len(marker) - 1):]
        require(all(not any(Path(name).iterdir()) for name in ("/app/data", "/app/cache", "/downloads")))
        result["checks"].append(current)

        current = "optional_browser"
        require(importlib.util.find_spec("playwright") is None)
        require(all(shutil.which(name) is None for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")))
        result["checks"].append(current)
        require(tuple(result["checks"]) == CHECKS)
        result["passed"] = True
    except Exception:
        result["error_code"] = current + "_failed"
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
