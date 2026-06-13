"""KI-Backends: Claude (Cloud) und OpenAI-kompatibel (Ollama/Open-WebUI/KI-Core).

Beide Provider liefern dasselbe Ergebnis-Dict:
    {<feldname>: {"wert": ..., "confidence_prozent": int, "begruendung": str}, ...,
     "gesamt_confidence": int, "zusammenfassung": str}
"""
import json
import re
import urllib.request

from stonebook.ai.analysis_schema import AI_FIELDS, build_tool, field_definitions_text

SYSTEM_PROMPT = """Du bist ein erfahrener Mineraloge und bestimmst Gesteins- und \
Mineralproben anhand von Fotos (Tageslicht, Mikroskop/Makro, UV 365/395 nm) und \
vorhandenen Felddaten einer privaten Sammlung aus der Schweiz (v.a. Region St. Gallen, \
Geröll/Schotter-Funde).

Regeln:
- Nur belegbare Aussagen treffen; bei Unsicherheit konservative Confidence-Werte vergeben.
- Felder ohne belastbare Grundlage: wert=null.
- Maße/Gewicht nur schätzen, wenn ein Maßstab erkennbar ist (kariertes Papier 5mm, Lineal); sonst null.
- Wertangaben (CHF/USD) sind grobe Schätzungen für Sammlerstücke dieser Art und Größe.
- Alle Texte auf Deutsch.

Felddefinitionen:
{felder}"""


def _known_data_text(object_data: dict) -> str:
    known = {k: v for k, v in object_data.items() if v is not None and str(v).strip()}
    return ("Bereits erfasste Felddaten des Objekts (als Kontext, ggf. korrigieren):\n"
            + json.dumps(known, ensure_ascii=False, indent=1)
            + "\n\nBestimme das Objekt und fülle alle ableitbaren Felder aus.")


def coerce_result(raw: dict) -> dict:
    """Validiert/normalisiert eine (ggf. unsaubere) Modellantwort in das Standardformat."""
    result: dict = {}
    num_fields = {f.name for f in AI_FIELDS if f.ftype in ("int", "scale")}
    float_fields = {f.name for f in AI_FIELDS if f.ftype == "float"}
    valid = {f.name for f in AI_FIELDS}
    for name, entry in raw.items():
        if name not in valid:
            continue
        if not isinstance(entry, dict):
            entry = {"wert": entry, "confidence_prozent": 0}
        wert = entry.get("wert")
        if isinstance(wert, str) and not wert.strip():
            wert = None
        if wert is not None and (name in num_fields or name in float_fields):
            try:
                num = float(str(wert).replace(",", ".").split()[0])
                wert = int(num) if name in num_fields else num
            except (ValueError, IndexError):
                wert = None
        try:
            conf = int(entry.get("confidence_prozent") or 0)
        except (ValueError, TypeError):
            conf = 0
        result[name] = {
            "wert": wert,
            "confidence_prozent": max(0, min(100, conf)),
            "begruendung": str(entry.get("begruendung") or ""),
        }
    try:
        result["gesamt_confidence"] = max(0, min(100, int(raw.get("gesamt_confidence") or 0)))
    except (ValueError, TypeError):
        result["gesamt_confidence"] = 0
    result["zusammenfassung"] = str(raw.get("zusammenfassung") or "")
    return result


def extract_json(text: str) -> dict:
    """Holt das erste vollständige JSON-Objekt aus einem (evtl. umrahmten) Text."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("Keine JSON-Struktur in der Antwort gefunden.")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Unvollständiges JSON in der Antwort.")


class AnthropicProvider:
    name = "Claude (Anthropic Cloud)"

    def __init__(self, api_key: str, model: str, timeout: float = 180.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def analyse(self, images: list[tuple[str, str, str]], object_data: dict) -> dict:
        import anthropic

        content = []
        for label, b64, media_type in images:
            content.append({"type": "text", "text": label})
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64}})
        content.append({"type": "text", "text": _known_data_text(object_data)})

        client = anthropic.Anthropic(api_key=self.api_key)
        tool = build_tool()
        msg = client.messages.create(
            model=self.model,
            max_tokens=8000,
            timeout=self.timeout,
            system=SYSTEM_PROMPT.format(felder=field_definitions_text()),
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return coerce_result(block.input)
        raise RuntimeError("Keine strukturierte Antwort vom Modell erhalten.")


class OpenAICompatProvider:
    """Ollama, Open-WebUI, LM Studio, OpenClaw-Gateway / KI-Core — alles OpenAI-/chat-kompatibel."""
    name = "Lokal / OpenAI-kompatibel"

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _json_instructions(self) -> str:
        keys = ", ".join(f'"{f.name}"' for f in AI_FIELDS)
        return (
            "\n\nAntworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt, ohne weiteren Text.\n"
            "Form: jedes Feld ist ein Objekt {\"wert\": <Wert oder null>, "
            "\"confidence_prozent\": <0-100>, \"begruendung\": <kurzer Text>}.\n"
            f"Erlaubte Feld-Schlüssel: {keys}.\n"
            "Zusätzlich auf oberster Ebene: \"gesamt_confidence\": <0-100> und "
            "\"zusammenfassung\": <2-4 Sätze>.")

    def analyse(self, images: list[tuple[str, str, str]], object_data: dict) -> dict:
        content = []
        for label, b64, media_type in images:
            content.append({"type": "text", "text": label})
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{b64}"}})
        content.append({"type": "text",
                        "text": _known_data_text(object_data) + self._json_instructions()})

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(felder=field_definitions_text())},
                {"role": "user", "content": content},
            ],
            "temperature": 0.2,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        text = self._post(payload)
        return coerce_result(extract_json(text))

    def _post(self, payload: dict) -> str:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unerwartete Antwortstruktur des Servers: {e}") from e

    def test_connection(self) -> str:
        """Listet Modelle (GET /models) — wirft bei Fehler eine Exception."""
        req = urllib.request.Request(f"{self.base_url}/models", method="GET")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        models = [m.get("id", "?") for m in body.get("data", [])]
        return f"Verbindung OK – {len(models)} Modelle verfügbar."
