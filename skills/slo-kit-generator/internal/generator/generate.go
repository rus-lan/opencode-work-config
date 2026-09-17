package generator

import (
	"fmt"
	"strings"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

func Generate(result *types.ScanResult, opts types.GenerateOptions) string {
	var b strings.Builder

	profile := opts.Profile
	if profile == "" {
		profile = "ecomtech-letsgo"
	}
	service := opts.Service
	if service == "" {
		service = result.ServiceName
	}
	product := opts.Product
	if product == "" {
		product = result.Product
	}

	b.WriteString("# slo-kit.yaml - сгенерировано slokit\n")
	b.WriteString("# Отредактируйте metadata и alerts перед использованием\n\n")

	b.WriteString(fmt.Sprintf("profile: %s\n", profile))
	b.WriteString(fmt.Sprintf("namespace: %s\n", strOrDefault(opts.Namespace, "TODO")))
	b.WriteString(fmt.Sprintf("service: %s\n", service))
	b.WriteString(fmt.Sprintf("product: %s\n", strOrDefault(product, "TODO")))
	b.WriteString(fmt.Sprintf("service_name_humanized: %s\n", humanize(service)))
	b.WriteString("\n")
	b.WriteString(fmt.Sprintf("title: %s\n", humanize(service)))
	b.WriteString(fmt.Sprintf("description: %s\n", humanize(service)))
	b.WriteString("\n")
	b.WriteString("user_impact:\n")
	b.WriteString("  degraded: TODO\n")
	b.WriteString("  outage: TODO\n")
	b.WriteString("\n")

	if opts.Team != "" {
		b.WriteString(fmt.Sprintf("team: %s\n", opts.Team))
	}
	if opts.CostCentre != "" {
		b.WriteString(fmt.Sprintf("cost_centre: %s\n", opts.CostCentre))
	}
	b.WriteString("\n")

	b.WriteString("alerts:\n")
	b.WriteString("  enabled: false\n")
	if opts.Team != "" {
		b.WriteString(fmt.Sprintf("  notify:\n    - %s\n", opts.Team))
	}
	b.WriteString("  min_severity: warning\n")
	b.WriteString("\n")

	b.WriteString("defaults:\n  latency_limit: \"0.5\"\n\n")

	b.WriteString("groups:\n")

	writeHTTPGroups(&b, result)
	writeRoutesGroups(&b, result, opts)
	writeConsumerGroups(&b, result, opts)
	writeJobGroups(&b, result, opts)
	writeQueJobGroups(&b, result, opts)
	writeGraphQLGroups(&b, result, opts)
	writeExternalGroups(&b, result, opts)

	if len(result.Warnings) > 0 {
		b.WriteString("\n# Warnings:\n")
		for _, w := range result.Warnings {
			b.WriteString(fmt.Sprintf("# - %s\n", w))
		}
	}

	return b.String()
}

func writeHTTPGroups(b *strings.Builder, result *types.ScanResult) {
	if result.OpenAPI == nil || len(result.OpenAPI.Endpoints) == 0 {
		return
	}

	groups := make(map[string][]types.Endpoint)
	for _, ep := range result.OpenAPI.Endpoints {
		tag := ep.Tag
		if tag == "" {
			tag = "api"
		}
		groups[tag] = append(groups[tag], ep)
	}

	for tag, endpoints := range groups {
		b.WriteString(fmt.Sprintf("  %s:\n", sanitizeGroupName(tag)))
		b.WriteString(fmt.Sprintf("    description: %s API\n", tag))
		b.WriteString("    labels:\n      serviceTier: \"2\"\n")
		b.WriteString("    defaults:\n      latency_limit: \"0.5\"\n")
		b.WriteString("    consists_of:\n      http:\n")
		for _, ep := range endpoints {
			b.WriteString(fmt.Sprintf("        - method: %s\n          handler: %s\n", ep.Method, ep.Path))
		}
		b.WriteString("\n")
	}
}

func writeConsumerGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	hasTopics := false
	for _, c := range result.Consumers {
		if len(c.Topics) > 0 {
			hasTopics = true
			break
		}
	}
	if !hasTopics {
		return
	}

	b.WriteString("  consumers:\n")
	b.WriteString("    description: Kafka consumers\n")
	b.WriteString("    labels:\n      serviceTier: \"2\"\n")
	b.WriteString("    defaults:\n      latency_limit: \"5\"\n")
	b.WriteString("    consists_of:\n      consumers:\n")
	for _, c := range result.Consumers {
		for _, topic := range c.Topics {
			b.WriteString(fmt.Sprintf("        - topic: %s\n", topic))
		}
	}
	b.WriteString("\n")
}

func writeJobGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	if len(result.Jobs) == 0 {
		return
	}

	if opts.Profile == "ecomtech-letsgo" || opts.Profile == "" {
		b.WriteString("  jobs:\n")
		b.WriteString("    description: Background jobs\n")
		b.WriteString("    labels:\n      serviceTier: \"3\"\n")
		b.WriteString("    defaults:\n      latency_limit: \"5\"\n")
		b.WriteString("    consists_of:\n      jobs:\n")
		for _, job := range result.Jobs {
			b.WriteString(fmt.Sprintf("        - queue: %s\n", job.Name))
		}
		b.WriteString("\n")
	}
}

func writeExternalGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	if len(result.Adapters) == 0 {
		return
	}

	b.WriteString("  # external integrations (adapters from app.letsgo.yaml)\n")
	b.WriteString("  external:\n")
	b.WriteString("    description: External HTTP integrations\n")
	b.WriteString("    labels:\n      serviceTier: \"2\"\n")
	b.WriteString("    defaults:\n      latency_limit: \"0.5\"\n")
	b.WriteString("    consists_of:\n      oif:\n")
	for _, adapter := range result.Adapters {
		name := strings.ReplaceAll(adapter.Name, "_", "-")
		b.WriteString(fmt.Sprintf("        - name: %s\n", name))
		b.WriteString(fmt.Sprintf("          description: %s\n", humanize(adapter.Name)))
		b.WriteString(fmt.Sprintf("          out_service: %s\n", name))
		b.WriteString(fmt.Sprintf("          out_if_id: \".*\"\n"))
		b.WriteString(fmt.Sprintf("          out_if_type: http\n"))
	}
}

func strOrDefault(s, def string) string {
	if s == "" {
		return def
	}
	return s
}

func humanize(s string) string {
	s = strings.ReplaceAll(s, "_", " ")
	s = strings.ReplaceAll(s, "-", " ")
	if len(s) > 0 {
		s = strings.ToUpper(s[:1]) + s[1:]
	}
	return s
}

func sanitizeGroupName(s string) string {
	s = strings.ToLower(s)
	s = strings.ReplaceAll(s, " ", "-")
	s = strings.ReplaceAll(s, "_", "-")
	return s
}

func writeRoutesGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	if len(result.Routes) == 0 {
		return
	}

	groups := make(map[string][]types.RouteInfo)
	for _, r := range result.Routes {
		ctrl := r.Controller
		if ctrl == "" {
			ctrl = "api"
		}
		groups[ctrl] = append(groups[ctrl], r)
	}

	for ctrl, routes := range groups {
		groupName := sanitizeGroupName(ctrl)
		if groupName == "graphql" {
			groupName = "graphql-api"
		}
		b.WriteString(fmt.Sprintf("  %s:\n", groupName))
		b.WriteString(fmt.Sprintf("    description: %s controller\n", ctrl))
		b.WriteString("    labels:\n      serviceTier: \"2\"\n")
		b.WriteString("    defaults:\n      latency_limit: \"0.5\"\n")
		b.WriteString("    consists_of:\n      http:\n")
		for _, r := range routes {
			b.WriteString(fmt.Sprintf("        - method: %s\n", r.Method))
			b.WriteString(fmt.Sprintf("          controller: %s\n", r.Controller))
			b.WriteString(fmt.Sprintf("          action: %s\n", r.Action))
		}
		b.WriteString("\n")
	}
}

func writeQueJobGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	if len(result.QueJobs) == 0 {
		return
	}

	profile := opts.Profile
	if profile == "" {
		profile = "ecomtech-letsgo"
	}

	if profile == "ecom-ruby" {
		b.WriteString("  jobs:\n")
		b.WriteString("    description: Que background jobs\n")
		b.WriteString("    labels:\n      serviceTier: \"3\"\n")
		b.WriteString("    defaults:\n      latency_limit: \"5\"\n")
		b.WriteString("    consists_of:\n      jobs:\n")
		for _, job := range result.QueJobs {
			b.WriteString(fmt.Sprintf("        - queue: %s\n", job.Queue))
			b.WriteString(fmt.Sprintf("          job_type: que\n"))
		}
		b.WriteString("\n")
	} else {
		b.WriteString("  # que jobs (custom SLI - профиль не поддерживает нативный тип job для que)\n")
		b.WriteString("  jobs:\n")
		b.WriteString("    description: Que background jobs\n")
		b.WriteString("    labels:\n      serviceTier: \"3\"\n")
		b.WriteString("    defaults:\n      latency_limit: \"5\"\n")
		b.WriteString("    consists_of:\n      custom:\n")
		for _, job := range result.QueJobs {
			b.WriteString(fmt.Sprintf("        - name: %s-availability\n", job.Name))
			b.WriteString(fmt.Sprintf("          description: Job %s availability\n", job.Name))
			b.WriteString(fmt.Sprintf("          error_query: |\n"))
			b.WriteString(fmt.Sprintf("            sum(increase(que_jobs_failed_total{queue=\"%s\",worker=\"%s\"}[{{.window}}]))\n", job.Queue, job.Name))
			b.WriteString(fmt.Sprintf("          total_query: |\n"))
			b.WriteString(fmt.Sprintf("            sum(increase(que_jobs_executed_total{queue=\"%s\",worker=\"%s\"}[{{.window}}]))\n", job.Queue, job.Name))
		}
		b.WriteString("\n")
	}
}

func writeGraphQLGroups(b *strings.Builder, result *types.ScanResult, opts types.GenerateOptions) {
	if len(result.GraphQL) == 0 {
		return
	}

	b.WriteString("  graphql:\n")
	b.WriteString("    description: GraphQL operations\n")
	b.WriteString("    labels:\n      serviceTier: \"2\"\n")
	b.WriteString("    defaults:\n      latency_limit: \"0.5\"\n")
	b.WriteString("    consists_of:\n      graphql:\n")
	for _, op := range result.GraphQL {
		b.WriteString(fmt.Sprintf("        - operation_name: %s\n", op.Name))
		b.WriteString(fmt.Sprintf("          operation_type: %s\n", op.Type))
	}
	b.WriteString("\n")
}
