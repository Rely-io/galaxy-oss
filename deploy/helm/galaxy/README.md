# galaxy-helm

![Version: 0.0.1](https://img.shields.io/badge/Version-0.0.1-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 0.0.1](https://img.shields.io/badge/AppVersion-0.0.1-informational?style=flat-square)

Rely Galaxy Framework Helm chart for Kubernetes

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | Affinity settings for pod assignment |
| env | object | `{"RELY_API_TOKEN":null,"RELY_API_URL":"https://magneto.rely.io/","RELY_INTEGRATION_DAEMON_INTERVAL":60,"RELY_INTEGRATION_EXECUTION_TYPE":"cronjob","RELY_INTEGRATION_ID":null,"RELY_INTEGRATION_TYPE":null}` | Environment variables to be set in the container |
| env.RELY_API_TOKEN | string | `nil` | The API token for the Rely API |
| env.RELY_API_URL | string | `"https://magneto.rely.io/"` | The URL for the Rely API |
| env.RELY_INTEGRATION_DAEMON_INTERVAL | int | `60` | The interval in minutes at which the integration should run only required if the execution type is daemon |
| env.RELY_INTEGRATION_EXECUTION_TYPE | string | `"cronjob"` | The execution type of the integration can be either cronjob or daemon |
| env.RELY_INTEGRATION_ID | string | `nil` | The identifier of this integration instance |
| env.RELY_INTEGRATION_TYPE | string | `nil` | The type of the integration |
| fullnameOverride | string | `""` | Override the fullname of the chart |
| image.pullPolicy | string | `"IfNotPresent"` | Pull policy for the image |
| image.repository | string | `"devrelyio/galaxy"` |  |
| image.tag | string | `""` | Tag to use for deploying the application |
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
