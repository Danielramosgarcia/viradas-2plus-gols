# whatsapp.py — Envio de mensagens via Evolution API

import os
import sys
import requests

EVOLUTION_URL = os.environ.get("EVOLUTION_URL", "http://evolution-api:8080")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "viradas-bot")
WHATSAPP_NUMBERS = os.environ.get("WHATSAPP_NUMBERS", "").split(",")


def send_message(text, numbers=None):
    """Envia mensagem de texto via Evolution API."""
    if numbers is None:
        numbers = WHATSAPP_NUMBERS

    results = []
    for number in numbers:
        number = number.strip()
        if not number:
            continue

        try:
            response = requests.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
                headers={
                    "Content-Type": "application/json",
                    "apikey": EVOLUTION_API_KEY,
                },
                json={
                    "number": number,
                    "textMessage": {"text": text},
                },
                timeout=30,
            )
            if response.status_code in (200, 201):
                print(f"[WHATSAPP] Mensagem enviada para {number}")
                results.append({"number": number, "status": "sent"})
            else:
                print(f"[WHATSAPP] Erro ao enviar para {number}: {response.status_code} {response.text}")
                results.append({"number": number, "status": "error", "detail": response.text})
        except Exception as e:
            print(f"[WHATSAPP] Exceção ao enviar para {number}: {e}")
            results.append({"number": number, "status": "error", "detail": str(e)})

    return results


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Teste do bot Viradas 2+ Gols!"
    print(f"Enviando: {msg}")
    send_message(msg)
