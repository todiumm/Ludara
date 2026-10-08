"""Cliente REST para a API Ludara."""
import requests


class APIError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class LudaraAPI:
    def __init__(self, base_url, timeout=12):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.token = None

    def set_token(self, token):
        self.token = token

    def _request(self, method, path, *, json=None, auth=True):
        headers = {"Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.session.request(
                method,
                self.base_url + path,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise APIError(f"Não foi possível conectar à API: {exc}") from exc

        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}

        if not response.ok:
            detail = payload.get("detail", "A API recusou a solicitação.")
            if isinstance(detail, list):
                detail = "; ".join(str(item.get("msg", item)) for item in detail)
            raise APIError(str(detail), response.status_code)
        return payload

    def register(self, username, email, password):
        result = self._request(
            "POST", "/auth/register",
            json={"username": username, "email": email, "password": password},
            auth=False,
        )
        self.token = result["access_token"]
        return result

    def login(self, identity, password):
        result = self._request(
            "POST", "/auth/login",
            json={"identity": identity, "password": password}, auth=False,
        )
        self.token = result["access_token"]
        return result

    def me(self):
        return self._request("GET", "/me")

    def update_profile(self, bio):
        return self._request("PATCH", "/me", json={"bio": bio})

    def logout(self):
        self.token = None
        self.session.cookies.clear()
