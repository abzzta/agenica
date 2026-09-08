"""
WebSocket Session Manager for Gemini Multimodal Live API.
Coordinates bidirectional audio streaming, real-time transcription, and asynchronous tool execution.
"""

import os
import json
import asyncio
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
import google.auth
from google.auth.transport.requests import Request as AuthRequest
from google import genai
from google.genai import types

from ..config import MAX_CONCURRENT_SESSIONS, SESSION_TIMEOUT_SECONDS
from .prompt_builder import build_live_instructions
from .tool_registry import LIVE_TOOLS
from .tool_executor import execute_live_tool, format_action_card

logger = logging.getLogger("agenica.live.session")


class LiveSessionManager:
    """Manages full lifecycle of a Gemini Live Audio WebSocket session."""

    def __init__(self):
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "ag-test-1310")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.quota_proj = os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT", self.project_id)
        self.model_name = "gemini-live-2.5-flash-native-audio"
        self.active_sessions: int = 0
        self._lock = asyncio.Lock()

    def _get_authenticated_client(self) -> genai.Client:
        """Initialize Google GenAI client with cloud-platform scopes and quota project."""
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if hasattr(creds, "with_quota_project") and self.quota_proj:
            try:
                creds = creds.with_quota_project(self.quota_proj)
            except Exception:
                pass

        if hasattr(creds, "refresh") and not creds.valid:
            try:
                creds.refresh(AuthRequest())
            except Exception:
                pass

        return genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
            credentials=creds,
        )

    async def handle_websocket(self, websocket: WebSocket):
        """Accept WebSocket and run full-duplex live audio pipeline."""
        async with self._lock:
            if self.active_sessions >= MAX_CONCURRENT_SESSIONS:
                await websocket.close(code=1013, reason="Service busy: max concurrent sessions active.")
                return
            self.active_sessions += 1

        try:
            await websocket.accept()
            client = self._get_authenticated_client()
            instructions = build_live_instructions()

            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Aoede"
                        )
                    )
                ),
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                system_instruction=types.Content(
                    parts=[types.Part(text=instructions)]
                ),
                tools=LIVE_TOOLS,
            )

            async with client.aio.live.connect(model=self.model_name, config=config) as session:
                # Task 1: Browser -> Gemini
                async def forward_browser_to_gemini():
                    try:
                        while True:
                            msg = await websocket.receive()
                            if "bytes" in msg and msg["bytes"]:
                                raw_pcm = msg["bytes"]
                                await session.send_realtime_input(
                                    audio=types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")
                                )
                            elif "text" in msg and msg["text"]:
                                txt = msg["text"]
                                try:
                                    parsed = json.loads(txt)
                                    msg_type = parsed.get("type")
                                    if msg_type == "ping":
                                        continue
                                    elif msg_type == "text":
                                        text_val = parsed.get("text", "")
                                        if text_val:
                                            await session.send_client_content(
                                                turns=[types.Content(role="user", parts=[types.Part(text=text_val)])],
                                                turn_complete=True,
                                            )
                                except Exception:
                                    pass
                    except WebSocketDisconnect:
                        pass
                    except Exception as e:
                        logger.error("browser_to_gemini error: %s", e)

                # Task 2: Gemini -> Browser
                async def forward_gemini_to_browser():
                    try:
                        tool_call_pending = False
                        while True:
                            try:
                                async for response in session.receive():
                                    # Handle tool calls
                                    if response.tool_call is not None:
                                        tool_call_pending = True
                                        function_responses = []
                                        for fc in response.tool_call.function_calls:
                                            call_id = fc.id
                                            fn_name = fc.name
                                            fn_args = fc.args or {}

                                            tool_result = await asyncio.to_thread(execute_live_tool, fn_name, fn_args)
                                            card = format_action_card(fn_name, tool_result)
                                            await websocket.send_text(json.dumps(card))

                                            function_responses.append(types.FunctionResponse(
                                                id=call_id,
                                                name=fn_name,
                                                response={"result": tool_result},
                                            ))

                                        if function_responses:
                                            await session.send_tool_response(function_responses=function_responses)

                                    # Handle server content
                                    sc = response.server_content
                                    if sc is not None:
                                        if getattr(sc, "interrupted", False):
                                            await websocket.send_text(json.dumps({"type": "interrupted"}))

                                        if hasattr(sc, "input_transcription") and sc.input_transcription and sc.input_transcription.text:
                                            await websocket.send_text(json.dumps({
                                                "type": "transcript_chunk",
                                                "role": "user",
                                                "text": sc.input_transcription.text,
                                            }))

                                        if hasattr(sc, "output_transcription") and sc.output_transcription and sc.output_transcription.text:
                                            await websocket.send_text(json.dumps({
                                                "type": "transcript_chunk",
                                                "role": "agent",
                                                "text": sc.output_transcription.text,
                                            }))

                                        model_turn = sc.model_turn
                                        if model_turn is not None:
                                            for part in model_turn.parts:
                                                if part.inline_data and part.inline_data.data:
                                                    await websocket.send_bytes(part.inline_data.data)

                                        if getattr(sc, "turn_complete", False):
                                            if tool_call_pending:
                                                tool_call_pending = False
                                            else:
                                                await websocket.send_text(json.dumps({"type": "turn_complete"}))

                            except asyncio.CancelledError:
                                break
                            except Exception as loop_err:
                                logger.error("session.receive error: %s", loop_err)
                                break
                    except WebSocketDisconnect:
                        pass
                    except Exception as e:
                        logger.error("gemini_to_browser error: %s", e)

                # Run with overall inactivity timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(forward_browser_to_gemini(), forward_gemini_to_browser()),
                        timeout=SESSION_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    await websocket.close(code=1000, reason="Session idle timeout reached.")

        except Exception as err:
            logger.error("Live session failed: %s", err)
            try:
                await websocket.send_text(json.dumps({
                    "type": "transcript",
                    "role": "agent",
                    "text": "Live session encountered a temporary error. Please re-tap to connect.",
                }))
            except Exception:
                pass
            try:
                await websocket.close()
            except Exception:
                pass
        finally:
            async with self._lock:
                self.active_sessions = max(0, self.active_sessions - 1)

