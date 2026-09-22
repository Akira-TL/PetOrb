from __future__ import annotations

import asyncio
import json
import logging
import shutil
import struct
from dataclasses import dataclass

from fastapi import WebSocket

from .detector import DetectorError, detect_image
from .risk import highest_risk, overall_copy
from .settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamConfig:
    codec: str
    width: int
    height: int
    fps: int

    @classmethod
    def from_message(cls, payload: dict[str, object]) -> "StreamConfig":
        codec = str(payload.get("codec", "")).lower()
        if codec not in {"h264", "h265"}:
            raise ValueError("codec must be h264 or h265")
        width = int(payload.get("width", 0))
        height = int(payload.get("height", 0))
        fps = int(payload.get("fps", 0))
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("stream width, height and fps must be positive")
        return cls(codec=codec, width=width, height=height, fps=fps)


class CameraStreamHub:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.source_connected = False
        self.config: StreamConfig | None = None
        self.frame_id = 0
        self.latest_inference: dict[str, object] | None = None
        self.viewers: set[WebSocket] = set()
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.stderr_task: asyncio.Task[None] | None = None
        self.inference_task: asyncio.Task[None] | None = None
        self.inference_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue(maxsize=2)
        self.lock = asyncio.Lock()

    async def attach_source(self) -> bool:
        async with self.lock:
            if self.source_connected:
                return False
            self.source_connected = True
            self.config = None
            self.frame_id = 0
            self.latest_inference = None
        await self.broadcast_json({"type": "stream_status", "status": "waiting_config"})
        return True

    async def configure_source(self, payload: dict[str, object]) -> None:
        if payload.get("type") != "stream_config":
            raise ValueError("first camera control message must be stream_config")
        config = StreamConfig.from_message(payload)
        if config == self.config and self.process is not None:
            return
        await self._start_ffmpeg(config)
        self.config = config
        await self.broadcast_json(
            {
                "type": "stream_status",
                "status": "streaming",
                "codec": config.codec,
                "width": config.width,
                "height": config.height,
                "source_fps": config.fps,
                "display_fps": self.settings.stream_display_fps,
                "inference_fps": self.settings.stream_inference_fps,
            }
        )

    async def feed_encoded(self, data: bytes) -> None:
        process = self.process
        if process is None or process.stdin is None:
            return
        try:
            process.stdin.write(data)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            await self.broadcast_json({"type": "stream_error", "message": f"FFmpeg input closed: {exc}"})

    async def detach_source(self) -> None:
        async with self.lock:
            self.source_connected = False
            self.config = None
        await self._stop_ffmpeg()
        await self.broadcast_json({"type": "stream_status", "status": "camera_disconnected"})

    async def serve_viewer(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.viewers.add(websocket)
        try:
            await websocket.send_text(json.dumps(self.status_snapshot(), ensure_ascii=False))
            if self.latest_inference is not None:
                await websocket.send_text(json.dumps(self.latest_inference, ensure_ascii=False))
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
        finally:
            self.viewers.discard(websocket)

    def status_snapshot(self) -> dict[str, object]:
        config = self.config
        return {
            "type": "stream_status",
            "status": "streaming" if self.process is not None else ("waiting_config" if self.source_connected else "camera_disconnected"),
            "camera_connected": self.source_connected,
            "frame_id": self.frame_id,
            "codec": config.codec if config else None,
            "width": config.width if config else None,
            "height": config.height if config else None,
            "source_fps": config.fps if config else None,
            "display_fps": self.settings.stream_display_fps,
            "inference_fps": self.settings.stream_inference_fps,
            "viewers": len(self.viewers),
        }

    async def shutdown(self) -> None:
        await self._stop_ffmpeg()
        if self.inference_task is not None:
            self.inference_task.cancel()
            await asyncio.gather(self.inference_task, return_exceptions=True)
            self.inference_task = None

    async def broadcast_json(self, payload: dict[str, object]) -> None:
        if not self.viewers:
            return
        text = json.dumps(payload, ensure_ascii=False)
        stale: list[WebSocket] = []
        for viewer in tuple(self.viewers):
            try:
                await asyncio.wait_for(viewer.send_text(text), timeout=0.1)
            except Exception:
                stale.append(viewer)
        for viewer in stale:
            self.viewers.discard(viewer)

    async def _broadcast_frame(self, frame_id: int, jpeg: bytes) -> None:
        if not self.viewers:
            return
        packet = struct.pack(">I", frame_id & 0xFFFFFFFF) + jpeg
        stale: list[WebSocket] = []
        for viewer in tuple(self.viewers):
            try:
                await asyncio.wait_for(viewer.send_bytes(packet), timeout=0.05)
            except Exception:
                stale.append(viewer)
        for viewer in stale:
            self.viewers.discard(viewer)

    async def _start_ffmpeg(self, config: StreamConfig) -> None:
        await self._stop_ffmpeg()
        ffmpeg = shutil.which(self.settings.ffmpeg_bin) if "/" not in self.settings.ffmpeg_bin else self.settings.ffmpeg_bin
        if not ffmpeg:
            raise RuntimeError(f"FFmpeg not found: {self.settings.ffmpeg_bin}")
        input_format = "h264" if config.codec == "h264" else "hevc"
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-f",
            input_format,
            "-i",
            "pipe:0",
            "-an",
            "-vf",
            f"fps={self.settings.stream_display_fps}",
            "-q:v",
            str(self.settings.stream_jpeg_quality),
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.reader_task = asyncio.create_task(self._read_decoded_jpegs(), name="petorb-ffmpeg-reader")
        self.stderr_task = asyncio.create_task(self._read_ffmpeg_stderr(), name="petorb-ffmpeg-stderr")
        if self.inference_task is None or self.inference_task.done():
            self.inference_task = asyncio.create_task(self._inference_worker(), name="petorb-inference-worker")

    async def _stop_ffmpeg(self) -> None:
        process = self.process
        self.process = None
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        current = asyncio.current_task()
        tasks = [task for task in (self.reader_task, self.stderr_task) if task is not None and task is not current]
        self.reader_task = None
        self.stderr_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        while not self.inference_queue.empty():
            try:
                self.inference_queue.get_nowait()
                self.inference_queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _read_decoded_jpegs(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        buffer = bytearray()
        try:
            while True:
                chunk = await process.stdout.read(64 * 1024)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        if len(buffer) > 8 * 1024 * 1024:
                            buffer.clear()
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if start > 0:
                            del buffer[:start]
                        break
                    jpeg = bytes(buffer[start : end + 2])
                    del buffer[: end + 2]
                    await self._handle_decoded_frame(jpeg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("decoded frame reader failed")
            await self.broadcast_json({"type": "stream_error", "message": f"FFmpeg decode failed: {exc}"})

    async def _read_ffmpeg_stderr(self) -> None:
        process = self.process
        if process is None or process.stderr is None:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.warning("ffmpeg: %s", line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            raise

    async def _handle_decoded_frame(self, jpeg: bytes) -> None:
        self.frame_id += 1
        frame_id = self.frame_id
        await self._broadcast_frame(frame_id, jpeg)
        stride = max(1, round(self.settings.stream_display_fps / self.settings.stream_inference_fps))
        if frame_id % stride != 0:
            return
        if self.inference_queue.full():
            try:
                self.inference_queue.get_nowait()
                self.inference_queue.task_done()
            except asyncio.QueueEmpty:
                pass
        self.inference_queue.put_nowait((frame_id, jpeg))

    async def _inference_worker(self) -> None:
        while True:
            frame_id, jpeg = await self.inference_queue.get()
            try:
                result = await detect_image(
                    image_bytes=jpeg,
                    filename=f"stream-{frame_id}.jpg",
                    request_id=f"stream-{frame_id}",
                    settings=self.settings,
                )
                risk_level = highest_risk(result.detections)
                overall_judgment, recommendation = overall_copy(risk_level)
                payload: dict[str, object] = {
                    "type": "inference",
                    "frame_id": frame_id,
                    "risk_level": risk_level,
                    "overall_judgment": overall_judgment,
                    "recommendation": recommendation,
                    "detections": [item.model_dump(mode="json") for item in result.detections],
                }
                self.latest_inference = payload
                await self.broadcast_json(payload)
            except DetectorError as exc:
                await self.broadcast_json(
                    {
                        "type": "inference_error",
                        "frame_id": frame_id,
                        "message": str(exc),
                    }
                )
            finally:
                self.inference_queue.task_done()
