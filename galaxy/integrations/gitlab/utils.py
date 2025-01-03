def map_users_to_groups(group_to_users):
    # Initialize an empty list to store the flattened users
    user_to_groups = {}
    username_to_user_id = {}

    # Iterate over the group_to_users dictionary and aggregate all group memberships
    try:
        for group_id, users in group_to_users.items():
            for user in users:
                user_memberships = user.get("groupMemberships", {}).get("edges", [])

                if user["id"] in user_to_groups:
                    existing_group_ids = set(
                        g.get("node", {}).get("id")
                        for g in user_to_groups[user["id"]]["groupMemberships"]["edges"]
                        if g.get("node", {}).get("id") is not None
                    )
                    user_to_groups[user["id"]]["groupMemberships"]["edges"].extend(
                        g
                        for g in user_memberships
                        if g.get("node", {}).get("id") not in existing_group_ids
                        and g.get("node", {}).get("id") is not None
                    )

                else:
                    user_to_groups[user["id"]] = user
                    username_to_user_id[user["username"]] = user["id"]
    except Exception as e:
        raise e
    return user_to_groups, username_to_user_id


def get_inactive_usernames_from_issues(issues, username_to_user_id):
    inactive_usernames = []
    for issue in issues:
        issue_data = issue.get("node")
        if not issue_data:
            continue

        author = issue_data.get("author")
        if author is None:
            continue

        author_username = author.get("username")
        if author_username and author_username not in username_to_user_id:
            inactive_usernames.append(author_username)

        for edge in issue_data.get("assignees", {}).get("edges", []):
            username = edge.get("node") and edge["node"].get("username")
            if username and username not in username_to_user_id:
                inactive_usernames.append(author_username)

    return inactive_usernames


def get_inactive_usernames_from_merge_requests(merge_requests, username_to_user_id):
    inactive_usernames = []
    for mr in merge_requests:
        mr_data = mr.get("node")
        if not mr_data:
            continue

        author = mr_data.get("author")
        if author is None:
            continue

        author_username = author.get("username")
        if author_username and author_username not in username_to_user_id:
            inactive_usernames.append(author_username)

        for edge in mr_data.get("assignees", {}).get("edges", []):
            username = edge.get("node") and edge["node"].get("username")
            if username and username not in username_to_user_id:
                inactive_usernames.append(author_username)

        for edge in mr_data.get("reviewers", {}).get("edges", []):
            username = edge.get("node") and edge["node"].get("username")
            if username and username not in username_to_user_id:
                inactive_usernames.append(author_username)

    return inactive_usernames


def get_inactive_usernames_from_pipelines(pipelines, username_to_user_id):
    inactive_usernames = []
    for pipeline in pipelines:
        pipeline_data = pipeline.get("node")
        if not pipeline_data:
            continue

        author = pipeline_data.get("user")
        if author is None:
            continue

        author_username = author.get("username")
        if author_username and author_username not in username_to_user_id:
            inactive_usernames.append(author_username)

    return inactive_usernames


def get_inactive_usernames_from_deployments(deployments, username_to_user_id):
    inactive_usernames = []
    for deployment in deployments:
        deployment_data = deployment.get("node")
        if not deployment_data:
            continue

        triggerer = deployment_data.get("triggerer")
        if triggerer is None:
            continue

        triggerer_username = triggerer.get("username")
        if triggerer_username and triggerer_username not in username_to_user_id:
            inactive_usernames.append(triggerer_username)

    return inactive_usernames


def add_user_to_inactive_group(inactive_user, inactive_group_template):
    inactive_user["groupMemberships"]["edges"] = [
        {
            "node": {
                "accessLevel": {"integerValue": None, "stringValue": None},
                "expiresAt": None,
                "group": {"id": inactive_group_template["id"], "name": inactive_group_template["name"]},
                "id": None,
            }
        }
    ]
    return inactive_user


def get_required_reviews(branch_rules: list[dict]) -> dict[str, int]:
    DEFAULT = "default"
    ALL_BRANCHES = "All branches"
    ALL_PROTECTED_BRANCHES = "All protected branches"

    # use of default as branch name for convenience (we can have main, master, etc)
    result = {DEFAULT: 0, ALL_BRANCHES: 0, ALL_PROTECTED_BRANCHES: 0}
    for branch in branch_rules["nodes"]:
        branch_name = branch["name"]
        if branch.get("isDefault", False):
            branch_name = DEFAULT

        approval_rules = branch.get("approvalRules", {}).get("nodes", [])

        # Sum the approvals required for each branch's approval rules
        total_reviews_required = sum(rule.get("approvalsRequired", 0) for rule in approval_rules)

        result[branch_name] = total_reviews_required

    default_reviews = result.get(DEFAULT, 0)
    all_reviews = result.get(ALL_BRANCHES, 0)
    protected_reviews = result.get(ALL_PROTECTED_BRANCHES, 0)

    # Determine the maximum between "All branches" and "All protected branches"
    all_max = max(all_reviews, protected_reviews)

    # Update the default value based on the calculated maximums
    if all_max > default_reviews:
        result[DEFAULT] = all_max
    else:
        result[DEFAULT] = default_reviews + all_max

    return result
