from typing import Any

from suanlinfang.http import HttpTransport
from suanlinfang.types import DecisionResult


class DecisionClient:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def decide(self, state: Any, questions: dict[str, Any]) -> DecisionResult:
        """智能决策（System One 协议）：state + 类型化问题集（1-32 题），单次前向返回校准概率。

        questions 每题：type ∈ choice/noul/score；criteria 形状按题型（choice {选项:描述}、
        noul {true/false:描述} 可选、score [等级描述...]）；answers 按同键回传。
        """
        body = self.transport.request_json(
            "POST", "/systemone", json={"state": state, "questions": questions}
        )
        return DecisionResult(
            inference_id=body.get("inferenceId", ""),
            answers=body.get("answers") or {},
            usage=body.get("usage") or {},
            latency_ms=body.get("latency_ms"),
        )
