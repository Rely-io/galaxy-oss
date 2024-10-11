from galaxy.integrations.pagerduty.client import PagerdutyClient


async def get_on_call_info(
    client: PagerdutyClient, user: dict, start_time: str, end_time: str
) -> tuple[list[dict], list[dict]]:
    """Fetch current and next on-call info for a user."""
    # Get current on-call status
    current_oncall = await client.get_on_calls(
        params={"user_ids[]": user.get("id"), "time_zone": user.get("time_zone")}
    )

    # Get next on-call status
    next_oncall = await client.get_on_calls(
        params={
            "user_ids[]": user.get("id"),
            "time_zone": user.get("time_zone"),
            "since": start_time,
            "until": end_time,
            "earliest": "true",
        }
    )

    return current_oncall, next_oncall


def update_user_on_call_info(user: dict, current_oncall: list[dict], next_oncall: list[dict]):
    """Update the user dictionary with on-call information."""
    is_oncall = len(current_oncall) > 0
    next_oncall_start = next_oncall[0].get("start") if next_oncall and next_oncall[0] is not None else None
    next_oncall_end = next_oncall[0].get("end") if next_oncall and next_oncall[0] is not None else None

    # Update on-call status if the user is not currently on-call
    if not is_oncall and next_oncall_start is None and next_oncall_end is None:
        is_oncall = True

    # Update user details
    user["oncall_schedule_link"] = (
        ((next_oncall[0] or {}).get("schedule") or {}).get("html_url")
        if next_oncall and next_oncall[0] is not None
        else None
    )
    user["is_currently_oncall"] = is_oncall
    user["next_oncall_start"] = next_oncall_start
    user["next_oncall_end"] = next_oncall_end
