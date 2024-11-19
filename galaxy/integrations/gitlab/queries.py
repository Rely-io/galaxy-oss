from datetime import datetime, timedelta
from typing import Optional

__all__ = ["Queries"]


class Queries:
    @staticmethod
    def get_repos(after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query Repositories($pageSize: Int, $after: String) {
                projects(membership: true, first: $pageSize, after: $after, sort: "createdAt_desc") {
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
                        branchRules {
                            nodes {
                                name
                                isDefault
                                approvalRules {
                                    nodes{
                                        name
                                        approvalsRequired
                                    }
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

        variables = {"after": after, "pageSize": page_size}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_group_repos(group: dict, after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query GroupRepos($fullPath: ID!, $after: String, $pageSize: Int) {
                group(fullPath: $fullPath) {
                    name
                    projects(first: $pageSize, after: $after, sort: ACTIVITY_DESC) {
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
                            branchRules {
                                nodes {
                                    name
                                    isDefault
                                    approvalRules {
                                        nodes{
                                            name
                                            approvalsRequired
                                        }
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

        variables = {"fullPath": group["full_path"], "after": after, "pageSize": page_size}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_issues(repository: dict, after: Optional[str] = None, history_days: int = 30, page_size: int = 50) -> dict:
        # Calculate the timestamp for filtering issues
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()

        query = """
            query Issues($fullPath: ID!, $after: String, $updatedAfter: Time, $pageSize: Int) {
                project(fullPath: $fullPath) {
                    name
                    issues(first: $pageSize, updatedAfter: $updatedAfter, after: $after, sort: CREATED_DESC) {
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
        variables = {
            "fullPath": repository["fullPath"],
            "after": after,
            "updatedAfter": history_days_timestamp,
            "pageSize": page_size,
        }

        return {"query": query, "variables": variables}

    @staticmethod
    def get_merge_requests(
        repository: dict, after: Optional[str] = None, page_size: int = 50, history_days: Optional[int] = 30
    ) -> dict:
        # Calculate the timestamp for filtering merge requests
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()

        query = """
            query MergeRequests($fullPath: ID!, $after: String, $updatedAfter: Time, $pageSize: Int) {
                project(fullPath: $fullPath) {
                    mergeRequests(after: $after, first: $pageSize, updatedAfter: $updatedAfter, sort: CREATED_DESC) {
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
                                activity: notes(filter:ONLY_ACTIVITY) {
                                    nodes {
                                        createdAt
                                        systemNoteMetadata {
                                            action
                                        }
                                    }
                                }
                                comments: notes(filter:ONLY_COMMENTS) {
                                    nodes {
                                        createdAt
                                        author {
                                            id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        variables = {
            "fullPath": repository["fullPath"],
            "pageSize": page_size,
            "after": after,
            "updatedAfter": history_days_timestamp,
        }

        return {"query": query, "variables": variables}

    @staticmethod
    def get_pipelines(
        repository: dict, after: Optional[str] = None, history_days: int = 30, page_size: int = 50
    ) -> dict:
        history_days_timestamp = (datetime.now() - timedelta(days=history_days)).isoformat()
        query = """
            query Pipelines($fullPath: ID!, $after: String, $updatedAfter: Time, $pageSize: Int) {
                project(fullPath: $fullPath) {
                    pipelines(first: $pageSize, after: $after, updatedAfter: $updatedAfter) {
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
        variables = {
            "fullPath": repository["fullPath"],
            "after": after,
            "updatedAfter": history_days_timestamp,
            "pageSize": page_size,
        }

        return {"query": query, "variables": variables}

    @staticmethod
    def get_environments(repository: dict, after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query Environments($fullPath: ID!, $after: String, $pageSize: Int) {
                project(fullPath: $fullPath) {
                    environments(first: $pageSize, after: $after) {
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
        variables = {"fullPath": repository["fullPath"], "after": after, "pageSize": page_size}

        return {"query": query, "variables": variables}

    @staticmethod
    def get_deployments(repository: dict, environment: dict, after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query Deployments($fullPath: ID!, $environmentName: String!, $after: String, $pageSize: Int) {
                project(fullPath: $fullPath) {
                    environment(name: $environmentName) {
                        id
                        name
                        externalUrl
                        state
                        deployments(first: $pageSize, after: $after, orderBy: {createdAt: DESC}) {
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
                                                    email: publicEmail
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
        variables = {
            "fullPath": repository["fullPath"],
            "environmentName": environment,
            "after": after,
            "pageSize": page_size,
        }
        return {"query": query, "variables": variables}

    @staticmethod
    def get_group(group: str, after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query Groups($after: String, $search: String, $pageSize: Int) {
                groups(after: $after, search: $search, first: $pageSize, sort: "createdAt_desc") {
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

        variables = {"search": group, "after": after, "pageSize": page_size}

        return {"query": query, "variables": variables}

    def get_users(self, group_id: str, after: Optional[str] = None, page_size: int = 50) -> dict:
        query = """
            query Users($after: String, $group_id: GroupID!, $pageSize: Int) {
                users(after: $after, groupId: $group_id, first: $pageSize, sort: CREATED_DESC) {
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

        variables = {"group_id": group_id, "after": after, "pageSize": page_size}

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

    @staticmethod
    def get_file(project_path: dict, file_path: str) -> dict:
        query = """
            query GetFile($projectPath: ID!, $filePath: String!) {
                project(fullPath: $projectPath) {
                    repository {
                        blobs(first: 1, paths: [$filePath]) {
                            nodes {
                                id: oid
                                name
                                path
                                size
                                content: rawBlob
                            }
                        }
                    }
                }
            }
        """
        variables = {"projectPath": project_path, "filePath": file_path}

        return {"query": query, "variables": variables}
