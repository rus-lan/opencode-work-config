package scanner

import (
	"os"
	"path/filepath"
	"testing"
)

const testOwnSpec = `openapi: 3.0.3
info:
  title: own-service
  version: v1
paths:
  /v1/health:
    get:
      tags: [health]
      operationId: health
  /v1/widgets:
    post:
      tags: [widgets]
      operationId: widgetsCreate
`

const testAdapterSpec = `openapi: 3.0.3
info:
  title: external-adapter
  version: v1
paths:
  /api/external/user/list:
    post:
      tags: [external]
      operationId: externalUserList
`

func writeTestFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

// newSpecFixture lays out a Let's Go-style service: its own spec.yaml plus
// external adapter specs in api/openapi/ and one at the repo root.
func newSpecFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	writeTestFile(t, filepath.Join(root, "api", "openapi", "spec.yaml"), testOwnSpec)
	writeTestFile(t, filepath.Join(root, "api", "openapi", "keeper_spec.yaml"), testAdapterSpec)
	writeTestFile(t, filepath.Join(root, "api", "openapi", "issues_service_spec.yaml"), testAdapterSpec)
	writeTestFile(t, filepath.Join(root, "user_conductor_spec.yaml"), testAdapterSpec)
	return root
}

func TestSelectOpenAPISpec(t *testing.T) {
	root := newSpecFixture(t)

	tests := []struct {
		name        string
		ownSpecPath string
		wantBase    string
		wantWarning bool
	}{
		{
			name:        "letsgo specPath wins over name preference",
			ownSpecPath: "api/openapi/spec.yaml",
			wantBase:    "spec.yaml",
		},
		{
			name:        "declared spec is used exactly even if adapter-looking",
			ownSpecPath: "api/openapi/keeper_spec.yaml",
			wantBase:    "keeper_spec.yaml",
		},
		{
			name:     "own-named candidate beats adapter specs",
			wantBase: "spec.yaml",
		},
		{
			name:        "missing declared spec falls back to name preference",
			ownSpecPath: "api/openapi/missing.yaml",
			wantBase:    "spec.yaml",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got, warning := selectOpenAPISpec(root, tt.ownSpecPath)
			if filepath.Base(got) != tt.wantBase {
				t.Fatalf("selectOpenAPISpec() = %s, want %s", filepath.Base(got), tt.wantBase)
			}
			if (warning != "") != tt.wantWarning {
				t.Fatalf("warning = %q, wantWarning = %v", warning, tt.wantWarning)
			}
		})
	}
}

func TestSelectOpenAPISpec_LegacyFallback(t *testing.T) {
	root := t.TempDir()
	// No spec.yaml — only external adapter specs are present.
	writeTestFile(t, filepath.Join(root, "api", "openapi", "keeper_spec.yaml"), testAdapterSpec)
	writeTestFile(t, filepath.Join(root, "api", "openapi", "issues_service_spec.yaml"), testAdapterSpec)

	got, warning := selectOpenAPISpec(root, "")
	if filepath.Base(got) != "issues_service_spec.yaml" {
		t.Fatalf("selectOpenAPISpec() = %s, want issues_service_spec.yaml (alphabetically first)", got)
	}
	if warning == "" {
		t.Fatal("want a warning when falling back to a *_spec.yaml candidate, got none")
	}
}

func TestSelectOpenAPISpec_NoCandidates(t *testing.T) {
	root := t.TempDir()

	got, warning := selectOpenAPISpec(root, "")
	if got != "" || warning != "" {
		t.Fatalf("selectOpenAPISpec() = (%q, %q), want (\"\", \"\")", got, warning)
	}
}

func TestParseOpenAPI_CountsOnlyOwnSpec(t *testing.T) {
	root := newSpecFixture(t)

	scan, warnings, err := ParseOpenAPI(root, "api/openapi/spec.yaml")
	if err != nil {
		t.Fatalf("ParseOpenAPI() error: %v", err)
	}
	if scan == nil {
		t.Fatal("ParseOpenAPI() = nil, want scan")
	}
	if len(warnings) != 0 {
		t.Fatalf("ParseOpenAPI() warnings = %v, want none", warnings)
	}
	if scan.Title != "own-service" {
		t.Fatalf("Title = %q, want own-service", scan.Title)
	}
	if scan.SpecPath != "api/openapi/spec.yaml" {
		t.Fatalf("SpecPath = %q, want api/openapi/spec.yaml", scan.SpecPath)
	}
	if len(scan.Endpoints) != 2 {
		t.Fatalf("Endpoints = %d, want 2 (only the service's own spec)", len(scan.Endpoints))
	}
	for _, ep := range scan.Endpoints {
		if ep.Path == "/api/external/user/list" {
			t.Fatalf("external adapter endpoint leaked into the scan: %+v", ep)
		}
	}
}

func TestParseOpenAPI_FallbackIncludesWarning(t *testing.T) {
	root := t.TempDir()
	writeTestFile(t, filepath.Join(root, "api", "openapi", "keeper_spec.yaml"), testAdapterSpec)

	scan, warnings, err := ParseOpenAPI(root, "")
	if err != nil {
		t.Fatalf("ParseOpenAPI() error: %v", err)
	}
	if scan == nil || len(scan.Endpoints) == 0 {
		t.Fatal("ParseOpenAPI() = empty, want the legacy fallback endpoint")
	}
	if len(warnings) != 1 {
		t.Fatalf("warnings = %v, want exactly one", warnings)
	}
}
