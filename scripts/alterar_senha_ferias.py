import os
import json
import requests
from datetime import datetime

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']  # Ex: https://msgferias.onrender.com/api/vacation/
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')  # Se precisar de autenticação

def main():
    hoje = datetime.utcnow().date().isoformat()
    for filename in os.listdir(FERIAS_DIR):
        if not filename.endswith('.json'):
            continue
        with open(os.path.join(FERIAS_DIR, filename)) as f:
            dados = json.load(f)
        if dados.get('data_inicio') == hoje:
            email = dados['email']
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
