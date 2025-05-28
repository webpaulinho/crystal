import os
import json
import requests
from datetime import datetime

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']  # Exemplo: https://msgferias.onrender.com/api/vacation/
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')  # Só se precisar

def main():
    hoje = datetime.utcnow().date().isoformat()  # 'YYYY-MM-DD'
    for filename in os.listdir(FERIAS_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(FERIAS_DIR, filename)
        with open(filepath) as f:
            dados = json.load(f)

        data_inicio = dados.get('data_inicio')
        email = dados.get('email')
        processado = dados.get('processado', False)

        # Só processa se for hoje e ainda não foi processado
        if data_inicio == hoje and not processado:
            print(f'Alterando senha para: {email}')
            payload = {
                "alterarSenha": True,
                "tipoAlteracaoSenha": "ferias"
            }
            headers = {'Content-Type': 'application/json'}
            if AUTH_TOKEN:
                headers['Authorization'] = f'Bearer {AUTH_TOKEN}'
            try:
                resp = requests.post(f"{BACKEND_URL}{email}", json=payload, headers=headers)
                print(f"Resposta para {email}: {resp.status_code} {resp.text}")
                if resp.status_code == 200:
                    # Marca como processado
                    dados['processado'] = True
                    with open(filepath, "w") as f:
                        json.dump(dados, f, ensure_ascii=False, indent=2)
                else:
                    print(f"Erro ao alterar senha de {email}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"Erro de requisição para {email}: {e}")

if __name__ == "__main__":
    main()
