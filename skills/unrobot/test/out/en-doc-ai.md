---
lang: en
kind: doc
---

# Getting started with the RPC API Gateway

The RPC API Gateway is the layer that connects your applications to blockchain networks. Every request you send passes through it. It scales, it stays up, and it hides the node complexity underneath so you don't have to manage nodes yourself. This page walks through the core concepts, how authentication works, and what happens to a request from start to finish.

It is more than a proxy. The gateway routes traffic across distributed nodes, which keeps responses fast and latency low. Published uptime sits at 99.9% across all supported regions. Every endpoint shares one schema, so integration stays simple.

You authenticate each request with an API key, passed in the `Authorization` header. The base URL for all requests is https://api.example.com, and it does not change between versions. That stability means you can think about your application logic instead of your infrastructure.

Here is a minimal request.

```bash
curl -X POST https://api.example.com/v1/rpc \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{"method":"getBlockNumber"}'
```

Responses come back in milliseconds. The payload is predictable and documented. The gateway validates your request and adds diagnostics that help when something goes wrong. It was built to feel right from the first call, and that is the whole point: teams ship sooner and grow without rebuilding the plumbing.
