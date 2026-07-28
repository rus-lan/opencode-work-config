---
lang: es
kind: doc
---

# Primeros pasos con la pasarela de API RPC

En el mundo de la infraestructura blockchain, la pasarela de API RPC juega un papel fundamental. Es una solución integral, robusta y potente que conecta tus aplicaciones con la red de nodos. Además, la plataforma ofrece una experiencia de usuario fluida que abstrae toda la complejidad. Esta documentación introduce los conceptos básicos, el flujo de autenticación y el ciclo de cada petición.

La pasarela no solo es un proxy, sino también una plataforma de orquestación de nodos de vanguardia. Asimismo, enruta el tráfico entre nodos distribuidos para ofrecer respuestas rápidas, estables y de baja latencia. Es importante destacar que el sistema mantiene una disponibilidad del 99.9% en todas las regiones. Cabe destacar que cada endpoint comparte un esquema uniforme que simplifica la integración.

Para empezar, autenticas cada petición con una clave de API en la cabecera `Authorization`. La URL base de todas las peticiones es https://api.example.com y se mantiene estable entre versiones. En consecuencia, esta consistencia te permite centrarte en la lógica de tu aplicación.

Una petición mínima se parece al siguiente ejemplo.

```bash
curl -X POST https://api.example.com/v1/rpc \
  -H "Authorization: Bearer <tu-clave-api>" \
  -d '{"method":"getBlockNumber"}'
```

La respuesta llega en milisegundos y lleva una carga limpia, predecible y bien documentada. Por otro lado, la pasarela no solo valida tu petición, sino también la enriquece con diagnósticos útiles. La plataforma ofrece una experiencia «orientada al desarrollador» que resulta intuitiva desde la primera llamada. En definitiva, este enfoque revolucionario permite a los equipos construir más rápido, lanzar antes y escalar más lejos.
