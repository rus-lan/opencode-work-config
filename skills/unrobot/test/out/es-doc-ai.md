---
lang: es
kind: doc
---

# Primeros pasos con la pasarela de API RPC

La pasarela de API RPC conecta tus aplicaciones con la red de nodos. Hace de capa intermedia: recibe tu petición, la enruta al nodo adecuado y te devuelve la respuesta. Esta documentación cubre lo básico. Verás cómo funciona la autenticación y qué pasa en cada petición, paso a paso.

Por dentro es algo más que un proxy. La pasarela reparte el tráfico entre nodos distribuidos, así que las respuestas llegan rápido y con poca latencia. El sistema mantiene una disponibilidad del 99.9% en todas las regiones. Y todos los endpoints comparten el mismo esquema, lo que te ahorra tener que aprender un formato distinto por cada uno.

Para empezar, autenticas cada petición con una clave de API en la cabecera `Authorization`. La URL base es https://api.example.com y no cambia entre versiones. Eso te deja centrarte en la lógica de tu aplicación.

Una petición mínima se parece a esto.

```bash
curl -X POST https://api.example.com/v1/rpc \
  -H "Authorization: Bearer <tu-clave-api>" \
  -d '{"method":"getBlockNumber"}'
```

La respuesta llega en milisegundos. Su carga es limpia y predecible, y viene documentada. Además de validar tu petición, la pasarela le añade diagnósticos que te ayudan a depurar. Desde la primera llamada notarás que la API es cómoda de usar. Con este enfoque los equipos construyen más rápido y lanzan antes.
