---
title: Passerelle d'API RPC
lang: fr
kind: doc
---

# Passerelle d'API RPC

La passerelle d'API RPC sert de point d'entrée unique vers un parc de nœuds. Elle reçoit chaque requête, la valide, puis la renvoie vers le bon réseau selon la chaîne visée et l'état des nœuds disponibles à cet instant. Une seule adresse à connaître. Plus besoin d'en gérer une par chaîne.

Elle gère le routage, la mise en cache et la limitation de débit. La même interface couvre les appels par lots ainsi que les abonnements aux flux. Visez une disponibilité de 99.9%. La fiabilité tient surtout à ces mécanismes, qui amortissent les pics de trafic et coupent les requêtes abusives avant qu'elles n'atteignent les nœuds, pas à un effet d'annonce.

Le gain de latence vient de deux choses. La mise en cache locale évite des allers-retours, et l'authentification se règle en amont une fois pour toutes. Pour envoyer une requête, utilisez le champ `method` avec le point de terminaison `eth_blockNumber`.

```bash
curl -X POST https://api.example.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

Trois transports passent par la même clé: HTTP, WebSocket et gRPC. Ce découpage modulaire vous laisse ajouter un nouveau transport sans toucher au reste du code, ce qui compte quand l'équipe grandit et que plusieurs personnes travaillent sur la même passerelle. Pour une grosse architecture distribuée, c'est un bon point de départ.
