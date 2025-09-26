
import requests, pandas as pd, os, time, random
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

VERBOSE = True
MAX_PAGES_PER_REPO = 10
MAX_PRS_PER_REPO = 100
OUTPUT_FILENAME = "dataset.csv"
GITHUB_TOKEN = "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"
BASE_URL = "https://api.github.com"
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "thiago-oss-research/1.0"}
TIMEOUT = (10, 45)
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=6, connect=6, read=6, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods={"GET"}, respect_retry_after_header=True, raise_on_status=False), pool_connections=100, pool_maxsize=100))
SESSION.headers.update(HEADERS)

def _safe_get_json(url, params=None, attempts=6):
    for i in range(attempts):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT, headers={"Connection": "close"})
        except Exception:
            time.sleep(min(90, (2 ** i) + random.random()))
            continue
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            time.sleep(min(max(1, int(r.headers.get("X-RateLimit-Reset", "0") or 0) - int(time.time())), 120))
            continue
        if r.status_code == 429 or (r.status_code == 403 and "secondary rate limit" in r.text.lower()):
            time.sleep(int(r.headers.get("Retry-After", "0") or 0) or min(90, (2 ** i) + random.random()))
            continue
        if r.status_code in (500, 502, 503, 504):
            time.sleep(min(90, (2 ** i) + random.random()))
            continue
        if r.ok:
            try: return r.json()
            except ValueError: return None
        return None
    return None

def get_top_repositories(limit=200):
    repos = []
    for page in range(1, (limit // 100) + 2):
        url = f"{BASE_URL}/search/repositories?q=stars:>1&sort=stars&order=desc&per_page=100&page={page}"
        data = _safe_get_json(url)
        if not data or "items" not in data: break
        repos.extend(data["items"])
        if len(repos) >= limit: break
        time.sleep(0.1)
    return repos[:limit]

def get_pull_requests(owner, repo):
    prs = []
    for page in range(1, MAX_PAGES_PER_REPO + 1):
        url = f"{BASE_URL}/repos/{owner}/{repo}/pulls?state=closed&per_page=100&page={page}"
        data = _safe_get_json(url)
        if not data or not isinstance(data, list): break
        for pr in data:
            if pr.get("merged_at") is None and pr.get("state") != "closed": continue
            reviews_count = get_reviews_count(owner, repo, pr["number"])
            if reviews_count < 1: continue
            created_raw = pr.get("created_at"); closed_raw = pr.get("merged_at") or pr.get("closed_at")
            if not created_raw or not closed_raw: continue
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            closed_at = datetime.fromisoformat(closed_raw.replace("Z", "+00:00"))
            time_diff = (closed_at - created_at).total_seconds() / 3600.0
            if time_diff < 1: continue
            files_url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr['number']}/files"
            files_data = _safe_get_json(files_url) or []
            num_files = len(files_data)
            additions = sum((f.get("additions") or 0) for f in files_data)
            deletions = sum((f.get("deletions") or 0) for f in files_data)
            comments_count = (pr.get("comments") or 0) + (pr.get("review_comments") or 0)
            participants_count = get_participants_count(owner, repo, pr["number"])
            description_length = len(pr.get("body") or "")
            prs.append({"repo": f"{owner}/{repo}", "pr_number": pr["number"], "state": "merged" if pr.get("merged_at") else "closed", "num_files": num_files, "additions": additions, "deletions": deletions, "analysis_time_hours": time_diff, "description_length": description_length, "participants_count": participants_count, "comments_count": comments_count, "reviews_count": reviews_count})
            if len(prs) >= MAX_PRS_PER_REPO: return prs
        time.sleep(0.1)
    return prs

def get_reviews_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    data = _safe_get_json(url)
    if not data or not isinstance(data, list):
        return 0
    return len(data)

def get_participants_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/events"
    data = _safe_get_json(url)
    if not data or not isinstance(data, list):
        return 0
    users = {event["actor"]["login"] for event in data if event.get("actor")}
    return len(users)

def get_closed_prs_count(owner, repo):

    q = f"repo:{owner}/{repo} is:pr is:closed"
    url = f"{BASE_URL}/search/issues?q={requests.utils.quote(q)}&per_page=1"
    data = _safe_get_json(url)
    if not data:
        return 0
    return data.get("total_count", 0)

if __name__ == "__main__":
    start_ts = datetime.now()
    print(f"[start] {start_ts.isoformat()} | cwd={os.getcwd()}", flush=True)

    top_repos = get_top_repositories(limit=200)
    print(f"[main] Top repos buscados: {len(top_repos)}", flush=True)

    repo_meta = {}
    for r in top_repos:
        key = f"{r['owner']['login']}/{r['name']}"
        repo_meta[key] = {
            "stars": r.get("stargazers_count", 0),
            "html_url": r.get("html_url", "")
        }
        print(f"[main] repo candidato: {key} | stars={repo_meta[key]['stars']}", flush=True)

    # 2) Filtrar elegíveis (>=100 PRs fechados no total do repo)
    eligible = []
    for r in top_repos:
        owner = r["owner"]["login"]
        name = r["name"]
        total_closed = get_closed_prs_count(owner, name)
        print(f"[eligibility] {owner}/{name} -> closed PRs={total_closed}", flush=True)
        if total_closed >= 100:
            eligible.append({
                "owner": owner,
                "repo": name,
                "key": f"{owner}/{name}",
                "total_closed_prs": total_closed
            })

    if not eligible:
        print("[main] Nenhum repositório elegível (>=100 PRs fechados). Encerrando após criar CSV vazio.", flush=True)

    # 3) Coletar PRs qualificados e JUNTAR metadados de repo em cada linha
    dataset = []
    for item in eligible:
        owner, name, key = item["owner"], item["repo"], item["key"]
        prs = get_pull_requests(owner, name)
        meta = repo_meta.get(key, {"stars": 0, "html_url": ""})
        for pr in prs:
            pr.update({"owner": owner, "repo_name": name, "stars": meta["stars"], "html_url": meta["html_url"], "total_closed_prs": item["total_closed_prs"]})
            dataset.append(pr)
    columns = ["owner", "repo_name", "repo", "stars", "html_url", "total_closed_prs", "pr_number", "state", "num_files", "additions", "deletions", "analysis_time_hours", "description_length", "participants_count", "comments_count", "reviews_count"]
    df = pd.DataFrame(dataset, columns=columns)
    try:
        df.to_csv(OUTPUT_FILENAME, index=False)
        print(f"[output] Arquivo gravado: {os.path.abspath(OUTPUT_FILENAME)} | linhas={len(df)} | vazio={df.empty}", flush=True)
    except Exception as e:
        print(f"[output] ERRO ao salvar CSV: {type(e).__name__}: {e}", flush=True)
    print(f"[end] {datetime.now().isoformat()} | verificados={len(top_repos)} | elegíveis={len(eligible)} | PRs={len(df)}", flush=True)
