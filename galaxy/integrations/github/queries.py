from collections.abc import Iterable
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


def build_graphql_query(query_type: QueryType, **params: Any) -> dict:
    builders_by_query_type = {
        QueryType.ISSUES: _build_issues_query,
        QueryType.PULL_REQUESTS: _build_pull_requests_query,
        QueryType.DEPLOYMENTS: _build_deployments_query,
        QueryType.REPOSITORY: _build_repository_query,
        QueryType.MEMBERS: _build_members_query,
        QueryType.TEAMS: _build_teams_query,
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
    last: int = 100,
    after: Optional[str] = None,
) -> tuple[str, dict[str, int | str | None]]:
    query = """
        query GetIssuesSearch(
            $query: String!
            $last: Int = 100
            $after: String = null
        ) {
            rateLimit {
                cost
                remaining
                limit
            }

            search(query: $query, type: ISSUE, last: $last, after: $after) {
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

    variables = {"query": query_var, "last": last, "after": after}
    return query, variables


def _build_pull_requests_query(
    repo_id: str,
    target_branch: Optional[str] = None,
    source_branch: Optional[str] = None,
    states: Optional[Iterable[str]] = None,
    labels: Optional[Iterable[str]] = None,
    last: int = 50,
    after: Optional[str] = None,
) -> tuple[str, dict[str, str | None | int | list[str] | Any]]:
    query = """
        query GetPullRequests(
            $owner: String!
            $name: String!
            $labels: [String!] = null
            $states: [PullRequestState!] = null
            $last: Int = 100
            $after: String = null
        ) {
            rateLimit {
                cost
                remaining
                limit
            }
            repository(owner: $owner, name: $name, followRenames: true) {
                pullRequests(
                    first: $last
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
                                    }
                                }
                            }
                            assignees(first: 25) {
                                nodes {
                                    databaseId
                                    login
                                }
                            }
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
        "last": last,
        "after": after,
    }
    return query, variables


def _build_deployments_query(
    repo_id: str, environments: Optional[Iterable[str]] = None, last: int = 50, after: Optional[str] = None
) -> tuple[str, dict[str, str | None | int | list[str] | Any]]:
    query = """
        ####################
        # Common
        ####################

        # Rate limit
        fragment rateLimit on RateLimit {
            cost
            remaining
            limit
        }

        # Pagination
        fragment pageInfo on PageInfo {
            hasNextPage
            endCursor
        }

        ####################
        # Deployments
        ####################

        fragment deploymentStatus on DeploymentStatus {
            state
            createdAt
            description
        }

        fragment deployment on Deployment {
            databaseId
            description
            state               # Ongoing, finished, canceled (state of the deployment)
            createdAt
            updatedAt
            commit {
                oid # The source commit hash
                committedDate
            }
            environment
            creator {
                login
            }
            statuses(last: 1) {
                nodes {
                    ...deploymentStatus # This captures the last deployment status (success/failure)
                }
            }
            task
            ref {
                name
            }
        }

        query GetDeployments(
            $owner: String!
            $name: String!
            $environments: [String!] = null
            $last: Int = 100
            $after: String = null
        ) {
            rateLimit {
                ...rateLimit
            }

            repository(owner: $owner, name: $name, followRenames: true) {
                deployments(
                    environments: $environments
                    orderBy: { field: CREATED_AT, direction: ASC }
                    last: $last
                    after: $after
                ) {
                    pageInfo {
                        ...pageInfo
                    }

                    edges {
                        node {
                            ...deployment
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
        "last": last,
        "after": after,
    }
    return query, variables


def _build_repository_query(repo_id: str) -> tuple[str, dict[str, Any]]:
    query = """
        ####################
        # Common
        ####################

        # Rate limit
        fragment rateLimit on RateLimit {
            cost
            remaining
            limit
        }
        query GetRepo(
            $owner: String!
            $name: String!
        ) {
            rateLimit {
                ...rateLimit
            }

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


def _build_teams_query(owner: str, after: Optional[str] = None) -> tuple[str, dict[str, str]]:
    query = """
        query OrganizationInfo($owner: String!) {
          organization(login: $owner) {
            teams(first: 100) {
              nodes {
                databaseId
                name
                description
                url
                repositories {
                  nodes {
                    databaseId
                    name
                  }
                }
                members(first: 100) {
                  nodes {
                    databaseId
                    login
                    createdAt
                    updatedAt
                    url
                    email
                  }
                }
              }
            }
          }
        }
    """

    variables = {"owner": owner}
    return query, variables


def _build_members_query(owner: str, after: Optional[str] = None) -> tuple[str, dict[str, str | None]]:
    query = """
        query OrganizationMembers($owner: String!) {
          organization(login: $owner) {
            membersWithRole(first: 100) {
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

    variables = {"owner": owner, "after": after}
    return query, variables
