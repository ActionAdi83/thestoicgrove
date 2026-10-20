"""Instagram API with Instagram Login: publish carousels, check the account, refresh tokens.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
Images must be reachable at public HTTPS URLs (JPEG); Instagram downloads them itself.
"""
import time

import requests

GRAPH = "https://graph.instagram.com"


class InstagramError(RuntimeError):
    pass


class Instagram:
    def __init__(self, token, api_version="v24.0"):
        self.token = token
        self.base = f"{GRAPH}/{api_version}"
        self._user = None

    def _req(self, method, path, **params):
        params["access_token"] = self.token
        url = f"{self.base}/{path.lstrip('/')}"
        for attempt in range(4):
            if method == "GET":
                r = requests.get(url, params=params, timeout=60)
            else:
                r = requests.post(url, data=params, timeout=60)
            if r.status_code < 500:
                break
            time.sleep(5 * (attempt + 1))  # transient server errors
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(f"{method} {path} -> {r.status_code}: {err.get('message', r.text)} "
                                 f"(code {err.get('code')}, subcode {err.get('error_subcode')})")
        return data

    def me(self):
        if not self._user:
            self._user = self._req("GET", "me", fields="user_id,username,account_type,media_count")
        return self._user

    def publishing_limit(self):
        uid = self.me()["user_id"]
        return self._req("GET", f"{uid}/content_publishing_limit", fields="quota_usage,config")

    def _wait_ready(self, container_id, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            status = self._req("GET", container_id, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                info = self._req("GET", container_id, fields="status")
                raise InstagramError(f"container {container_id} {status}: {info.get('status')}")
            time.sleep(4)
        raise InstagramError(f"container {container_id} not ready after {timeout}s")

    def publish_carousel(self, image_urls, caption, log=print):
        if not 2 <= len(image_urls) <= 10:
            raise ValueError("a carousel needs 2-10 images")
        uid = self.me()["user_id"]
        children = []
        for i, url in enumerate(image_urls, 1):
            c = self._req("POST", f"{uid}/media", image_url=url, is_carousel_item="true")
            children.append(c["id"])
            log(f"  item {i}/{len(image_urls)} uploaded ({c['id']})")
        for cid in children:
            self._wait_ready(cid)
        parent = self._req("POST", f"{uid}/media", media_type="CAROUSEL",
                           children=",".join(children), caption=caption)
        self._wait_ready(parent["id"])
        media = self._req("POST", f"{uid}/media_publish", creation_id=parent["id"])
        info = self._req("GET", media["id"], fields="permalink,timestamp")
        return {"media_id": media["id"], "permalink": info.get("permalink"), "timestamp": info.get("timestamp")}


def refresh_token(token):
    """Long-lived tokens last 60 days; refreshing (allowed once the token is 24h old) resets that."""
    r = requests.get(f"{GRAPH}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "access_token" not in data:
        raise InstagramError(f"token refresh failed: {data}")
    return data["access_token"], data.get("expires_in")
