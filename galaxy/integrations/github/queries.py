from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any, Optional

__all__ = ["QueryType", "build_graphql_query"]


class QueryType(str, Enum):
    ISSUES = "issues"
    PULL_REQUESTS = "pull_requests"
    DEPLOYMENTS = "deployments"
    REPOSITORY = "repository"
    REPOSITORIES = "repositories"
    MEMBERS = "members"
    TEAMS = "teams"
    TEAM_MEMBERS = "team_members"
    TEAM_REPOS = "team_repos"
    COMMITS = "commits"


def build_graphql_query(query_type: QueryType, **params: Any) -> dict:
    builders_by_query_type = {
        QueryType.ISSUES: _build_issues_query,
        QueryType.PULL_REQUESTS: _build_pull_requests_query,
        QueryType.DEPLOYMENTS: _build_deployments_query,
        QueryType.REPOSITORY: _build_repository_query,
        QueryType.MEMBERS: _build_members_query,
        QueryType.TEAMS: _build_teams_query,
        QueryType.TEAM_MEMBERS: _build_team_members,
        QueryType.TEAM_REPOS: _build_team_repos,
        QueryType.COMMITS: _build_commits_query,
    }

    query, variables = builders_by_query_type[query_type](**params)

    return {"query": query, "variables": variables}


def _build_issues_query(
    repo_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_filter_field: Optional[str] = "created",
    state: Optional[str] = "open",
    labels: Optional[Iterable[str]] = None,
    sort: Optional[str] = "created-desc",
    page_size: int = 50,
    after: Optional[str] = None,
) -> tuple[str, dict[str, int | str | None]]:
    query = """
        query GetIssuesSearch(
            $query: String!
            $pageSize: Int = 50
            $after: String = null
        ) {
            search(query: $query, type: ISSUE, first: $pageSize, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        ... on Issue {
                            databaseId
                            state
                            createdAt
                            closedAt
                            updatedAt
                            labels(last: 100) {
                                nodes {
                                    name
                                    description
                                }
                            }
                            body
                            author {
                                login
                                avatarUrl
                            }
                            assignees(first: 10) {
                                nodes {
                                    login
                                    avatarUrl
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    query_var = (
        "repo:REPO is:issue state:STATE label:LABELS sort:SORT"
        "TIME_FILTER_FIELD:=>START_TIME TIME_FILTER_FIELD:<=END_TIME".replace("repo:REPO", f"repo:{repo_id}")
        .replace("state:STATE", f"state:{state}" if state else "")
        .replace("sort:SORT", f"sort:{sort}" if sort else "")
        .replace("label:LABELS", f"label:{','.join(labels)}" if labels else "")
    )

    if start_time and end_time:
        query_var = query_var.replace(
            "TIME_FILTER_FIELD:=>START_TIME TIME_FILTER_FIELD:<=END_TIME",
            f"{time_filter_field}:{start_time}..{end_time}",
        )
    else:
        query_var = query_var.replace(
            "TIME_FILTER_FIELD:=>START_TIME", f"{time_filter_field}:>={start_time}" if start_time else ""
        ).replace("TIME_FILTER_FIELD:<=END_TIME", f"{time_filter_field}:<={end_time}" if end_time else "")

    variables = {"query": query_var, "pageSize": page_size, "after": after}
    return query, variables


def _build_pull_requests_query(
    repo_id: str,
    states: Optional[Iterable[str]] = None,
    labels: Optional[Iterable[str]] = None,
    page_size: int = 50,
    after: Optional[str] = None,
) -> tuple[str, dict[str, str | None | int | list[str] | Any]]:
    query = """
        query GetPullRequests(
            $owner: String!
            $name: String!
            $labels: [String!] = null
            $states: [PullRequestState!] = null
            $pageSize: Int = 50
            $after: String = null
        ) {
            repository(owner: $owner, name: $name, followRenames: true) {
                pullRequests(
                    first: $pageSize
                    after: $after
                    labels: $labels
                    states: $states
                    orderBy: { field: CREATED_AT, direction: DESC }
                ) {
                    edges {
                        node {
                            number
                            title
                            body
                            createdAt
                            updatedAt
                            closedAt
                            mergedAt
                            state
                            url
                            author {
                                login
                            }
                            comments(first: 25) {
                                edges {
                                    node {
                                        author {
                                            login
                                        }
                                    }
                                }
                            }
                            commits {
                                totalCount
                            }
                            changedFiles
                            labels(first: 15) {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                            reviews(first: 25) {
                                edges {
                                    node {
                                        author {
                                            login
                                        }
                                        state
                                        createdAt
                                    }
                                }
                            }
                            assignees(first: 25) {
                                nodes {
                                    databaseId
                                    login
                                }
                            }
                            additions
                            deletions
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
    """

    owner, name = repo_id.split("/", maxsplit=1)

    variables = {
        "owner": owner,
        "name": name,
        "labels": list(labels) if labels else None,
        "states": list(states or ["MERGED"]),
        "pageSize": page_size,
        "after": after,
    }
    return query, variables


def _build_deployments_query(
    repo_id: str, environments: Optional[Iterable[str]] = None, page_size: int = 50, after: Optional[str] = None
) -> tuple[str, dict[str, str | None | int | list[str] | Any]]:
    query = """
        query GetDeployments(
            $owner: String!
            $name: String!
            $environments: [String!] = null
            $pageSize: Int = 50
            $after: String = null
        ) {
            repository(owner: $owner, name: $name, followRenames: true) {
                deployments(
                    environments: $environments
                    orderBy: { field: CREATED_AT, direction: ASC }
                    last: $pageSize
                    after: $after
                ) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            databaseId
                            description
                            state
                            createdAt
                            updatedAt
                            commit {
                                oid
                                committedDate
                            }
                            environment
                            creator {
                                login
                            }
                            statuses(last: 1) {
                                nodes {
                                    state
                                    createdAt
                                    description
                                }
                            }
                            task
                            ref {
                                name
                            }
                        }
                    }
                }
            }
        }
    """

    owner, name = repo_id.split("/", maxsplit=1)

    variables = {
        "owner": owner,
        "name": name,
        "environments": list(environments) if environments else None,
        "pageSize": page_size,
        "after": after,
    }
    return query, variables


def _build_repository_query(repo_id: str) -> tuple[str, dict[str, Any]]:
    query = """
        query GetRepo($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name, followRenames: true) {
                name
                url
                description
                createdAt
                updatedAt
                isPrivate
                languages(first: 100) {
                  edges {
                    node {
                      name
                    }
                  }
                }
                defaultBranchRef {
                  name
                  target {
                    ... on Commit {
                      file(path: "README.md") {
                        object {
                          ... on Blob {
                            text
                          }
                        }
                      }
                    }
                  }
                }
                primaryLanguage {
                  name
                }
                totalPullRequests: pullRequests {
                  totalCount
                }
                openPullRequests: pullRequests(states: OPEN) {
                  totalCount
                }
                issues: issues {
                  totalCount
                }
                openIssues: issues(states: OPEN) {
                  totalCount
                }
                owner {
                  login
                }
                codeOwners: object(expression: "HEAD:.github/CODEOWNERS") {
                  ... on Blob {
                    text
                  }
                }
                lastCommits: defaultBranchRef {
                  target {
                    ... on Commit {
                      history(first: 5) {
                        nodes {
                          oid
                          message
                          author {
                            name
                            date
                          }
                        }
                      }
                    }
                  }
                }
            }
        }
    """

    owner, name = repo_id.split("/", maxsplit=1)

    variables = {"owner": owner, "name": name}
    return query, variables


def _build_teams_query(owner: str, after: Optional[str] = None, page_size: int = 50) -> tuple[str, dict[str, str]]:
    query = """
        query OrganizationInfo(
            $owner: String!
            $after: String = null
            $pageSize: Int = 50
        ) {
            organization(login: $owner) {
                teams(first: $pageSize, after: $after) {
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    nodes {
                        databaseId
                        name
                        description
                        url
                    }
                }
            }
        }
    """

    variables = {"owner": owner, "after": after, "pageSize": page_size}
    return query, variables


def _build_team_members(
    owner: str, team: str, after: Optional[str] = None, page_size: int = 50
) -> tuple[str, dict[str, str]]:
    query = """
        query GetTeamMembers(
            $owner: String!
            $team: String!
            $pageSize: Int = 50
            $after: String = null
        ) {
            organization(login: $owner) {
                team(slug: $team) {
                    members(first: $pageSize, after: $after) {
                        nodes {
                            databaseId
                            login
                            createdAt
                            updatedAt
                            url
                            email
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
        }
    """

    variables = {"owner": owner, "team": team, "after": after, "pageSize": page_size}
    return query, variables


def _build_team_repos(
    owner: str, team: str, after: Optional[str] = None, page_size: int = 50
) -> tuple[str, dict[str, str]]:
    query = """
        query GetTeamRepos(
            $owner: String!
            $team: String!
            $pageSize: Int = 50
            $after: String = null
        ) {
            organization(login: $owner) {
                team(slug: $team) {
                    repositories(first: $pageSize, after: $after) {
                        nodes {
                            databaseId
                            name
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
        }
    """

    variables = {"owner": owner, "team": team, "after": after, "pageSize": page_size}
    return query, variables


def _build_members_query(
    owner: str, after: Optional[str] = None, page_size: int = 50
) -> tuple[str, dict[str, str | None]]:
    query = """
        query OrganizationMembers($owner: String!, $after: String, $pageSize: Int) {
          organization(login: $owner) {
            membersWithRole(first: $pageSize, after: $after) {
              pageInfo {
                endCursor
                hasNextPage
              }
              edges {
                node {
                  databaseId
                  login
                  name
                  email
                  avatarUrl
                }
                role
              }
            }
          }
        }
    """

    variables = {"owner": owner, "after": after, "pageSize": page_size}
    return query, variables


def _build_commits_query(
    repo_id: str, branch: str, *, after: str | None = None, since: datetime | None = None, page_size: int = 50
) -> tuple[str, dict[str, str]]:
    query = """
        query GetCommits(
            $owner: String!
            $name: String!
            $branch: String!
            $since: GitTimestamp
            $after: String = null
            $pageSize: Int = 50
        ) {
            repository(owner: $owner, name: $name, followRenames: true) {
                commits: object(expression: $branch) {
                    ... on Commit {
                        history(first: $pageSize, after: $after, since: $since) {
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                            nodes {
                                oid
                                committedDate
                                author {
                                    user {
                                        login
                                    }
                                }
                                parents {
                                    totalCount
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    owner, name = repo_id.split("/", maxsplit=1)
    variables = {
        "owner": owner,
        "name": name,
        "branch": branch,
        "after": after,
        "pageSize": page_size,
        "since": since.isoformat() if since is not None else None,
    }
    return query, variables
