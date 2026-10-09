import os
import json
import re
import time
from datetime import datetime

from knowledge import KnowledgeBase
from research_v3 import WebResearch

try:
    from input_interpreter import interpret
    from function_router import route_function
    from sage_model_api import SAGEAI, SAGEResponse
    from request_router import execute
    from analysis import analyze
    print("SAGE: deterministic router loaded.")
except Exception as e:
    raise RuntimeError(f"SAGE failed to load request_router.py: {e}") from e

# Wired into execute() below so analysis_engine (statistics/percentage
# requests classified by input_interpreter.py) actually runs instead of
# silently falling through to the AI path. conversion_engine is left
# unwired — no implementation for it exists yet. remember/forget/
# log_chat/access_chat/shutdown/clear_chat are deliberately NOT wired
# here: those are already handled for real, earlier, by
# handle_natural_intent() below, before a message ever reaches
# ask_sage_stream(). Wiring them here too would risk double-handling.
def _run_analysis(text: str) -> str:
    result = analyze(text)
    if result is None:
        return "I couldn't find a calculation to perform in that."
    _, display = result
    return display


ROUTER_TOOLS = {
    "analysis_engine": _run_analysis,
}

# ============================================================
# SAGE — Smart Autonomous Guidance Entity
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PERSONALITY_FILE = os.path.join(BASE_DIR, "personality.txt")
IDENTITY_FILE = os.path.join(BASE_DIR, "identity.json")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")

OLLAMA_URL = "http://localhost:11434/api/chat"


MAX_CONVERSATION_MESSAGES = 20
LOCAL_KNOWLEDGE_TOP_K = 5
LOCAL_KNOWLEDGE_THRESHOLD = 0.55
WEB_MAX_RESULTS = 6


# ============================================================
# INPUT ROUTING
# ============================================================

CASUAL_RESPONSES = {
    "hi": "Hello, Lunar.",
    "hello": "Hello, Lunar.",
    "hey": "Hey, Lunar.",
    "hiya": "Hello.",
    "yo": "Hey.",
    "sup": "Operational.",
    "thanks": "You're welcome.",
    "thank you": "You're welcome.",
    "thx": "You're welcome.",
    "ok": "Understood.",
    "okay": "Understood.",
    "alright": "Understood.",
    "sure": "Understood.",
    "cool": "Indeed.",
    "bye": "Bye, Lunar.",
    "goodbye": "Goodbye.",
    "good morning": "Good morning, Lunar.",
    "good afternoon": "Good afternoon, Lunar.",
    "good evening": "Good evening, Lunar.",
    "good night": "Good night, Lunar."
}

RESEARCH_TERMS = (
    "research", "look up", "search online", "search the web",
    "find out", "investigate", "verify", "fact check",
    "check online", "latest", "recent", "current", "today",
    "news", "source", "sources"
)

URL_RE = re.compile(r'https?://[^\s<>"\']+')

def normalize_input(text):
    return re.sub(r"\s+", " ", text.strip().lower())

def extract_urls(text):
    return URL_RE.findall(text)

def is_casual_input(text):
    return normalize_input(text) in CASUAL_RESPONSES

def should_research(text):
    """Decide whether external research is appropriate.

    Casual conversation is always excluded. Explicit research requests and
    URLs are research targets. Normal questions are allowed to reach the
    local-first pipeline; the local retrieval layer decides whether web
    research is needed.
    """
    normalized = normalize_input(text)

    if normalized in CASUAL_RESPONSES:
        return False

    if extract_urls(text):
        return True

    if any(term in normalized for term in RESEARCH_TERMS):
        return True

    # Normal information-seeking questions may use the web only after
    # local knowledge has been checked. Casual inputs were already excluded.
    question_starts = (
        "what ", "why ", "how ", "when ", "where ", "who ",
        "which ", "can ", "could ", "does ", "do ", "is ",
        "are ", "will ", "would ", "should ", "isn't ", "aren't "
    )
    if normalized.endswith("?") or normalized.startswith(question_starts):
        return True

    return False


# ============================================================
# DEFAULT PERSONALITY SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
    "humor": 75,
    "sarcasm": 65,
    "honesty": 100,
    "friendliness": 60,
    "verbosity": 35,
    "autonomy": 40
}


# ============================================================
# FILE FUNCTIONS
# ============================================================

def load_text(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================
# LOAD SAGE DATA
# ============================================================

def load_personality():
    return load_text(PERSONALITY_FILE).strip()

identity = load_json(
    IDENTITY_FILE,
    {
        "name": "SAGE",
        "full_name": "Smart Autonomous Guidance Entity",
        "creator": "Lunar",
        "core_model": "Gemma 4B",
        "purpose": "Local AI assistant and future robotics controller"
    }
)

memory = load_json(
    MEMORY_FILE,
    {
        "self": identity,
        "facts": [],
        "preferences": [],
        "experiences": []
    }
)

settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())


# Make sure new settings are added automatically
for key, value in DEFAULT_SETTINGS.items():
    if key not in settings:
        settings[key] = value

save_json(SETTINGS_FILE, settings)


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation = []

# External information systems.
# KnowledgeBase is local/read-only retrieval.
# WebResearch is strictly read-only web search.
knowledge_base = KnowledgeBase(KNOWLEDGE_DIR)
web_research = WebResearch()

# Native MLX SAGE model runtime.
# Loads only the selected Qwen3 + SAGE adapter into memory.
sage_ai = SAGEAI()
last_response_metadata = {}


# ============================================================
# PERSONALITY PROMPT
# ============================================================


def build_system_prompt():
    """Compatibility helper for older callers.

    The permanent SAGE personality is learned into the fine-tuned model.
    Runtime-only state is assembled by sage_runtime_prompt.py through SAGEAI.
    """
    from sage_runtime_prompt import build_runtime_system_prompt
    return build_runtime_system_prompt(
        identity=identity,
        memory=memory,
        settings=settings,
        research_context="",
    )


# ============================================================
# KNOWLEDGE + READ-ONLY WEB RESEARCH
# ============================================================

def _format_local_context(results):

    blocks = []

    for r in results:

        location = []

        if r.get("page") is not None:
            location.append(
                f"page={r['page']}"
            )

        if r.get("chapter"):
            location.append(
                f"chapter={r['chapter']}"
            )

        if r.get("section"):
            location.append(
                f"section={r['section']}"
            )

        if r.get("subsection"):
            location.append(
                f"subsection={r['subsection']}"
            )

        location_text = " | ".join(location)

        if location_text:
            source_header = (
                f"[LOCAL SOURCE: {r['source']} | "
                f"{location_text} | "
                f"relevance={r['score']}]"
            )
        else:
            source_header = (
                f"[LOCAL SOURCE: {r['source']} | "
                f"relevance={r['score']}]"
            )

        blocks.append(
            f"{source_header}\n"
            f"{r['text']}"
        )

    return "\n\n".join(blocks)

def _format_web_context(results):
    if not results:
        return ""
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[WEB SOURCE {i}]\nTITLE: {r.get('title','')}\nURL: {r.get('url','')}\nCONTENT: {r.get('content','')}"
        )
    return "\n\n".join(blocks)


def get_local_memory_context(query):
    """Search explicit persistent memory without changing it."""
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    matches = []

    for category in ["facts", "preferences", "experiences"]:
        for item in memory.get(category, []):
            info = item.get("information", "") if isinstance(item, dict) else str(item)
            words = set(re.findall(r"[a-z0-9]+", info.lower()))
            overlap = len(query_words & words)
            if overlap:
                matches.append({
                    "source": f"memory.json:{category}",
                    "score": round(min(0.99, overlap / max(1, len(query_words))), 4),
                    "text": info
                })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:LOCAL_KNOWLEDGE_TOP_K]

def retrieve_before_web(query):
    try:
        local = knowledge_base.search(
            query,
            top_k=LOCAL_KNOWLEDGE_TOP_K,
            threshold=LOCAL_KNOWLEDGE_THRESHOLD
        )
    except Exception:
        local = []

    memory_results = get_local_memory_context(query)

    combined = local + memory_results
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    normalized = normalize_input(query)

    # Explicit requests for web research only.
    urls = extract_urls(query)

    explicit_research = (
        bool(urls)
        or any(term in normalized for term in (
            "research",
            "look up",
            "search online",
            "search the web",
            "investigate",
            "verify",
            "fact check",
            "check online",
            "latest",
            "recent",
            "current",
            "today",
            "news",
            "sources"
        ))
    )

    # Local knowledge always gets first priority.
    if combined and not explicit_research:
        return {
            "mode": "local",
            "local_results": combined,
            "web_results": [],
            "context": _format_local_context(combined)
        }

    # No local knowledge and no explicit request for web research.
    if not explicit_research:
        return {
            "mode": "none",
            "local_results": combined,
            "web_results": [],
            "context": ""
        }

    # Explicit web research.
    if urls:
        web = web_research.research_url(urls[0])
    else:
        web = web_research.research(query)

    if web.get("ok"):
        return {
            "mode": "web",
            "local_results": combined,
            "web_results": web.get("results", []),
            "context": _format_web_context(web.get("results", [])),
            "evidence_score": web.get("evidence_score", 0),
            "evidence_level": web.get("evidence_level", "VERY LOW"),
            "transcript": web.get("transcript", ""),
            "metadata": web.get("metadata", {})
        }

    # If web research fails but local information exists,
    # fall back to local knowledge.
    if combined:
        return {
            "mode": "local",
            "local_results": combined,
            "web_results": [],
            "context": _format_local_context(combined),
            "error": web.get("error")
        }

    return {
        "mode": "none",
        "local_results": [],
        "web_results": [],
        "context": "",
        "error": web.get("error", "No information available.")
    }



def research_footer(retrieval):
    if retrieval.get("mode") != "web":
        return ""
    return (
        "\n────────────────────────────────\n"
        f"Evidence Score — {retrieval.get('evidence_score', 0)}%\n"
        f"Level — {retrieval.get('evidence_level', 'VERY LOW')}\n"
        "────────────────────────────────"
    )
def build_research_prompt(retrieval):
    if retrieval["mode"] == "local":
        return f"""
LOCAL KNOWLEDGE

The following information was retrieved from SAGE's
local knowledge database.

Use it to answer Lunar's question.

Answer directly and naturally.

Do not mention that you are consulting a source.

Source information:

{retrieval["context"]}

END LOCAL KNOWLEDGE
"""

    if retrieval["mode"] == "web":
        return f"""
WEB RESEARCH

The following information was retrieved by SAGE's
read-only research system.

Use it as evidence.

Answer directly and naturally.
Do not invent information.
Do not claim you personally browsed the internet.
If sources conflict, state the conflict.

WEB EVIDENCE:

{retrieval["context"]}

END WEB EVIDENCE
"""

    return """
No sufficiently relevant local information was found.

Answer from your existing knowledge if appropriate.
If uncertain, say so.
"""

def _append_conversation(user_message, reply):
    """Append a completed conversational turn and enforce the history cap."""
    conversation.append({
        "role": "user",
        "content": user_message,
    })
    conversation.append({
        "role": "assistant",
        "content": reply,
    })

    if len(conversation) > MAX_CONVERSATION_MESSAGES:
        del conversation[:-MAX_CONVERSATION_MESSAGES]


def _set_deterministic_metadata(*, elapsed_s, request, function, text):
    """Expose deterministic-path telemetry using the same shape as AI telemetry."""
    global last_response_metadata
    last_response_metadata = {
        "model": "NONE",
        "route": getattr(request, "kind", "deterministic"),
        "thinking": False,
        "elapsed_s": elapsed_s,
        "prompt_tokens": 0,
        "generation_tokens": 0,
        "generation_tps": 0.0,
        "prompt_tps": 0.0,
        "peak_memory_gb": 0.0,
        "hidden_thinking_chars": 0,
        "text": text,
        "handler": getattr(request, "handler", ""),
        "function": str(function),
    }


def _set_ai_metadata(response: SAGEResponse, *, route_name: str):
    global last_response_metadata
    last_response_metadata = {
        "model": response.model,
        "route": route_name,
        "thinking": response.thinking,
        "elapsed_s": response.elapsed_s,
        "prompt_tokens": response.prompt_tokens,
        "generation_tokens": response.generation_tokens,
        "generation_tps": response.generation_tps,
        "prompt_tps": response.prompt_tps,
        "peak_memory_gb": response.peak_memory_gb,
        "hidden_thinking_chars": response.hidden_thinking_chars,
        "text": response.text,
    }


def get_last_response_metadata():
    """Return a copy of the most recent response telemetry."""
    return dict(last_response_metadata)


def ask_sage_stream(user_message):
    """Stream SAGE events while preserving the legacy ask_sage() text API.

    Yielded events are suitable for the future SwiftUI backend:
      thinking_started
      thinking_finished
      token
      complete

    Raw Qwen chain-of-thought is never yielded.
    """
    global last_response_metadata

    t0 = time.perf_counter()

    request = interpret(user_message)
    t1 = time.perf_counter()

    function = route_function(request)
    t2 = time.perf_counter()

    result = execute(request, ROUTER_TOOLS)
    t3 = time.perf_counter()

    # ------------------------------------------------------------
    # Deterministic path — no model invocation.
    # ------------------------------------------------------------
    if result is not None:
        if not result.ok:
            reply = result.error or "Request failed."
            _append_conversation(user_message, reply)
            _set_deterministic_metadata(
                elapsed_s=time.perf_counter() - t0,
                request=request,
                function=function,
                text=reply,
            )
            return

        reply = result.text
        _append_conversation(user_message, reply)
        elapsed = time.perf_counter() - t0
        _set_deterministic_metadata(
            elapsed_s=elapsed,
            request=request,
            function=function,
            text=reply,
        )

        print(
            f"[TIMING] interpret={t1-t0:.3f}s "
            f"route={t2-t1:.3f}s "
            f"execute={t3-t2:.3f}s "
            f"deterministic_total={elapsed:.3f}s"
        )

        # Deterministic results are already complete.
        from sage_model_runtime import GenerationEvent
        yield GenerationEvent(
            type="complete",
            text=reply,
            model="NONE",
            thinking=False,
            elapsed_s=elapsed,
        )
        return

    # ------------------------------------------------------------
    # Knowledge / web retrieval.
    # ------------------------------------------------------------
    _append_conversation(user_message, None)
    # Remove only the temporary assistant placeholder; keep the user turn.
    conversation.pop()
    t4 = time.perf_counter()

    retrieval = retrieve_before_web(user_message)
    t5 = time.perf_counter()

    research_context = build_research_prompt(retrieval)
    route_name = retrieval.get("mode", "model")

    # Respect the deterministic requester's context policy.
    context_limit = getattr(request, "context_messages", 4)
    model_messages = conversation[-context_limit:] if context_limit > 0 else []
    # Remove the placeholder assistant message we added above.
    if model_messages and model_messages[-1]["role"] == "assistant" and model_messages[-1]["content"] == "":
        model_messages = model_messages[:-1]

    t6 = time.perf_counter()

    # ------------------------------------------------------------
    # Native MLX SAGE inference.
    # ------------------------------------------------------------
    try:
        generator = sage_ai.stream(
            request,
            model_messages,
            identity=identity,
            memory=memory,
            settings=settings,
            research_context=research_context,
            route_name=route_name,
        )

        while True:
            try:
                event = next(generator)
            except StopIteration as stop:
                response = stop.value
                break
            yield event

        elapsed_total = time.perf_counter() - t0
        if response is None:
            raise RuntimeError("SAGE model runtime returned no response.")

        conversation.append({
            "role": "assistant",
            "content": response.text,
        })

        if len(conversation) > MAX_CONVERSATION_MESSAGES:
            del conversation[:-MAX_CONVERSATION_MESSAGES]

        _set_ai_metadata(response, route_name=route_name)

        print(
            f"[TIMING] interpret={t1-t0:.3f}s "
            f"route={t2-t1:.3f}s "
            f"execute={t3-t2:.3f}s "
            f"retrieval={t5-t4:.3f}s "
            f"prompt={t6-t5:.3f}s "
            f"model_total={elapsed_total:.3f}s "
            f"model={response.model} "
            f"tokens={response.generation_tokens} "
            f"tok_s={response.generation_tps:.2f}"
        )
        return

    except Exception as exc:
        reply = f"SAGE model runtime error: {type(exc).__name__}: {exc}"
        conversation.append({
            "role": "assistant",
            "content": reply,
        })
        last_response_metadata = {
            "model": "ERROR",
            "route": route_name,
            "thinking": False,
            "elapsed_s": time.perf_counter() - t0,
            "prompt_tokens": 0,
            "generation_tokens": 0,
            "generation_tps": 0.0,
            "prompt_tps": 0.0,
            "peak_memory_gb": 0.0,
            "hidden_thinking_chars": 0,
            "text": reply,
            "error": str(exc),
        }

        from sage_model_runtime import GenerationEvent
        yield GenerationEvent(
            type="complete",
            text=reply,
            model="ERROR",
            thinking=False,
            elapsed_s=last_response_metadata["elapsed_s"],
        )


def ask_sage(user_message):
    """Legacy text-returning interface.

    The actual model execution now happens through the native MLX SAGE runtime.
    This function consumes its stream and prints generated tokens for the CLI.
    The SwiftUI app should use ask_sage_stream() instead.
    """
    output = []
    announced_thinking = False

    for event in ask_sage_stream(user_message):
        if event.type == "thinking_started":
            announced_thinking = True
            print("\n[SAGE thinking]", end=" ", flush=True)
        elif event.type == "thinking_finished":
            if announced_thinking:
                print(" done.")
        elif event.type == "token":
            print(event.text, end="", flush=True)
            output.append(event.text)
        elif event.type == "complete":
            if not output:
                print(event.text, end="", flush=True)
                output.append(event.text)

    print()
    return "".join(output).strip()


def remember(category, information):

    valid_categories = [
        "facts",
        "preferences",
        "experiences"
    ]

    if category not in valid_categories:
        return (
            "Invalid memory category. Use: "
            "facts, preferences, or experiences."
        )

    memory.setdefault(category, [])

    memory[category].append({
        "information": information,
        "date": datetime.now().strftime("%Y-%m-%d")
    })

    save_json(MEMORY_FILE, memory)

    return f"Memory stored under '{category}'."


# ============================================================
# SETTINGS
# ============================================================

def set_personality(setting, value):

    setting = setting.lower().strip()

    aliases = {
        "humour": "humor",
        "sarcasm": "sarcasm",
        "honesty": "honesty",
        "friendly": "friendliness",
        "friendliness": "friendliness",
        "verbose": "verbosity",
        "verbosity": "verbosity",
        "autonomy": "autonomy"
    }

    setting = aliases.get(setting, setting)

    if setting not in DEFAULT_SETTINGS:
        return (
            "Unknown personality setting.\n\n"
            "Available settings:\n"
            "humor\n"
            "sarcasm\n"
            "honesty\n"
            "friendliness\n"
            "verbosity\n"
            "autonomy"
        )

    try:
        value = int(value)
    except ValueError:
        return "The value must be a number between 0 and 100."

    if value < 0 or value > 100:
        return "Personality settings must be between 0 and 100."

    settings[setting] = value

    save_json(SETTINGS_FILE, settings)

    return f"{setting.capitalize()} set to {value}%."


def show_settings():

    return f"""
SAGE PERSONALITY SETTINGS

Humor:        {settings["humor"]}%
Sarcasm:      {settings["sarcasm"]}%
Honesty:      {settings["honesty"]}%
Friendliness: {settings["friendliness"]}%
Verbosity:    {settings["verbosity"]}%
Autonomy:     {settings["autonomy"]}%
"""


# ============================================================
# NATURAL-LANGUAGE INTENTS / COMMANDS
# ============================================================

def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"[!?.,]+", " ", text)
    return re.sub(r"\s+", " ", text)

def get_setting_name(text):
    aliases = {
        "humor":"humor", "humour":"humor", "funny":"humor", "fun":"humor",
        "jokes":"humor", "sarcasm":"sarcasm", "sarcastic":"sarcasm",
        "honesty":"honesty", "honest":"honesty", "friendly":"friendliness",
        "friendliness":"friendliness", "warmth":"friendliness",
        "verbosity":"verbosity", "verbose":"verbosity", "length":"verbosity",
        "autonomy":"autonomy", "independence":"autonomy"
    }
    for word, setting in aliases.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return setting
    return None

def parse_personality_change(text):
    setting = get_setting_name(text)
    if not setting:
        return None
    explicit = re.search(r"\b(?:to|at|=)\s*(\d{1,3})\s*%?\b|\b(\d{1,3})\s*%\b", text)
    if explicit:
        return setting, int(explicit.group(1) or explicit.group(2))
    if any(x in text for x in ["more", "increase", "raise", "higher", "turn up", "boost"]):
        return setting, min(100, settings[setting] + 10)
    if any(x in text for x in ["less", "decrease", "lower", "turn down", "reduce"]):
        return setting, max(0, settings[setting] - 10)
    return None

def handle_natural_intent(user_input):
    text = normalize_text(user_input)
    if not text:
        return True, "", False

    exit_phrases = ["shut down", "shutdown", "go offline", "power down", "terminate"]
    if any(x in text for x in exit_phrases):
        return True, "Shutting down.", True

    clear_phrases = ["clear conversation", "clear the conversation", "clear our conversation",
                     "clear chat", "clear the chat", "forget this conversation",
                     "forget this chat", "reset conversation", "reset the conversation"]
    if any(x in text for x in clear_phrases):
        conversation.clear()
        return True, "Cleared.", False

    identity_phrases = ["who are you", "what are you", "what is your name", "whats your name",
                        "tell me about yourself", "identify yourself"]
    if any(x in text for x in identity_phrases):
        return True, "I'm SAGE.", False

    settings_phrases = ["show personality settings", "show your personality settings", "show settings",
                        "show your settings", "what are your settings", "what are your personality settings"]
    if any(x in text for x in settings_phrases):
        return True, show_settings(), False

    setting = get_setting_name(text)
    if setting and any(x in text for x in ["how much", "how funny", "how sarcastic", "how honest",
                                           "how friendly", "how verbose", "how autonomous",
                                           "what's your", "whats your", "what is your", "show your", "check your"]):
        return True, f"{setting.capitalize()}: {settings[setting]}%.", False

    change = parse_personality_change(text)
    if change:
        setting, value = change
        if not 0 <= value <= 100:
            return True, "Use a value from 0 to 100.", False
        settings[setting] = value
        save_json(SETTINGS_FILE, settings)
        return True, f"{setting.capitalize()}: {value}%.", False

    memory_patterns = [
        r"^(?:remember|save|store|note|keep in mind)\s+(?:that\s+)?(.+)$",
        r"^(?:don't forget|do not forget)\s+(?:that\s+)?(.+)$",
        r"^(?:make a note|make a note of)\s+(?:that\s+)?(.+)$"
    ]
    for pattern in memory_patterns:
        m = re.match(pattern, text)
        if m:
            info = m.group(1).strip()
            category = "facts" if re.search(r"\b(i am|i'm|my name|i live|i have)\b", info) else "preferences"
            return True, remember(category, info), False

    forget_patterns = [r"^(?:forget|delete|remove)\s+(?:that|this|it)$",
                       r"^(?:forget|delete|remove)\s+(?:that\s+)?(.+)$"]
    for pattern in forget_patterns:
        m = re.match(pattern, text)
        if m:
            target = m.group(1).strip()
            if target in {"that", "this", "it"}:
                return True, "I need to know what to forget.", False
            removed = False
            for category in ["facts", "preferences", "experiences"]:
                old = memory.get(category, [])
                new = [item for item in old if target not in ((item.get("information", "") if isinstance(item, dict) else str(item)).lower())]
                removed |= len(new) != len(old)
                memory[category] = new
            if removed:
                save_json(MEMORY_FILE, memory)
                return True, "Forgotten.", False
            return True, "I don't have that in memory.", False

    # Local knowledge maintenance. These commands affect only SAGE's
    # local index; they never modify source documents.
    if text in ["rebuild knowledge", "rebuild your knowledge", "update local knowledge index"]:
        try:
            count = knowledge_base.rebuild()
            return True, f"Knowledge index rebuilt: {count} chunks.", False
        except Exception as e:
            return True, f"Knowledge index rebuild failed: {e}", False

    if text in ["knowledge status", "check knowledge", "show knowledge status"]:
        status = knowledge_base.status()
        return True, (
            f"Knowledge: {status['documents']} documents, "
            f"{status['chunks']} chunks. Embeddings: {status['embedding_model']}."
        ), False

    # Keep farewells short without shutting the program down.
    if text in ["bye", "goodbye", "good bye", "see you", "see ya", "later", "good night", "goodnight"]:
        return True, "Bye.", False

    return False, None, False

def handle_command(command):
    parts = command.strip().split()
    if not parts:
        return True, "", False
    cmd = parts[0].lower()

    if cmd == "/help":
        print("""
SAGE

Natural language:
  remember / forget / change personality / ask settings / identity / clear / shut down

Developer:
  /help  /settings  /set <setting> <value>  /identity  /memory
  /remember <category> <text>  /clear  /quit
""")
        return True, "", False
    if cmd == "/settings":
        return True, show_settings(), False
    if cmd == "/set":
        if len(parts) != 3:
            return True, "Usage: /set <setting> <value>", False
        return True, set_personality(parts[1], parts[2]), False
    if cmd == "/identity":
        return True, json.dumps(identity, indent=2), False
    if cmd == "/memory":
        return True, json.dumps(memory, indent=2, ensure_ascii=False), False
    if cmd == "/remember":
        if len(parts) < 3:
            return True, "Usage: /remember <category> <information>", False
        return True, remember(parts[1], " ".join(parts[2:])), False
    if cmd == "/clear":
        conversation.clear()
        return True, "Cleared.", False
    if cmd in ["/quit", "/exit"]:
        return True, "Shutting down.", True
    return handle_natural_intent(command)

# ============================================================
# MAIN
# ============================================================

def main():

    print("""
============================================================
 SAGE
 Smart Autonomous Guidance Entity
============================================================

Models: SAGE-Qwen 1.7B / 4B / 8B
Runtime: Native MLX

Type /help for commands.
============================================================
""")

    print(show_settings())

    while True:

        try:

            user_input = input("\nLunar > ").strip()

            if not user_input:
                continue

            is_command, result, should_exit = handle_command(user_input)

            if is_command:
                if result:
                    print("\nSAGE > ", end="", flush=True)
                    print(result)
                if should_exit:
                    break
                continue

            print("\nSAGE > ", end="", flush=True)

            ask_sage(user_input)

        except KeyboardInterrupt:

            print("\n\nSAGE shutting down.")

            break

        except EOFError:

            print("\n\nSAGE shutting down.")

            break


if __name__ == "__main__":
    main()
    
    
def run_reasoner(messages, model_decision):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model_decision.model,
            "messages": messages,
            "stream": False,
            "think": True,
            "options": {
                "temperature": model_decision.temperature,
                "top_p": model_decision.top_p,
                "top_k": model_decision.top_k,
                "num_predict": model_decision.think_max_tokens,
            },
        },
        timeout=model_decision.think_max_seconds + 60,
    )

    response.raise_for_status()

    data = response.json()
    message = data["message"]

    return {
        "thinking": message.get("thinking", ""),
        "content": message.get("content", ""),
    }
    
def run_writer(user_message, reasoning, retrieval):
    writer_messages = [
        {
            "role": "system",
            "content": (
                build_system_prompt()
                + "\n\n"
                "You are the final SAGE response writer.\n"
                "Do not perform the problem-solving again.\n"
                "Use the supplied reasoning/result as internal working material.\n"
                "Do not expose hidden reasoning.\n"
                "Write only the final answer to the user.\n"
                "Be concise, technically precise, and natural.\n"
            )
        },
        {
            "role": "user",
            "content": (
                f"USER QUESTION:\n{user_message}\n\n"
                f"REASONING RESULT:\n{reasoning}\n"
            )
        }
    ]

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "SAGE-1.7B",
            "messages": writer_messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "num_predict": 768,
            },
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["message"]["content"].strip()
