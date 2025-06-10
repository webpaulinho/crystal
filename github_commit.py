import requests
import base64
import os
import json

def commit_json_to_github(repo, path, content_dict, commit_message, github_token):
    """
    Salva (cria ou atualiza) um arquivo JSON em qualquer local do repositório via API do GitHub.
    """
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json"
    }
    content_str = json.dumps(content_dict, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode()).decode()

    # Verifica se o arquivo já existe para obter o SHA (necessário para atualizar)
    print(f"Verificando existência do arquivo: {path}")
    r = requests.get(api_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        print(f"Arquivo existente encontrado com SHA: {sha}")
    else:
        sha = None
        print(f"Arquivo não encontrado. Status code: {r.status_code}, Resposta: {r.text}")

    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    print(f"Enviando requisição para salvar arquivo: {path}")
    resp = requests.put(api_url, headers=headers, json=data)
    if resp.status_code in (200, 201):
        print(f"✅ Arquivo '{path}' salvo com sucesso! Status code: {resp.status_code}")
        return True
    else:
        print("❌ Falha ao salvar no GitHub:")
        print(f"🔁 URL chamada: {api_url}")
        print("📦 Payload enviado:")
        print(json.dumps(data, indent=2))
        print(f"🔑 Token presente? {'Sim' if github_token else 'Não'}")
        print(f"📄 Status code: {resp.status_code}")
        print("🧾 Resposta completa da API:")
        print(resp.text)
        return False
