package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/sbmt/slo-kit-generator/internal/generator"
	"github.com/sbmt/slo-kit-generator/internal/scanner"
	"github.com/sbmt/slo-kit-generator/internal/types"
)

func main() {
	if len(os.Args) < 2 {
		printHelp()
		os.Exit(1)
	}

	switch os.Args[1] {
	case "generate":
		cmdGenerate(os.Args[2:])
	case "scan":
		cmdScan(os.Args[2:])
	case "help", "--help", "-h":
		printHelp()
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n\n", os.Args[1])
		printHelp()
		os.Exit(1)
	}
}

func cmdGenerate(args []string) {
	fs := flag.NewFlagSet("generate", flag.ExitOnError)
	profile := fs.String("profile", "ecomtech-letsgo", "slo-kit profile")
	namespace := fs.String("namespace", "", "kubernetes namespace")
	service := fs.String("service", "", "service name (auto-detected from app.letsgo.yaml)")
	product := fs.String("product", "", "product name (auto-detected from app.letsgo.yaml)")
	team := fs.String("team", "", "team name")
	costCentre := fs.String("cost-centre", "", "cost centre")
	output := fs.String("output", "configs/slo-kit.yaml", "output file path")
	fs.Parse(args)

	if fs.NArg() < 1 {
		fmt.Fprintln(os.Stderr, "usage: slokit generate <service-path> [flags]")
		fs.PrintDefaults()
		os.Exit(1)
	}

	servicePath := fs.Arg(0)
	result, err := scanService(servicePath, *profile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "scan error: %v\n", err)
		os.Exit(1)
	}

	yaml := generator.Generate(result, types.GenerateOptions{
		ServicePath: servicePath,
		Profile:     *profile,
		Namespace:   *namespace,
		Service:     *service,
		Product:     *product,
		Team:        *team,
		CostCentre:  *costCentre,
		Output:      *output,
	})

	outPath := *output
	if outPath == "configs/slo-kit.yaml" {
		outPath = servicePath + "/configs/slo-kit.yaml"
	}
	os.MkdirAll(servicePath+"/configs", 0755)
	if err := os.WriteFile(outPath, []byte(yaml), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "write error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Generated: %s\n", outPath)
	fmt.Printf("  HTTP endpoints: %d\n", countEndpoints(result))
	fmt.Printf("  Consumers: %d (topics: %d)\n", len(result.Consumers), countTopics(result))
	fmt.Printf("  Jobs: %d\n", len(result.Jobs))
	fmt.Printf("  Adapters: %d\n", len(result.Adapters))
	if len(result.Warnings) > 0 {
		fmt.Println("  Warnings:")
		for _, w := range result.Warnings {
			fmt.Printf("    - %s\n", w)
		}
	}
}

func cmdScan(args []string) {
	fs := flag.NewFlagSet("scan", flag.ExitOnError)
	profile := fs.String("profile", "ecomtech-letsgo", "slo-kit profile")
	fs.Parse(args)

	if fs.NArg() < 1 {
		fmt.Fprintln(os.Stderr, "usage: slokit scan <service-path> [--profile X]")
		os.Exit(1)
	}

	servicePath := fs.Arg(0)
	result, err := scanService(servicePath, *profile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "scan error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Service: %s\n", result.ServiceName)
	fmt.Printf("Product: %s\n", result.Product)
	fmt.Printf("Profile: %s\n", *profile)

	if result.OpenAPI != nil {
		spec := result.OpenAPI.SpecPath
		if spec == "" {
			spec = "(unknown)"
		}
		fmt.Printf("\nOpenAPI (%s, spec: %s): %d endpoints\n", result.OpenAPI.Title, spec, len(result.OpenAPI.Endpoints))
		for _, ep := range result.OpenAPI.Endpoints {
			tag := ep.Tag
			if tag == "" {
				tag = "(no tag)"
			}
			fmt.Printf("  [%s] %s %s\n", tag, ep.Method, ep.Path)
		}
	}

	fmt.Printf("\nConsumers: %d\n", len(result.Consumers))
	for _, c := range result.Consumers {
		fmt.Printf("  %s (group: %s, topics: %v)\n", c.DriverName, c.GroupID, c.Topics)
	}

	fmt.Printf("\nJobs: %d\n", len(result.Jobs))
	for _, j := range result.Jobs {
		fmt.Printf("  %s (controller: %s)\n", j.Name, j.Controller)
	}

	fmt.Printf("\nAdapters: %d\n", len(result.Adapters))
	for _, a := range result.Adapters {
		fmt.Printf("  %s (spec: %s, protocol: %s)\n", a.Name, a.SpecPath, a.Protocol)
	}

	if len(result.GraphQL) > 0 {
		fmt.Printf("\nGraphQL: %d\n", len(result.GraphQL))
		for _, g := range result.GraphQL {
			fmt.Printf("  %s (type=%s)\n", g.Name, g.Type)
		}
	}

	if len(result.Routes) > 0 {
		fmt.Printf("\nRoutes: %d\n", len(result.Routes))
		for _, r := range result.Routes {
			fmt.Printf("  %s %s#%s\n", r.Method, r.Controller, r.Action)
		}
	}

	if len(result.QueJobs) > 0 {
		fmt.Printf("\nQue Jobs: %d\n", len(result.QueJobs))
		for _, j := range result.QueJobs {
			fmt.Printf("  %s (queue: %s)\n", j.Name, j.Queue)
		}
	}

	if len(result.Warnings) > 0 {
		fmt.Println("\nWarnings:")
		for _, w := range result.Warnings {
			fmt.Printf("  - %s\n", w)
		}
	}
}

func scanService(path, profile string) (*types.ScanResult, error) {
	result, warnings := scanner.ParseLetsgo(path)
	if result == nil {
		result = scanner.ParseGradle(path)
		if result == nil {
			result = scanner.ParseGoMod(path)
			if result == nil {
				result = &types.ScanResult{}
			}
		}
	}
	result.Profile = profile
	result.Warnings = warnings

	openapi, openapiWarnings, err := scanner.ParseOpenAPI(path, result.OwnSpecPath)
	if err != nil {
		result.Warnings = append(result.Warnings, "openapi: "+err.Error())
	} else {
		result.Warnings = append(result.Warnings, openapiWarnings...)
		if openapi != nil {
			result.OpenAPI = openapi
		}
	}

	if result.OpenAPI == nil {
		if spring := scanner.ParseSpring(path); spring != nil {
			result.OpenAPI = spring
		}
	}

	scanner.ResolveTopics(result, path)

	scanner.ParseRuby(path, result)

	return result, nil
}

func countEndpoints(r *types.ScanResult) int {
	if r.OpenAPI == nil {
		return 0
	}
	return len(r.OpenAPI.Endpoints)
}

func countTopics(r *types.ScanResult) int {
	total := 0
	for _, c := range r.Consumers {
		total += len(c.Topics)
	}
	return total
}

func printHelp() {
	fmt.Println(`slokit - генератор slo-kit.yaml из сканирования сервиса

Usage:
  slokit generate <service-path> [flags]    Сгенерировать slo-kit.yaml
  slokit scan <service-path> [--profile X]  Только сканирование (без генерации)

Flags for generate:
  --profile string      slo-kit profile (default "ecomtech-letsgo")
  --namespace string    kubernetes namespace
  --service string      service name (auto from app.letsgo.yaml or settings.gradle.kts)
  --product string      product name (auto from app.letsgo.yaml or path)
  --team string         team name
  --cost-centre string  cost centre
  --output string       output file (default "configs/slo-kit.yaml")

Examples:
  slokit scan ~/Documents/ECOM/automation
  slokit generate --namespace ts --team t102 --cost-centre E001 ~/Documents/ECOM/automation
  slokit generate --profile ecom-kotlin --namespace opercrm --team t102 ~/Documents/ECOM/gitlab/opercrm.smkt/nrt-data-api

Note: flags must come BEFORE the service path (Go flag parsing).`)
}
