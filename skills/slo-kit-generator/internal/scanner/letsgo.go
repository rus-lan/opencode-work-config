package scanner

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/sbmt/slo-kit-generator/internal/types"
	"gopkg.in/yaml.v3"
)

type letsgoManifest struct {
	APIVersion string `yaml:"apiVersion"`
	Kind       string `yaml:"kind"`
	Metadata   struct {
		Name    string `yaml:"name"`
		Product string `yaml:"product"`
	} `yaml:"metadata"`
	Spec struct {
		Drivers map[string]struct {
			Kind   string                 `yaml:"kind"`
			Params map[string]interface{} `yaml:"params"`
		} `yaml:"drivers"`
		Controllers map[string]letsgoController `yaml:"controllers"`
		Adapters    map[string]struct {
			Kind     string `yaml:"kind"`
			Protocol string `yaml:"protocol"`
			SpecPath string `yaml:"specPath"`
		} `yaml:"adapters"`
	} `yaml:"spec"`
}

// letsgoController is one entry under spec.controllers in app.letsgo.yaml.
// The OpenAPI spec may be declared at the controller level or under its
// params, depending on the Let's Go version.
type letsgoController struct {
	Kind         string            `yaml:"kind"`
	Protocol     string            `yaml:"protocol"`
	Format       string            `yaml:"format"`
	Tasks        []string          `yaml:"tasks"`
	Dependencies map[string]string `yaml:"dependencies"`
	SpecPath     string            `yaml:"specPath"`
	Params       struct {
		SpecPath string `yaml:"specPath"`
	} `yaml:"params"`
}

// specPathOf returns the OpenAPI spec declared for the controller
// (top-level or under params).
func (c letsgoController) specPath() string {
	if c.SpecPath != "" {
		return c.SpecPath
	}
	return c.Params.SpecPath
}

func ParseLetsgo(path string) (*types.ScanResult, []string) {
	manifestPath := filepath.Join(path, "app.letsgo.yaml")
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, []string{"app.letsgo.yaml not found: " + err.Error()}
	}

	var m letsgoManifest
	if err := yaml.Unmarshal(data, &m); err != nil {
		return nil, []string{"failed to parse app.letsgo.yaml: " + err.Error()}
	}

	result := &types.ScanResult{
		ServiceName: m.Metadata.Name,
		Product:     m.Metadata.Product,
	}
	var warnings []string

	for name, driver := range m.Spec.Drivers {
		if driver.Kind == "kafkaConsumerGroup" {
			result.Consumers = append(result.Consumers, types.ConsumerInfo{
				DriverName: name,
			})
		}
	}

	for name, ctrl := range m.Spec.Controllers {
		switch ctrl.Kind {
		case "schedule":
			for _, task := range ctrl.Tasks {
				result.Jobs = append(result.Jobs, types.JobInfo{
					Name:       task,
					Controller: name,
				})
			}
		case "queue":
			// queue controllers reference consumer drivers via dependencies.consumer
			// topics will be resolved from .env.example
		}
	}

	result.OwnSpecPath = controllerSpecPath(m.Spec.Controllers)

	for name, adapter := range m.Spec.Adapters {
		if adapter.Kind == "http" {
			result.Adapters = append(result.Adapters, types.AdapterInfo{
				Name:     name,
				SpecPath: adapter.SpecPath,
				Kind:     adapter.Kind,
				Protocol: adapter.Protocol,
			})
		}
	}

	return result, warnings
}

// controllerSpecPath returns the service's own OpenAPI spec path from the
// controllers map. It prefers the controller named "api" (the standard
// Let's Go HTTP controller), then falls back to the first http/oapi
// controller with a specPath. Names are sorted for determinism.
func controllerSpecPath(controllers map[string]letsgoController) string {
	names := make([]string, 0, len(controllers))
	for name := range controllers {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		if name != "api" {
			continue
		}
		if specPath := controllers[name].specPath(); specPath != "" {
			return specPath
		}
	}
	for _, name := range names {
		ctrl := controllers[name]
		if ctrl.Kind != "http" && ctrl.Protocol != "oapi" {
			continue
		}
		if specPath := ctrl.specPath(); specPath != "" {
			return specPath
		}
	}
	return ""
}

func camelToScreamingSnake(s string) string {
	var b strings.Builder
	for i, r := range s {
		if i > 0 && r >= 'A' && r <= 'Z' {
			b.WriteByte('_')
		}
		if r >= 'a' && r <= 'z' {
			b.WriteRune(r - 'a' + 'A')
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}
