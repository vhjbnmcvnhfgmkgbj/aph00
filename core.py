"""منطق مشترک: ارتباط با API، تشخیص دستورها، شکل‌دهی متن فارسی. (بدون وابستگی به Kivy)"""
import json
import re
import ssl
import sys
import textwrap
import urllib.error
import urllib.request
import webbrowser

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa
    _CTX = ssl.create_default_context()

ON_ANDROID = "ANDROID_ARGUMENT" in __import__("os").environ or hasattr(sys, "getandroidapilevel")

# ---------------------------------------------------------------- فارسی
_FA = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def is_rtl(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if _FA.match(c)) / len(letters) > 0.3


def shape(text: str, width: int = 26) -> str:
    """حروف را وصل و ترتیب راست‌به‌چپ را درست می‌کند (Kivy خودش این کار را نمی‌کند)."""
    if not is_rtl(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError:
        return text
    out = []
    for line in text.split("\n"):
        for part in (textwrap.wrap(line, width) or [""]):
            out.append(get_display(arabic_reshaper.reshape(part)))
    return "\n".join(out)


def norm(s: str) -> str:
    s = s.strip().lower().replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"[\u200c\u200f\u200e]", " ", s)
    return re.sub(r"\s+", " ", s)


# ---------------------------------------------------------------- مغز (API)
SYSTEM_PROMPT = """You are J.A.R.V.I.S, a capable, witty and concise AI assistant running on the user's Android phone.
You can control the phone. When the user asks you to DO something (open an app, open a website, search the web, search/play something on YouTube), reply with ONLY a single-line JSON object and nothing else:
{"action": "<open_app|open_url|web_search|youtube_search>", "target": "<app name / url / search query>", "say": "<very short confirmation in the user's language>"}
For open_app use the app's common name (chrome, telegram, instagram, camera, settings, ...). If the request is ambiguous, ask one short question in plain text.
For everything else answer in plain text in the same language as the user: short, no markdown, no emojis, natural to be read aloud."""


class BrainError(Exception):
    pass


def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise BrainError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:250]}")
    except Exception as e:  # noqa
        raise BrainError(f"Network error: {e}")


class Brain:
    def __init__(self, get_settings):
        self.get = get_settings
        self.history = []

    def reset(self):
        self.history.clear()

    def ask(self, text):
        cfg = self.get()
        if not cfg.get("api_key"):
            raise BrainError("کلید API تنظیم نشده. از دکمه‌ی SET کلید را وارد کنید.")
        self.history.append(("user", text))
        try:
            if cfg.get("provider") == "anthropic":
                ans = self._anthropic(cfg)
            else:
                ans = self._gemini(cfg)
        except BrainError:
            self.history.pop()
            raise
        self.history.append(("assistant", ans))
        self.history = self.history[-20:]
        while self.history and self.history[0][0] != "user":
            self.history.pop(0)
        return ans

    def _gemini(self, cfg):
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{cfg['model']}:generateContent")
        body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user" if r == "user" else "model", "parts": [{"text": t}]}
                             for r, t in self.history]}
        data = _post(url, body, {"x-goog-api-key": cfg["api_key"]})
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip() or "(پاسخ خالی)"
        except (KeyError, IndexError):
            raise BrainError(f"Unexpected response: {str(data)[:250]}")

    def _anthropic(self, cfg):
        body = {"model": cfg["model"], "max_tokens": 1000, "system": SYSTEM_PROMPT,
                "messages": [{"role": r, "content": t} for r, t in self.history]}
        data = _post("https://api.anthropic.com/v1/messages", body,
                     {"x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01"})
        try:
            return "".join(b.get("text", "") for b in data["content"]).strip() or "(پاسخ خالی)"
        except (KeyError, TypeError):
            raise BrainError(f"Unexpected response: {str(data)[:250]}")


# ---------------------------------------------------------------- اکشن‌ها
ALLOWED = {"open_app", "open_url", "web_search", "youtube_search"}

APP_ALIASES = {  # اسم فارسی -> اسم‌هایی که در لیبل برنامه ممکن است باشد
    "کروم": ["chrome"], "گوگل کروم": ["chrome"], "تلگرام": ["telegram"], "واتساپ": ["whatsapp"],
    "واتس اپ": ["whatsapp"], "اینستاگرام": ["instagram"], "یوتیوب": ["youtube"],
    "دوربین": ["camera", "دوربین"], "تنظیمات": ["settings", "تنظیمات"],
    "ماشین حساب": ["calculator", "ماشین حساب"], "گالری": ["gallery", "photos", "گالری"],
    "عکس ها": ["photos", "gallery"], "مخاطبین": ["contacts", "مخاطبین"], "ساعت": ["clock", "ساعت"],
    "نقشه": ["maps", "نقشه"], "نقشه گوگل": ["maps"], "اسپاتیفای": ["spotify"], "دیسکورد": ["discord"],
    "جیمیل": ["gmail"], "پلی استور": ["play store"], "فروشگاه پلی": ["play store"],
    "شماره گیر": ["phone", "dialer"], "تماس": ["phone", "dialer"], "پیامک": ["messages"],
    "فایرفاکس": ["firefox"], "توییتر": ["twitter", "x"], "تیک تاک": ["tiktok"], "نتفلیکس": ["netflix"],
}
_STOP = {"برنامه", "برنامه‌ی", "اپ", "اپلیکیشن", "app", "application", "the", "لطفا", "جارویس"}


def clean_target(s: str) -> str:
    s = re.sub(r"[.!؟?،,\"']", " ", norm(s))
    return " ".join(w for w in s.split() if w not in _STOP)


def view_uri(uri: str):
    if ON_ANDROID:
        import android_utils
        android_utils.view_uri(uri)
    else:
        webbrowser.open(uri)


def open_url(url):
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if not re.match(r"^https?://\S+$", url, re.I):
        return False, "آدرس معتبر نیست."
    view_uri(url)
    return True, url


def web_search(q):
    from urllib.parse import quote_plus
    view_uri("https://www.google.com/search?q=" + quote_plus(q))
    return True, q


def youtube_search(q):
    from urllib.parse import quote_plus
    view_uri("https://www.youtube.com/results?search_query=" + quote_plus(q))
    return True, q


def open_app(name):
    n = clean_target(name)
    if not n:
        return False, "نام برنامه مشخص نیست."
    if not ON_ANDROID:
        return False, "باز کردن برنامه فقط روی اندروید کار می‌کند."
    import android_utils
    names = [n] + APP_ALIASES.get(n, [])
    apps = [(norm(label), pkg, label) for label, pkg in android_utils.list_launchable_apps()]
    for want in names:                                   # اول تطابق دقیق، بعد شروع، بعد شامل بودن
        for test in (lambda l: l == want, lambda l: l.startswith(want), lambda l: want in l):
            for nl, pkg, label in apps:
                if test(nl):
                    android_utils.launch_package(pkg)
                    return True, label
    return False, f"برنامه‌ای به اسم «{name}» روی گوشی پیدا نشد."


_FUNCS = {"open_app": open_app, "open_url": open_url, "web_search": web_search,
          "youtube_search": youtube_search}


def parse_action(raw):
    s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(d, dict) and d.get("action") in ALLOWED and str(d.get("target", "")).strip():
        return d
    return None


def execute(act):
    ok, msg = _FUNCS[act["action"]](str(act["target"]))
    return str(act.get("say") or f"انجام شد: {msg}") if ok else msg


_FA_OPEN = re.compile(r"^(?:لطفا\s+)?(?:جارویس\s+)?(.+?)\s*(?:رو|را)?\s*"
                      r"(?:باز\s*کن|باز\s*بکن|بازکن|اجرا\s*کن|اجرا\s*بکن|بالا\s*بیار)\s*[.!]?$")
_EN_OPEN = re.compile(r"^(?:please\s+)?(?:jarvis\s+)?(?:open|launch|start|run)\s+(.+?)\s*[.!]?$")
_FA_SEARCH = re.compile(r"^(?:لطفا\s+)?(?:جارویس\s+)?(.+?)\s*(?:رو|را)?\s*(?:سرچ|جستجو)\s*(?:کن|بکن)\s*$")
_EN_SEARCH = re.compile(r"^(?:search(?: for)?|google)\s+(.+)$")
_URL = re.compile(r"^[\w-]+(\.[\w-]+)*\.(com|org|net|ir|io|dev|app|co|ai|me)(/\S*)?$")


def try_local(text):
    t = norm(text)
    m = _FA_SEARCH.match(t) or _EN_SEARCH.match(t)
    if m:
        q = next(g for g in m.groups() if g)
        web_search(q)
        return f"در گوگل «{q}» را جستجو کردم."
    m = _FA_OPEN.match(t) or _EN_OPEN.match(t)
    if not m:
        return None
    raw = norm(m.group(1)).strip(" .!؟?")
    if _URL.match(raw):
        open_url(raw)
        return f"{raw} باز شد."
    tgt = clean_target(m.group(1))
    if not tgt:
        return None
    ok, label = open_app(tgt)
    return f"«{label}» باز شد." if ok else None


def process(text, brain):
    local = try_local(text)
    if local:
        return local
    raw = brain.ask(text)
    act = parse_action(raw)
    return execute(act) if act else raw
