import json
import base64
from pathlib import Path
from typing import Any

import requests


def deploy_to_runpod(api_key: str, endpoint_id: str, script_path: str, input_json: str) -> Any:
    """Submit a serverless job to RunPod endpoint with embedded code.

    We package the best solution script as base64 text and send as part of input.
    The remote handler is expected to reconstruct and execute it.
    """
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = json.loads(input_json) if input_json else {}

    code_text = Path(script_path).read_text()
    payload["code_b64"] = base64.b64encode(code_text.encode()).decode()
    payload.setdefault("handler", "auto")

    resp = requests.post(url, headers=headers, json={"input": payload}, timeout=30)
    resp.raise_for_status()
    return resp.json()


