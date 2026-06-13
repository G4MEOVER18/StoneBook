# KI-Backends in StoneBook

StoneBook kann die mineralogische Bildanalyse über zwei austauschbare Backends ausführen.
Beide liefern dasselbe Ergebnis: pro Feld einen Vorschlag mit Confidence-Wert und Begründung.

## Überblick

| Eigenschaft | Claude (Cloud) | Lokal / OpenAI-kompatibel |
|---|---|---|
| Datenschutz | Bilder verlassen das Gerät | Bleibt im eigenen Netz / offline |
| Qualität | Sehr hoch (Tool-Use, JSON-Schema erzwungen) | Modellabhängig |
| Kosten | API-Nutzung | Eigene Hardware |
| Strukturierte Antwort | Erzwungenes Tool-Use | JSON-Modus + robustes Parsing |

Das Backend wird unter **Einstellungen → KI-Backend** gewählt und in den App-Settings
gespeichert. API-Keys liegen im **Windows Credential Manager** (keyring), nie im Repo.

## Claude (Anthropic Cloud)

1. API-Key (`sk-ant-…`) in den Einstellungen hinterlegen.
2. Modell wählen: `claude-sonnet-4-6` (Standard) oder `claude-opus-4-7` (stärker).

Die Analyse nutzt erzwungenes **Tool-Use** mit einem JSON-Schema über alle Felder — die
Antwort ist damit garantiert maschinenlesbar.

## Lokal / OpenAI-kompatibel

Funktioniert mit jedem Server, der den Endpunkt `POST /chat/completions` im OpenAI-Format
mit `image_url`-Inhalten (base64 Data-URI) versteht.

### Ollama

```bash
ollama pull gemma3:27b        # vision-fähiges Modell
ollama serve                  # stellt http://localhost:11434/v1 bereit
```

In den Einstellungen:
- Vorlage **„Ollama (lokal)"** → Base-URL `http://localhost:11434/v1`
- Modell z.B. `gemma3:27b`, `llava`, `qwen2.5-vl`, `llama3.2-vision`
- API-Key leer

### Open-WebUI

- Base-URL `http://<host>:3000/api`
- API-Key aus Open-WebUI (Einstellungen → Konto → API-Keys)

### LM Studio

- Lokalen Server starten (Port 1234), Base-URL `http://localhost:1234/v1`

### OpenClaw-Gateway / KI-Core

Eigene Node-Infrastruktur mit OpenAI-kompatiblem Endpunkt:
- Base-URL `http://<host>:18789/v1`
- Bearer-Token als API-Key
- Modell z.B. `openclaw/main` (oder das dahinterliegende Vision-Modell)

> **Wichtig:** Für die Bildanalyse muss das Modell Bilder verarbeiten können. Reine
> Text-Modelle liefern keine sinnvollen Ergebnisse. Der Button **„Verbindung testen"**
> prüft Erreichbarkeit und listet die verfügbaren Modelle.

## Timeout

Lokale Modelle haben oft einen Cold-Start (~30–60 s). Der Timeout ist in den Einstellungen
konfigurierbar (Standard 180 s).

## Wie die strukturierte Antwort entsteht

- **Claude:** `tool_choice` erzwingt das Tool `analyse_ergebnis` mit vollständigem JSON-Schema.
- **Lokal:** `response_format={"type":"json_object"}` plus eine präzise Feldliste im Prompt;
  die Antwort wird mit einem klammer-balancierenden Parser extrahiert und über
  `coerce_result()` typgeprüft (Zahlen, Confidence-Clamping, Filtern unbekannter Felder).

Beide Wege münden im selben Vorschlagsdialog mit farbcodierter Confidence
(grün ≥ 80, gelb ≥ 50, rot < 50) und selektiver Übernahme ins Datenblatt.
