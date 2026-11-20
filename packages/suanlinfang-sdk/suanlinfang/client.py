import logging

from suanlinfang.config import SdkConfig
from suanlinfang.http import HttpTransport
from suanlinfang.image import ImageClient
from suanlinfang.ocr import OcrClient
from suanlinfang.stt import SttClient
from suanlinfang.tts import TtsClient

logger = logging.getLogger("suanlinfang.sdk")


class SuanlinfangClient:
    """算邻坊开放 API 客户端门面：image / stt / tts / ocr 四产品子客户端。

    用法：
        client = SuanlinfangClient(api_key="nk-...")
        result = client.stt.transcribe_url("https://.../a.wav")
    也可用 with 语句（复用底层 httpx 连接池）。
    """

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float = 60.0):
        self.config = SdkConfig(api_key=api_key, base_url=base_url, timeout=timeout)
        self._transport = HttpTransport(self.config)
        self.image = ImageClient(self._transport)
        self.stt = SttClient(self._transport)
        self.tts = TtsClient(self._transport)
        self.ocr = OcrClient(self._transport)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "SuanlinfangClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
