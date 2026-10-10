"""پل به اندروید با pyjnius: باز کردن لینک/برنامه، صدا (TTS) و تشخیص گفتار."""
from android import activity as android_activity
from jnius import PythonJavaClass, autoclass, java_method

PythonActivity = autoclass("org.kivy.android.PythonActivity")
Intent = autoclass("android.content.Intent")
Uri = autoclass("android.net.Uri")
Locale = autoclass("java.util.Locale")
TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
RecognizerIntent = autoclass("android.speech.RecognizerIntent")


def _activity():
    return PythonActivity.mActivity


def view_uri(uri: str):
    i = Intent(Intent.ACTION_VIEW, Uri.parse(uri))
    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    _activity().startActivity(i)


def list_launchable_apps():
    act = _activity()
    pm = act.getPackageManager()
    i = Intent(Intent.ACTION_MAIN)
    i.addCategory(Intent.CATEGORY_LAUNCHER)
    lst = pm.queryIntentActivities(i, 0)
    out = []
    for k in range(lst.size()):
        ri = lst.get(k)
        out.append((str(ri.loadLabel(pm)), str(ri.activityInfo.packageName)))
    return out


def launch_package(pkg: str):
    act = _activity()
    intent = act.getPackageManager().getLaunchIntentForPackage(pkg)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(intent)


class _InitListener(PythonJavaClass):
    __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
    __javacontext__ = "app"

    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    @java_method("(I)V")
    def onInit(self, status):
        self.cb(status)


class AndroidTTS:
    """خروجی صوتی با موتور TTS خود گوشی. فارسی فقط وقتی کار می‌کند که موتور گوشی فارسی داشته باشد."""

    def __init__(self, warn=lambda m: None):
        self.warn = warn
        self.ready = False
        self._queued = None
        self._warned = False
        self._listener = _InitListener(self._on_init)
        self.tts = TextToSpeech(_activity(), self._listener)

    def _on_init(self, status):
        self.ready = status == 0
        if self.ready and self._queued:
            text, fa = self._queued
            self._queued = None
            self.say(text, fa)

    def idle(self):
        try:
            return not self.tts.isSpeaking()
        except Exception:  # noqa
            return True

    def say(self, text, persian=False):
        if not self.ready:
            self._queued = (text, persian)
            return
        if persian:
            res = self.tts.setLanguage(Locale("fa", "IR"))
            if res < 0:
                res = self.tts.setLanguage(Locale("fa"))
            if res < 0 and not self._warned:
                self._warned = True
                self.warn("موتور صدای گوشی فارسی ندارد؛ در تنظیمات گوشی (Text-to-speech) یک موتور با زبان فارسی نصب کنید.")
        else:
            self.tts.setLanguage(Locale.ENGLISH)
        self.tts.speak(text, TextToSpeech.QUEUE_FLUSH, None, "jarvis")


_REQ = 7721


class VoiceInput:
    """ورودی صوتی با پنجره‌ی استاندارد تشخیص گفتار گوگل (بدون نیاز به مجوز میکروفون)."""

    def __init__(self, on_text, on_error):
        self.on_text, self.on_error = on_text, on_error
        android_activity.bind(on_activity_result=self._result)

    def start(self, lang="fa-IR"):
        try:
            i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang)
            i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak...")
            _activity().startActivityForResult(i, _REQ)
        except Exception as e:  # noqa
            self.on_error(f"تشخیص گفتار در این گوشی در دسترس نیست: {e}")

    def _result(self, request, result, intent):
        if request != _REQ:
            return
        if result == -1 and intent is not None:
            lst = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if lst is not None and lst.size() > 0:
                self.on_text(str(lst.get(0)))
