# Galaxy Framework - Integration: pagerduty


## Integration docs pagerduty

This integration is responsible for retrieving data from PagerDuty.

### Configuration

Besides the common configuration, the following environment variables are used to configure the integration:

- `RELY_PAGERDUTY_API_TOKEN`: The API token for the PagerDuty API
- `RELY_PAGERDUTY_API_URL`: The URL for the PagerDuty API
- `RELY_PAGERDUTY_INTEGRATION_EXECUTION_TYPE`: The execution type of the integration can be either cronjob or daemon
- `RELY_PAGERDUTY_INTEGRATION_DAEMON_INTERVAL`: The interval in minutes at which the integration should run only required if the execution type is daemon
- `DAYS_OF_HISTORY`: The number of days to retrieve the incidents history
