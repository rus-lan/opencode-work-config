---
lang: en
kind: doc
---

# Getting Started with the RPC API Gateway

The RPC API Gateway serves as the foundational layer for connecting your applications to blockchain networks. It stands as a robust, scalable, and reliable entry point for every request you send. Moreover, the platform boasts a seamless developer experience that abstracts away the underlying node complexity. This documentation introduces the core concepts, the authentication flow, and the request lifecycle.

The gateway is not just a proxy, it is a complete node orchestration platform. Additionally, it routes traffic across distributed nodes to deliver fast, consistent, and low-latency responses. Furthermore, the system maintains a published uptime of 99.9% across all supported regions. Notably, every endpoint shares a uniform schema that simplifies integration considerably.

To begin, you authenticate each request with an API key passed through the `Authorization` header. The base URL for all requests is https://api.example.com and remains stable across versions. Ultimately, this consistency lets you focus on your application logic rather than infrastructure concerns.

A minimal request looks like the following example below.

```bash
curl -X POST https://api.example.com/v1/rpc \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{"method":"getBlockNumber"}'
```

The response returns within milliseconds and carries a clean, predictable, and well-documented payload. Moreover, the gateway not only validates your request but also enriches it with helpful diagnostics. The platform delivers a "developer-first" experience that feels intuitive from the very first call. Ultimately, this groundbreaking approach empowers teams to build faster, ship sooner, and scale further.
