"""Aplicativo Ludara: login/registro, perfil e protótipo 3D."""
import os
from urllib.parse import urlparse
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from api_client import LudaraAPI, APIError
from engine3d import Engine3D
from multiplayer import LudaraMultiplayer
from secure_session import SecureSession
from theme import BG, SURFACE, ORANGE, WHITE, MUTED, APP_NAME, APP_VERSION

API_URL = os.environ.get("LUDARA_API_URL", "https://ludarabackend.wasmer.app/").rstrip("/")


def label(text, size=16, color=WHITE, **kwargs):
    return Label(text=text, font_size=dp(size), color=color, **kwargs)


def styled_button(text, callback, height=46):
    button = Button(text=text, size_hint_y=None, height=dp(height),
                    background_normal="", background_color=ORANGE,
                    color=(1, 1, 1, 1), bold=True)
    button.bind(on_release=lambda *_: callback())
    return button


def text_field(hint, password=False, multiline=False):
    field = TextInput(hint_text=hint, password=password, multiline=multiline,
                      size_hint_y=None, height=dp(46 if not multiline else 100),
                      background_normal="", background_active="",
                      background_color=SURFACE, foreground_color=WHITE,
                      hint_text_color=MUTED, cursor_color=ORANGE,
                      padding=(dp(12), dp(12)))
    return field


class LudaraApp(App):
    def build(self):
        self.title = f"{APP_NAME} {APP_VERSION}"
        Window.clearcolor = BG
        self.api = LudaraAPI(API_URL)
        self.user = None
        self.token = None
        self.multiplayer = None
        self.engine = None
        self._secure = None
        self.root_box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        try:
            self._secure = SecureSession()
        except RuntimeError as exc:
            # Permite abrir telas públicas, mas não persiste token em armazenamento inseguro.
            self.secure_error = str(exc)
        else:
            self.secure_error = None
        self.show_auth()
        return self.root_box

    def _reset(self):
        self.root_box.clear_widgets()

    def _header(self, subtitle):
        self.root_box.add_widget(label("LUDARA", 30, ORANGE, size_hint_y=None, height=dp(42), bold=True))
        self.root_box.add_widget(label(subtitle, 14, MUTED, size_hint_y=None, height=dp(28)))

    def _message(self, message):
        self.root_box.add_widget(label(message, 13, MUTED, size_hint_y=None, height=dp(52)))

    def show_auth(self, message=""):
        self._reset()
        self._header("Entre no seu universo")
        self.identity = text_field("Usuário ou e-mail")
        self.password = text_field("Senha", password=True)
        self.root_box.add_widget(self.identity)
        self.root_box.add_widget(self.password)
        self.root_box.add_widget(styled_button("ENTRAR", self.login))
        self.root_box.add_widget(styled_button("CRIAR CONTA", self.show_register))
        if self.secure_error:
            self._message("Armazenamento seguro nativo ainda não integrado ao APK. Login pode ser usado nesta sessão, mas não será persistido.")
        if message:
            self._message(message)

    def show_register(self):
        self._reset()
        self._header("Crie sua conta")
        self.reg_username = text_field("Nome de usuário (3–24 caracteres)")
        self.reg_email = text_field("E-mail")
        self.reg_password = text_field("Senha (mínimo 10 caracteres)", password=True)
        for field in (self.reg_username, self.reg_email, self.reg_password):
            self.root_box.add_widget(field)
        self.root_box.add_widget(styled_button("REGISTRAR", self.register))
        self.root_box.add_widget(styled_button("VOLTAR", self.show_auth))

    def login(self):
        identity, password = self.identity.text.strip(), self.password.text
        if not identity or not password:
            self.show_auth("Preencha usuário/e-mail e senha.")
            return
        self._reset()
        self._header("Conectando...")
        Clock.schedule_once(lambda _dt: self._login_worker(identity, password), 0.05)

    def _login_worker(self, identity, password):
        # Chamado pela thread Kivy; requests é síncrono, portanto a UI pode pausar em redes lentas.
        try:
            result = self.api.login(identity, password)
            self.token = result["access_token"]
            self.user = self.api.me()
            if self._secure:
                try:
                    self._secure.save_token(self.token)
                except Exception:
                    self.secure_error = "Não foi possível salvar sessão segura neste dispositivo."
            self.show_home()
        except APIError as exc:
            self.show_auth(str(exc))

    def register(self):
        username, email, password = self.reg_username.text.strip(), self.reg_email.text.strip(), self.reg_password.text
        if not username or not email or not password:
            self.show_register()
            self._message("Preencha todos os campos.")
            return
        try:
            result = self.api.register(username, email, password)
            self.token = result["access_token"]
            self.user = self.api.me()
            if self._secure:
                self._secure.save_token(self.token)
            self.show_home()
        except Exception as exc:
            self.show_register()
            self._message(str(exc))

    def show_home(self):
        self._reset()
        username = (self.user or {}).get("username", "Jogador")
        self._header(f"Bem-vindo, {username}")
        self.root_box.add_widget(label("Entre em uma sala e explore a cena 3D.", 14, MUTED))
        self.root_box.add_widget(styled_button("JOGAR — SALA LOBBY", self.show_game, 54))
        self.root_box.add_widget(styled_button("EDITAR PERFIL", self.show_profile))
        self.root_box.add_widget(styled_button("SAIR", self.logout))

    def show_profile(self):
        self._reset()
        self._header("Seu perfil")
        self.bio_field = text_field("Conte algo sobre você", multiline=True)
        self.bio_field.text = (self.user or {}).get("bio", "")
        self.root_box.add_widget(self.bio_field)
        self.root_box.add_widget(styled_button("SALVAR PERFIL", self.save_profile))
        self.root_box.add_widget(styled_button("VOLTAR", self.show_home))

    def save_profile(self):
        try:
            self.user = self.api.update_profile(self.bio_field.text[:500])
            self.show_home()
        except APIError as exc:
            self._message(str(exc))

    def show_game(self):
        self._reset()
        self.root_box.padding = dp(6)
        self.root_box.spacing = dp(4)
        top = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        top.add_widget(label("LUDARA 3D", 16, ORANGE))
        top.add_widget(styled_button("VOLTAR", self.leave_game, 36))
        self.root_box.add_widget(top)
        self.engine = Engine3D(size_hint=(1, 1))
        self.root_box.add_widget(self.engine)
        controls = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(5))
        for text, forward, side in (("◀",0,-1),("▲",1,0),("▼",-1,0),("▶",0,1)):
            btn = Button(text=text, background_normal="", background_color=ORANGE)
            btn.bind(on_press=lambda _b, f=forward, s=side: self.engine.move(f, s))
            btn.bind(on_release=lambda *_: self.engine.move(0, 0))
            controls.add_widget(btn)
        controls.add_widget(styled_button("PULAR", self.engine.jump, 42))
        self.root_box.add_widget(controls)
        self._connect_multiplayer()

    def _connect_multiplayer(self):
        parsed = urlparse(API_URL)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = f"{scheme}://{parsed.netloc}"
        self.multiplayer = LudaraMultiplayer(
            ws_url, "lobby", self.token,
            on_event=lambda event: Clock.schedule_once(lambda _dt: self._apply_event(event), 0),
            on_error=lambda error: Clock.schedule_once(lambda _dt: self._toast(f"Multiplayer: {error}"), 0),
        )
        self.multiplayer.connect()

    def _apply_event(self, event):
        kind = event.get("type")
        if kind == "position" and self.engine:
            self.engine.set_remote_player(event.get("user_id", "?"), event.get("x", 0), event.get("y", 0), event.get("z", 0))
        elif kind == "player_left" and self.engine:
            self.engine.remove_remote_player(event.get("user_id", "?"))
        elif kind == "error":
            self._toast(event.get("message", "Erro multiplayer"))

    def _toast(self, message):
        # Evita alterar layout do jogo em callbacks de rede; o texto aparece no console de log do app.
        print("[Ludara]", message)

    def leave_game(self):
        if self.multiplayer:
            self.multiplayer.close()
            self.multiplayer = None
        self.root_box.padding = dp(18)
        self.root_box.spacing = dp(12)
        self.show_home()

    def logout(self):
        if self.multiplayer:
            self.multiplayer.close()
        if self._secure:
            try:
                self._secure.clear_token()
            except Exception:
                pass
        self.api.logout()
        self.token = None
        self.user = None
        self.show_auth("Você saiu da conta.")

    def on_start(self):
        if not self._secure:
            return
        try:
            token = self._secure.load_token()
            if token:
                self.api.set_token(token)
                self.token = token
                self.user = self.api.me()
                self.show_home()
        except Exception as exc:
            print("[Ludara] Sessão salva indisponível:", exc)
            try:
                self._secure.clear_token()
            except Exception:
                pass

    def on_stop(self):
        if self.multiplayer:
            self.multiplayer.close()


if __name__ == "__main__":
    LudaraApp().run()
