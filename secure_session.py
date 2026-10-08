"""Wrapper para armazenamento seguro nativo; nunca usa fallback em texto puro."""


class SecureSession:
    def __init__(self):
        try:
            from jnius import autoclass
            self._secure = autoclass("com.ludara.security.SecurePreferences")
            self._activity = autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception as exc:
            raise RuntimeError(
                "Armazenamento seguro Android indisponível. Integre SecurePreferences.java "
                "ao APK antes de usar login persistente. O token não será salvo em texto puro."
            ) from exc

    def save_token(self, token):
        if not token:
            raise ValueError("Token vazio")
        self._secure.saveToken(self._activity, token)

    def load_token(self):
        token = self._secure.loadToken(self._activity)
        return str(token) if token else None

    def clear_token(self):
        self._secure.clearToken(self._activity)
