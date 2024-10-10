# Galaxy

Galaxy framework is the integrations framework for Rely.io. This framework allow you integrations 3rd party API's
with rely app in a very simple fashion. The framework is built using python, and it is designed to have reusable components,
so the integrations can be easily added to the framework. Galaxy uses JQ syntax to map the retrieved data from the 3rd party API's
into the Rely data model.

# Installation

## Pre-requisites

The plugin you'll be connecting to must already exist in your Rely.io organization account.

### Creating the plugin

In your Rely application, go to Portal Builder > Plugins and select "Add Data Source". Select the tool you'll be using and tick the "Is your plugin self hosted?" option. Fill the required information and submit.

### Obtaining the plugin token

The plugin token connects your plugin to our API and allows authenticated communication to happen between the two.

There are 2 ways to do this.

#### In app

Select "View details" on the plugin you're using and move to the "Self-hosted instructions" tab. You'll notice there's a command to create a Kubernetes secret that already makes use of your token. You may extract the token from here or simply use the command directly in step 2 of the Helm install detailed below.

#### Programmatically

Firstly obtain a personal long lived token by going to your organization's Settings and clicking "Generate an API key". This key will be used to communicate with our API.

Select "View details" on the plugin you're using and copy the plugin's ID.

Now in a terminal, make an API call to our API replacing the variables with the obtained values

```bash
curl --request GET --url https://magneto.rely.io/api/v1/legacy/plugins/{PLUGIN_ID}/token --header 'Authorization: Bearer {API_KEY}'
```

And now you have obtained the plugin token to use during installation.

## Helm

### Fresh Install

1. Create a Kubernetes namespace (alternatively, you may skip this step and use a different workspace in step 2)

   ```bash
   kubectl create namespace rely-galaxy
   ```

2. Create a `my_values.yaml` file (name isn't important) with the variables we need to setup on the chart, example below:

   ```yaml
   env:
     RELY_API_TOKEN: the_rely_api_token
     RELY_API_URL: https://magneto.rely.io
     RELY_INTEGRATION_ID: "1234567"
     RELY_INTEGRATION_TYPE: pagerduty
   ```
   This values will run galaxy in `daemon` mode with a `60` minutes schedule interval. without relying on kubernetes cronjob.
   If we want to run galaxy in `cronjob` mode (by default if we don't set the `RELY_INTEGRATION_EXECUTION_TYPE`), we can remove the `RELY_INTEGRATION_EXECUTION_TYPE` and `RELY_INTEGRATION_DAEMON_INTERVAL` values.
   Then the kubernetes cronjob will be created and run the integration every interval of time according to the `schedule` property in the yaml value file (by default the schedule is set to run each 59 minutes).

3. Install the **Rely.io Galaxy Framework** helm chart:

   ```bash
   helm upgrade --install -f my_values.yaml \
     relyio-galaxy \
     oci://registry-1.docker.io/devrelyio/galaxy-helm \
     -n rely-galaxy
   ```

  INFO: Instead of creating a yaml file, you can also pass the values directly in the command line:

  ```bash
  helm upgrade --install relyio-galaxy \
    --set env.RELY_API_TOKEN=the_rely_api_token \
    --set env.RELY_API_URL=https://magneto.rely.io \
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set env.RELY_INTEGRATION_TYPE=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy
  ```

### Upgrade

#### To the latest version

```bash
helm upgrade -f my_values.yaml \
  relyio-galaxy \
  oci://registry-1.docker.io/devrelyio/galaxy-helm \
  -n rely-galaxy
```
or

```bash
helm upgrade relyio-galaxy \
    --set env.RELY_API_TOKEN=the_rely_api_token \
    --set env.RELY_API_URL=https://magneto.rely.io \
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set env.RELY_INTEGRATION_TYPE=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy
```

#### To a specific version

```bash
helm upgrade -f my_values.yaml \
  relyio-galaxy \
  oci://registry-1.docker.io/devrelyio/galaxy-helm \
  -n rely-galaxy \
  --version 1.0.0
```
or

```bash
helm upgrade relyio-galaxy \
    --set env.RELY_API_TOKEN=the_rely_api_token \
    --set env.RELY_API_URL=https://magneto.rely.io \
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set env.RELY_INTEGRATION_TYPE=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy \
    --version 1.0.0
```

### Configuration

#### Required variables

Helm chart requires the following values to be set or it will fail to install:

- `env.RELY_API_URL`: The rely api url, ex: https://magneto.rely.io/
- `env.RELY_API_TOKEN`: Go to rely app and get the token for the plugin installation
- `env.RELY_INTEGRATION_TYPE`: The name of the integration, ex: gitlab
- `env.RELY_INTEGRATION_ID`: Go to rely app and get the rely integration installation id

These are the minimum values that need to be set for the framework to work. You can also set other values that are in the [`values.yaml`](deploy/helm/galaxy/values.yaml) file.

Additionally, you can set the following values:

- `env.RELY_INTEGRATION_EXECUTION_TYPE`: The execution type of the integration. The default value is `cronjob`. If you want to run the integration in daemon mode you need to set this value to `daemon`.
- `env.RELY_INTEGRATION_DAEMON_INTERVAL`: The interval in minutes that the integration will run in daemon mode. The default value is `60`.
- `schedule`: The cronjob schedule for the integration. The default value is `59 * * * *`.

<br/>

> **NOTE** <br/>
> Depending on the integration you are using you might need to set other values. You can find the values needed for each integration in its own documentation.

## Docker

You can simply run the framework by:

```bash
docker run --env-file .env devrelyio/galaxy:latest
```

The content of the env file is as follows:

```dotenv
RELY_INTEGRATION_TYPE=<the name of the integration, ex: gitlab>
RELY_API_URL=https://magneto.rely.io/
RELY_API_TOKEN=<go to rely app and get the token for the plugin installation>
RELY_INTEGRATION_ID=<go to rely app and get the rely integration installation id>
```

# Development

## How to install the Galaxy CLI

```bash
git clone
cd galaxy
make install
galaxy --help
```

## How to run the Galaxy Framework

To run an integration you need to deploy the framework with the proper configuration. The configuration can be done by either
setting the environment variables or by feeding the framework with a configuration files. If you want to use the configuration files,
you need to create a file called `config.yaml` and pass the path to the file in cli options. The file should look like this:

```yaml
rely:
  token: "<your_rely_integration_token>"
  url: "<rely_api_url>"
integration:
  # The identifier of this integration instance.
  id: "<rely_integration_id>"
  # The type of the integration.
  type: "<rely_integration_type>"
# The execution type of the integration.
  executionType: "<rely_integration_execution_type>"
  scheduledInterval: 60
  defaultModelMappings: {}
  properties:
    "<integration_property_key>": "<integration_property_value>"

```

You can also set the environment variables, you can find all the environment variables for the framework and each of
the integrations in the [`env.example`](env.example) file.

Once you choose how to configure the framework and have all the configs needed for the integration, you need to deploy the docker image.

When you run the integration it will first a load config file - either the one provided in the config params or the default one.
Then environment variables will be loaded and a env substitution is done against the config file.
Finally, it will load the integration configuration from the Rely API and then it will run the integration.
If you want to run the integration in dry-run mode you can pass the `--dry-run` flag to the galaxy command and it will not
fetch any config from or create any entity in Rely.

If you are deploying it in a Kubernetes cluster you can use the helm chart provided.

One important thing to note is that can either run the framework in cronjob mode, where you schedule it to run on a certain frequency,
 or you can run it in daemon mode, where you expose the webhooks endpoint for the integration and the framework will use its internal scheduler
to run the jobs with a predefined frequency. The framework default mode is cronjob mode, to run it in daemon mode you need to set the environmental variable
`RELY_INTEGRATION_EXECUTION_TYPE=daemon`.

Galaxy is organized as a monorepo, where each integration is a separate package. The framework is the main package that orchestrates the integrations
and the code is organized in a way that makes it easy to add new integrations. Inside the core folder you have all the framework and the shared code
and inside the integrations folder is the code of each integration. All the integrations are using the same base structure
where you will find a `config.json` file,
a `main.py` file, a `routes.py` file and a folder called `.rely` and another called `tests`.
The `config.json` file is the configuration file for the integration, the `main.py` file is the entry point of the integration,
the `routes.py` is the file where the endpoints of the integration are defined. Inside the `.rely` folder you will find the
`blueprints.json` file, which contains the blueprints for the integration, the `automations.json` file, which is the
automations file for the integration and the `mappings.yaml` file,
that has the JQ mappings use to map the data from the integration to the Rely data model.
The mapper works using JQ, so you can use the JQ syntax to query the data retrieved
from the integration api and transform it to a Rely entity. The `tests` folder contains the tests for the integration.

## Build, Test and Deploy

Use the built-in continuous integration in Galaxy. The CI is configured to run the tests and build the docker image,
the cli package for the framework and the integrations. On every tag the docker image is deployed to the docker hub on
`devrelyio/galaxy:latest` and `devrelyio/galaxy:<tag>` and the cli package is deployed to the PyPI repository of the repo.

## Contributing

If you want to contribute to the framework, you can follow the steps below:

1. Install  the galaxy cli as described above.
2. Run the scaffold  command to create a new plugin.

```bash
galaxy scaffold -i <integration_name>
```

This will create all the base files and wire the integration to the framework. After you have the initial structure you can start coding the integration
by adding the necessary code to collect the data from the api of the integration `client.py` file, the `main.py` file and the `routes.py` file.
You can also add the necessary blueprints, automations and mappings inside the `rely.io` folder.

Once you have all the files in place, you can run the validate the integration by running the command below:

```bash
make validate
```

If you want to test the integration, you can run the command below:

```bash
make test
```

If all the validation and test pass, you can run the integration by running the command below:

```bash
make run
```

Or to run the integration in debug mode:

```bash
make run-debug
```

Don't forget to add the necessary configs to the `.env` file as described above.

If you want instead of using make run the framework using the cli you first need to install the new version by running:

```bash
make
```

and then you can run the framework by running making sure that your .env has the right configuration needed for the integration:

```bash
galaxy run
```

or you can run also run the galaxy in dry-run mode to see the output of the integration without sending the data to Rely:

```bash
galaxy run --dry-run
```

## License

Galaxy is licensed under the [Apache License 2.0](LICENSE).
