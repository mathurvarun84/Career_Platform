import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from jose import jwt


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET missing in .env")

    user_id = "4f76ae22-433f-4254-9229-50dc8be25047"
    token = jwt.encode({"sub": user_id, "role": "authenticated"}, secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    files = {
        "resume": (
            "tmp_api_resume.txt",
            Path("tmp_api_resume.txt").read_bytes(),
            "text/plain",
        )
    }
    data = {
        "jd_text": "Engineering Manager role requiring distributed systems, leadership, and API reliability.",
        "run_sim": "true",
    }

    with requests.post(
        "http://127.0.0.1:8000/api/analyze",
        headers=headers,
        files=files,
        data=data,
        stream=True,
        timeout=600,
    ) as resp:
        print("status:", resp.status_code)
        resp.raise_for_status()
        final_result = None
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if not raw.startswith("data: "):
                continue
            payload = json.loads(raw[6:])
            event = payload.get("event")
            if event == "step_complete":
                print("step_complete:", payload.get("step"), payload.get("label"))
            elif event == "error":
                print("error_event:", payload)
                raise RuntimeError(str(payload))
            elif event == "analysis_complete":
                final_result = payload.get("result")
                print("analysis_complete: received final payload")
        if not final_result:
            raise RuntimeError("No analysis_complete payload received")
        rewrites = (final_result.get("rewrites") or {}).get("rewrites") or {}
        exp = rewrites.get("experience") or {}
        print("experience_markers:", {k: str(v).count("##COMPANY##") for k, v in exp.items()})
        print("job_id:", final_result.get("job_id"))


if __name__ == "__main__":
    main()
