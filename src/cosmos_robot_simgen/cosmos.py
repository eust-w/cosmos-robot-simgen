from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class CosmosClientError(RuntimeError):
    """Raised when Cosmos3 Nano inference cannot complete."""


@dataclass(frozen=True)
class CosmosGeneration:
    video_bytes: bytes
    request_payload: Dict[str, Any]
    response_metadata: Dict[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.video_bytes).hexdigest()


def cosmos_artifact_index(generation: CosmosGeneration) -> Dict[str, Any]:
    return {
        "video": "raw/cosmos_preview.mp4",
        "request": "raw/cosmos_request.json",
        "response_metadata": "raw/cosmos_response_metadata.json",
        "video_sha256": generation.sha256,
        "video_bytes": len(generation.video_bytes),
    }


UrlOpen = Callable[..., Any]


class Cosmos3NanoClient:
    """Small NIM-compatible client for Cosmos3 Nano generator endpoints."""

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        timeout_s: int = 900,
        opener: Optional[UrlOpen] = None,
    ) -> None:
        if not endpoint:
            raise CosmosClientError("Cosmos3 Nano endpoint is required")
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._opener = opener or urllib.request.urlopen

    @classmethod
    def from_environment(cls, endpoint: Optional[str] = None) -> "Cosmos3NanoClient":
        resolved_endpoint = endpoint or os.environ.get("COSMOS3_NANO_URL", "")
        api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("COSMOS3_NANO_API_KEY")
        return cls(endpoint=resolved_endpoint, api_key=api_key)

    def generate_video(
        self,
        prompt: str,
        *,
        resolution: str = "720_16_9",
        num_output_frames: int = 189,
        seed: int = 42,
        fps: int = 24,
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        negative_prompt: Optional[str] = None,
        image: Optional[str] = None,
    ) -> CosmosGeneration:
        if not prompt.strip():
            raise CosmosClientError("prompt is required")
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "resolution": resolution,
            "num_output_frames": num_output_frames,
            "seed": seed,
            "fps": fps,
        }
        if steps is not None:
            payload["steps"] = steps
        if guidance_scale is not None:
            payload["guidance_scale"] = guidance_scale
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if image:
            payload["image"] = image

        data = self._post_json(payload)
        encoded_video = data.get("b64_video")
        if not isinstance(encoded_video, str) or not encoded_video:
            raise CosmosClientError("Cosmos3 Nano response did not contain a non-empty b64_video field")
        try:
            video_bytes = base64.b64decode(encoded_video, validate=True)
        except ValueError as exc:
            raise CosmosClientError("Cosmos3 Nano returned invalid base64 video data") from exc
        if not video_bytes:
            raise CosmosClientError("Cosmos3 Nano returned an empty video")

        metadata = {key: value for key, value in data.items() if key != "b64_video"}
        metadata["b64_video_bytes"] = len(encoded_video)
        return CosmosGeneration(video_bytes=video_bytes, request_payload=payload, response_metadata=metadata)

    def _post_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CosmosClientError(f"Cosmos3 Nano HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise CosmosClientError(f"Cosmos3 Nano endpoint is unreachable: {exc.reason}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CosmosClientError("Cosmos3 Nano response was not valid JSON") from exc
        if not isinstance(data, dict):
            raise CosmosClientError("Cosmos3 Nano response must be a JSON object")
        return data

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def write_cosmos_artifacts(output_dir: Path, generation: CosmosGeneration) -> Dict[str, Any]:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    video_path = raw_dir / "cosmos_preview.mp4"
    video_path.write_bytes(generation.video_bytes)

    request_path = raw_dir / "cosmos_request.json"
    request_path.write_text(json.dumps(generation.request_payload, indent=2, sort_keys=True), encoding="utf-8")

    response_path = raw_dir / "cosmos_response_metadata.json"
    response_metadata = dict(generation.response_metadata)
    response_metadata["video_sha256"] = generation.sha256
    response_metadata["video_bytes"] = len(generation.video_bytes)
    response_path.write_text(json.dumps(response_metadata, indent=2, sort_keys=True), encoding="utf-8")

    return cosmos_artifact_index(generation)
