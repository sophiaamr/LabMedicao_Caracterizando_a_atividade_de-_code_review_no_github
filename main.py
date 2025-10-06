import os
import time
import random
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import local, Lock

OUTPUT_FILENAME = "dataset.csv"
BASE_URL = "https://api.github.com"

def _load_tokens():
    env_multi = os.getenv("GITHUB_TOKENS", "").strip()
    if env_multi:
        tokens = [t.strip() for t in env_multi.split(",") if t.strip()]
        if tokens:
            return tokens
    single = os.getenv("GITHUB_TOKEN", "").strip()
    return [single] if single else []

TOKENS = _load_tokens()
if not TOKENS:
    raise RuntimeError("Defina GITHUB_TOKENS (vírgula) ou GITHUB_TOKEN")

TIMEOUT = (10, 45)
MAX_DEEP_PRS_PER_REPO = int(os.getenv("MAX_DEEP_PRS_PER_REPO", "3000"))

class TokenRotator:
    def __init__(self, tokens):
        self.tokens = tokens
        self.n = len(tokens)
        self.lock = Lock()
        self.idx = 0
    def current(self):
        with self.lock:
            return self.tokens[self.idx]
    def next(self):
        with self.lock:
            self.idx = (self.idx + 1) % self.n
            return self.tokens[self.idx]
    def set_on_session(self, session):
        session.headers["Authorization"] = f"token {self.current()}"

TOKEN_ROTATOR = TokenRotator(TOKENS)

BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "oss-research/1.0"
}

_thread = local()

def _get_session():
    s = getattr(_thread, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(BASE_HEADERS)
        TOKEN_ROTATOR.set_on_session(s)
        _thread.session = s
    return s

def _rotate_token_on_session():
    TOKEN_ROTATOR.next()
    TOKEN_ROTATOR.set_on_session(_get_session())

def _sleep_backoff(i):
    time.sleep(min(90, (2 ** i) + random.random()))

def _safe_get_json(url, params=None, attempts=6):
    for i in range(attempts):
        try:
            r = _get_session().get(url, params=params, timeout=TIMEOUT)
        except Exception:
            _sleep_backoff(i)
            continue
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            _rotate_token_on_session()
            reset = int(r.headers.get("X-RateLimit-Reset", "0") or 0)
            wait = max(1, reset - int(time.time())) + 2
            time.sleep(min(wait, 60))
            continue
        if r.status_code == 429 or (r.status_code == 403 and "secondary rate limit" in r.text.lower()):
            retry_after = int(r.headers.get("Retry-After", "0") or 0)
            _rotate_token_on_session()
            time.sleep(retry_after or min(30, (2 ** i) + random.random()))
            continue
        if r.status_code in (500, 502, 503, 504):
            _sleep_backoff(i)
            continue
        if r.ok:
            try:
                return r.json()
            except ValueError:
                return None
        _sleep_backoff(i)
    return None

def get_top_repositories(limit=200):
    repos = []
    page = 1
    per_page = 100
    while len(repos) < limit:
        url = f"{BASE_URL}/search/repositories"
        params = {"q": "stars:>1", "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
        data = _safe_get_json(url, params=params)
        if not data or "items" not in data or not data["items"]:
            break
        repos.extend(data["items"])
        page += 1
        time.sleep(0.1)
    return repos[:limit]

def get_closed_prs_count(owner, repo):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
    params = {"state": "closed", "per_page": 100, "page": 1}
    for attempt in range(3):
        try:
            session = _get_session()
            r = session.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
                _rotate_token_on_session()
                reset = int(r.headers.get("X-RateLimit-Reset", "0") or 0)
                wait = max(1, reset - int(time.time())) + 2
                time.sleep(min(wait, 60))
                continue
            if not r.ok:
                if attempt == 2:
                    print(f"[ERROR] {owner}/{repo}: HTTP {r.status_code}")
                    return 0
                time.sleep(2 ** attempt)
                continue
            link_header = r.headers.get("Link", "")
            if "rel=\"last\"" in link_header:
                import re
                match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
                if match:
                    last_page = int(match.group(1))
                    params_last = params.copy()
                    params_last["page"] = last_page
                    r_last = session.get(url, params=params_last, timeout=TIMEOUT)
                    if r_last.ok:
                        last_data = r_last.json()
                        items_last_page = len(last_data) if isinstance(last_data, list) else 0
                        total = (last_page - 1) * 100 + items_last_page
                        print(f"[COUNT] {owner}/{repo} -> {total} PRs")
                        return total
            data = r.json()
            if isinstance(data, list):
                count = len(data)
                print(f"[COUNT] {owner}/{repo} -> {count} PRs (página única)")
                return count
            return 0
        except Exception as e:
            if attempt == 2:
                print(f"[ERROR] {owner}/{repo}: {e}")
                return 0
            time.sleep(2 ** attempt)
    return 0

def _parse_dt(iso_str):
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

def get_reviews(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    data = _safe_get_json(url) or []
    return [rv for rv in data if isinstance(rv, dict)]

def get_issue_comments(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    data = _safe_get_json(url) or []
    return [c for c in data if isinstance(c, dict)]

def get_review_comments(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    data = _safe_get_json(url) or []
    return [c for c in data if isinstance(c, dict)]

def get_pr_files(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    data = _safe_get_json(url) or []
    return [f for f in data if isinstance(f, dict)]

def get_pr_detail(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    return _safe_get_json(url) or {}

def get_participants_count(owner, repo, pr_number):
    users = set()
    pr = get_pr_detail(owner, repo, pr_number)
    if pr.get("user") and pr["user"].get("login"):
        users.add(pr["user"]["login"])
    for rv in get_reviews(owner, repo, pr_number):
        u = (rv.get("user") or {}).get("login")
        if u:
            users.add(u)
    for c in get_issue_comments(owner, repo, pr_number):
        u = (c.get("user") or {}).get("login")
        if u:
            users.add(u)
    for c in get_review_comments(owner, repo, pr_number):
        u = (c.get("user") or {}).get("login")
        if u:
            users.add(u)
    return len(users)

def get_pull_requests(owner, repo, max_deep=MAX_DEEP_PRS_PER_REPO):
    results = []
    page = 1
    per_page = 100
    deep_analyzed = 0
    print(f"[início] {owner}/{repo} - limite: {max_deep} PRs", flush=True)
    while True:
        if max_deep is not None and deep_analyzed >= max_deep:
            print(f"[limite] {owner}/{repo} - atingiu {max_deep} PRs analisados", flush=True)
            break
        url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {"state": "closed", "per_page": per_page, "page": page}
        data = _safe_get_json(url, params=params)
        if not data or not isinstance(data, list) or not data:
            break
        for pr in data:
            merged_at = pr.get("merged_at")
            closed_at = pr.get("closed_at")
            created_at = pr.get("created_at")
            if not created_at or not (merged_at or closed_at):
                continue
            end_raw = merged_at or closed_at
            try:
                duration_h = (_parse_dt(end_raw) - _parse_dt(created_at)).total_seconds() / 3600.0
            except Exception:
                continue
            if duration_h < 1.0:
                continue
            if max_deep is not None and deep_analyzed >= max_deep:
                print(f"[limite] {owner}/{repo} - parou em {deep_analyzed} PRs", flush=True)
                return results
            reviews = get_reviews(owner, repo, pr["number"])
            if len(reviews) < 1:
                continue
            deep_analyzed += 1
            if deep_analyzed % 100 == 0:
                print(f"[progresso] {owner}/{repo}: {deep_analyzed}/{max_deep} PRs processados", flush=True)
            comments_total = int(pr.get("comments", 0)) + int(pr.get("review_comments", 0))
            participants_count = get_participants_count(owner, repo, pr["number"])
            files = get_pr_files(owner, repo, pr["number"])
            num_files = len(files)
            additions = sum(int(f.get("additions", 0) or 0) for f in files)
            deletions = sum(int(f.get("deletions", 0) or 0) for f in files)
            description_length = len(pr.get("body") or "")
            results.append({
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
                "participants_count": participants_count,
                "comments_count": comments_total,
                "reviews_count": len(reviews),
            })
        page += 1
        time.sleep(0.1)
    print(f"[fim] {owner}/{repo}: {len(results)} PRs coletados", flush=True)
    return results

def iter_top_repositories_sorted():
    page = 1
    per_page = 100
    seen = set()
    while True:
        url = f"{BASE_URL}/search/repositories"
        params = {"q": "stars:>1", "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
        data = _safe_get_json(url, params=params)
        if not data or "items" not in data or not data["items"]:
            break
        for r in data["items"]:
            key = f"{r['owner']['login']}/{r['name']}"
            if key in seen:
                continue
            seen.add(key)
            yield r
        page += 1
        time.sleep(0.1)

def _eligibility_task(repo_json):
    owner = repo_json["owner"]["login"]
    name = repo_json["name"]
    key = f"{owner}/{name}"
    total_closed = get_closed_prs_count(owner, name)
    return key, owner, name, total_closed, repo_json.get("stargazers_count", 0), repo_json.get("html_url", "")

def _collect_prs_task(item):
    owner, name, key = item["owner"], item["repo"], item["key"]
    prs = get_pull_requests(owner, name, max_deep=MAX_DEEP_PRS_PER_REPO)
    return key, prs

if __name__ == "__main__":
    start_ts = datetime.now()
    print(f"{start_ts.isoformat()} | cwd={os.getcwd()}", flush=True)
    TARGET = 200
    ELIGIBILITY_WORKERS = int(os.getenv("ELIGIBILITY_WORKERS", "2"))
    PR_WORKERS = int(os.getenv("PR_WORKERS", "2"))
    eligible = []
    repo_meta = {}
    print("Buscando repositórios", flush=True)
    with ThreadPoolExecutor(max_workers=ELIGIBILITY_WORKERS) as pool:
        futures = []
        INFLIGHT_MAX = ELIGIBILITY_WORKERS * 4
        for r in iter_top_repositories_sorted():
            if len(eligible) >= TARGET:
                break
            futures.append(pool.submit(_eligibility_task, r))
            if len(futures) >= INFLIGHT_MAX:
                done = []
                for f in as_completed(futures):
                    done.append(f)
                    if len(done) >= ELIGIBILITY_WORKERS:
                        break
                for f in done:
                    try:
                        key, owner, name, total_closed, stars, html_url = f.result()
                        print(f"[eligibility] {key} -> closed PRs={total_closed}", flush=True)
                        if total_closed >= 100 and len(eligible) < TARGET:
                            repo_meta[key] = {"stars": stars, "html_url": html_url}
                            eligible.append({"owner": owner, "repo": name, "key": key, "total_closed_prs": total_closed})
                    except Exception as e:
                        print(f"[eligibility-error] {e}", flush=True)
                futures = [f for f in futures if not f.done()]
        for f in as_completed(futures):
            if len(eligible) >= TARGET:
                break
            try:
                key, owner, name, total_closed, stars, html_url = f.result()
                print(f"[eligibility] {key} -> closed PRs={total_closed}", flush=True)
                if total_closed >= 100 and len(eligible) < TARGET:
                    repo_meta[key] = {"stars": stars, "html_url": html_url}
                    eligible.append({"owner": owner, "repo": name, "key": key, "total_closed_prs": total_closed})
            except Exception as e:
                print(f"[eligibility-error] {e}", flush=True)
    print(f"[main] Elegíveis reunidos: {len(eligible)} (alvo={TARGET})", flush=True)
    if len(eligible) < TARGET:
        print("[main] AVISO: não foi possível atingir 200 dentro do limite da Search API.", flush=True)
    dataset = []
    if eligible:
        print(f"[collect] Iniciando coleta de PRs em {len(eligible)} repositórios (workers={PR_WORKERS})...", flush=True)
        with ThreadPoolExecutor(max_workers=PR_WORKERS) as pool:
            future_map = {pool.submit(_collect_prs_task, item): item for item in eligible}
            processed = 0
            for fut in as_completed(future_map):
                item = future_map[fut]
                key = item["key"]
                try:
                    k, prs = fut.result()
                    meta = repo_meta.get(k, {"stars": 0, "html_url": ""})
                    for pr in prs:
                        pr.update({"stars": meta["stars"], "html_url": meta["html_url"], "total_closed_prs": item["total_closed_prs"]})
                        dataset.append(pr)
                except Exception as e:
                    print(f"[collect-error] {key}: {e}", flush=True)
                processed += 1
                if processed % 10 == 0 or processed == len(eligible):
                    print(f"[collect] Progresso: {processed}/{len(eligible)} repositórios", flush=True)
    columns = [
        "owner", "repo_name", "repo", "stars", "html_url", "total_closed_prs",
        "pr_number", "state", "num_files", "additions", "deletions",
        "analysis_time_hours", "description_length",
        "participants_count", "comments_count", "reviews_count",
    ]
    df = pd.DataFrame(dataset, columns=columns)
    df.to_csv(OUTPUT_FILENAME, index=False)
    print(f"[output] Arquivo gravado: {os.path.abspath(OUTPUT_FILENAME)} | linhas={len(df)} | vazio={df.empty}", flush=True)
    print(f"[end] {datetime.now().isoformat()} | elegíveis={len(eligible)} | PRs={len(df)}", flush=True)
