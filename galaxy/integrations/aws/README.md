# Galaxy Framework - Integration: aws


## Integration docs aws

This integration is responsible for retrieving data from AWS.

### Configuration

Besides the common configuration, the following environment variables are used to configure the integration:

- `RELY_AWS_ACCOUNT_ID`: The account ID for the AWS API
- `RELY_AWS_ACCESS_KEY_ID`: The access key ID for the AWS API
- `RELY_AWS_SECRET_ACCESS_KEY`: The secret access key for the AWS API


### Mapping between AWS resources and Galaxy entities

We read tags to link AWS resources to Galaxy entities.

Tags that we look for to link Cloud Resource to an Environment
- service, Service, application, Application, app, App, component, Component

Tags that we look for to link Cloud Resource to a Service
- env, Env, ENV, environment, Environment, ENVIRONMENT, stage, Stage, STAGE
