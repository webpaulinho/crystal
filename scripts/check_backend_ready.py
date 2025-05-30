import requests
import time
import sys
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "https://msgferias.onrender.com/")  # Usa o valor do secret, mas já deixa seu endereço por padrão
MAX_TRIES = 10
WAIT_SECONDS = 6

for i in range(MAX_TRIES):
    try:
        resp = requests.get(BACKEND_URL, timeout=5)
        if resp.status_code < 500:
            print(f"Backend online! ({i+1} tentativas) Status: {resp.status_code}")
            sys.exit(0)
        else:
            print(f"Tentativa {i+1}: Status {resp.status_code} (backend ainda não está pronto)")
    except Exception as e:
        print(f"Tentativa {i+1}: Backend ainda não está pronto... ({e})")
    time.sleep(WAIT_SECONDS)

print("Backend não respondeu a tempo. Abortando.")
sys.exit(1)
