---
lang: de
kind: doc
---

# RPC-API-Gateway: Übersicht

Ein RPC-API-Gateway steht zwischen Ihrer Anwendung und den Nodes. Moderne Anwendungen brauchen Tempo, und sie dürfen dabei nicht an Zuverlässigkeit verlieren. Das ist der ganze Anspruch. Unsere Node-Plattform fügt sich in bestehende Infrastruktur ein. Sie müssen kaum etwas umbauen. Für Entwickler bringt sie eigene Werkzeuge mit, und auch Betreiber und Architekten finden, was sie für ihre Arbeit am Gateway brauchen.

Das Gateway ist stark. Trotzdem lässt es sich erstaunlich einfach bedienen, was im Alltag mehr zählt als jede Benchmark-Zahl. Teams werden so in Minuten produktiv statt in Tagen. Die Plattform garantiert eine Verfügbarkeit von 99.9%. Diese Zahl ergibt sich aus der Architektur dahinter, nicht aus einem Versprechen auf einer Folie.

## Schnellstart

Ein einziger Aufruf reicht. Senden Sie eine Anfrage an den Endpunkt `eth_blockNumber`, um den aktuellen Block zu erhalten.

```bash
curl -X POST https://api.example.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
```

Die Lösung deckt viele Anwendungsfälle ab. Lesezugriffe gehören dazu, ebenso Schreibzugriffe, und wer Live-Daten braucht, abonniert einfach einen Stream. Damit wird das Gateway zur zentralen Schnittstelle für jede dezentrale Anwendung, egal wie groß.

## Authentifizierung

Jeder Aufruf braucht einen API-Schlüssel. Übergeben Sie den Schlüssel im Header, dann prüft die Plattform ihn selbst und lässt den Rest sicher durchlaufen. Mehr ist nicht nötig.
