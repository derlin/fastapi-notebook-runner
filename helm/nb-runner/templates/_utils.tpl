{{/*
nb_runner.labels: common labels added to all resources. The "extraLabels" argument is optional and supports templating.
Usage:

  {{ include "nb_runner.labels" (dict "context" . "extraLabels" dict) }}

*/}}
{{- define "nb_runner.labels" -}}
appName: {{ .context.Release.Name | quote }}
chartName: {{ .context.Chart.Name | quote }}
version: {{ .context.Chart.Version | quote }}
{{- range $k, $v := default dict .extraLabels }}
{{ $k }}: {{ tpl $v .context | quote }}
{{- end -}}
{{- end -}}
