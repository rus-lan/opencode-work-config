package scanner

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

func ParseGoMod(servicePath string) *types.ScanResult {
	goModPath := filepath.Join(servicePath, "go.mod")
	data, err := os.ReadFile(goModPath)
	if err != nil {
		return nil
	}

	lines := strings.Split(string(data), "\n")
	var modulePath string
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "module ") {
			modulePath = strings.TrimSpace(strings.TrimPrefix(line, "module "))
			break
		}
	}
	if modulePath == "" {
		return nil
	}

	segments := strings.Split(modulePath, "/")
	var service, product string

	if len(segments) >= 2 {
		service = segments[len(segments)-1]
		product = segments[len(segments)-2]
	} else {
		service = filepath.Base(servicePath)
		product = ""
	}

	product = detectProductFromPath(servicePath, product)

	return &types.ScanResult{
		ServiceName: service,
		Product:     product,
	}
}

func detectProductFromPath(servicePath, fallback string) string {
	parts := strings.Split(filepath.Clean(servicePath), string(os.PathSeparator))
	for _, p := range parts {
		switch p {
		case "opercrm.smkt", "opercrm":
			return "opercrm"
		case "gi.mm":
			return "gi"
		case "faq.mm":
			return "faq"
		case "ts.mm":
			return "ts"
		case "erm.mm":
			return "erm"
		case "cc-exchanger.mm":
			return "cc-exchanger"
		case "cc-exchanger.smkt":
			return "cc-exchanger"
		}
	}
	return fallback
}
