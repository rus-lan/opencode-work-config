package scanner

import (
	"os"
	"path/filepath"
	"regexp"

	"github.com/sbmt/slo-kit-generator/internal/types"
)

var (
	rootProjectNameRe = regexp.MustCompile(`rootProject\.name\s*=\s*["']([^"']+)["']`)
	springBootRe      = regexp.MustCompile(`(?i)spring-boot|org\.springframework\.boot`)
	kotlinRe          = regexp.MustCompile(`(?i)org\.jetbrains\.kotlin|kotlinOptions|KotlinCompile`)
)

func ParseGradle(servicePath string) *types.ScanResult {
	settingsPath := filepath.Join(servicePath, "settings.gradle.kts")
	data, err := os.ReadFile(settingsPath)
	if err != nil {
		return nil
	}

	m := rootProjectNameRe.FindStringSubmatch(string(data))
	if len(m) < 2 {
		return nil
	}

	serviceName := m[1]

	isKotlin := false
	isSpring := false

	for _, gradleFile := range []string{
		filepath.Join(servicePath, "build.gradle.kts"),
		filepath.Join(servicePath, "service", "build.gradle.kts"),
		filepath.Join(servicePath, "api", "build.gradle.kts"),
	} {
		gdata, err := os.ReadFile(gradleFile)
		if err != nil {
			continue
		}
		content := string(gdata)
		if springBootRe.MatchString(content) {
			isSpring = true
		}
		if kotlinRe.MatchString(content) {
			isKotlin = true
		}
	}

	if !isSpring && !isKotlin {
		return nil
	}

	product := detectProductFromPath(servicePath, "")

	return &types.ScanResult{
		ServiceName: serviceName,
		Product:     product,
	}
}
