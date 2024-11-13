# Galaxy Framework - Integration: Github


## Integration docs Github

This integration is responsible for retrieving data from Github. To retrieve data from Github, the integration uses the Github API. The integration retrieves the following data from Github:

- Teams
- Repositories
- Pull Requests
- Environments
- Deployments
- Workflow Runs

### Configuration

Besides the common configuration, the following environment variables are used to configure the integration:

- `RELY_INTEGRATION_GITHUB_APP_ID`: The app ID for the Github API (**mandatory**)
- `RELY_INTEGRATION_GITHUB_APP_INSTALLATION_ID`: The installation ID for the Github API (**mandatory**)
- `RELY_INTEGRATION_GITHUB_APP_PRIVATE_KEY`: The private key for the Github API (**mandatory**)
- `RELY_INTEGRATION_GITHUB_URL`: The URL for the Github API (**optional**, default: https://api.github.com)
- `DAYS_OF_HISTORY`: The number of days to retrieve the repository history (**optional**, default: 30, min: 1)
- `RELY_INTEGRATION_GITHUB_API_PAGE_SIZE`: The page size for the Github API requests (**optional**, default: 50, min: 1, max: 100)
- `RELY_INTEGRATION_GITHUB_API_TIMEOUT`: The timeout in seconds for the Github API requests (**optional**, default: 60, min: 5)
- `RELY_INTEGRATION_GITHUB_IGNORE_ARCHIVED`: If the integration should ignore archived repositories (**optional**, default: true)
- `RELY_INTEGRATION_GITHUB_IGNORE_OLD`: If the integration should ignore repositories that have not been updated in a long time (triple time of `DAYS_OF_HISTORY`, for the default is 90 days) (**optional**, default: true)

Although some of the previous environment variables are optional, you might need to configure them depending on the Github API usage, as example, if you have a lot of data to retrieve, you might need to decrease the page size and increase the timeout.
