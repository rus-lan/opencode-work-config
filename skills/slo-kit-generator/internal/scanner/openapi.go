package scanner

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

type openapiSpec struct {
	OpenAPI string `yaml:"openapi"`
	Info    struct {
		Title string `yaml:"title"`
	} `yaml:"info"`
	Paths map[string]map[string]struct {
		Tags        []string `yaml:"tags"`
		OperationID string   `yaml:"operationId"`
	} `yaml:"paths"`
}

// ownSpecNames are file names that unambiguously identify the service's own
// OpenAPI spec, as opposed to external adapter specs (*_spec.yaml).
var ownSpecNames = map[string]bool{
	"spec.yaml":    true,
	"openapi.yaml": true,
	"openapi.yml":  true,
}

// ParseOpenAPI scans the service's own OpenAPI spec. ownSpecPath is the spec
// declared in app.letsgo.yaml (controllers.api.specPath); when empty, the
// spec is selected from glob candidates by name preference. Inbound
// endpoints are collected only from the selected spec, so external adapter
// specs are never counted as service endpoints.
func ParseOpenAPI(servicePath string, ownSpecPath string) (*types.OpenAPIScan, []string, error) {
	specFile, warning := selectOpenAPISpec(servicePath, ownSpecPath)
	if specFile == "" {
		return nil, nil, nil
	}

	data, err := os.ReadFile(specFile)
	if err != nil {
		return nil, nil, err
	}

	var spec openapiSpec
	if err := yaml.Unmarshal(data, &spec); err != nil {
		return nil, nil, err
	}

	scan := &types.OpenAPIScan{
		Title:    spec.Info.Title,
		SpecPath: relToService(servicePath, specFile),
	}

	for path, methods := range spec.Paths {
		for method, op := range methods {
			method = strings.ToUpper(method)
			if method == "" || method == "PARAMETERS" {
				continue
			}
			tag := ""
			if len(op.Tags) > 0 {
				tag = op.Tags[0]
			}
			scan.Endpoints = append(scan.Endpoints, types.Endpoint{
				Method: method,
				Path:   path,
				Tag:    tag,
			})
		}
	}

	sort.Slice(scan.Endpoints, func(i, j int) bool {
		if scan.Endpoints[i].Tag != scan.Endpoints[j].Tag {
			return scan.Endpoints[i].Tag < scan.Endpoints[j].Tag
		}
		return scan.Endpoints[i].Path < scan.Endpoints[j].Path
	})

	if warning == "" {
		return scan, nil, nil
	}
	return scan, []string{warning}, nil
}

// selectOpenAPISpec picks the service's own OpenAPI spec inside servicePath.
//
// Priority:
//  1. ownSpecPath — the exact file declared in app.letsgo.yaml
//     (controllers.api.specPath);
//  2. a candidate literally named spec.yaml / openapi.yaml / openapi.yml,
//     which wins over *_spec.yaml files (likely external adapter specs);
//  3. legacy behaviour — the alphabetically first candidate, with a warning
//     when the fallback looks like an external adapter spec.
func selectOpenAPISpec(servicePath string, ownSpecPath string) (string, string) {
	if ownSpecPath != "" {
		specFile := ownSpecPath
		if !filepath.IsAbs(specFile) {
			specFile = filepath.Join(servicePath, specFile)
		}
		if info, err := os.Stat(specFile); err == nil && !info.IsDir() {
			return specFile, ""
		}
		// Declared spec is missing — fall through to candidate search.
	}

	candidates := findOpenAPIFiles(servicePath)
	if len(candidates) == 0 {
		return "", ""
	}

	for _, candidate := range candidates {
		if ownSpecNames[filepath.Base(candidate)] {
			return candidate, ""
		}
	}

	fallback := candidates[0]
	if isAdapterSpecName(filepath.Base(fallback)) {
		return fallback, "openapi: service's own spec not found, using " +
			filepath.Base(fallback) + ", which looks like an external adapter spec"
	}
	return fallback, ""
}

// isAdapterSpecName reports whether a spec file name matches the external
// adapter convention (*_spec.yaml / *_spec.yml).
func isAdapterSpecName(base string) bool {
	return strings.HasSuffix(base, "_spec.yaml") || strings.HasSuffix(base, "_spec.yml")
}

// relToService renders file relative to servicePath for display.
func relToService(servicePath, file string) string {
	if rel, err := filepath.Rel(servicePath, file); err == nil {
		return filepath.ToSlash(rel)
	}
	return file
}

func findOpenAPIFiles(servicePath string) []string {
	var result []string

	// External adapter specs at the repo root (e.g. ./user_conductor_spec.yaml)
	// are intentionally not globbed: they are oif sources (see adapters in
	// app.letsgo.yaml) and must never become inbound endpoints.
	patterns := []string{
		"api/openapi/*.yaml",
		"api/openapi/*.yml",
		"api/*.yaml",
		"api/*.yml",
		"openapi.yaml",
		"openapi.yml",
	}

	for _, pattern := range patterns {
		matches, _ := filepath.Glob(filepath.Join(servicePath, pattern))
		result = append(result, matches...)
	}

	return result
}
