# galaxy-helm

![Version: 0.0.1](https://img.shields.io/badge/Version-0.0.1-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 0.0.1](https://img.shields.io/badge/AppVersion-0.0.1-informational?style=flat-square)

Rely Galaxy Framework Helm chart for Kubernetes

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | Affinity settings for pod assignment |
| env | object | `{"RELY_API_TOKEN":null,"RELY_INTEGRATION_ID":null}` | Environment variables to be set in the container if not using external secrets |
| env.RELY_API_TOKEN | string | `nil` | The API token for the Rely API |
| env.RELY_INTEGRATION_ID | string | `nil` | The identifier of this integration instance |
| externalSecrets | object | `{"allAsEnv":false,"enabled":false,"envs":[],"target":"my-vault-secrets"}` | External secrets configuration |
| externalSecrets.allAsEnv | bool | `false` | All keys in secrets file will be exported as environment variables |
| externalSecrets.enabled | bool | `false` | Enable external secrets |
| externalSecrets.envs | list | `[]` | environment variables to be set in the container from the external secrets if allAsEnv is false envs is an array of objects with the following keys name -- The name of the environment variable to setup key -- The key in the secret to use eg.: envs: - name: "RELY_API_TOKEN"   key: "api_token" |
| externalSecrets.target | string | `"my-vault-secrets"` | The name of the external secrets |
| fullnameOverride | string | `""` | Override the fullname of the chart |
| image.pullPolicy | string | `"IfNotPresent"` | Pull policy for the image |
| image.repository | string | `"devrelyio/galaxy"` |  |
| image.tag | string | `""` | Tag to use for deploying the application |
| integration | object | `{"apiUrl":"https://magneto.rely.io/","daemonInterval":60,"executionType":"cronjob","type":null}` | The configuration for the integration |
| integration.apiUrl | string | `"https://magneto.rely.io/"` | The url for the Rely API |
| integration.daemonInterval | int | `60` | The interval in minutes at which the integration should run only required if the execution type is daemon |
| integration.executionType | string | `"cronjob"` | The execution type of the integration can be either cronjob or daemon |
| integration.type | string | `nil` | The type of the integration can be any of the following: pagerduty, github, gitlab, bitbucket, sonarqube, aws, opsgenie, gcp |
| nameOverride | string | `""` | Override the name of the chart |
| nodeSelector | object | `{}` | Node labels for pod assignment |
| podAnnotations | object | `{}` | The annotations to add to the pod |
| podLabels | object | `{}` | The labels to instances of the pod |
| podSecurityContext | object | `{}` | The security context for the pod |
| resources | object | `{}` | The resource requests and limits for the containers |
| schedule | string | `"*/59 * * * *"` | This is a cron expression that defines the schedule for the cronjob |
| securityContext | object | `{}` | The security context for the container |
| serviceAccount.annotations | object | `{}` | Annotations to add to the service account |
| serviceAccount.automount | bool | `true` | Automatically mount a ServiceAccount's API credentials? |
| serviceAccount.create | bool | `false` | Specifies whether a service account should be created |
| serviceAccount.name | string | `""` | The name of the service account to use. -- If not set and create is true, a name is generated using the fullname template |
| tolerations | list | `[]` | Toleration labels for pod assignment |
| volumeMounts | list | `[]` | Additional volumeMounts on the output Deployment definition. |
| volumes | list | `[]` | Additional volumes on the output Deployment definition. |

