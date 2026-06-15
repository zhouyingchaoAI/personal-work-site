"""会议助手：实时转写（ASR）、翻译、AI 总结与会议记录存储。

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

MEETING_ASR_DEFAULT_MODEL = "whisper-1"
MEETING_SEGMENT_LIMIT = 2000
MEETING_AUDIO_MAX_BYTES = 25 * 1024 * 1024

MEETING_SUMMARY_SYSTEM = (
    "你是会议纪要助手。根据会议转写文本生成结构化中文纪要，输出 Markdown，包含以下小节：\n"
    "## 会议主题\n## 核心要点\n## 讨论与结论\n## 待办事项\n"
    "待办事项用列表，尽量标注负责人和时间（转写中没有就不要编造）。\n"
    "转写来自语音识别，可能有错字，按上下文合理理解；不要编造转写中不存在的内容。"
)

MEETING_TRANSLATE_TARGETS = {
    "zh": "简体中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "ru": "俄语",
    "fr": "法语",
    "de": "德语",
}


def meeting_asr_settings() -> dict:
    config = read_config()
    return {
        "api_url": str(config.get("meeting_asr_api_url") or "").strip(),
        "api_key": str(config.get("meeting_asr_api_key") or ""),
        "model": str(config.get("meeting_asr_model") or "").strip() or MEETING_ASR_DEFAULT_MODEL,
    }


def meeting_config_api() -> dict:
    settings = meeting_asr_settings()
    settings["api_key_masked"] = "已配置" if settings.pop("api_key") else "未配置"
    return {"ok": True, **settings}


def save_meeting_config(payload: dict) -> dict:
    payload = payload or {}
    config = read_config()
    config["meeting_asr_api_url"] = str(payload.get("api_url", "") or "").strip().rstrip("/")
    config["meeting_asr_model"] = str(payload.get("model", "") or "").strip()[:100] or MEETING_ASR_DEFAULT_MODEL
    # Key 留空表示保持原值不变；本地 Xinference 等无鉴权服务用 api_key_clear 显式清空。
    if payload.get("api_key_clear"):
        config["meeting_asr_api_key"] = ""
    else:
        api_key = str(payload.get("api_key", "") or "").strip()
        if api_key:
            config["meeting_asr_api_key"] = api_key
    write_config(config)
    return meeting_config_api()


def _meeting_audio_bytes(audio: str):
    """解出 data URI 里的音频字节与 MIME，限制大小防止异常上传。"""
    audio = str(audio or "").strip()
    if not audio.startswith("data:"):
        raise ValueError("audio 需要是 data URI")
    head, _, payload = audio.partition(",")
    mime = head[5:].split(";")[0] or "audio/webm"
    raw = base64.b64decode(payload)
    if not raw:
        raise ValueError("音频内容为空")
    if len(raw) > MEETING_AUDIO_MAX_BYTES:
        raise ValueError("单段音频超过 25MB 限制")
    return raw, mime


def meeting_transcribe(payload: dict, username: str = "") -> dict:
    """调用 OpenAI 兼容 /v1/audio/transcriptions 转写一段音频。"""
    payload = payload or {}
    raw, mime = _meeting_audio_bytes(payload.get("audio", ""))
    language = str(payload.get("language", "") or "").strip()[:10]
    text = _meeting_asr_request(raw, mime, language, meeting_asr_settings())
    return {"ok": True, "text": text}


def meeting_test_asr(payload: dict) -> dict:
    """设置页"测试识别"：用内置样例音频（内容为"语音测试"）实测当前（含未保存）配置。"""
    payload = payload or {}
    settings = meeting_asr_settings()
    for key in ("api_url", "api_key", "model"):
        override = str(payload.get(key, "") or "").strip()
        if override:
            settings[key] = override
    sample = DIGITAL_HUMAN_DIR / "voice-sample.mp3"
    if not sample.exists():
        raise ValueError("缺少测试音频文件 voice-sample.mp3")
    text = _meeting_asr_request(sample.read_bytes(), "audio/mpeg", "zh", settings)
    return {"ok": True, "model": settings["model"], "text": text}


def _meeting_asr_request(raw: bytes, mime: str, language: str, settings: dict) -> str:
    # 地址显式配置（如本地 Xinference）时使用其自身 Key（可为空=无鉴权）。
    url, key = resolve_speech_api_target(settings["api_url"], settings["api_key"])
    if not url:
        raise ValueError("未配置语音识别 API 地址")

    suffix = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(mime, "webm")
    boundary = uuid.uuid4().hex
    fields = [("model", settings["model"])]
    if language:
        fields.append(("language", language))
    parts = []
    for name, value in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="segment.{suffix}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode("utf-8") + raw + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/audio/transcriptions",
        data=b"".join(parts),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise ValueError(f"语音识别接口返回 {exc.code}：{detail}") from exc
    return str(data.get("text", "") or "").strip()


def _meeting_llm_chat(system: str, user: str, temperature: float = 0.2) -> str:
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        raise ValueError("尚未配置智能助手接口")
    body = json.dumps(
        {
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        settings["url"] + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["key"]},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"] or "").strip()


def meeting_translate(payload: dict) -> dict:
    payload = payload or {}
    text = str(payload.get("text", "") or "").strip()
    if not text:
        raise ValueError("text is required")
    target = str(payload.get("target", "") or "en").strip()
    target_name = MEETING_TRANSLATE_TARGETS.get(target)
    if not target_name:
        raise ValueError(f"不支持的目标语言：{target}")
    translated = _meeting_llm_chat(
        f"你是同声传译。把用户给出的会议发言翻译成{target_name}，只输出译文，不要解释。"
        "发言来自语音识别可能有错字，按上下文合理翻译。",
        text[:MEETING_SEGMENT_LIMIT],
        temperature=0.1,
    )
    return {"ok": True, "text": translated}


def meeting_summarize(payload: dict, username: str = "") -> dict:
    payload = payload or {}
    transcript = str(payload.get("transcript", "") or "").strip()
    if not transcript:
        raise ValueError("transcript is required")
    title = str(payload.get("title", "") or "").strip()
    prompt = f"会议标题：{title}\n\n" if title else ""
    prompt += f"会议转写文本：\n{transcript[:24000]}"
    summary = _meeting_llm_chat(MEETING_SUMMARY_SYSTEM, prompt, temperature=0.3)
    if not summary:
        raise ValueError("模型没有返回总结内容")
    return {"ok": True, "summary": summary}


# ---------------------------------------------------------------------------
# 会议记录存储（按用户隔离）
# ---------------------------------------------------------------------------

def _meeting_dir(username: str):
    safe = Path(str(username or "")).name
    if not safe:
        raise ValueError("用户无效")
    path = USER_DATA_DIR / safe / "meetings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _meeting_path(username: str, meeting_id: str):
    safe = Path(str(meeting_id or "")).name
    if not safe or not re.match(r"^[0-9A-Za-z_-]+$", safe):
        raise ValueError("会议 ID 无效")
    return _meeting_dir(username) / f"{safe}.json"


def meeting_save(payload: dict, username: str = "") -> dict:
    payload = payload or {}
    meeting_id = str(payload.get("id", "") or "").strip() or datetime.now().strftime("m%Y%m%d%H%M%S")
    path = _meeting_path(username, meeting_id)
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    segments = payload.get("segments")
    record = {
        "id": meeting_id,
        "title": str(payload.get("title", "") or "").strip()[:200] or existing.get("title") or "未命名会议",
        "created_at": existing.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration": int(payload.get("duration", existing.get("duration", 0)) or 0),
        "language": str(payload.get("language", "") or existing.get("language", "") or "")[:10],
        "translate_target": str(payload.get("translate_target", "") or existing.get("translate_target", "") or "")[:10],
        "segments": segments if isinstance(segments, list) else existing.get("segments", []),
        "summary": str(payload.get("summary", existing.get("summary", "")) or ""),
    }
    # 段落字段做基本清洗，避免脏数据撑爆存储。
    cleaned = []
    for item in record["segments"][:2000]:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "time": str(item.get("time", "") or "")[:20],
                "text": str(item.get("text", "") or "")[:MEETING_SEGMENT_LIMIT],
                "translation": str(item.get("translation", "") or "")[:MEETING_SEGMENT_LIMIT],
            }
        )
    record["segments"] = cleaned
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "id": meeting_id, "meeting": record}


def meeting_list(username: str = "") -> dict:
    items = []
    for path in sorted(_meeting_dir(username).glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append(
            {
                "id": data.get("id") or path.stem,
                "title": data.get("title") or "未命名会议",
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "duration": int(data.get("duration", 0) or 0),
                "segment_count": len(data.get("segments", []) or []),
                "has_summary": bool(str(data.get("summary", "") or "").strip()),
            }
        )
    return {"ok": True, "meetings": items}


def meeting_get(meeting_id: str, username: str = "") -> dict:
    path = _meeting_path(username, meeting_id)
    if not path.exists():
        raise ValueError("会议记录不存在")
    return {"ok": True, "meeting": json.loads(path.read_text(encoding="utf-8"))}


def meeting_delete(payload: dict, username: str = "") -> dict:
    payload = payload or {}
    path = _meeting_path(username, str(payload.get("id", "") or ""))
    if path.exists():
        path.unlink()
    return {"ok": True}
