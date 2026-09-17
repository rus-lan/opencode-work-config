package scanner

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

func ResolveTopics(result *types.ScanResult, servicePath string) {
	envPath := filepath.Join(servicePath, ".env.example")
	data, err := os.ReadFile(envPath)
	if err != nil {
		if len(result.Consumers) > 0 {
			result.Warnings = append(result.Warnings, ".env.example not found, consumer topics not resolved")
		}
		return
	}

	envVars := parseEnvFile(string(data))

	for i := range result.Consumers {
		c := &result.Consumers[i]
		prefix := "DRIVERS_" + camelToScreamingSnake(c.DriverName)

		if topics, ok := envVars[prefix+"_TOPICS"]; ok && topics != "" {
			for _, t := range strings.Split(topics, ",") {
				t = strings.TrimSpace(t)
				if t != "" {
					c.Topics = append(c.Topics, t)
				}
			}
		}

		if groupID, ok := envVars[prefix+"_GROUP_ID"]; ok {
			c.GroupID = groupID
		}
	}

	hasResolvedTopics := false
	for _, c := range result.Consumers {
		if len(c.Topics) > 0 {
			hasResolvedTopics = true
			break
		}
	}
	if !hasResolvedTopics && len(result.Consumers) > 0 {
		result.Warnings = append(result.Warnings, "consumer topics not found in .env.example (values may be empty/runtime-configured)")
	}
}

func parseEnvFile(content string) map[string]string {
	result := make(map[string]string)
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		val = strings.Trim(val, `"'`)
		result[key] = val
	}
	return result
}
