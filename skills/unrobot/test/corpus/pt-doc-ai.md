---
lang: pt
kind: doc
---

# Guia do Gateway de API RPC

No mundo atual, o gateway de API RPC desempenha um papel crucial na infraestrutura de qualquer aplicação descentralizada. Esta plataforma de nós robusta foi projetada para entregar desempenho, segurança e confiabilidade. Vale ressaltar que cada requisição é roteada de forma transparente para o nó mais saudável. Além disso, a arquitetura poderosa garante uma disponibilidade de 99.9% em todas as regiões.

É importante destacar que a integração é simples e direta. Consequentemente, qualquer desenvolvedor pode começar em minutos. Por outro lado, soluções legadas exigem configuração manual extensa. Dessa forma, nossa solução completa elimina essa complexidade por completo.

Para enviar sua primeira chamada, use o endpoint base `https://api.example.com` com sua chave. O parâmetro `method` define a operação desejada. Atualmente, oferecemos uma ampla gama de métodos padrão do protocolo.

```bash
curl https://api.example.com \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

A resposta retorna o número do bloco atual de forma transparente. Por fim, é importante destacar que cada chave suporta limites configuráveis, monitoramento detalhado e alertas automáticos. Em suma, o gateway oferece tudo que sua equipe precisa para escalar com confiança, velocidade e tranquilidade. Sem dúvida, esta é a abordagem de ponta que define o padrão do mercado moderno.
