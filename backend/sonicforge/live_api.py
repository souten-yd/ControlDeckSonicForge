from __future__ import annotations

import json
import struct
import wave
from array import array
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .access import websocket_peer_is_trusted
from .edge_protocol import (
    AudioFrame,
    EdgeProtocolError,
    SequenceTracker,
    STREAM_MIC,
    STREAM_SPEAKER,
)
from .host.client import HostApiError, HostIdentity
from .jobs import HostedExecution
from .live_host_session import LiveHostSession
from .live_runtime import LiveTurnRunner
from .live_workers import LiveWorkerPool
from .pipeline_schema import AudioFormat, LiveSessionCreate, compile_pipeline
from .spool import AdaptiveSpoolFile, AudioSpoolManager

MAX_HELLO_BYTES = 64 * 1024
MIN_PTT_MS = 100


def _json_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _default_input() -> AudioFormat:
    return AudioFormat(codec="pcm_s16le", rate=16000, channels=1, frame_ms=20)


def _default_output() -> AudioFormat:
    return AudioFormat(codec="pcm_s16le", rate=24000, channels=1, frame_ms=20)


def _select_format(values: list[AudioFormat], *, output: bool) -> AudioFormat:
    preferred = 24000 if output else 16000
    pcm = [
        item for item in values if item.codec == "pcm_s16le" and item.channels == 1
    ]
    if not pcm:
        raise EdgeProtocolError("live v1 requires mono pcm_s16le")
    exact = next((item for item in pcm if item.rate == preferred), None)
    return exact or pcm[0]


def _formats(session: LiveSessionCreate) -> tuple[AudioFormat, AudioFormat]:
    if session.device is None:
        return _default_input(), _default_output()
    return (
        _select_format(session.device.audio.input, output=False),
        _select_format(session.device.audio.output, output=True),
    )


def _pcm_file_to_wav(raw_path: Path, wav_path: Path, fmt: AudioFormat) -> None:
    if fmt.codec != "pcm_s16le" or fmt.channels != 1:
        raise EdgeProtocolError("invalid PCM input format")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("rb") as source, wave.open(str(wav_path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(fmt.rate)
        while True:
            chunk = source.read(256 * 1024)
            if not chunk:
                break
            if len(chunk) % 2:
                raise EdgeProtocolError("PCM spool is not 16-bit aligned")
            stream.writeframesraw(chunk)


def _wav_mono_pcm(path: Path, target_rate: int) -> bytes:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        source_rate = stream.getframerate()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    if width != 2 or channels not in {1, 2}:
        raise EdgeProtocolError("live output requires 16-bit mono/stereo PCM WAV")
    samples = array("h")
    samples.frombytes(raw)
    if struct.pack("=H", 1) != struct.pack("<H", 1):
        samples.byteswap()
    if channels == 2:
        mono = [
            max(
                -32768,
                min(32767, (int(samples[i]) + int(samples[i + 1])) // 2),
            )
            for i in range(0, len(samples) - 1, 2)
        ]
    else:
        mono = [int(value) for value in samples]
    if source_rate <= 0 or target_rate <= 0:
        raise EdgeProtocolError("invalid live audio sample rate")
    if source_rate != target_rate and mono:
        target_count = max(1, round(len(mono) * target_rate / source_rate))
        if target_count == 1:
            mono = [mono[0]]
        else:
            scale = (len(mono) - 1) / (target_count - 1)
            resampled: list[int] = []
            for index in range(target_count):
                position = index * scale
                left = int(position)
                right = min(left + 1, len(mono) - 1)
                fraction = position - left
                sample = round(
                    mono[left] * (1.0 - fraction) + mono[right] * fraction
                )
                resampled.append(max(-32768, min(32767, sample)))
            mono = resampled
    return struct.pack(f"<{len(mono)}h", *mono) if mono else b""


async def _send_audio(
    websocket: WebSocket,
    path: Path,
    fmt: AudioFormat,
    *,
    chunk_index: int | None = None,
) -> None:
    pcm = _wav_mono_pcm(path, fmt.rate)
    samples_per_frame = max(1, round(fmt.rate * fmt.frame_ms / 1000))
    bytes_per_frame = samples_per_frame * 2
    await websocket.send_json(
        {
            "type": "turn.audio.start",
            "format": fmt.model_dump(mode="json"),
            "bytes": len(pcm),
            "chunk": chunk_index,
        }
    )
    sequence = 0
    sample_clock = 0
    for offset in range(0, len(pcm), bytes_per_frame):
        payload = pcm[offset : offset + bytes_per_frame]
        if not payload:
            continue
        await websocket.send_bytes(
            AudioFrame(
                stream=STREAM_SPEAKER,
                sequence=sequence,
                sample_clock=sample_clock,
                payload=payload,
            ).encode()
        )
        sequence = (sequence + 1) & 0xFFFFFFFF
        sample_clock = (sample_clock + len(payload) // 2) & 0xFFFFFFFF
    await websocket.send_json(
        {"type": "turn.audio.end", "frames": sequence, "chunk": chunk_index}
    )


def create_live_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v1/live", tags=["live"])
    spool_manager = AudioSpoolManager(base.settings)

    async def authenticate(websocket: WebSocket) -> HostIdentity | None:
        has_host = bool(
            websocket.headers.get("authorization")
            or websocket.headers.get("x-control-deck-addon-id")
        )
        if not has_host:
            if not websocket_peer_is_trusted(
                websocket, bind_host=base.settings.host
            ):
                raise HostApiError(
                    "trusted_local_peer_required",
                    "Unauthenticated live sessions are limited to trusted local-network peers",
                    status_code=403,
                )
            return None
        return await base.host_client.authenticate(websocket.headers)

    @router.websocket("/ws")
    async def live_ws(websocket: WebSocket):
        host_session: LiveHostSession | None = None
        worker_pool: LiveWorkerPool | None = None
        session_failed = False
        raw_spool: AdaptiveSpoolFile | None = None
        raw_path: Path | None = None
        try:
            identity = await authenticate(websocket)
        except HostApiError as exc:
            await websocket.close(code=4403 if exc.status_code == 403 else 4401)
            return
        await websocket.accept()
        try:
            first = await websocket.receive_text()
            if len(first.encode("utf-8")) > MAX_HELLO_BYTES:
                raise EdgeProtocolError("live hello is too large")
            value = json.loads(first)
            if not isinstance(value, dict) or value.get("type") != "hello":
                raise EdgeProtocolError("first live message must be hello")
            session_raw = value.get("session")
            if (
                not isinstance(session_raw, dict)
                or _json_bytes(session_raw) > MAX_HELLO_BYTES
            ):
                raise EdgeProtocolError("invalid live session contract")
            session = LiveSessionCreate.model_validate(session_raw)
            compiled = compile_pipeline(session.pipeline)
            active = session.pipeline.stages[
                compiled.start_index : compiled.stop_index + 1
            ]
            if session.pipeline.input.kind != "audio_stream":
                raise EdgeProtocolError("PTT live transport requires audio_stream input")
            if session.save_input_audio:
                raise EdgeProtocolError(
                    "save_input_audio belongs to the meeting recorder and is not implemented in PTT v1"
                )
            if any(stage.kind == "audio.process" for stage in active):
                raise EdgeProtocolError("audio.process is not implemented in live v1")
            if any(stage.kind == "host.ai.text" for stage in active) and identity is None:
                raise EdgeProtocolError(
                    "ControlDeck Host AI is required for this live pipeline"
                )

            host_session = LiveHostSession(
                host_client=base.host_client,
                jobs=base.jobs,
                identity=identity,
                title=f"SonicForge live session: {session.preset}",
            )
            await host_session.start(
                keep_llm_warm=session.keep_warm
                and any(stage.kind == "host.ai.text" for stage in active)
            )
            worker_pool = LiveWorkerPool(
                settings=base.settings,
                host_session=host_session,
            )
            runner = LiveTurnRunner(
                jobs=base.jobs,
                session_factory=base.session_factory,
                host_client=base.host_client,
                host_session=host_session,
                worker_pool=worker_pool,
            )
            input_format, output_format = _formats(session)
            max_input_bytes = (
                input_format.rate
                * input_format.channels
                * 2
                * session.max_utterance_seconds
                if session.max_utterance_seconds is not None
                else None
            )
            await websocket.send_json(
                {
                    "type": "ready",
                    "protocol": "sonic-live/1",
                    "preset": session.preset,
                    "input_format": input_format.model_dump(mode="json"),
                    "output_format": output_format.model_dump(mode="json"),
                    "mode": "half_duplex_ptt",
                    "max_utterance_seconds": session.max_utterance_seconds,
                    "streaming_response": session.streaming_response,
                    "keep_warm": session.keep_warm,
                    "spool": {
                        "policy": "ram-first-disk-fallback",
                        "ram_available": spool_manager.ram_available,
                    },
                }
            )

            tracker = SequenceTracker()
            recording = False
            recorded_bytes = 0
            turn_number = 0

            async def hosted_turn(title: str) -> HostedExecution | None:
                current = await host_session.identity()
                if current is None:
                    return None
                if "jobs.write" not in current.granted_capabilities:
                    raise HostApiError(
                        "capability_not_granted",
                        "jobs.write is required for hosted live turns",
                        status_code=403,
                    )
                created = await base.host_client.create_or_attach_job(
                    current, title=title
                )
                raw = created.get("job") if isinstance(created, dict) else None
                host_job_id = raw.get("id") if isinstance(raw, dict) else None
                if not isinstance(host_job_id, str) or not host_job_id:
                    raise HostApiError(
                        "invalid_host_response",
                        "ControlDeck did not return a Host Job",
                        status_code=502,
                    )
                return HostedExecution(identity=current, host_job_id=host_job_id)

            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                text = message.get("text")
                binary = message.get("bytes")
                if text is not None:
                    if len(text.encode("utf-8")) > MAX_HELLO_BYTES:
                        raise EdgeProtocolError("live control message is too large")
                    control = json.loads(text)
                    if not isinstance(control, dict):
                        raise EdgeProtocolError("live control message must be an object")
                    kind = control.get("type")
                    if kind == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue
                    if kind == "ptt.start":
                        if recording:
                            raise EdgeProtocolError("PTT is already recording")
                        if raw_spool is not None:
                            raw_spool.cleanup()
                        tracker = SequenceTracker()
                        recording = True
                        recorded_bytes = 0
                        turn_number += 1
                        raw_spool = spool_manager.open("live-input", suffix=".pcm")
                        raw_path = None
                        await websocket.send_json(
                            {
                                "type": "ptt.started",
                                "turn": turn_number,
                                "memory_backed": raw_spool.memory_backed,
                            }
                        )
                        continue
                    if kind == "ptt.stop":
                        if not recording or raw_spool is None:
                            raise EdgeProtocolError("PTT is not recording")
                        recording = False
                        raw_path = raw_spool.finalize()
                        raw_spool = None
                        duration_ms = (
                            recorded_bytes
                            * 1000
                            // max(1, input_format.rate * input_format.channels * 2)
                        )
                        if duration_ms < MIN_PTT_MS:
                            raw_path.unlink(missing_ok=True)
                            raw_path = None
                            await websocket.send_json(
                                {
                                    "type": "turn.error",
                                    "code": "input_too_short",
                                    "message": "PTT audio is too short",
                                }
                            )
                            continue
                        input_path = raw_path.with_suffix(".wav")
                        _pcm_file_to_wav(raw_path, input_path, input_format)
                        raw_path.unlink(missing_ok=True)
                        raw_path = None
                        try:
                            execution = await hosted_turn(
                                f"SonicForge live turn {turn_number}: {session.preset}"
                            )
                            await websocket.send_json(
                                {
                                    "type": "turn.started",
                                    "turn": turn_number,
                                    "host_job_id": execution.host_job_id
                                    if execution
                                    else None,
                                }
                            )

                            async def emit(event: dict[str, Any]) -> None:
                                event = dict(event)
                                event.setdefault("turn", turn_number)
                                await websocket.send_json(event)

                            async def emit_audio(path: Path, chunk: int) -> None:
                                await _send_audio(
                                    websocket,
                                    path,
                                    output_format,
                                    chunk_index=chunk,
                                )

                            result = await runner.run(
                                session,
                                input_path,
                                hosted=execution,
                                emit=emit,
                                emit_audio=emit_audio,
                            )
                            try:
                                if (
                                    result.audio_path is not None
                                    and not result.streamed_audio
                                ):
                                    await _send_audio(
                                        websocket,
                                        result.audio_path,
                                        output_format,
                                    )
                                await websocket.send_json(
                                    {
                                        "type": "turn.complete",
                                        "turn": turn_number,
                                        "job_id": result.job_id,
                                        "asset_id": result.asset_id,
                                        "transcript": result.transcript,
                                        "response_text": result.response_text,
                                        "streamed_audio": result.streamed_audio,
                                    }
                                )
                            finally:
                                result.cleanup()
                        except Exception as exc:
                            await websocket.send_json(
                                {
                                    "type": "turn.error",
                                    "turn": turn_number,
                                    "code": "turn_failed",
                                    "message": str(exc)[:500],
                                }
                            )
                        finally:
                            input_path.unlink(missing_ok=True)
                        continue
                    if kind == "close":
                        if worker_pool is not None:
                            await worker_pool.close()
                            worker_pool = None
                        if host_session is not None:
                            await host_session.close(failed=session_failed)
                            host_session = None
                        await websocket.close(code=1000)
                        return
                    raise EdgeProtocolError(
                        f"unsupported live control message: {kind}"
                    )

                if binary is not None:
                    if not recording or raw_spool is None:
                        raise EdgeProtocolError(
                            "audio frame received outside PTT recording"
                        )
                    frame = AudioFrame.decode(binary)
                    if frame.stream != STREAM_MIC:
                        raise EdgeProtocolError(
                            "client may only send microphone frames"
                        )
                    observation = tracker.observe(frame)
                    if observation.duplicate_or_old:
                        await websocket.send_json(
                            {
                                "type": "audio.warning",
                                "code": "duplicate_or_old",
                                "sequence": frame.sequence,
                            }
                        )
                        continue
                    if observation.gap:
                        await websocket.send_json(
                            {
                                "type": "audio.warning",
                                "code": "sequence_gap",
                                "missing_frames": observation.gap,
                                "sequence": frame.sequence,
                            }
                        )
                    if len(frame.payload) % 2:
                        raise EdgeProtocolError(
                            "PCM frame payload must be 16-bit aligned"
                        )
                    if (
                        max_input_bytes is not None
                        and recorded_bytes + len(frame.payload) > max_input_bytes
                    ):
                        recording = False
                        raw_spool.cleanup()
                        raw_spool = None
                        raw_path = None
                        await websocket.send_json(
                            {
                                "type": "turn.error",
                                "code": "configured_utterance_limit",
                                "message": "PTT audio reached the explicitly configured max_utterance_seconds",
                            }
                        )
                        continue
                    raw_spool.write(frame.payload)
                    recorded_bytes += len(frame.payload)
        except WebSocketDisconnect:
            return
        except (EdgeProtocolError, ValueError, json.JSONDecodeError) as exc:
            session_failed = True
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "protocol_error",
                        "message": str(exc)[:500],
                    }
                )
                await websocket.close(code=4400)
            except RuntimeError:
                pass
        finally:
            if raw_spool is not None:
                raw_spool.cleanup()
            if raw_path is not None:
                raw_path.unlink(missing_ok=True)
            if worker_pool is not None:
                await worker_pool.close()
            if host_session is not None:
                await host_session.close(failed=session_failed)

    return router
