# Galaxy

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![CI](https://github.com/Rely-io/galaxy-oss/actions/workflows/release_on_tag.yml/badge.svg?event=release)](https://github.com/Rely-io/galaxy-oss/actions/workflows/release_on_tag.yml)

Galaxy is a solution developed by Rely.io that enables seamless integration of third-party systems with our internal developer portal. With Galaxy, you can leverage existing [integrations](https://www.rely.io/product/integrations) to ingest your data into Rely.io or create custom integrations tailored to your needs.

Built with Python, Galaxy offers reusable components, making it easy to add integrations to the framework. It employs JQ syntax to accurately map data from third-party APIs into the Rely data model.

## Installation

### Pre-requisites

To setup an integration with a third-party tool you must create a plugin for it. If you haven't done it yet, please follow the instructions on the next step "*Creating the plugin*". Otherwise feel free to skip this step.

#### Creating the plugin

In your Rely.io application, go to `Portal Builder` > `Plugins` and select "*Add Data Source*". Select the tool you'll be using and tick the "*Is your plugin self hosted?*" option. Fill the required information and submit.

#### Obtaining the plugin token

The plugin token connects your plugin to our API and allows authenticated communication to happen between the two.

There are 2 ways to do this.

##### In Rely.io

Select *"View details"* on the plugin you want to setup and move to the *"self-hosted instructions"* tab. You'll notice there's a command to create a Kubernetes secret that already makes use of your token. You may extract the token from here or simply use the command directly in step 2 of the Helm install detailed below.

![self-hosted-instructions](images/self-hosted-instructions.png)

##### Programmatically

First obtain a personal long lived token by going to your organization's `Settings` and clicking *"Generate an API key"*. This key will be used to communicate with our API.

Select *"View details"* on the plugin you're using and copy the plugin's ID.

![get-api-token](images/get-api-token.png)

Now in a terminal, make an API call to our API replacing the variables with the obtained values

```bash
  curl --request GET --url https://magneto.rely.io/api/v1/legacy/plugins/{PLUGIN_ID}/token --header 'Authorization: Bearer {API_KEY}'
```

And now you have obtained the plugin token to use during installation.

### Helm

#### Fresh Install

1. Create a Kubernetes namespace (alternatively, you may skip this step and use a different workspace in step 2)

   ```bash
   kubectl create namespace rely-galaxy
   ```

2. Create a `my_values.yaml` file (name isn't important) with the variables we need to setup on the chart, example below:

   ```yaml
   integration:
     type: gitlab

   env:
     RELY_API_TOKEN: the_rely_api_token
     RELY_INTEGRATION_ID: "1234567"

   ```

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
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set integration.type=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy
  ```

#### Upgrade

##### To the latest version

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
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set integration.type=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy
```

##### To a specific version

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
    --set env.RELY_INTEGRATION_ID=1234567 \
    --set integration.type=pagerduty \
    oci://registry-1.docker.io/devrelyio/galaxy-helm \
    -n rely-galaxy \
    --version 1.0.0
```

#### Configuration

##### Required variables

Helm chart requires the following values to be set or it will fail to install:

- `integration.apiUrl`: The rely api url, ex: https://magneto.rely.io/
- `integration.type`: The name of the integration, ex: gitlab

These are the minimum values that need to be set for the framework to work. You can also set other values that are in the [`values.yaml`](deploy/helm/galaxy/values.yaml) file.

Additionally, you can set the following values:

- `integration.executionType`: The execution type of the integration. The default value is `cronjob`. If you want to run the integration in daemon mode you need to set this value to `daemon`.
- `integration.daemonInterval`: The interval in minutes that the integration will run in daemon mode. The default value is `60`.
- `schedule`: The cronjob schedule for the integration. The default value is `59 * * * *`.

###### External Secrets

If we use external secrets with [External Secrets Operator](https://external-secrets.io/) we need to set `externalSecrets.enabled` to `true` and set the `externalSecrets.target` to the name of the secret that contains the values for the `RELY_API_TOKEN` and `RELY_INTEGRATION_ID`. When we use external secrets we can set all values from the secret file set in `target` as env vars in the helm chart if we set `externalSecrets.allAsEnv` to `true`. If we don't set this value to `true` we need to set the values we want to use in the helm chart as env vars in the `envs` section.

Example of external secrets configuration in the `my_values.yaml` file when we want to set all values from the secret file as env vars in the helm chart:

```yaml
externalSecrets
  enabled: true
  target: my-external-secrets
  allAsEnv: true
  envs: []
```

Example of external secrets configuration in the `my_values.yaml` file when we want to set only the `RELY_API_TOKEN` and `RELY_INTEGRATION_ID` values from the secret file as env vars in the helm chart:

```yaml
externalSecrets
  enabled: true
  target: my-external-secrets
  allAsEnv: false
  envs:
    - name: RELY_API_TOKEN
      key: RELY_API_TOKEN
    - name: RELY_INTEGRATION_ID
      key: RELY_INTEGRATION_ID
```

The `envs` section is an array of objects that contains the `name` of the env var that we want to set in the helm chart and the `key` that is the key of the value in the secret file.

The creation of the external secrets are outside of the scope of this documentation, but for the previous examples we can assume as example of an `ExternalSecret` resource configuration, that would be created prior to the helm chart install, look like this:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-vault-secrets
  namespace: rely-galaxy
spec:
  refreshInterval: "5m"
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: my-external-secrets
    creationPolicy: Owner
  data:
    - secretKey: RELY_API_TOKEN
      remoteRef:
        key: "secret/data/rely"
        property: rely_api_token
    - secretKey: RELY_INTEGRATION_ID
      remoteRef:
        key: "secret/data/rely"
        property: rely_integration_id
```

> NOTE:
>
> This previous example is just for demonstration purposes and assumes that the external secrets are stored on [Vault](https://www.vaultproject.io/) and the secret `rely` in the vault backend has the keys `rely_api_token` and `rely_integration_id` with the values for the `RELY_API_TOKEN` and `RELY_INTEGRATION_ID` respectively. The `target` in the `ExternalSecret` resource is the name of the secret that contains the values for the `RELY_API_TOKEN` and `RELY_INTEGRATION_ID`.

> **NOTE** <br/>
> Depending on the integration you are using you might need to set other values. You can find the values needed for each integration in its own documentation.


###### Base kubernetes secrets

If we are not using external secrets, the helm chart also requires the following environment variables to be set:

- `env.RELY_API_TOKEN`: Go to rely app and get the token for the plugin installation
- `env.RELY_INTEGRATION_ID`: Go to rely app and get the rely integration installation id

<br/>

> **NOTE** <br/>
> Depending on the integration you are using you might need to set other values. You can find the values needed for each integration in its own documentation.

### Docker

You can simply run Galaxy by:

```bash
docker run --env-file .env devrelyio/galaxy:latest
```

The content of the .env file is as follows:

```dotenv
RELY_INTEGRATION_TYPE=<the name of the integration, ex: gitlab>
RELY_API_URL=https://magneto.rely.io/
RELY_API_TOKEN=<go to rely app and get the token for the plugin installation>
RELY_INTEGRATION_ID=<go to rely app and get the rely integration installation id>
RELY_INTEGRATION_EXECUTION_TYPE=daemon         # This will ensure your Docker container will run continuously
```

### Contributing

Interested in contributing? Great!

Start by reading our [contribution guidelines](CONTRIBUTING.md) and then follow the steps below:

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

### License

Galaxy is licensed under the [Apache License 2.0](LICENSE).
