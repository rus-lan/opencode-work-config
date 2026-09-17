package scanner

import (
	"path/filepath"
	"testing"
)

func controllerWithParamsSpec(specPath string) letsgoController {
	c := letsgoController{Kind: "http", Protocol: "oapi"}
	c.Params.SpecPath = specPath
	return c
}

func controllerWithTopLevelSpec(specPath string) letsgoController {
	return letsgoController{Kind: "http", Protocol: "oapi", SpecPath: specPath}
}

// controllerWithSpec builds a controller with specPath under params
// (the customers/loyalty manifest layout).
func controllerWithSpec(specPath string) letsgoController {
	return controllerWithParamsSpec(specPath)
}

func TestControllerSpecPath(t *testing.T) {
	tests := []struct {
		name        string
		controllers map[string]letsgoController
		want        string
	}{
		{
			name: "api controller, specPath under params",
			controllers: map[string]letsgoController{
				"api": controllerWithParamsSpec("api/openapi/spec.yaml"),
			},
			want: "api/openapi/spec.yaml",
		},
		{
			name: "api controller, top-level specPath",
			controllers: map[string]letsgoController{
				"api": controllerWithTopLevelSpec("api/openapi/spec.yaml"),
			},
			want: "api/openapi/spec.yaml",
		},
		{
			name: "api controller wins over other http controllers",
			controllers: map[string]letsgoController{
				"api":   controllerWithSpec("api/openapi/spec.yaml"),
				"extra": controllerWithSpec("api/openapi/extra.yaml"),
			},
			want: "api/openapi/spec.yaml",
		},
		{
			name: "api without specPath falls back to first http controller (sorted)",
			controllers: map[string]letsgoController{
				"api":   {Kind: "http", Protocol: "oapi"},
				"zeta":  controllerWithSpec("api/openapi/zeta.yaml"),
				"alpha": controllerWithSpec("api/openapi/alpha.yaml"),
			},
			want: "api/openapi/alpha.yaml",
		},
		{
			name: "non-http controllers are ignored",
			controllers: map[string]letsgoController{
				"api":    {Kind: "schedule"},
				"worker": {Kind: "queue", SpecPath: "api/openapi/worker.yaml"},
			},
			want: "",
		},
		{
			name:        "empty controllers",
			controllers: map[string]letsgoController{},
			want:        "",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := controllerSpecPath(tt.controllers); got != tt.want {
				t.Fatalf("controllerSpecPath() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestParseLetsgo_OwnSpecPath(t *testing.T) {
	root := t.TempDir()
	manifest := `apiVersion: backstage.io/v1alpha1
kind: Service
metadata:
  name: test-service
spec:
  controllers:
    api:
      stateful: true
      kind: http
      protocol: oapi
      params:
        specPath: api/openapi/spec.yaml
  adapters:
    keeper:
      kind: http
      protocol: oapi
      specPath: api/openapi/keeper_spec.yaml
`
	writeTestFile(t, filepath.Join(root, "app.letsgo.yaml"), manifest)

	result, _ := ParseLetsgo(root)
	if result == nil {
		t.Fatal("ParseLetsgo() = nil, want result")
	}
	if result.OwnSpecPath != "api/openapi/spec.yaml" {
		t.Fatalf("OwnSpecPath = %q, want api/openapi/spec.yaml", result.OwnSpecPath)
	}
	if len(result.Adapters) != 1 {
		t.Fatalf("Adapters = %d, want 1", len(result.Adapters))
	}
}
