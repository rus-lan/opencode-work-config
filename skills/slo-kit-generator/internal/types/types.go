package types

type ScanResult struct {
	ServiceName string
	Product     string
	Profile     string
	// OwnSpecPath is the service's own OpenAPI spec declared in
	// app.letsgo.yaml (controllers.api.specPath). It disambiguates the
	// service spec from external adapter specs in the same directory.
	OwnSpecPath string
	OpenAPI     *OpenAPIScan
	Consumers   []ConsumerInfo
	Jobs        []JobInfo
	Adapters    []AdapterInfo
	GraphQL     []GraphQLOp
	Routes      []RouteInfo
	QueJobs     []QueJobInfo
	Warnings    []string
}

type OpenAPIScan struct {
	Title     string
	SpecPath  string
	Endpoints []Endpoint
}

type Endpoint struct {
	Method string
	Path   string
	Tag    string
}

type ConsumerInfo struct {
	DriverName string
	Topics     []string
	GroupID    string
}

type JobInfo struct {
	Name       string
	Controller string
}

type AdapterInfo struct {
	Name     string
	SpecPath string
	Kind     string
	Protocol string
}

type GraphQLOp struct {
	Name string
	Type string
}

type RouteInfo struct {
	Method     string
	Controller string
	Action     string
}

type QueJobInfo struct {
	Name  string
	Queue string
}

type GenerateOptions struct {
	ServicePath string
	Profile     string
	Namespace   string
	Service     string
	Product     string
	Team        string
	CostCentre  string
	Output      string
}
