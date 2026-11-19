#!/usr/bin/env python3
"""Calcula o rank do perfil (mesma fórmula do github-readme-stats) e grava assets/rank.json
no formato do shields.io endpoint."""
import datetime, json, os, sys, urllib.request

USER = os.environ.get("GH_USER", "DiamondDust01")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_FILE", "assets/rank.json")

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestReviewContributions
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

def gql(after=None):
    body = json.dumps({"query": QUERY, "variables": {"login": USER, "after": after}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "User-Agent": "rank-badge", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"Erro GraphQL: {data['errors']}")
    return data["data"]["user"]

def commits_last_year():
    """Conta commits do usuário no último ano pela busca de commits (repos públicos, branch padrão).

    Usado no lugar de contributionsCollection, que retorna 0 quando as contribuições do perfil
    não são computadas pelo GitHub (ex.: contribuições privadas)."""
    since = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    q = f"author:{USER}+author-date:>={since}"
    req = urllib.request.Request(f"https://api.github.com/search/commits?q={q}&per_page=1", headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "rank-badge"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["total_count"]

def stats():
    user, stars, after = None, 0, None
    while True:
        user = gql(after)
        repos = user["repositories"]
        stars += sum(n["stargazerCount"] for n in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    c = user["contributionsCollection"]
    return dict(commits=max(c["totalCommitContributions"], commits_last_year()), reviews=c["totalPullRequestReviewContributions"],
                prs=user["pullRequests"]["totalCount"], issues=user["issues"]["totalCount"],
                stars=stars, followers=user["followers"]["totalCount"])

def rank(s):
    exp_cdf = lambda x: 1 - 2 ** -x
    log_cdf = lambda x: x / (1 + x)
    total_weight = 2 + 3 + 1 + 1 + 4 + 1
    score = (2 * exp_cdf(s["commits"] / 250) + 3 * exp_cdf(s["prs"] / 50) + 1 * exp_cdf(s["issues"] / 25)
             + 1 * exp_cdf(s["reviews"] / 2) + 4 * log_cdf(s["stars"] / 50) + 1 * log_cdf(s["followers"] / 10))
    percentile = (1 - score / total_weight) * 100
    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    return levels[next(i for i, t in enumerate(thresholds) if percentile <= t)], percentile

def main():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN ausente")
    s = stats()
    level, pct = rank(s)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"schemaVersion": 1, "label": "RANK", "message": level, "color": "7C3AED"}, f)
        f.write("\n")
    print(s, level, round(pct, 1))

if __name__ == "__main__":
    main()
