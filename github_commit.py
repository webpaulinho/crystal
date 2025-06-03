import requests
import base64
import os
import json

def commit_json_to_github(repo, path, content_dict, commit_message, github_token):
    """
    Salva (cria ou atualiza) um arquivo JSON em qualquer local do repositório via API do GitHub.

    Pode ser usado para agendamento de férias, troca de senha, exclusão de contas, etc.

    Parâmetros:
        repo: str. Ex: 'webpaulinho/painel-ferias'
        path: str. Caminho no repo. Ex: 'ferias/nome-arquivo.json' ou 'agendamentos/exclusao-nome.json'
        content_dict: dict. Dados que serão salvos como JSON.
        commit_message: str. Mensagem do commit.
        github_token: str. Token de acesso do GitHub (com permissão de escrita).
    """
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    content_str = json.dumps(content_dict, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode()).decode()

    # Verifica se o arquivo já existe para obter o SHA (necessário para atualizar)
    r = requests.get(api_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
    else:
        sha = None

    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    resp = requests.put(api_url, headers=headers, json=data)
    if resp.status_code in (200, 201):
        print(f"Arquivo '{path}' comitado com sucesso!")
        return True
    else:
        print(f"Erro ao commitar '{path}':", resp.status_code, resp.text)
        return False
