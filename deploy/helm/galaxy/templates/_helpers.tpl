{{/*
Expand the name of the chart.
*/}}
{{- define "galaxy-helm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "galaxy-helm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "galaxy-helm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "galaxy-helm.labels" -}}
helm.sh/chart: {{ include "galaxy-helm.chart" . }}
{{ include "galaxy-helm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "galaxy-helm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "galaxy-helm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "galaxy-helm.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "galaxy-helm.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create a validation for required values
*/}}
{{- define "galaxy-helm.required.envs" -}}
{{- if not .Values.externalSecrets.enabled -}}
{{- required "RELY_API_TOKEN is a required value" .Values.env.RELY_API_TOKEN -}}
{{- required "RELY_INTEGRATION_ID is a required value" .Values.env.RELY_INTEGRATION_ID -}}
{{- else -}}
{{- required "externalSecrets.target is a required value" .Values.externalSecrets.target -}}
{{- if not .Values.externalSecrets.allAsEnv -}}
{{- required "externalSecrets.envs cannot be empty" .Values.externalSecrets.envs -}}
{{- end -}}
{{- end }}
{{- required "integration.apiUrl is a required value" .Values.integration.apiUrl -}}
{{- required "integration.type is a required value" .Values.integration.type -}}
{{- end }}

{{/*
Set default environment variables
*/}}
{{- define "galaxy-helm.base.envs" -}}
- name: RELY_API_URL
  value: {{ .Values.integration.apiUrl | quote}}
- name: RELY_INTEGRATION_TYPE
  value: {{ .Values.integration.type | quote }}
- name: RELY_INTEGRATION_EXECUTION_TYPE
  value: {{ .Values.integration.executionType | quote }}
- name: RELY_INTEGRATION_DAEMON_INTERVAL
  value: {{ .Values.integration.daemonInterval | quote }}
{{- end -}}
