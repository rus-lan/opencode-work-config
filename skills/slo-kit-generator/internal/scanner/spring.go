package scanner

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

var (
	springMappingRe      = regexp.MustCompile(`@(Get|Post|Put|Delete|Patch)Mapping\s*(?:\(\s*(?:"([^"]*)"|value\s*=\s*"([^"]*)"|path\s*=\s*"([^"]*)")?\s*\))?`)
	springClassRMRe      = regexp.MustCompile(`@RequestMapping\s*\(\s*(?:"([^"]*)"|value\s*=\s*"([^"]*)"|path\s*=\s*"([^"]*)")?`)
	springMethodRMRe     = regexp.MustCompile(`@RequestMapping\s*\(\s*(?:[^)]*\s)?method\s*=\s*RequestMethod\.(\w+)`)
	springRestControllerRe = regexp.MustCompile(`@RestController\b|@Controller\b`)
)

func ParseSpring(servicePath string) *types.OpenAPIScan {
	javaFiles, err := findJavaFiles(servicePath)
	if err != nil {
		return nil
	}

	var endpoints []types.Endpoint

	for _, file := range javaFiles {
		data, err := os.ReadFile(file)
		if err != nil {
			continue
		}

		source := string(data)
		if !springRestControllerRe.MatchString(source) {
			continue
		}

		classPath := extractClassRequestMapping(source)
		tag := extractControllerTag(file)

		fileEndpoints := parseSpringMappings(source, classPath)
		for _, ep := range fileEndpoints {
			ep.Tag = tag
			endpoints = append(endpoints, ep)
		}
	}

	if len(endpoints) == 0 {
		return nil
	}

	sort.Slice(endpoints, func(i, j int) bool {
		if endpoints[i].Tag != endpoints[j].Tag {
			return endpoints[i].Tag < endpoints[j].Tag
		}
		return endpoints[i].Path < endpoints[j].Path
	})

	return &types.OpenAPIScan{
		Title:     "Spring Boot (annotations)",
		Endpoints: endpoints,
	}
}

func findJavaFiles(servicePath string) ([]string, error) {
	var files []string
	searchDirs := []string{
		filepath.Join(servicePath, "service", "src", "main", "java"),
		filepath.Join(servicePath, "src", "main", "java"),
		filepath.Join(servicePath, "api", "src", "main", "java"),
	}

	for _, dir := range searchDirs {
		if _, err := os.Stat(dir); os.IsNotExist(err) {
			continue
		}
		err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}
			if !info.IsDir() && (strings.HasSuffix(path, ".java") || strings.HasSuffix(path, ".kt")) {
				files = append(files, path)
			}
			return nil
		})
		if err != nil {
			return files, err
		}
	}

	return files, nil
}

func extractClassRequestMapping(source string) string {
	lines := strings.Split(source, "\n")
	for i, line := range lines {
		if strings.Contains(line, "@RequestMapping") && i+1 < len(lines) {
			rest := strings.Join(lines[i:], "\n")
			if m := springClassRMRe.FindStringSubmatch(rest); len(m) >= 2 {
				for _, g := range m[1:] {
					if g != "" {
						return g
					}
				}
			}
		}
	}
	return ""
}

func extractControllerTag(filePath string) string {
	base := filepath.Base(filePath)
	name := strings.TrimSuffix(base, filepath.Ext(base))
	if strings.HasSuffix(name, "Controller") {
		name = strings.TrimSuffix(name, "Controller")
	}
	if strings.HasSuffix(name, "Resource") {
		name = strings.TrimSuffix(name, "Resource")
	}
	return toSnakeCase(name)
}

func parseSpringMappings(source string, classPath string) []types.Endpoint {
	var endpoints []types.Endpoint

	matches := springMappingRe.FindAllStringSubmatch(source, -1)
	for _, m := range matches {
		method := strings.ToUpper(m[1])
		path := classPath
		for _, g := range m[2:] {
			if g != "" {
				path = joinSpringPaths(classPath, g)
				break
			}
		}
		if path == "" {
			path = "/"
		}
		endpoints = append(endpoints, types.Endpoint{
			Method: method,
			Path:   path,
		})
	}

	rmMatches := springMethodRMRe.FindAllStringSubmatchIndex(source, -1)
	for _, m := range rmMatches {
		method := strings.ToUpper(source[m[2]:m[3]])
		if method == "" {
			continue
		}
		matchStart := m[0]
		contextEnd := matchStart + 200
		if contextEnd > len(source) {
			contextEnd = len(source)
		}
		context := source[matchStart:contextEnd]

		subPath := ""
		if cm := springClassRMRe.FindStringSubmatch(context); len(cm) >= 2 {
			for _, g := range cm[1:] {
				if g != "" {
					subPath = g
					break
				}
			}
		}
		path := joinSpringPaths(classPath, subPath)
		if path == "" {
			path = "/"
		}
		endpoints = append(endpoints, types.Endpoint{
			Method: method,
			Path:   path,
		})
	}

	return endpoints
}

func joinSpringPaths(base, sub string) string {
	if sub == "" {
		return base
	}
	if base == "" {
		return sub
	}
	if !strings.HasPrefix(sub, "/") {
		sub = "/" + sub
	}
	return base + sub
}
