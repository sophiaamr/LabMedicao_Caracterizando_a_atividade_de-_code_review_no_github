import os
import time
import json
import math
import hashlib
import random
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "dataset.csv")
BASE_URL = "https://api.github.com"


TOKENS_ENV = os.getenv("GITHUB_TOKENS", "").strip()
SINGLE_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
TOKENS = [t.strip() for t in TOKENS_ENV.split(",") if t.strip()] or ([SINGLE_TOKEN] if SINGLE_TOKEN else [])
TOKENS = [
    ]
if not TOKENS:
    raise RuntimeError(
        "Nenhum token encontrado. Defina GITHUB_TOKENS (comma-separated) ou GITHUB_TOKEN no ambiente."
    )

DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "oss-research/1.1"
}

TIMEOUT = (10, 45)
MAX_DEEP_PRS_PER_REPO = int(os.getenv("MAX_DEEP_PRS_PER_REPO", "3000"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))

CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", ".cache/github_api_cache.sqlite")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)

def _now_ts() -> int:
    return int(time.time())

def _iso_to_dt(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

def _params_fingerprint(params: dict | None) -> str:
    if not params:
        return "noparams"
    s = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _cache_key(url: str, params: dict | None) -> str:
    return hashlib.sha256(f"{url}|{_params_fingerprint(params)}".encode("utf-8")).hexdigest()

class SQLiteCache:
    def __init__(self, path: str, ttl_seconds: int):
        self.path = path
        self.ttl = ttl_seconds
        self._lock = threading.RLock()
        self._ensure_schema()

    def _ensure_schema(self):
        with self._conn() as con:
            con.execute("""
              CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                params_fpr TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_json TEXT,
                etag TEXT,
                last_modified TEXT,
                created_at INTEGER NOT NULL
              )
            """)
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=NORMAL;")

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path, timeout=30)
        try:
            yield con
        finally:
            con.close()

    def get(self, url: str, params: dict | None):
        key = _cache_key(url, params)
        with self._lock, self._conn() as con:
            cur = con.execute("SELECT status_code, response_json, etag, last_modified, created_at FROM cache WHERE cache_key=?",
                              (key,))
            row = cur.fetchone()
            if not row:
                return None
            status_code, response_json, etag, last_modified, created_at = row

            if (_now_ts() - int(created_at)) > self.ttl:
                return {"stale": True, "etag": etag, "last_modified": last_modified, "json": json.loads(response_json) if response_json else None}
            return {"stale": False, "etag": etag, "last_modified": last_modified, "json": json.loads(response_json) if response_json else None}

    def put(self, url: str, params: dict | None, status_code: int, response_json: dict | list | None,
            etag: str | None, last_modified: str | None):
        key = _cache_key(url, params)
        with self._lock, self._conn() as con:
            con.execute("""
              INSERT OR REPLACE INTO cache(cache_key, url, params_fpr, status_code, response_json, etag, last_modified, created_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key, url, _params_fingerprint(params), status_code,
                json.dumps(response_json) if response_json is not None else None,
                etag, last_modified, _now_ts()
            ))


CACHE = SQLiteCache(CACHE_DB_PATH, CACHE_TTL_SECONDS)

class TokenSession:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({**DEFAULT_HEADERS, "Authorization": f"token {token}"})
        self.remaining = None
        self.reset_epoch = 0
        self.lock = threading.Lock()

    def update_rate(self, resp: requests.Response):
        try:
            self.remaining = int(resp.headers.get("X-RateLimit-Remaining", "0") or "0")
            self.reset_epoch = int(resp.headers.get("X-RateLimit-Reset", "0") or "0")
        except Exception:
            pass

    def wait_if_needed(self):
        if self.remaining is not None and self.remaining <= 0:
            wait = max(1, self.reset_epoch - int(time.time())) + 2
            time.sleep(min(wait, 120))


class TokenRotator:
    def __init__(self, tokens: list[str]):
        self.pool = [TokenSession(t) for t in tokens]
        self.idx = 0
        self.lock = threading.Lock()

    def pick(self) -> TokenSession:
        with self.lock:
            n = len(self.pool)
            for _ in range(n):
                s = self.pool[self.idx]
                self.idx = (self.idx + 1) % n
                if s.remaining is None or s.remaining > 0:
                    return s
            s = self.pool[0]
            s.wait_if_needed()
            return s


ROTATOR = TokenRotator(TOKENS)

def _sleep_backoff(i: int):
    time.sleep(min(90, (2 ** i) + random.random()))

def safe_get_json(url: str, params: dict | None = None, attempts: int = 6):
    cached = CACHE.get(url, params)
    headers = {}
    if cached:
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        elif cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

        if cached.get("stale") is False and cached.get("json") is not None:
            return cached["json"]

    for i in range(attempts):
        sess = ROTATOR.pick()
        try:
            with sess.lock:
                sess.wait_if_needed()
                r = sess.session.get(url, params=params, timeout=TIMEOUT, headers=headers or None)
                sess.update_rate(r)
        except Exception:
            _sleep_backoff(i)
            continue

        if r.status_code == 304 and cached:
            return cached.get("json")

        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            wait = max(1, int(r.headers.get("X-RateLimit-Reset", "0") or 0) - int(time.time())) + 2
            time.sleep(min(wait, 120))
            continue

        if r.status_code in (429, 403) and ("secondary rate limit" in (r.text or "").lower()):
            retry_after = int(r.headers.get("Retry-After", "0") or 0)
            time.sleep(retry_after or min(90, (2 ** i) + random.random()))
            continue

        if r.status_code in (500, 502, 503, 504):
            _sleep_backoff(i)
            continue

        if r.ok:
            etag = r.headers.get("ETag") or None
            last_mod = r.headers.get("Last-Modified") or None
            try:
                payload = r.json()
            except ValueError:
                payload = None
            CACHE.put(url, params, r.status_code, payload, etag, last_mod)
            return payload

        _sleep_backoff(i)

    return None

def iter_top_repositories_sorted(max_pages=10, per_page=100):
    seen = set()
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/search/repositories"
        params = {
            "q": "stars:>1",
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }
        data = safe_get_json(url, params=params)
        items = (data or {}).get("items") or []
        if not items:
            break
        for r in items:
            key = f"{r['owner']['login']}/{r['name']}"
            if key in seen:
                continue
            seen.add(key)
            yield r
        time.sleep(0.05)  

def get_closed_prs_count(owner, repo):
    q = f"repo:{owner}/{repo} is:pr is:closed"
    url = f"{BASE_URL}/search/issues"
    params = {"q": q, "per_page": 1}
    data = safe_get_json(url, params=params)
    if not data:
        return 0
    return int(data.get("total_count", 0))

def get_reviews(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    data = safe_get_json(url) or []
    return [rv for rv in data if isinstance(rv, dict)]

def get_issue_comments(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    data = safe_get_json(url) or []
    return [c for c in data if isinstance(c, dict)]

def get_review_comments(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    data = safe_get_json(url) or []
    return [c for c in data if isinstance(c, dict)]

def get_pr_files(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    data = safe_get_json(url) or []
    return [f for f in data if isinstance(f, dict)]

def get_pr_detail(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    return safe_get_json(url) or {}

def _parse_dt(iso_str):
    return _iso_to_dt(iso_str)

def fetch_single_pr(owner: str, repo: str, pr: dict):

    merged_at = pr.get("merged_at")
    closed_at = pr.get("closed_at")
    created_at = pr.get("created_at")
    if not created_at or not (merged_at or closed_at):
        return None

    end_raw = merged_at or closed_at
    try:
        duration_h = (_parse_dt(end_raw) - _parse_dt(created_at)).total_seconds() / 3600.0
    except Exception:
        return None
    if duration_h < 1.0:
        return None

    reviews = get_reviews(owner, repo, pr["number"])
    if len(reviews) < 1:
        return None

    detail = get_pr_detail(owner, repo, pr["number"])
    issue_comments = get_issue_comments(owner, repo, pr["number"])
    review_comments = get_review_comments(owner, repo, pr["number"])
    files = get_pr_files(owner, repo, pr["number"])

    users = set()
    u = (detail.get("user") or {}).get("login")
    if u:
        users.add(u)
    for rv in reviews:
        u = (rv.get("user") or {}).get("login")
        if u:
            users.add(u)
    for c in issue_comments:
        u = (c.get("user") or {}).get("login")
        if u:
            users.add(u)
    for c in review_comments:
        u = (c.get("user") or {}).get("login")
        if u:
            users.add(u)

    num_files = len(files)
    additions = sum(int(f.get("additions", 0) or 0) for f in files)
    deletions = sum(int(f.get("deletions", 0) or 0) for f in files)
    description_length = len(detail.get("body") or pr.get("body") or "")

    return {
        "owner": owner,
        "repo_name": repo,
        "repo": f"{owner}/{repo}",
        "pr_number": pr["number"],
        "state": "merged" if merged_at else "closed",
        "num_files": num_files,
        "additions": additions,
        "deletions": deletions,
        "analysis_time_hours": duration_h,
        "description_length": description_length,
        "participants_count": len(users),
        "comments_count": int(detail.get("comments", 0)) + int(detail.get("review_comments", 0)),
        "reviews_count": len(reviews),
    }

def get_pull_requests(owner, repo, max_deep=MAX_DEEP_PRS_PER_REPO):

    print(f"[início] {owner}/{repo} - limite: {max_deep} PRs", flush=True)
    results = []
    page = 1
    per_page = 100
    deep_analyzed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        while True:
            if max_deep is not None and deep_analyzed >= max_deep:
                print(f"[limite] {owner}/{repo} - atingiu {max_deep} PRs analisados", flush=True)
                break

            url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
            params = {"state": "closed", "per_page": per_page, "page": page}
            data = safe_get_json(url, params=params)
            if not data or not isinstance(data, list) or not data:
                break

            for pr in data:
                if max_deep is not None and deep_analyzed >= max_deep:
                    break
                futures.append(ex.submit(fetch_single_pr, owner, repo, pr))
                deep_analyzed += 1
                if deep_analyzed % 200 == 0:
                    print(f"[progresso] {owner}/{repo}: {deep_analyzed}/{max_deep} PRs agendados", flush=True)

            page += 1
            time.sleep(0.02)

        for fut in as_completed(futures):
            item = fut.result()
            if item:
                results.append(item)

    print(f"[fim] {owner}/{repo}: {len(results)} PRs coletados (válidos)", flush=True)
    return results


if __name__ == "__main__":
    start_ts = datetime.now(timezone.utc)
    print(f"[start] {start_ts.isoformat()} | cwd={os.getcwd()} | tokens={len(TOKENS)} | max_workers={MAX_WORKERS}", flush=True)

    TARGET = 200
    eligible = []
    repo_meta = {}

    print("Buscando repositórios por estrelas até completar 200 elegíveis...", flush=True)

    candidates = list(iter_top_repositories_sorted(max_pages=10))
    print(f"[eligibility] Candidatos recebidos da Search API: {len(candidates)}", flush=True)

    def _eligibility_item(r):
        owner = r["owner"]["login"]
        name = r["name"]
        key = f"{owner}/{name}"
        stars = r.get("stargazers_count", 0)
        html_url = r.get("html_url", "")
        total_closed = get_closed_prs_count(owner, name)
        return key, owner, name, stars, html_url, total_closed

    with ThreadPoolExecutor(max_workers=min(32, MAX_WORKERS * max(1, len(TOKENS)))) as ex:
        futs = [ex.submit(_eligibility_item, r) for r in candidates]
        for fut in as_completed(futs):
            key, owner, name, stars, html_url, total_closed = fut.result()
            print(f"[eligibility] {key} -> closed PRs={total_closed}", flush=True)
            if total_closed >= 100 and len(eligible) < TARGET:
                repo_meta[key] = {"stars": stars, "html_url": html_url}
                eligible.append({
                    "owner": owner,
                    "repo": name,
                    "key": key,
                    "total_closed_prs": total_closed
                })
            if len(eligible) >= TARGET:
                break

    print(f"[main] Elegíveis reunidos: {len(eligible)} (alvo={TARGET})", flush=True)
    if len(eligible) < TARGET:
        print("[main] AVISO: não foi possível atingir 200 dentro do limite da Search API. Aumente max_pages.", flush=True)

    dataset = []

    def _collect_repo(item):
        owner, name, key = item["owner"], item["repo"], item["key"]
        prs = get_pull_requests(owner, name, max_deep=MAX_DEEP_PRS_PER_REPO)
        meta = repo_meta.get(key, {"stars": 0, "html_url": ""})
        for pr in prs:
            pr.update({
                "stars": meta["stars"],
                "html_url": meta["html_url"],
                "total_closed_prs": item["total_closed_prs"]
            })
        return prs

    with ThreadPoolExecutor(max_workers=min(12, len(eligible), MAX_WORKERS)) as ex:
        futs = [ex.submit(_collect_repo, item) for item in eligible]
        for fut in as_completed(futs):
            prs = fut.result()
            dataset.extend(prs)

    columns = [
        "owner", "repo_name", "repo", "stars", "html_url", "total_closed_prs",
        "pr_number", "state",
        "num_files", "additions", "deletions",
        "analysis_time_hours",
        "description_length",
        "participants_count", "comments_count",
        "reviews_count",
    ]
    df = pd.DataFrame(dataset, columns=columns)
    df.to_csv(OUTPUT_FILENAME, index=False)
    print(f"[output] Arquivo gravado: {os.path.abspath(OUTPUT_FILENAME)} | linhas={len(df)} | vazio={df.empty}", flush=True)
    print(f"[end] {datetime.now(timezone.utc).isoformat()} | elegíveis={len(eligible)} | PRs={len(df)}", flush=True)