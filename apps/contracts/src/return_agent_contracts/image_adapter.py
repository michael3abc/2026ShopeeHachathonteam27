"""Internal image transport adapter. Loaded bytes are ephemeral model inputs."""

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from .attachments import ImageContent


@dataclass
class HttpEvidenceImageProvider:
    base_url: str
    service_token: str
    client: httpx.Client
    max_bytes: int = 10 * 1024 * 1024

    def load_image(self, case_ref: str, artifact_ref: str) -> ImageContent:
        try:
            return self._load_image(case_ref, artifact_ref)
        except httpx.RequestError as error:
            raise RuntimeError(
                f"Image transport failed ({type(error).__name__})"
            ) from None

    def _load_image(self, case_ref: str, artifact_ref: str) -> ImageContent:
        prefix = "artifact://upload/"
        identifier = artifact_ref.removeprefix(prefix)
        if (
            not artifact_ref.startswith(prefix)
            or len(identifier) != 32
            or any(c not in "0123456789abcdef" for c in identifier)
        ):
            raise ValueError("Invalid upload reference")
        url = f"{self.base_url.rstrip('/')}/internal/cases/{quote(case_ref, safe='')}/images/{identifier}"
        with self.client.stream(
            "GET", url, headers={"Authorization": f"Bearer {self.service_token}"}
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Image fetch failed ({response.status_code})")
            media_type = response.headers.get("content-type", "").split(";")[0]
            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Invalid image response type")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > self.max_bytes:
                    raise ValueError("Image response exceeds size limit")
            if not content:
                raise ValueError("Empty image response")
            return ImageContent(media_type=media_type, content=bytes(content))
