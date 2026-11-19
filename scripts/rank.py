#!/usr/bin/env python3
"""Calcula o rank do perfil (mesma fórmula do github-readme-stats) e grava assets/rank.json
no formato do shields.io endpoint."""
import datetime, json, os, sys, urllib.request

USER = os.environ.get("GH_USER", "DiamondDust01")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_FILE", "assets/rank.json")
RANK_TOKEN = os.environ.get("RANK_TOKEN", "")  # PAT opcional: enxerga repos privados/da org e conta todas as branches

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

def gql_raw(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {token}", "User-Agent": "rank-badge", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"Erro GraphQL: {data['errors']}")
    return data["data"]

HISTORY = "history(first: 100, since: $since, author: {id: $uid}, after: %s) { nodes { oid } pageInfo { hasNextPage endCursor } }"
REPOS_Q = """
query($since: GitTimestamp!, $uid: ID!, $after: String) {
  viewer { repositories(first: 20, after: $after, isFork: false, ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
    nodes { nameWithOwner refs(refPrefix: "refs/heads/", first: 100) { nodes { name target { ... on Commit { %s } } } } }
    pageInfo { hasNextPage endCursor }
  } }
}""" % (HISTORY % "null")
BRANCH_Q = """
query($owner: String!, $name: String!, $ref: String!, $since: GitTimestamp!, $uid: ID!, $after: String) {
  repository(owner: $owner, name: $name) { ref(qualifiedName: $ref) { target { ... on Commit { %s } } } }
}""" % (HISTORY % "$after")

def commits_all_branches(token):
    """Commits únicos (por SHA) do último ano em todas as branches de todos os repos visíveis ao token."""
    uid = gql_raw("{ viewer { id } }", {}, token)["viewer"]["id"]
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    shas, after = set(), None
    while True:
        page = gql_raw(REPOS_Q, {"since": since, "uid": uid, "after": after}, token)["viewer"]["repositories"]
        for repo in page["nodes"]:
            owner, name = repo["nameWithOwner"].split("/")
            for br in repo["refs"]["nodes"]:
                hist = (br["target"] or {}).get("history")
                while hist:
                    shas.update(n["oid"] for n in hist["nodes"])
                    if not hist["pageInfo"]["hasNextPage"]:
                        break
                    d = gql_raw(BRANCH_Q, {"owner": owner, "name": name, "ref": "refs/heads/" + br["name"], "since": since,
                                           "uid": uid, "after": hist["pageInfo"]["endCursor"]}, token)
                    hist = d["repository"]["ref"]["target"]["history"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return len(shas)

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
    return dict(commits=max(c["totalCommitContributions"], commits_all_branches(RANK_TOKEN) if RANK_TOKEN else commits_last_year()), reviews=c["totalPullRequestReviewContributions"],
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
