import requests
import pandas as pd
from datetime import datetime
import time
import os

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
BASE_URL = "https://api.github.com"


def get_top_repositories(limit=200):
    repos = []
    page = 1
    while len(repos) < limit:
        url = f"{BASE_URL}/search/repositories?q=stars:>1&sort=stars&order=desc&per_page=100&page={page}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()["items"]
        repos.extend(data)
        page += 1
        if not data:
            break
    return repos[:limit]


def get_pull_requests(owner, repo):
    prs = []
    page = 1
    while True:
        url = f"{BASE_URL}/repos/{owner}/{repo}/pulls?state=closed&per_page=100&page={page}"
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        for pr in data:
            if pr.get("merged_at") is None and pr.get("state") != "closed":
                continue
            reviews_count = get_reviews_count(owner, repo, pr["number"])
            if reviews_count < 1:
                continue
            created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            closed_at = datetime.fromisoformat((pr["merged_at"] or pr["closed_at"]).replace("Z", "+00:00"))
            time_diff = (closed_at - created_at).total_seconds() / 3600
            if time_diff < 1:
                continue

            files_url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr['number']}/files"
            files_data = requests.get(files_url, headers=HEADERS).json()
            num_files = len(files_data)
            additions = sum(f["additions"] for f in files_data)
            deletions = sum(f["deletions"] for f in files_data)
            comments_count = pr["comments"] + pr["review_comments"]
            participants_count = get_participants_count(owner, repo, pr["number"])
            description_length = len(pr["body"] or "")

            prs.append({
                "repo": f"{owner}/{repo}",
                "pr_number": pr["number"],
                "state": "merged" if pr["merged_at"] else "closed",
                "num_files": num_files,
                "additions": additions,
                "deletions": deletions,
                "analysis_time_hours": time_diff,
                "description_length": description_length,
                "participants_count": participants_count,
                "comments_count": comments_count,
                "reviews_count": reviews_count
            })
        page += 1
        time.sleep(1)
    return prs


def get_reviews_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return 0
    return len(r.json())


def get_participants_count(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/events"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return 0
    users = {event["actor"]["login"] for event in r.json() if event.get("actor")}
    return len(users)


if __name__ == "__main__":
    top_repos = get_top_repositories()
    dataset = []
    for repo in top_repos:
        owner = repo["owner"]["login"]
        name = repo["name"]
        prs = get_pull_requests(owner, name)
        if len(prs) >= 100:
            dataset.extend(prs)
    df = pd.DataFrame(dataset)
    df.to_csv("dataset_prs.csv", index=False)
    print(f"Dataset salvo com {len(df)} PRs em dataset_prs.csv")
