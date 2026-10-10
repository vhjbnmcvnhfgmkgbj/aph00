"""J.A.R.V.I.S برای اندروید (Kivy). ساخت APK: README.md را ببینید."""
import json
import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

import core

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "DejaVuSans.ttf")

BG = (0.016, 0.024, 0.04, 1)
PANEL = (0.04, 0.06, 0.09, 1)
CYAN = (0, 0.94, 1, 1)
GREEN = (0, 1, 0.61, 1)
AMBER = (1, 0.69, 0, 1)
RED = (1, 0.23, 0.36, 1)
DIM = (0.05, 0.42, 0.45, 1)
TEXT = (0.79, 0.97, 1, 1)

Window.clearcolor = BG
Window.softinput_mode = "resize"

DEFAULTS = {"api_key": "", "provider": "gemini", "model": "gemini-2.5-flash", "voice": True}


class Bubble(BoxLayout):
    def __init__(self, text, color, align, border, **kw):
        super().__init__(size_hint_y=None, padding=(dp(10), dp(8)), **kw)
        self.border = border
        self.lbl = Label(text=text, color=color, font_name=FONT, font_size=sp(15), halign=align,
                         valign="top", size_hint_y=None)
        self.lbl.bind(width=self._wrap, texture_size=self._fit)
        self.add_widget(self.lbl)
        with self.canvas.before:
            Color(*PANEL)
            self.bg = RoundedRectangle(radius=[dp(10)])
            Color(*border)
            self.line = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=self._draw, size=self._draw)

    def _wrap(self, inst, w):
        inst.text_size = (w, None)

    def _fit(self, inst, size):
        inst.height = size[1]
        self.height = size[1] + dp(16)

    def _draw(self, *_):
        self.bg.pos, self.bg.size = self.pos, self.size
        self.line.pos, self.line.size = (self.x, self.y), (dp(3), self.height)


class JarvisApp(App):
    title = "Jarvis"

    # ------------------------------------------------------------ settings
    def _settings_path(self):
        return os.path.join(self.user_data_dir, "settings.json")

    def load_settings(self):
        self.cfg = dict(DEFAULTS)
        try:
            with open(self._settings_path(), encoding="utf-8") as f:
                self.cfg.update(json.load(f))
        except Exception:  # noqa
            pass

    def save_settings(self):
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump(self.cfg, f)
        except Exception:  # noqa
            pass

    # ------------------------------------------------------------ build
    def build(self):
        self.load_settings()
        self.brain = core.Brain(lambda: self.cfg)
        self.tts = None
        self.voice_in = None

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        head = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        head.add_widget(Label(text="J.A.R.V.I.S", color=CYAN, font_name=FONT, font_size=sp(20),
                              bold=True, halign="left", size_hint_x=0.5, text_size=(dp(160), None)))
        self.status = Label(text="ONLINE", color=GREEN, font_name=FONT, font_size=sp(12), size_hint_x=0.3)
        head.add_widget(self.status)
        head.add_widget(self._btn("SET", self.open_settings, 0.2))
        root.add_widget(head)

        self.scroll = ScrollView(do_scroll_x=False)
        self.chat = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=(0, dp(4)))
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)
        root.add_widget(self.scroll)

        self.preview = Label(text="", color=DIM, font_name=FONT, font_size=sp(13), size_hint_y=None,
                             height=0, halign="right", valign="middle")
        self.preview.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        root.add_widget(self.preview)

        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.input = TextInput(multiline=False, font_name=FONT, font_size=sp(16),
                               background_color=PANEL, foreground_color=GREEN, cursor_color=CYAN,
                               hint_text="...", padding=(dp(10), dp(12)))
        self.input.bind(on_text_validate=lambda *_: self.send(), text=self._on_typing)
        bar.add_widget(self.input)
        bar.add_widget(self._btn("MIC", self.on_mic, None, width=dp(58)))
        bar.add_widget(self._btn("SEND", lambda *_: self.send(), None, width=dp(66)))
        root.add_widget(bar)

        Clock.schedule_once(self._after_build, 0.3)
        return root

    def _btn(self, text, cb, hint, width=None):
        b = Button(text=text, font_name=FONT, font_size=sp(13), bold=True, color=CYAN,
                   background_normal="", background_color=PANEL)
        if width:
            b.size_hint_x = None
            b.width = width
        else:
            b.size_hint_x = hint
        b.bind(on_release=lambda *_: cb())
        return b

    def _after_build(self, _dt):
        self.add_ai("سلام، من جارویس هستم. بنویسید یا با دکمه‌ی MIC بگویید. مثلاً: «کروم رو باز کن».")
        if core.ON_ANDROID:
            try:
                import android_utils
                self.tts = android_utils.AndroidTTS(lambda m: Clock.schedule_once(lambda dt: self.add_sys(m)))
                self.voice_in = android_utils.VoiceInput(
                    lambda t: Clock.schedule_once(lambda dt: self.send(t)),
                    lambda m: Clock.schedule_once(lambda dt: self.add_sys(m)))
            except Exception as e:  # noqa
                self.add_sys(f"Android bridge error: {e}")
        if not self.cfg.get("api_key"):
            self.add_sys("اول از دکمه‌ی SET کلید API را وارد کنید.")
            Clock.schedule_once(lambda dt: self.open_settings(), 0.6)

    # ------------------------------------------------------------ chat
    def _add(self, text, color, border, align):
        self.chat.add_widget(Bubble(core.shape(text), color, align, border))
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.15)

    def add_user(self, t):
        self._add(t, GREEN, GREEN, "right" if core.is_rtl(t) else "left")

    def add_ai(self, t):
        t = t.replace("**", "").replace("`", "")
        self._add(t, CYAN, CYAN, "right" if core.is_rtl(t) else "left")

    def add_sys(self, t):
        self._add(t, AMBER, AMBER, "right" if core.is_rtl(t) else "left")

    def _on_typing(self, _inst, value):
        # کیبورد اندروید در Kivy حروف فارسی را جدا نشان می‌دهد؛ پیش‌نمایش درست اینجا نمایش داده می‌شود.
        if core.is_rtl(value):
            self.preview.text = core.shape(value, 34)
            self.preview.height = dp(18) * (self.preview.text.count("\n") + 1)
        else:
            self.preview.text = ""
            self.preview.height = 0

    def set_status(self, text, color):
        self.status.text, self.status.color = text, color

    # ------------------------------------------------------------ actions
    def send(self, text=None):
        text = (text if text is not None else self.input.text).strip()
        self.input.text = ""
        if not text:
            return
        self.add_user(text)
        low = text.lower()
        if low in ("/clear", "clear", "پاک کن"):
            self.chat.clear_widgets()
            return
        if low in ("/reset", "reset"):
            self.brain.reset()
            self.add_ai("حافظه پاک شد.")
            return
        self.set_status("THINKING", AMBER)
        threading.Thread(target=self._work, args=(text,), daemon=True).start()

    def _work(self, text):
        try:
            reply, err = core.process(text, self.brain), False
        except core.BrainError as e:
            reply, err = str(e), True
        except Exception as e:  # noqa
            reply, err = f"Unexpected: {e}", True
        Clock.schedule_once(lambda dt: self._done(reply, err))

    def _done(self, reply, err):
        if err:
            self.add_sys(reply)
            self.set_status("ERROR", RED)
            return
        self.add_ai(reply)
        self.set_status("ONLINE", GREEN)
        if self.cfg.get("voice") and self.tts:
            self.tts.say(reply, core.is_rtl(reply))

    def on_mic(self):
        if self.voice_in:
            self.voice_in.start("fa-IR")
        else:
            self.add_sys("ورودی صوتی فقط روی گوشی اندروید کار می‌کند.")

    # ------------------------------------------------------------ settings popup
    def open_settings(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

        def lab(t):
            return Label(text=t, color=TEXT, font_name=FONT, font_size=sp(13), size_hint_y=None,
                         height=dp(24), halign="left", text_size=(dp(280), None))

        key = TextInput(text=self.cfg.get("api_key", ""), password=True, multiline=False,
                        font_name=FONT, size_hint_y=None, height=dp(44))
        prov = Spinner(text=self.cfg.get("provider", "gemini"), values=("gemini", "anthropic"),
                       font_name=FONT, size_hint_y=None, height=dp(44))
        model = TextInput(text=self.cfg.get("model", ""), multiline=False, font_name=FONT,
                          size_hint_y=None, height=dp(44))
        sw_row = BoxLayout(size_hint_y=None, height=dp(44))
        sw_row.add_widget(lab("Voice output"))
        sw = Switch(active=bool(self.cfg.get("voice", True)))
        sw_row.add_widget(sw)

        for w in (lab("API key"), key, lab("Provider"), prov, lab("Model"), model, sw_row):
            box.add_widget(w)
        save = Button(text="SAVE", font_name=FONT, bold=True, size_hint_y=None, height=dp(48),
                      background_normal="", background_color=DIM)
        box.add_widget(save)
        pop = Popup(title="Settings", content=box, size_hint=(0.92, None), height=dp(470),
                    title_font=FONT)

        def do_save(*_):
            self.cfg["api_key"] = key.text.strip()
            self.cfg["provider"] = prov.text
            self.cfg["model"] = model.text.strip() or DEFAULTS["model"]
            self.cfg["voice"] = sw.active
            self.save_settings()
            pop.dismiss()
            self.add_sys("تنظیمات ذخیره شد.")
        prov.bind(text=lambda i, v: setattr(model, "text", "gemini-2.5-flash" if v == "gemini" else "claude-sonnet-5-5"))
        save.bind(on_release=do_save)
        pop.open()


if __name__ == "__main__":
    JarvisApp().run()
