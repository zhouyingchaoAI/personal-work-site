"""3D 数字人（承希犇犇）对话与语音接口。

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

DIGITAL_HUMAN_DIR = BASE_DIR / "数字人"

DIGITAL_HUMAN_ACTIONS = (
    "greet",
    "welcome",
    "goodbye",
    "thanks",
    "ok",
    "cheer",
    "goal",
    "laugh",
    "kiss",
    "awesome",
)

DIGITAL_HUMAN_SYSTEM_PROMPT = (
    "你是\"犇犇\"，湖南承希科技的 3D 数字人办公助手，正在通过语音和用户实时对话。\n"
    "回答要求：\n"
    "1. 用口语化中文回答，内容会被朗读出来，控制在 80 字以内，不要使用 Markdown、列表和表情符号。\n"
    "2. 可以回答办公平台（周报、出差报告、邮件、日记、论坛、资讯）相关问题，也可以闲聊。\n"
    "3. 同时为这句回答挑选一个肢体动作，动作必须从下面列表中选，没有合适的就用 null：\n"
    "   greet(打招呼) welcome(欢迎) goodbye(再见) thanks(感谢) ok(确认) "
    "cheer(加油鼓劲) goal(定目标) laugh(大笑) kiss(么么哒) awesome(称赞牛掰)\n"
    "4. 只输出一个 JSON 对象，格式：{\"text\": \"回答内容\", \"action\": \"动作名或null\"}，不要输出其他内容。"
)

WEEKLY_STAGE_CONVERSATION_PROMPT = (
    "你正在协助用户分阶段撰写周报，当前阶段是：{stage}。\n"
    "这不是一次性生成周报的请求：只围绕当前阶段与用户多轮讨论。结合用户的附件内容和上下文，"
    "先澄清或润色，再给出一版可直接放入该阶段的简洁中文草稿。"
    "不要进入下一阶段，不要生成完整周报，也不要说已写入页面。"
    "回答不超过 180 字；草稿尽量按“分类：内容”分行。"
)

# 接口异常时按关键词兜底选动作，保证数字人仍有肢体反馈。
DIGITAL_HUMAN_ACTION_KEYWORDS = (
    ("greet", ("你好", "您好", "嗨", "哈喽", "hello", "hi")),
    ("goodbye", ("再见", "拜拜", "回见", "晚安")),
    ("thanks", ("谢谢", "感谢", "辛苦")),
    ("welcome", ("欢迎",)),
    ("cheer", ("加油", "鼓励", "打气")),
    ("laugh", ("哈哈", "好笑", "搞笑", "笑话")),
    ("awesome", ("厉害", "牛", "棒", "真棒")),
    ("ok", ("好的", "可以", "没问题", "确认")),
)


# edge-tts 支持的中文音色（2026-06 实测 list_voices 结果），id 必须是合法 ShortName。
DIGITAL_HUMAN_TTS_VOICES = [
    {"id": "zh-CN-XiaoyiNeural", "label": "晓伊 · 女声 · 活泼（默认）"},
    {"id": "zh-CN-XiaoxiaoNeural", "label": "晓晓 · 女声 · 温暖"},
    {"id": "zh-CN-YunxiNeural", "label": "云希 · 男声 · 阳光"},
    {"id": "zh-CN-YunxiaNeural", "label": "云夏 · 男声 · 少年"},
    {"id": "zh-CN-YunjianNeural", "label": "云健 · 男声 · 激情"},
    {"id": "zh-CN-YunyangNeural", "label": "云扬 · 男声 · 新闻播报"},
    {"id": "zh-CN-liaoning-XiaobeiNeural", "label": "晓北 · 女声 · 东北话"},
    {"id": "zh-CN-shaanxi-XiaoniNeural", "label": "晓妮 · 女声 · 陕西话"},
    {"id": "zh-TW-HsiaoChenNeural", "label": "晓臻 · 女声 · 台湾腔"},
    {"id": "zh-HK-HiuMaanNeural", "label": "晓曼 · 女声 · 粤语"},
]

DIGITAL_HUMAN_TTS_DEFAULT_VOICE = "zh-CN-XiaoyiNeural"
_TTS_VOICE_PATTERN = re.compile(r"^[A-Za-z]{2,3}-[A-Za-z]{2,10}(?:-[A-Za-z]+)*Neural$")
_TTS_RATE_PATTERN = re.compile(r"^[+-]\d{1,3}%$")
_TTS_PITCH_PATTERN = re.compile(r"^[+-]\d{1,3}Hz$")


def _valid_tts_voice(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not _TTS_VOICE_PATTERN.match(value):
        raise ValueError(f"音色名称格式不正确：{value}")
    return value


def _valid_tts_rate(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not _TTS_RATE_PATTERN.match(value):
        raise ValueError(f"语速格式不正确（示例 +15%）：{value}")
    return value


def _valid_tts_pitch(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not _TTS_PITCH_PATTERN.match(value):
        raise ValueError(f"语调格式不正确（示例 +20Hz）：{value}")
    return value


def _valid_tts_provider(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if value not in ("edge", "api"):
        raise ValueError(f"语音引擎只支持 edge 或 api：{value}")
    return value


def digital_human_tts_settings() -> dict:
    config = read_config()
    return {
        "provider": str(config.get("digital_human_tts_provider") or "").strip() or "edge",
        "voice": str(config.get("digital_human_tts_voice") or "").strip() or DIGITAL_HUMAN_TTS_DEFAULT_VOICE,
        "rate": str(config.get("digital_human_tts_rate") or "").strip() or "+0%",
        "pitch": str(config.get("digital_human_tts_pitch") or "").strip() or "+0Hz",
        "api_url": str(config.get("digital_human_tts_api_url") or "").strip(),
        "api_key": str(config.get("digital_human_tts_api_key") or ""),
        "api_model": str(config.get("digital_human_tts_api_model") or "").strip() or "tts-1",
        "api_voice": str(config.get("digital_human_tts_api_voice") or "").strip() or "alloy",
    }


def digital_human_tts_config_api() -> dict:
    settings = digital_human_tts_settings()
    settings["api_key_masked"] = "已配置" if settings.pop("api_key") else "未配置"
    return {"ok": True, "voices": DIGITAL_HUMAN_TTS_VOICES, **settings}


def save_digital_human_tts_config(payload: dict) -> dict:
    payload = payload or {}
    provider = _valid_tts_provider(payload.get("provider", ""))
    voice = _valid_tts_voice(payload.get("voice", ""))
    rate = _valid_tts_rate(payload.get("rate", ""))
    pitch = _valid_tts_pitch(payload.get("pitch", ""))
    config = read_config()
    config["digital_human_tts_provider"] = provider or "edge"
    config["digital_human_tts_voice"] = voice or DIGITAL_HUMAN_TTS_DEFAULT_VOICE
    config["digital_human_tts_rate"] = rate or "+0%"
    config["digital_human_tts_pitch"] = pitch or "+0Hz"
    config["digital_human_tts_api_url"] = str(payload.get("api_url", "") or "").strip().rstrip("/")
    config["digital_human_tts_api_model"] = str(payload.get("api_model", "") or "").strip()[:100]
    config["digital_human_tts_api_voice"] = str(payload.get("api_voice", "") or "").strip()[:100]
    # Key 留空表示保持原值不变；本地 Xinference 等无鉴权服务用 api_key_clear 显式清空。
    if payload.get("api_key_clear"):
        config["digital_human_tts_api_key"] = ""
    else:
        api_key = str(payload.get("api_key", "") or "").strip()
        if api_key:
            config["digital_human_tts_api_key"] = api_key
    write_config(config)
    return digital_human_tts_config_api()


def _tts_rate_to_speed(rate: str) -> float:
    """把 edge 风格的 ±N% 语速换算成 OpenAI 兼容接口的 speed 倍率。"""
    try:
        return max(0.25, min(4.0, 1.0 + int(rate.rstrip("%")) / 100))
    except Exception:
        return 1.0


def resolve_speech_api_target(api_url: str, api_key: str):
    """解析语音类接口的地址和 Key。

    - 显式配置了地址（如本地 Xinference http://host:9997）就用它自己的 Key，
      为空表示该服务无鉴权，不能错误回退成大模型网关的 Key。
    - 地址留空才整体回退到大模型网关的地址 + Key。
    """
    fallback = assistant_settings()
    if api_url:
        return api_url, api_key
    return fallback["url"], (api_key or fallback["key"])


def speech_api_headers(key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    return headers


def _synthesize_via_api(text: str, settings: dict) -> bytes:
    """调用 OpenAI 兼容的 /v1/audio/speech 接口（NewAPI 网关或本地 Xinference 均可）。"""
    url, key = resolve_speech_api_target(settings["api_url"], settings["api_key"])
    if not url:
        raise ValueError("未配置语音 API 地址")
    body = {
        "model": settings["api_model"] or "tts-1",
        "input": text,
        "voice": settings["api_voice"] or "alloy",
        "response_format": "mp3",
    }
    speed = _tts_rate_to_speed(settings["rate"])
    if speed != 1.0:
        body["speed"] = speed
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=speech_api_headers(key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            content_type = (response.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise ValueError(f"语音 API 返回 {exc.code}：{detail}") from exc
    if "json" in content_type:
        # 网关把错误包成 200 JSON 的情况。
        raise ValueError(f"语音 API 返回异常：{raw.decode('utf-8', 'ignore')[:300]}")
    return raw


def digital_human_page() -> str:
    return (DIGITAL_HUMAN_DIR / "index.html").read_text(encoding="utf-8")


def digital_human_asset(relative: str):
    """Resolve an exports asset path, refusing traversal outside the exports dir."""
    rel = Path(urllib.parse.unquote(relative))
    if rel.is_absolute() or ".." in rel.parts:
        return None
    path = DIGITAL_HUMAN_DIR / "exports" / rel
    if not path.exists() or not path.is_file():
        return None
    return path


def digital_human_static(relative: str):
    """Resolve a top-level static file of the digital human page (e.g. logo_1.png)."""
    name = Path(urllib.parse.unquote(relative)).name
    path = DIGITAL_HUMAN_DIR / name
    if not name or not path.exists() or not path.is_file():
        return None
    return path


def _guess_digital_human_action(text: str):
    lowered = str(text or "").lower()
    for action, keywords in DIGITAL_HUMAN_ACTION_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return action
    return None


def _parse_digital_human_reply(content: str) -> dict:
    """Extract {"text", "action"} from model output, tolerating extra prose around the JSON."""
    content = str(content or "").strip()
    candidate = content
    match = re.search(r"\{.*\}", content, re.S)
    if match:
        candidate = match.group(0)
    try:
        data = json.loads(candidate)
    except Exception:
        data = {"text": content}
    text = str(data.get("text", "") or "").strip() or content
    action = str(data.get("action", "") or "").strip()
    if action not in DIGITAL_HUMAN_ACTIONS:
        action = _guess_digital_human_action(text)
    return {"text": text, "action": action}


def _strip_markdown_for_speech(text: str) -> str:
    """龙虾的回答常带 Markdown，朗读和字幕展示前做轻量清洗。"""
    text = str(text or "")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _digital_human_lobster_reply(username: str, message: str, bound: dict) -> str:
    """把数字人对话桥接到用户绑定的龙虾，会话沿用悬浮助手的固定 session。"""
    user = find_user(username)
    if not user:
        raise ValueError("用户不存在")
    token = _openclaw_sso_token(public_user(user))
    target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        f"{target}/api/agents/{int(bound['agent_id'])}/chat",
        data=json.dumps(
            {"message": message, "session_id": f"office-assistant-{username}"},
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with opener.open(request, timeout=185) as response:
        data = json.loads(response.read().decode("utf-8"))
    reply = str(data.get("reply", "") or "").strip()
    if not reply:
        raise ValueError("龙虾没有返回内容")
    return reply


def get_digital_human_kb(username: str) -> dict:
    """用户给数字人配置的知识库接入：{enabled, kb_ids}（kb_ids 空表示全部可见库）。"""
    entry = read_config().get("user_digital_human_kb", {}).get(username or "") or {}
    return {"enabled": bool(entry.get("enabled")), "kb_ids": list(entry.get("kb_ids") or [])}


def save_digital_human_kb(payload: dict, username: str) -> dict:
    payload = payload or {}
    config = read_config()
    mapping = config.setdefault("user_digital_human_kb", {})
    mapping[username or ""] = {
        "enabled": bool(payload.get("enabled")),
        "kb_ids": [str(x) for x in (payload.get("kb_ids") or []) if x][:20],
    }
    write_config(config)
    return {"ok": True, **get_digital_human_kb(username)}


def digital_human_chat(payload: dict, username: str = "") -> dict:
    payload = payload or {}
    message = str(payload.get("message", "") or "").strip()
    weekly_stage = str(payload.get("weekly_stage", "") or "").strip()
    if not message:
        raise ValueError("message is required")
    file_ids = payload.get("file_ids") or []
    if file_ids:
        try:
            attachment_context = writing_agent_attachment_context(file_ids, username)
            if attachment_context:
                message += attachment_context
        except Exception as exc:
            raise ValueError(f"附件读取失败：{exc}") from exc

    # 周报由专用 Agent 工作流生成结构化草稿。先在对话中完整展示供用户确认，
    # 只有明确点击确认后才交给前端周报编辑器，避免未经核对直接写入页面。
    if username and _weekly_intent(message, "weekly") and not weekly_stage:
        runtime_chat = globals().get("agent_chat")
        if runtime_chat:
            weekly_result = runtime_chat({"kind": "weekly", "messages": [{"role": "user", "content": message}]}, username)
            if weekly_result.get("ok"):
                result = {
                    "ok": True,
                    "text": str(weekly_result.get("reply") or "周报草稿已生成。"),
                    "action": None,
                    "source": "weekly-agent",
                }
                for call in weekly_result.get("skill_calls") or []:
                    if call.get("name") == "weekly.compose":
                        draft = (call.get("result") or {}).get("draft")
                        if draft:
                            result["ui_action"] = {"type": "weekly_draft_review", "draft": draft}
                            result["text"] += " 我已按周报三区格式整理出完整草稿，请先核对内容；确认无误后点击“确认写入周报编辑页”，再进行人工调整和邮件发送。"
                            break
                return result

    # 用户开启「连接知识库」时，先检索指定知识库，命中片段作为参考资料注入（龙虾/本地模型分支共用）。
    kb_pref = get_digital_human_kb(username) if username else {"enabled": False, "kb_ids": []}
    kb_note = ""
    kb_sources = []
    if kb_pref["enabled"]:
        try:
            hits = kb_search(
                {"query": message[:300], "top_k": 4, "kb_ids": kb_pref["kb_ids"]}, username
            ).get("results", [])
            if hits:
                refs = "\n\n".join(f"[{i + 1}]《{h['doc_name']}》：{str(h['text'])[:300]}" for i, h in enumerate(hits))
                kb_note = (
                    "以下是企业知识库中与用户问题相关的资料片段，回答时优先依据这些内容，"
                    "资料里没有的信息不要编造；与资料无关的闲聊可忽略资料：\n" + refs
                )
                kb_sources = [{"doc_name": h["doc_name"], "score": h["score"]} for h in hits]
        except Exception as exc:
            # 检索失败不阻塞对话，降级为普通闲聊。
            print(f"[digital-human] 知识库检索失败（{username}）：{exc}")

    # 绑定了龙虾就直通龙虾（与原悬浮助手一致），未绑定走本地犇犇人设模型。
    bound = get_assistant_lobster(username) if username else None
    if bound and bound.get("agent_id"):
        lobster_message = f"{kb_note}\n\n用户问题：{message}" if kb_note else message
        reply = _strip_markdown_for_speech(_digital_human_lobster_reply(username, lobster_message, bound))
        action = _guess_digital_human_action(message) or _guess_digital_human_action(reply)
        result = {
            "ok": True,
            "text": reply,
            "action": action,
            "source": "lobster",
            "lobster": {"agent_id": bound.get("agent_id"), "agent_name": bound.get("agent_name", "")},
        }
        if kb_sources:
            result["kb_sources"] = kb_sources
        return result

    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        raise ValueError("尚未配置智能助手接口，请先在管理页配置模型地址和密钥")

    messages = [{"role": "system", "content": DIGITAL_HUMAN_SYSTEM_PROMPT}]
    if weekly_stage:
        messages.append({
            "role": "system",
            "content": WEEKLY_STAGE_CONVERSATION_PROMPT.format(stage=weekly_stage[:40]),
        })
    if kb_note:
        messages.append({"role": "system", "content": kb_note})
    history = payload.get("history", [])
    if isinstance(history, list):
        # 周报草稿本身可能很长；数字人仅需要短上下文来承接修改请求，避免把整份
        # 草稿重复送入网关导致 400（上下文超限）。完整草稿始终留在前端审核卡中。
        for item in history[-4:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = str(item.get("content", "") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:220]})
    messages.append({"role": "user", "content": message[:800]})

    body = json.dumps(
        assistant_generation_payload(settings, {"model": settings["model"], "messages": messages, "temperature": 0.6}),
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        settings["url"] + "/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings["key"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise ValueError(f"对话模型返回 {exc.code}：{detail or '请求失败'}") from exc
    content = data["choices"][0]["message"]["content"]
    reply = _parse_digital_human_reply(content)
    if not reply["text"]:
        raise ValueError("模型没有返回内容")
    result = {"ok": True, "text": reply["text"], "action": reply["action"], "source": "model"}
    if kb_sources:
        result["kb_sources"] = kb_sources
    return result


# OpenAI 官方音色 + CosyVoice 常见音色，探测失败时的兜底候选。
DIGITAL_HUMAN_API_VOICE_FALLBACK = ["中文女", "中文男", "粤语女", "日语男", "英文女", "英文男", "韩语女", "alloy", "echo", "nova", "shimmer"]


def probe_tts_api_voices(payload: dict) -> dict:
    """探测 API 语音服务支持的音色列表。

    标准 OpenAI 协议没有"列音色"接口；CosyVoice/Xinference 在收到非法音色时
    会把可用音色清单放进错误信息里，借此反查。探测不到就返回常见候选。
    """
    payload = payload or {}
    settings = digital_human_tts_settings()
    for key in ("api_url", "api_key", "api_model"):
        override = str(payload.get(key, "") or "").strip()
        if override:
            settings[key] = override
    url, key = resolve_speech_api_target(settings["api_url"], settings["api_key"])
    if not url:
        raise ValueError("未配置语音 API 地址")
    body = {
        "model": settings["api_model"] or "tts-1",
        "input": "probe",
        "voice": "__voice_list_probe__",
        "response_format": "mp3",
    }
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=speech_api_headers(key),
        method="POST",
    )
    detail = ""
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
    except Exception as exc:
        raise ValueError(f"语音服务连接失败：{exc}") from exc
    match = re.search(r"available speakers[:：]?\s*\[([^\]]*)\]", detail, re.I)
    if match:
        voices = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
        if voices:
            return {"ok": True, "voices": voices, "source": "service"}
    return {"ok": True, "voices": DIGITAL_HUMAN_API_VOICE_FALLBACK, "source": "fallback"}


def digital_human_tts(payload: dict) -> dict:
    payload = payload or {}
    text = str(payload.get("text", "") or "").strip()
    if not text:
        raise ValueError("text is required")
    # 语音是逐句播放的，超长文本截断以控制合成耗时。
    text = text[:400]
    settings = digital_human_tts_settings()
    # 支持单次覆盖（设置页"试听"用），格式校验失败直接报错。
    provider = _valid_tts_provider(payload.get("provider", "")) or settings["provider"]
    settings["voice"] = _valid_tts_voice(payload.get("voice", "")) or settings["voice"]
    settings["rate"] = _valid_tts_rate(payload.get("rate", "")) or settings["rate"]
    settings["pitch"] = _valid_tts_pitch(payload.get("pitch", "")) or settings["pitch"]
    for key in ("api_url", "api_key", "api_model", "api_voice"):
        override = str(payload.get(key, "") or "").strip()
        if override:
            settings[key] = override

    if provider == "api":
        audio = _synthesize_via_api(text, settings)
    else:
        audio = _synthesize_via_edge(text, settings)
    if not audio:
        raise ValueError("语音合成失败：没有返回音频数据")
    encoded = base64.b64encode(audio).decode("ascii")
    return {"ok": True, "audio": "data:audio/mpeg;base64," + encoded}


def _synthesize_via_edge(text: str, settings: dict) -> bytes:
    try:
        import edge_tts
    except ImportError as exc:
        raise ValueError("服务器未安装 edge-tts，无法合成语音") from exc

    import asyncio

    async def _synthesize() -> bytes:
        communicate = edge_tts.Communicate(text, settings["voice"], rate=settings["rate"], pitch=settings["pitch"])
        chunks = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    try:
        return asyncio.run(asyncio.wait_for(_synthesize(), timeout=30))
    except Exception as exc:
        raise ValueError(f"语音合成失败：{exc}") from exc
