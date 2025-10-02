import requests
import pandas as pd
from datetime import datetime
import time

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": "token",
    "Accept": "application/vnd.github.v3+json"
}

def get_top_repositories():
    repos = []
    for page in range(1, 3):
        url = f"{BASE_URL}/search/repositories"
        params = {
            "q": "stars:>1",
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
            "page": page
        }
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 200:
            repos.extend(r.json()["items"])
        time.sleep(0.1)
    return repos

def count_merged_closed_prs(owner, repo):
    count = 0
    page = 1
    while True:
        url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
        r = requests.get(url, headers=HEADERS, params={"state": "all", "per_page": 100, "page": page})
        if r.status_code != 200:
            break
        prs = r.json()
        if not prs:
            break
        count += sum(1 for pr in prs if pr["state"] == "closed" or pr.get("merged_at"))
        if len(prs) < 100:
            break
        page += 1
        time.sleep(0.1)
    return count

def get_reviews_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    r = requests.get(url, headers=HEADERS)
    return len(r.json()) if r.status_code == 200 else 0

def get_pr_details(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    r = requests.get(url, headers=HEADERS)
    return r.json() if r.status_code == 200 else None

def get_comments_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    r1 = requests.get(url, headers=HEADERS)
    issue_comments = len(r1.json()) if r1.status_code == 200 else 0

    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    r2 = requests.get(url, headers=HEADERS)
    review_comments = len(r2.json()) if r2.status_code == 200 else 0

    return issue_comments + review_comments

def get_participants_count(owner, repo, pr_number):
    participants = set()

    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/events"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        for event in r.json():
            if event.get("actor"):
                participants.add(event["actor"]["login"])

    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        for comment in r.json():
            if comment.get("user"):
                participants.add(comment["user"]["login"])

    return len(participants)

def collect_valid_prs(owner, repo):
    valid_prs = []
    page = 1

    while True:
        url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
        r = requests.get(url, headers=HEADERS, params={"state": "all", "per_page": 100, "page": page})
        if r.status_code != 200:
            break

        prs = r.json()
        if not prs:
            break

        for pr in prs:
            if not (pr["state"] == "closed" or pr.get("merged_at")):
                continue

            if get_reviews_count(owner, repo, pr["number"]) < 1:
                continue

            created = datetime.fromisoformat(pr["created_at"].replace('Z', '+00:00'))
            closed_str = pr.get("merged_at") or pr.get("closed_at")
            if not closed_str:
                continue
            closed = datetime.fromisoformat(closed_str.replace('Z', '+00:00'))

            if (closed - created).total_seconds() < 3600:
                continue

            pr_details = get_pr_details(owner, repo, pr["number"])
            if not pr_details:
                continue

            pr_data = {
                "repository": f"{owner}/{repo}",
                "pr_number": pr["number"],
                "final_status": "MERGED" if pr.get("merged_at") else "CLOSED",
                "files_changed": pr_details.get("changed_files", 0),
                "additions": pr_details.get("additions", 0),
                "deletions": pr_details.get("deletions", 0),
                "total_changes": pr_details.get("additions", 0) + pr_details.get("deletions", 0),
                "analysis_time_hours": (closed - created).total_seconds() / 3600,
                "description_length": len(pr.get("body") or ""),
                "reviews_count": get_reviews_count(owner, repo, pr["number"]),
                "comments_count": get_comments_count(owner, repo, pr["number"]),
                "participants_count": get_participants_count(owner, repo, pr["number"])
            }

            valid_prs.append(pr_data)
            time.sleep(0.1)

        if len(prs) < 100:
            break
        page += 1

    return valid_prs

if __name__ == "__main__":
    print("Buscando repositórios")
    top_repos = get_top_repositories()

    print("Filtrando repositórios")
    valid_repos = []
    for repo in top_repos:
        owner = repo["owner"]["login"]
        name = repo["name"]
        if count_merged_closed_prs(owner, name) >= 100:
            valid_repos.append(repo)

    print(f"\nColetando PRs de {len(valid_repos)}")
    dataset = []
    for i, repo in enumerate(valid_repos):
        owner = repo["owner"]["login"]
        name = repo["name"]

        repo_prs = collect_valid_prs(owner, name)
        dataset.extend(repo_prs)
        print(f"  Coletados: {len(repo_prs)} PRs válidos")

    if dataset:
        df = pd.DataFrame(dataset)
        df.to_csv("lab3.csv", index=False)
        print(f"\nDataset salvo com {len(df)} PRs em lab3.csv")
        print(f"MERGED: {len(df[df['final_status'] == 'MERGED'])}")
        print(f"CLOSED: {len(df[df['final_status'] == 'CLOSED'])}")
    else:
        print("Nenhum PR válido encontrado!")
