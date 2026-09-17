package scanner

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

var (
	rubyFieldRe  = regexp.MustCompile(`field\s+:(\w+)\s*,\s*(resolver|mutation)`)
	karafkaRe    = regexp.MustCompile(`topic\s+ENV\.fetch\("(KAFKA_\w+_TOPIC)"`)
	queClassRe   = regexp.MustCompile(`class\s+(Que::[\w:]+)\s*<`)
	queQueueRe   = regexp.MustCompile(`queue\s*[=:]\s*['"]?([\w_-]+)`)
	railsRouteRe = regexp.MustCompile(`^\s*(get|post|put|patch|delete)\s+['"]([^'"]+)['"](?:.*to:\s*['"]([^'"]+)['"])?`)
)

func ParseRuby(servicePath string, result *types.ScanResult) {
	parseRubyGraphQL(servicePath, result)
	parseKarafka(servicePath, result)
	parseRailsRoutes(servicePath, result)
	parseQueJobs(servicePath, result)
}

func parseRubyGraphQL(servicePath string, result *types.ScanResult) {
	files := []string{
		filepath.Join(servicePath, "app", "graphql", "types", "query_type.rb"),
		filepath.Join(servicePath, "app", "graphql", "types", "mutation_type.rb"),
	}

	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}

		matches := rubyFieldRe.FindAllStringSubmatch(string(data), -1)
		for _, m := range matches {
			opName := m[1]
			opType := m[2]
			if opType == "resolver" {
				opType = "query"
			}
			result.GraphQL = append(result.GraphQL, types.GraphQLOp{
				Name: opName,
				Type: opType,
			})
		}
	}

	sort.Slice(result.GraphQL, func(i, j int) bool {
		return result.GraphQL[i].Name < result.GraphQL[j].Name
	})
}

func parseKarafka(servicePath string, result *types.ScanResult) {
	karafkaPath := filepath.Join(servicePath, "karafka.rb")
	data, err := os.ReadFile(karafkaPath)
	if err != nil {
		return
	}

	envVars := resolveDeployEnv(servicePath)

	matches := karafkaRe.FindAllStringSubmatch(string(data), -1)
	if len(matches) == 0 {
		return
	}

	var topics []string
	for _, m := range matches {
		envKey := m[1]
		if topicName, ok := envVars[envKey]; ok && topicName != "" {
			topics = append(topics, topicName)
		}
	}

	if len(topics) > 0 {
		result.Consumers = append(result.Consumers, types.ConsumerInfo{
			DriverName: "karafka",
			Topics:     topics,
		})
	}
}

func resolveDeployEnv(servicePath string) map[string]string {
	envVars := make(map[string]string)

	for _, envFile := range []string{"prod.yaml", "test.yaml", "dyn.yaml"} {
		path := filepath.Join(servicePath, "deploy", envFile)
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}

		var doc struct {
			Common struct {
				Env map[string]string `yaml:"env"`
			} `yaml:"common"`
			Apps map[string]struct {
				Env map[string]string `yaml:"env"`
			} `yaml:"apps"`
		}
		if err := yaml.Unmarshal(data, &doc); err != nil {
			continue
		}

		for k, v := range doc.Common.Env {
			if strings.HasPrefix(k, "KAFKA_") && strings.HasSuffix(k, "_TOPIC") {
				envVars[k] = strings.Trim(v, `"`)
			}
		}
		for _, app := range doc.Apps {
			for k, v := range app.Env {
				if strings.HasPrefix(k, "KAFKA_") && strings.HasSuffix(k, "_TOPIC") {
					envVars[k] = strings.Trim(v, `"`)
				}
			}
		}
	}

	return envVars
}

func parseRailsRoutes(servicePath string, result *types.ScanResult) {
	routesPath := filepath.Join(servicePath, "config", "routes.rb")
	data, err := os.ReadFile(routesPath)
	if err != nil {
		return
	}

	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		m := railsRouteRe.FindStringSubmatch(line)
		if len(m) < 3 {
			continue
		}

		method := strings.ToUpper(m[1])
		path := m[2]
		controllerAction := ""
		if len(m) >= 4 && m[3] != "" {
			controllerAction = m[3]
		}

		route := types.RouteInfo{
			Method: method,
		}

		if controllerAction != "" {
			parts := strings.SplitN(controllerAction, "#", 2)
			if len(parts) == 2 {
				route.Controller = parts[0]
				route.Action = parts[1]
			}
		}

		route.Controller = strOrDefault(route.Controller, path)
		result.Routes = append(result.Routes, route)
	}
}

func parseQueJobs(servicePath string, result *types.ScanResult) {
	jobsDir := filepath.Join(servicePath, "app", "jobs", "que")
	files, _ := filepath.Glob(filepath.Join(jobsDir, "**", "*.rb"))
	files = append(files, globFiles(jobsDir, "*.rb")...)

	sort.Strings(files)

	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}

		match := queClassRe.FindStringSubmatch(string(data))
		if len(match) < 2 {
			continue
		}

		fullClass := match[1]
		parts := strings.Split(fullClass, "::")
		workerName := parts[len(parts)-1]

		queue := ""
		if qm := queQueueRe.FindStringSubmatch(string(data)); len(qm) >= 2 {
			queue = qm[1]
		}
		if queue == "" {
			queue = toSnakeCase(workerName)
		}

		result.QueJobs = append(result.QueJobs, types.QueJobInfo{
			Name:  workerName,
			Queue: queue,
		})
	}

	parseQueSchedule(servicePath, result)
}

func parseQueSchedule(servicePath string, result *types.ScanResult) {
	path := filepath.Join(servicePath, "config", "que_schedule.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}

	var schedule map[string]struct {
		Class string `yaml:"class"`
		Queue string `yaml:"queue"`
	}
	if err := yaml.Unmarshal(data, &schedule); err != nil {
		return
	}

	for _, entry := range schedule {
		parts := strings.Split(entry.Class, "::")
		workerName := parts[len(parts)-1]

		queue := entry.Queue
		if queue == "" {
			queue = toSnakeCase(workerName)
		}

		alreadyExists := false
		for i := range result.QueJobs {
			if result.QueJobs[i].Name == workerName {
				result.QueJobs[i].Queue = queue
				alreadyExists = true
				break
			}
		}
		if !alreadyExists {
			result.QueJobs = append(result.QueJobs, types.QueJobInfo{
				Name:  workerName,
				Queue: queue,
			})
		}
	}
}

func toSnakeCase(s string) string {
	var b strings.Builder
	for i, r := range s {
		if i > 0 && r >= 'A' && r <= 'Z' {
			b.WriteByte('_')
		}
		if r >= 'A' && r <= 'Z' {
			b.WriteRune(r + 32)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func globFiles(dir, pattern string) []string {
	matches, _ := filepath.Glob(filepath.Join(dir, pattern))
	return matches
}

func strOrDefault(s, def string) string {
	if s == "" {
		return def
	}
	return s
}
