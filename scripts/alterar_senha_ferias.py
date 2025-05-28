import os
import json
import requests
from datetime import datetime

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']  # Exemplo: https://msgferias.onrender.com/api/vacation/
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')  # Só se precisar

def main():
    hoje = datetime.utcnow().date().isoformat()  # Exemplo: '2025-05-28'
    for filename in os.listdir(FERIAS_DIR):
        if not filename.endswith('.json'):
            continue
        with open(os.path.join(FERIAS_DIR, filename)) as f:
            dados = json.load(f)
        data_inicio = dados.get('data_inicio')
        email = dados.get('email')
        if not data_inicio or not email:
            continue
        if data_inicio == hoje:
            print(f'Alterando senha para: {email}')
            payload = {
                "alterarSenha": True,
                "tipoAlteracaoSenha": "ferias"
            }
            headers = {'Content-Type': 'application/json'}
            if AUTH_TOKEN:
                headers['Authorization'] = f'Bearer {AUTH_TOKEN}'
            resp = requests.post(f"{BACKEND_URL}{email}", json=payload, headers=headers)
            print(f"Resposta para {email}: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    main()
