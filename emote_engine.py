import io
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageTk, ImageSequence


DEFAULT_TWITCH_GLOBALS = [
    ("Kappa", "25"),
    ("LUL", "425618"),
    ("PogChamp", "305954156"),
    ("Keepo", "1902"),
    ("BibleThump", "86"),
    ("DansGame", "33"),
    ("Kreygasm", "41"),
    ("4Head", "354"),
    ("ResidentSleeper", "245"),
    ("WutFace", "28087"),
    ("FailFish", "360"),
    ("NotLikeThis", "58765"),
    ("SeemsGood", "64138"),
    ("VoHiYo", "81274"),
    ("HeyGuys", "30259"),
    ("BabyRage", "22639"),
    ("PJSalt", "36"),
    ("SwiftRage", "34"),
    ("SMOrc", "52"),
    ("TriHard", "120232"),
    ("CoolCat", "58127"),
    ("CurseLit", "114836"),
    ("StinkyCheese", "90076"),
    ("bleedPurple", "166266"),
    ("PopCorn", "115233"),
    ("OSFrog", "55338"),
    ("KonCha", "160400"),
    ("TehePelo", "160404"),
]


class EmoteAndBadgeManager:
    """
    Motore asincrono ad alte prestazioni per Emote Grafiche
    (Twitch Native, 7TV, BetterTTV, FrankerFaceZ) e Badge Ufficiali Twitch
    con supporto GIF/WebP animate, pool di download e cache in RAM.
    """

    def __init__(
        self,
        tk_root,
        session=None,
        client_id="kimne78kx3ncx6brgo4mv6wki5h1ko",
        should_animate_cb=None,
    ):
        self.root = tk_root
        self.client_id = client_id
        self.should_animate_cb = should_animate_cb

        if session is not None:
            self.session = session
        else:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": "TwixyDesktop/2.0"})

        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="twixy_emote")

        # Cataloghi separati: global + channel (il canale ha precedenza in caso di omonimia)
        self.global_emotes = {
            name: {
                "url": f"https://static-cdn.jtvnw.net/emoticons/v2/{eid}/default/dark/1.0",
                "source": "Twitch",
            }
            for name, eid in DEFAULT_TWITCH_GLOBALS
        }
        self.channel_emotes = {}
        self.emote_catalog = dict(self.global_emotes)

        self.global_badges = {}   # {(set_id, version): {"url": str, "title": str}}
        self.channel_badges = {}  # {(set_id, version): {"url": str, "title": str}}
        self.badge_catalog = {}

        # Cache immagini decodificate per Tkinter:
        # cache_key -> {"master": ImageTk.PhotoImage, "frames": [PIL.Image], "last_used": float}
        self.photo_cache = {}
        self._animated_keys = []
        self._anim_idx = 0

        self._loading = set()
        self._failed = set()
        self._callbacks = {}  # cache_key -> [fn(cache_key, master_photo), ...]
        self._decoded_queue = queue.Queue()
        self._ui_notify_queue = queue.Queue()

        self._loaded_channel_key = None
        self._channel_req_seq = 0
        self._running = True

        self._load_global_assets_async()
        self.root.after(65, self._tick_animations)

    def stop(self):
        self._running = False
        self.clear_pending_callbacks()
        for q in (self._decoded_queue, self._ui_notify_queue):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def clear_pending_callbacks(self):
        with self._lock:
            self._callbacks.clear()

    def _rebuild_emote_catalog(self):
        with self._lock:
            merged = dict(self.global_emotes)
            merged.update(self.channel_emotes)
            self.emote_catalog = merged

    def _rebuild_badge_catalog(self):
        with self._lock:
            merged = dict(self.global_badges)
            merged.update(self.channel_badges)
            self.badge_catalog = merged

    def register_emote(self, name, url, source="Twitch", is_channel=False):
        if not name or not url:
            return
        entry = {"url": url, "source": source}
        with self._lock:
            if is_channel:
                self.channel_emotes[name] = entry
            else:
                self.global_emotes.setdefault(name, entry)
            self.emote_catalog[name] = entry

    def get_emote_info(self, name):
        return self.emote_catalog.get(name)

    def get_badge_info(self, set_id, version):
        key = (str(set_id), str(version))
        res = self.badge_catalog.get(key)
        if res:
            return res
        # Fallback su version "1" se versione esatta mancante
        return self.badge_catalog.get((str(set_id), "1"))

    @staticmethod
    def _extract_7tv_url(em):
        data = em.get("data") or {}
        host = data.get("host") or {}
        base_u = str(host.get("url") or "").strip()
        if base_u.startswith("//"):
            base_u = "https:" + base_u
        if not base_u:
            eid = em.get("id")
            if eid:
                base_u = f"https://cdn.7tv.app/emote/{eid}"
            else:
                return None

        files = host.get("files") or []
        chosen = None
        preferred_names = ("1x.webp", "1x.gif", "1x.png", "2x.webp", "2x.gif", "2x.png")
        avail = {str(f.get("name") or ""): f for f in files if isinstance(f, dict)}
        for pname in preferred_names:
            if pname in avail:
                chosen = pname
                break
        if not chosen:
            chosen = "1x.webp"
        return f"{base_u.rstrip('/')}/{chosen}"

    # ------------------------------------------------------------------
    # CARICAMENTO ASINCRONO GLOBALI (Twitch Badges, 7TV, BTTV, FFZ)
    # ------------------------------------------------------------------
    def _load_global_assets_async(self):
        def worker():
            # 1. Twitch Global Badges via GQL (nessun token richiesto)
            try:
                q = {
                    "query": """
                    query GlobalBadges {
                      badges {
                        setID
                        version
                        image1x: imageURL(size: NORMAL)
                        title
                      }
                    }
                    """
                }
                rg = self.session.post(
                    "https://gql.twitch.tv/gql",
                    json=q,
                    headers={"Client-ID": self.client_id},
                    timeout=8,
                )
                if rg.status_code == 200:
                    badges = ((rg.json().get("data") or {}).get("badges") or [])
                    new_gb = {}
                    for b in badges:
                        sid = str(b.get("setID") or "")
                        ver = str(b.get("version") or "")
                        url = b.get("image1x") or ""
                        if sid and ver and url:
                            new_gb[(sid, ver)] = {"url": url, "title": b.get("title") or sid}
                    if new_gb:
                        with self._lock:
                            self.global_badges.update(new_gb)
                        self._rebuild_badge_catalog()
            except Exception:
                pass

            # 2. 7TV Global Emotes
            try:
                r = self.session.get("https://7tv.io/v3/emote-sets/global", timeout=6)
                if r.status_code == 200:
                    new_7tv = {}
                    for em in (r.json().get("emotes") or []):
                        name = em.get("name")
                        url = self._extract_7tv_url(em)
                        if name and url:
                            new_7tv[name] = {"url": url, "source": "7TV"}
                    if new_7tv:
                        with self._lock:
                            self.global_emotes.update(new_7tv)
                        self._rebuild_emote_catalog()
            except Exception:
                pass

            # 3. BetterTTV Global Emotes
            try:
                r = self.session.get("https://api.betterttv.net/3/cached/emotes/global", timeout=6)
                if r.status_code == 200:
                    new_bttv = {}
                    for em in (r.json() or []):
                        code, eid = em.get("code"), em.get("id")
                        if code and eid:
                            new_bttv[code] = {
                                "url": f"https://cdn.betterttv.net/emote/{eid}/1x",
                                "source": "BTTV",
                            }
                    if new_bttv:
                        with self._lock:
                            self.global_emotes.update(new_bttv)
                        self._rebuild_emote_catalog()
            except Exception:
                pass

            # 4. FrankerFaceZ Global Emotes
            try:
                r = self.session.get("https://api.frankerfacez.com/v1/set/global", timeout=6)
                if r.status_code == 200:
                    sets = r.json().get("sets") or {}
                    new_ffz = {}
                    for sdata in sets.values():
                        for em in (sdata.get("emoticons") or []):
                            name = em.get("name")
                            urls = em.get("urls") or {}
                            u = urls.get("1") or urls.get("2") or urls.get("4")
                            if name and u:
                                if u.startswith("//"):
                                    u = "https:" + u
                                new_ffz[name] = {"url": u, "source": "FFZ"}
                    if new_ffz:
                        with self._lock:
                            self.global_emotes.update(new_ffz)
                        self._rebuild_emote_catalog()
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # CARICAMENTO ASINCRONO CANALE (Twitch Badges, 7TV, BTTV, FFZ, Helix)
    # ------------------------------------------------------------------
    def load_channel_assets(
        self,
        channel_login="",
        channel_id="",
        oauth_token="",
        auth_client_id="",
        on_updated=None,
    ):
        login = str(channel_login or "").strip().lower()
        cid = str(channel_id or "").strip()
        if not login and not cid:
            return

        ch_key = f"{login}:{cid}"
        with self._lock:
            if ch_key == self._loaded_channel_key and self.channel_emotes:
                return
            self._loaded_channel_key = ch_key
            self._channel_req_seq += 1
            req_seq = self._channel_req_seq
            self.channel_emotes = {}
            self.channel_badges = {}
        self._rebuild_emote_catalog()
        self._rebuild_badge_catalog()

        def worker():
            resolved_cid = cid
            new_ch_badges = {}
            new_ch_emotes = {}

            # 1. Twitch Channel Badges + eventuale risoluzione channel_id via GQL
            if login:
                try:
                    q = {
                        "query": """
                        query ChannelBadges($login: String!) {
                          user(login: $login) {
                            id
                            broadcastBadges {
                              setID
                              version
                              image1x: imageURL(size: NORMAL)
                              title
                            }
                          }
                        }
                        """,
                        "variables": {"login": login},
                    }
                    rc = self.session.post(
                        "https://gql.twitch.tv/gql",
                        json=q,
                        headers={"Client-ID": self.client_id},
                        timeout=8,
                    )
                    if rc.status_code == 200:
                        u = ((rc.json().get("data") or {}).get("user") or {})
                        if not resolved_cid and u.get("id"):
                            resolved_cid = str(u["id"])
                        for b in (u.get("broadcastBadges") or []):
                            sid = str(b.get("setID") or "")
                            ver = str(b.get("version") or "")
                            url = b.get("image1x") or ""
                            if sid and ver and url:
                                new_ch_badges[(sid, ver)] = {
                                    "url": url,
                                    "title": b.get("title") or sid,
                                }
                except Exception:
                    pass

            if req_seq != self._channel_req_seq or not self._running:
                return

            if resolved_cid:
                # 2. 7TV Channel Emotes
                try:
                    r = self.session.get(f"https://7tv.io/v3/users/twitch/{resolved_cid}", timeout=6)
                    if r.status_code == 200:
                        eset = r.json().get("emote_set") or {}
                        for em in (eset.get("emotes") or []):
                            name = em.get("name")
                            url = self._extract_7tv_url(em)
                            if name and url:
                                new_ch_emotes[name] = {"url": url, "source": "7TV"}
                except Exception:
                    pass

                # 3. BetterTTV Channel + Shared Emotes
                try:
                    r = self.session.get(
                        f"https://api.betterttv.net/3/cached/users/twitch/{resolved_cid}",
                        timeout=6,
                    )
                    if r.status_code == 200:
                        j = r.json()
                        for em in (j.get("channelEmotes", []) + j.get("sharedEmotes", [])):
                            code, eid = em.get("code"), em.get("id")
                            if code and eid:
                                new_ch_emotes[code] = {
                                    "url": f"https://cdn.betterttv.net/emote/{eid}/1x",
                                    "source": "BTTV",
                                }
                except Exception:
                    pass

                # 4. FrankerFaceZ Channel Emotes
                try:
                    r = self.session.get(f"https://api.frankerfacez.com/v1/room/id/{resolved_cid}", timeout=6)
                    if r.status_code == 200:
                        sets = r.json().get("sets") or {}
                        for sdata in sets.values():
                            for em in (sdata.get("emoticons") or []):
                                name = em.get("name")
                                urls = em.get("urls") or {}
                                u = urls.get("1") or urls.get("2") or urls.get("4")
                                if name and u:
                                    if u.startswith("//"):
                                        u = "https:" + u
                                    new_ch_emotes[name] = {"url": u, "source": "FFZ"}
                except Exception:
                    pass

                # 5. Twitch Helix Global & Channel Emotes (se autenticato)
                if oauth_token:
                    tok = oauth_token.replace("oauth:", "").strip()
                    hdrs = {
                        "Client-Id": auth_client_id or self.client_id,
                        "Authorization": f"Bearer {tok}",
                    }
                    for hurl in (
                        "https://api.twitch.tv/helix/chat/emotes/global",
                        f"https://api.twitch.tv/helix/chat/emotes?broadcaster_id={resolved_cid}",
                    ):
                        try:
                            rh = self.session.get(hurl, headers=hdrs, timeout=6)
                            if rh.status_code == 200:
                                is_ch = "broadcaster_id=" in hurl
                                for em in (rh.json().get("data") or []):
                                    name = em.get("name")
                                    eid = em.get("id")
                                    if name and eid:
                                        url = f"https://static-cdn.jtvnw.net/emoticons/v2/{eid}/default/dark/1.0"
                                        if is_ch:
                                            new_ch_emotes[name] = {"url": url, "source": "Twitch"}
                                        else:
                                            with self._lock:
                                                self.global_emotes.setdefault(name, {"url": url, "source": "Twitch"})
                        except Exception:
                            pass

            if req_seq != self._channel_req_seq or not self._running:
                return

            with self._lock:
                self.channel_badges = new_ch_badges
                self.channel_emotes = new_ch_emotes
            self._rebuild_badge_catalog()
            self._rebuild_emote_catalog()

            if on_updated and self._running:
                self._ui_notify_queue.put(on_updated)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # DOWNLOAD, DECODIFICA (STATIC + GIF/WEBP ANIMATE) E CACHE RAM
    # ------------------------------------------------------------------
    def get_emote_photo(self, cache_key, url, target_height=22, on_loaded=None):
        return self.get_or_request_image(
            cache_key, url, target_height=target_height, is_badge=False, on_loaded=on_loaded
        )

    def get_badge_photo(self, set_id, version, target_height=18, on_loaded=None):
        info = self.get_badge_info(set_id, version)
        if not info or not info.get("url"):
            return None
        ck = f"badge:{set_id}/{version}:{info['url']}"
        return self.get_or_request_image(
            ck, info["url"], target_height=target_height, is_badge=True, on_loaded=on_loaded
        )

    def get_or_request_image(self, cache_key, url, target_height=22, is_badge=False, on_loaded=None):
        if not cache_key or not url:
            return None

        entry = self.photo_cache.get(cache_key)
        if entry is not None:
            entry["last_used"] = time.time()
            master = entry["master"]
            if on_loaded:
                try:
                    on_loaded(cache_key, master)
                except Exception:
                    pass
            return master

        with self._lock:
            if cache_key in self._failed:
                return None
            if on_loaded:
                cbs = self._callbacks.setdefault(cache_key, [])
                if len(cbs) < 25:
                    cbs.append(on_loaded)
            if cache_key in self._loading:
                return None
            self._loading.add(cache_key)

        try:
            self._executor.submit(self._download_and_decode, cache_key, url, target_height, is_badge)
        except Exception:
            with self._lock:
                self._loading.discard(cache_key)
        return None

    def _download_and_decode(self, cache_key, url, target_height, is_badge):
        try:
            if not self._running:
                return
            r = self.session.get(url, timeout=6)
            if r.status_code != 200 or not r.content:
                with self._lock:
                    self._failed.add(cache_key)
                    self._callbacks.pop(cache_key, None)
                return

            pil_img = Image.open(io.BytesIO(r.content))
            frames = []
            max_frames = 1 if is_badge else 24
            n_frames = getattr(pil_img, "n_frames", 1)

            if n_frames > max_frames:
                step = n_frames / float(max_frames)
                keep_indices = {int(i * step) for i in range(max_frames)}
            else:
                keep_indices = None

            for idx, frame in enumerate(ImageSequence.Iterator(pil_img)):
                if keep_indices is None or idx in keep_indices:
                    rgba = frame.convert("RGBA")
                    w, h = rgba.size
                    if h > 0:
                        max_w = target_height if is_badge else 64
                        min_w = target_height if is_badge else 12
                        new_w = max(min_w, min(max_w, int(round(w * (target_height / float(h))))))
                        rgba = rgba.resize((new_w, target_height), Image.Resampling.LANCZOS)
                    frames.append(rgba)
                    if is_badge:
                        break

            if not frames:
                with self._lock:
                    self._failed.add(cache_key)
                    self._callbacks.pop(cache_key, None)
                return

            if not self._running:
                return
            self._decoded_queue.put((cache_key, frames))
        except Exception:
            with self._lock:
                self._failed.add(cache_key)
                self._callbacks.pop(cache_key, None)
        finally:
            with self._lock:
                self._loading.discard(cache_key)

    def _drain_main_thread_queues(self, max_decoded=24):
        """Crea PhotoImage e lancia callback esclusivamente nel thread UI Tkinter."""
        processed = 0
        while processed < max_decoded and self._running:
            try:
                cache_key, frames = self._decoded_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            try:
                master = ImageTk.PhotoImage(frames[0], master=self.root)
                self.photo_cache[cache_key] = {
                    "master": master,
                    "frames": frames,
                    "last_used": time.time(),
                }
                if len(frames) > 1 and cache_key not in self._animated_keys:
                    self._animated_keys.append(cache_key)

                with self._lock:
                    cbs = self._callbacks.pop(cache_key, [])
                for cb in cbs:
                    try:
                        cb(cache_key, master)
                    except Exception:
                        pass
            except Exception:
                with self._lock:
                    self._failed.add(cache_key)
                    self._callbacks.pop(cache_key, None)

        while self._running:
            try:
                notify_cb = self._ui_notify_queue.get_nowait()
            except queue.Empty:
                break
            try:
                notify_cb()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # MOTORE ANIMAZIONE GLOBALE (~14 FPS, ZERO LAG QUANDO ICONIC/NASCOSTO)
    # ------------------------------------------------------------------
    def _tick_animations(self):
        if not self._running:
            return
        try:
            self._drain_main_thread_queues(max_decoded=24)

            should_run = True
            if self.root.state() == "iconic":
                should_run = False
            elif self.should_animate_cb is not None:
                try:
                    should_run = bool(self.should_animate_cb())
                except Exception:
                    should_run = True

            if should_run and self._animated_keys:
                self._anim_idx += 1
                now = time.time()
                # Aggiorna solo le emote animate usate recentemente (ultimi 120s)
                for ck in self._animated_keys:
                    entry = self.photo_cache.get(ck)
                    if not entry:
                        continue
                    if now - entry["last_used"] > 120.0:
                        continue
                    frames = entry["frames"]
                    if len(frames) > 1:
                        try:
                            entry["master"].paste(frames[self._anim_idx % len(frames)])
                        except Exception:
                            pass
        except Exception:
            pass
        self.root.after(75, self._tick_animations)
