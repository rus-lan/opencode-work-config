---
lang: pt
kind: doc
---

# Guia do Gateway de API RPC

O gateway de API RPC fica entre a sua aplicação e os nós. Cada requisição vai para o nó mais saudável do momento, e o roteamento acontece sem você precisar escolher nada à mão. O foco do projeto é desempenho e disponibilidade: a meta de uptime é de 99.9% em todas as regiões.

Integrar leva poucos minutos. Um desenvolvedor abre a chave, faz a primeira chamada e já está rodando. Compare com as soluções antigas, que ainda pedem configuração manual extensa antes de qualquer teste.

Para enviar a primeira chamada, use o endpoint base `https://api.example.com` com a sua chave. O parâmetro `method` define a operação. Os métodos disponíveis seguem o protocolo padrão.

```bash
curl https://api.example.com \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

A resposta traz o número do bloco atual. Cada chave tem limites configuráveis, monitoramento detalhado e alertas que disparam sozinhos quando algo sai do esperado. É o suficiente para a sua equipe escalar com calma, sem surpresas de configuração no meio do caminho.
