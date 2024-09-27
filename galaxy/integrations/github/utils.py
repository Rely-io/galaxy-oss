def map_users_to_teams(team_to_users: dict[str, dict]) -> dict[str, list]:
    user_to_teams = {}
    try:
        for team_id, users in team_to_users.items():
            for user_login in users:
                if user_login in user_to_teams:
                    user_to_teams[user_login].add(team_id)
                else:
                    user_to_teams[user_login] = {team_id}
    except Exception as e:
        raise e
    return {user_login: list(teams) for user_login, teams in user_to_teams.items()}


def extract_repositories_from_team(team: dict) -> list[dict]:
    repos = team.get("repositories", {}).get("nodes", [])
    return [r["databaseId"] for r in repos]


def extract_team_members_from_team(team: dict) -> list[dict]:
    members = team.get("members", {}).get("nodes", [])
    return [m["login"] for m in members]


def get_inactive_usernames_from_pull_requests(prs: list[dict], users: list):
    inactive_usernames = []

    for pr in prs:
        mentioned_users = {pr.get("author").get("login")}
        mentioned_users.update(u["login"] for u in pr.get("assignees", {}).get("nodes", []))
        mentioned_users.update(u["login"] for u in pr.get("reviews", {}).get("nodes", []))

        inactive_usernames.extend([user_login for user_login in mentioned_users if user_login not in users])

    return inactive_usernames
