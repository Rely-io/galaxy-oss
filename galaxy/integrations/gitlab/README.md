# Galaxy Framework - Integration: Gitlab

## Integration docs Gitlab

This integration is responsible for retrieving data from Gitlab. To retrieve data from Gitlab, the integration uses the Gitlab API. The integration retrieves the following data from Gitlab:

- Groups
- Group Members
- Repositories
- Issues
- Merge Requests
- Pipelines
- Environments
- Deployments
- Jobs

### Configuration

Besides the common configuration, the following environment variables are used to configure the integration:

- `RELY_INTEGRATION_GITLAB_ORGANIZATION`: The organization name for the Gitlab API (**mandatory**)
- `RELY_INTEGRATION_GITLAB_SECRET_TOKEN`: The API token for the Gitlab API (**mandatory**)
- `RELY_INTEGRATION_GITLAB_URL`: The URL for the Gitlab API (**optional**, default: <https://gitlab.com/api>)
- `DAYS_OF_HISTORY`: The number of days to retrieve the repository history (**optional**, default: 30, min: 1)
- `RELY_INTEGRATION_GITLAB_API_PAGE_SIZE`: The page size for the Gitlab API requests (**optional**, default: 50, min: 1, max: 100)
- `RELY_INTEGRATION_GITLAB_API_TIMEOUT`: The timeout in seconds for the Gitlab API requests (**optional**, default: 60, min: 5)
- `RELY_INTEGRATION_GITLAB_IGNORE_ARCHIVED`: If the integration should ignore archived repositories (**optional**, default: true)
- `RELY_INTEGRATION_GITLAB_API_MAX_CONCURRENCY`: The maximum number of concurrent requests to the Gitlab API (**optional**, default: 10, min: 1)
- `RELY_INTEGRATION_GITLAB_FILES_TO_CHECK`: The configuration for the files to check for in the repositories (**optional**, default: ''). Can be a string with the format `file::destination::regex`, where:
  - `file`: The file name to check
  - `destination`: The destination to save the file
  - `regex`: The regex to check the file content (**optional**)

    Additional files to check can be added by separating them with `||`, as example: `file1::destination1::||file2::destination2::regex2`. Also, the regex is optional, if not provided, the integration will check if the file exists. Alternatively, you can provide a json array minified with the files to check, as example: `[{"file": "file1", "destination": "destination1", "regex": "regex1"}, {"file": "file2", "destination": "destination2", "regex": "regex2"}]`.

Although some of the previous environment variables are optional, you might need to configure them depending on the Gitlab API usage, as example, if you have a lot of data to retrieve, you might need to decrease the page size and increase the timeout.
