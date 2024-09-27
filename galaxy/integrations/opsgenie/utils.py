from dateutil.parser import isoparse
from datetime import datetime, timezone


def map_users_to_teams(team_users):
    flat_users = {}
    for team in team_users:
        team_id = team.get("id")
        for member in team.get("members", []):
            user_id = member.get("user", {}).get("id")
            if not user_id:
                continue
            if user_id in flat_users:
                if team_id not in flat_users[user_id]:
                    flat_users[user_id].append(team)
            else:
                flat_users[user_id] = [team]
    return flat_users


def flatten_team_timeline(schedules):
    for schedule in schedules:
        if not schedule.get("enabled"):
            continue

        # Flatten all ongoing and future time-periods across all rotations into a single list
        schedule_rotations = schedule.get("timeline", {}).get("finalTimeline", {}).get("rotations", [])
        team_timeline = [
            period
            for rotation in schedule_rotations
            for period in rotation.get("periods", [])
            if period.get("type") and (period.get("type") != "historical")
        ]
    return team_timeline


def get_user_on_call_teams(user):
    teams_on_call = []
    for team in user["teams"]:
        ongoing_periods = [
            period
            for period in team["timeline"]
            if isoparse(period["startDate"]) <= isoparse(period["endDate"]) <= isoparse(period["endDate"])
        ]
        user_on_call = user["id"] in [period["recipient"]["id"] for period in ongoing_periods]
        if user_on_call:
            teams_on_call.append(team["id"])

    return teams_on_call


def get_user_next_on_call_shift(user):
    # Initialize the variable to hold the next shift (start with None)
    next_shift = {"startDate": None, "endDate": None, "teamId": None}

    # Get the current time for comparison, making it offset-aware
    now = datetime.now(timezone.utc)

    # Iterate over all the teams the user is part of
    for team in user["teams"]:
        # Iterate over all periods in the team's timeline
        for period in team["timeline"]:
            # Parse the start and end dates of the period (usually offset-aware)
            start_date = isoparse(period["startDate"])

            # Check if the user's ID is in the list of recipients and the period is in the future
            if user["id"] == period["recipient"]["id"] and start_date > now:
                # If next_shift is not set or the start_date is earlier than the current next_shift, update next_shift
                if next_shift["startDate"] is None or start_date < isoparse(next_shift["startDate"]):
                    next_shift = {"startDate": period["startDate"], "endDate": period["endDate"], "teamId": team["id"]}

    # Return the next shift if found, otherwise return an empty dictionary
    return next_shift
