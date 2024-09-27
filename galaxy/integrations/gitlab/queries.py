from datetime import datetime, timedelta
from typing import Optional

__all__ = ["Queries"]


class Queries:
    @staticmethod
    def get_repos(after: Optional[str] = None) -> dict:
        query = """
            query Projects($after: String) {
                projects(membership: true, after: $after) {
                    nodes {
                        id
                        createdAt
                        lastActivityAt
                        languages {
                            name
                        }
                        name
                        archived
                        visibility
                        description
                        webUrl
                        mergeRequests {
                            count
                        }
                        issues {
                            count
                        }
                        openIssuesCount
                        openMergeRequestsCount
                        fullPath
                        starCount
                        updatedAt
                        repository {
                            rootRef
                            blobs(first: 1, paths: ["README.md", "README.rst", "README"]) {
                                nodes {
                                    rawBlob
                                    path
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
        """

        variables = {"after": after}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_group_repos(group: dict, after: Optional[str] = None) -> dict:
        query = """
            query Group($fullPath: ID!, $after: String) {
                group(fullPath: $fullPath) {
                    name
                    projects(after: $after) {
                        nodes {
                            id
                            createdAt
                            lastActivityAt
                            languages {
                                name
                            }
                            name
                            archived
                            visibility
                            description
                            webUrl
                            mergeRequests {
                                count
                            }
                            issues {
                                count
                            }
                            openIssuesCount
                            openMergeRequestsCount
                            fullPath
                            starCount
                            updatedAt
                            repository {
                                rootRef
                                blobs(first: 1, paths: ["README.md", "README.rst", "README"]) {
                                    nodes {
                                        rawBlob
                                        path
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

        variables = {"fullPath": group["full_path"], "after": after}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_issues(repository: dict, after: Optional[str] = None, history_days: Optional[int] = 30) -> dict:
        # Calculate the timestamp for filtering issues
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()

        query = """
            query Project($fullPath: ID!, $after: String, $updatedAfter: Time) {
                project(fullPath: $fullPath) {
                    name
                    issues(after: $after, last: 100, updatedAfter: $updatedAfter) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                id
                                descriptionHtml
                                createdAt
                                updatedAt
                                closedAt
                                webUrl
                                author {
                                    id
                                    username
                                }
                                title
                                state
                                labels {
                                    edges {
                                        node {
                                            title
                                        }
                                    }
                                }
                                assignees {
                                    edges {
                                        node {
                                            id
                                            username
                                            state
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        # Add the updatedAfter variable to filter issues by the updated timestamp
        variables = {"fullPath": repository["fullPath"], "after": after, "updatedAfter": history_days_timestamp}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_merge_requests(
        repository: dict, after: Optional[str] = None, last: int = 100, history_days: Optional[int] = 30
    ) -> dict:
        # Calculate the timestamp for filtering merge requests
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()

        query = """
            query Project($fullPath: ID!, $after: String, $updatedAfter: Time) {
                project(fullPath: $fullPath) {
                    mergeRequests(after: $after, last: 100, updatedAfter: $updatedAfter) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                id
                                createdAt
                                updatedAt
                                mergedAt
                                title
                                descriptionHtml
                                webUrl
                                author {
                                    id
                                    username
                                }
                                commitCount
                                state
                                labels {
                                    edges {
                                        node {
                                            title
                                        }
                                    }
                                }
                                assignees {
                                    edges {
                                        node {
                                            id
                                            username
                                            state
                                        }
                                    }
                                }
                                reviewers {
                                    edges {
                                        node {
                                            id
                                            username
                                        }
                                    }
                                }
                                sourceBranch
                                targetBranch
                                diffStatsSummary {
                                    additions
                                    deletions
                                    changes
                                    fileCount
                                }
                                commits(last: 1) {                  # Fetch the latest commit
                                    edges {
                                        node {
                                            sha # The commit hash
                                            message # Optional: the commit message
                                            authoredDate # Optional: when the commit was authored
                                        }
                                    }
                                }
                                pipelines(last: 1) {               # Fetch the latest pipeline run
                                    edges {
                                        node {
                                            id
                                            status
                                            createdAt
                                            updatedAt
                                            startedAt
                                            finishedAt
                                            sha
                                            duration
                                            ref
                                            user {
                                                username
                                            }
                                            triggeredByPath
                                            failureReason
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

        """

        # Add the updatedAfter variable to filter merge requests by the updated timestamp
        variables = {
            "fullPath": repository["fullPath"],
            "last": last,
            "after": after,
            "updatedAfter": history_days_timestamp,
        }

        return {"query": query, "variables": variables}

    @staticmethod
    def get_pipelines(repository: dict, after: Optional[str] = None, history_days: Optional[int] = 30) -> dict:
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()
        query = """
           query Project($fullPath: ID!, $after: String, $updatedAfter: Time) {
            project(fullPath: $fullPath) {
                pipelines(last: 100, after: $after, updatedAfter: $updatedAfter) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            status
                            createdAt
                            updatedAt
                            startedAt
                            finishedAt
                            sha
                            jobs {
                                edges {
                                    node {
                                        id
                                        name
                                        status
                                        createdAt
                                        startedAt
                                        finishedAt
                                        duration
                                        failureMessage
                                        retried
                                        triggered
                                        allowFailure
                                        stage {
                                            name
                                        }
                                        project {
                                            name
                                        }
                                        pipeline {
                                            id
                                            ref
                                        }
                                    }
                                }
                            }
                            duration
                            failureReason
                            ref
                            triggeredByPath
                            user {
                                id
                                username
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {"fullPath": repository["fullPath"], "after": after, "updatedAfter": history_days_timestamp}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_environments(repository: dict, after: Optional[str] = None) -> dict:
        query = """
        query Project($fullPath: ID!, $after: String) {
            project(fullPath: $fullPath) {
                environments(last: 20, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            name
                            externalUrl
                            state
                            createdAt
                            updatedAt
                        }
                    }
                }
            }
        }
        """
        variables = {"fullPath": repository["fullPath"], "after": after}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_deployments(repository: dict, environment: dict, after: Optional[str] = None) -> dict:
        query = """
            query Project($fullPath: ID!, $environmentName: String!, $after: String) {
                project(fullPath: $fullPath) {
                    environment(name: $environmentName) {
                        id
                        name
                        externalUrl
                        state
                        deployments(last: 100, after: $after) {
                            pageInfo {
                                hasNextPage
                                endCursor
                            }
                            edges {
                                node {
                                    iid
                                    id
                                    status
                                    job {
                                        id
                                        name
                                        refName
                                        pipeline {
                                            id
                                            commit {
                                                id
                                                message
                                                shortId
                                                title
                                                author {
                                                    name
                                                    username
                                                    email
                                                }
                                            }
                                        }
                                    }
                                    triggerer {
                                        id
                                        name
                                        username
                                    }
                                    createdAt
                                    finishedAt
                                    updatedAt
                                }
                            }
                        }
                        createdAt
                        updatedAt
                    }
                }
            }
        """
        variables = {"fullPath": repository["fullPath"], "environmentName": environment, "after": after}
        return {"query": query, "variables": variables}

    @staticmethod
    def get_group(group: str, after: Optional[str] = None) -> dict:
        query = """
            query Groups($after: String, $search: String) {
              groups(after: $after, search: $search) {
                nodes {
                  id
                  name
                  description
                  webUrl
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }

        """

        variables = {"search": group, "after": after}

        return {"query": query, "variables": variables}

    def get_users(self, group_id: str, after: Optional[str] = None) -> dict:
        query = """
            query Users($after: String, $group_id: GroupID!) {
              users(after: $after, groupId: $group_id) {
                nodes {
                  id
                  name
                  username
                  groupMemberships {
                    edges {
                      node {
                        id
                        expiresAt
                        accessLevel {
                          integerValue
                          stringValue
                        }
                        group {
                          id
                          name
                        }
                      }
                    }
                  }
                  state
                  organization
                  commitEmail
                  groupCount
                  createdAt
                  publicEmail
                  webUrl
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
        """

        variables = {"group_id": group_id, "after": after}

        return {"query": query, "variables": variables}

    def get_user(self) -> dict:
        query = """
            {
              currentUser {
                id
                username
                name
                email
                organization
              }
            }
        """
        variables = {}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_user_by_username(username: str) -> dict:
        query = """
            query User($username: String!) {
              user(username: $username) {
                id
                username
                name
                email
                organization
                webUrl
                createdAt
                state
                publicEmail
                groupMemberships {
                  edges {
                    node {
                      group {
                        id
                        name
                      }
                      accessLevel {
                        integerValue
                        stringValue
                      }
                      expiresAt
                    }
                  }
                }
              }
            }
        """
        variables = {"username": username}

        return {"query": query, "variables": variables}
