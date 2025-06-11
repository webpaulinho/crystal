import os
import sys
import json
import requests
from datetime import datetime
import time
import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build
import tempfile
from pprint import pprint
import traceback

# Adiciona o diretório raiz ao sys.path para importar github_commit.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from github_commit import commit_json_to_github

# DEBUG: Verificando se o JSON da conta foi carregado corretamente
print("DEBUG: Primeiro caractere do JSON da conta:", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_SCRIPT", "")[:1])

# Usa variável exclusiva para o script
if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_SCRIPT") and not os.path.exists("service-account-script.json"):
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON_SCRIPT"])
        SERVICE_ACCOUNT_FILE = f.name
else:
    SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_SCRIPT", "service-account-script.json")

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']
print(f"BACKEND_URL: {BACKEND_URL}")
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')
FERIAS_SENHA_PADRAO = os.environ["FERIAS_SENHA_PADRAO"]
SAIDA_SENHA_PADRAO = os.environ["SAIDA_SENHA_PADRAO"]
GMAIL_SENDER = "administrador@tecafrio.com.br"
GMAIL_RECIPIENT = "paulo.quintino@tecafrio.com.br"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service(user_email):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES, subject=user_email
    )
    return build('gmail', 'v1', credentials=creds)

def send_email_gmail_api(service, to, subject, body):
    try:
        message = MIMEText(body, 'plain')
        message['to'] = to
        message['subject'] = subject
        message['from'] = GMAIL_SENDER
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        payload = {'raw': raw}

        print("📤 Payload do e-mail:")
        pprint(payload)

        print("📨 Tentando enviar e-mail via Gmail API...")
        result = service.users().messages().send(userId="me", body=payload).execute()
        print("✅ E-mail enviado com sucesso!")
        pprint(result)
        return True
    except Exception as err:
        print("❌ Erro ao tentar enviar e-mail:")
        traceback.print_exc()
        return False

def wait_for_service_ready(url, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("✅ Serviço backend está pronto!")
                return True
        except requests.ConnectionError:
            pass
        print("⏳ Aguardando o serviço backend ficar pronto...")
        time.sleep(5)
    print("⛔ Timeout ao esperar o backend.")
    return False

def main():
    hoje = datetime.utcnow().date().isoformat()
    for filename in os.listdir(FERIAS_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(FERIAS_DIR, filename)
        with open(filepath, encoding='utf-8') as f:
            dados = json.load(f)

        data_inicio = dados.get('data_inicio')
        email = dados.get('email')
        nome = dados.get('nome', email)
        processado = dados.get('processado', False)

        print(f"\n🗂️ Verificando arquivo: {filename}")
        print(f"📅 Início programado: {data_inicio} | Hoje: {hoje} | Processado: {processado}")

        if data_inicio == hoje and not processado:
            print(f"🔐 Iniciando troca de senha para: {email}")
            payload = {
                "alterarSenha": True,
                "tipoAlteracaoSenha": "ferias",
                "novaSenha": FERIAS_SENHA_PADRAO,
                "changeAtNextLogin": True
            }

            headers = {'Content-Type': 'application/json'}
            if AUTH_TOKEN:
                headers['Authorization'] = f'Bearer {AUTH_TOKEN}'

            try:
                print(f"➡️ POST para {BACKEND_URL}/api/alterar-senha/{email}")
                resp = requests.post(f"{BACKEND_URL}/api/alterar-senha/{email}", json=payload, headers=headers)
                print(f"🧾 Resposta: {resp.status_code} {resp.text}")

                try:
                    resposta_json = resp.json() if 'application/json' in resp.headers.get('Content-Type', '') else {}
                except Exception as err:
                    print("⚠️ Erro ao parsear JSON da resposta.")
                    traceback.print_exc()
                    resposta_json = {}

                service = get_gmail_service(GMAIL_SENDER)

                if resp.status_code == 200 and resposta_json.get("ok"):
                    dados['processado'] = True
                    print("🛠️ Atualizando campo 'processado' para True...")
                    print("🆕 Conteúdo final a ser salvo no GitHub:")
                    print(json.dumps(dados, indent=2, ensure_ascii=False))

                    repo = "webpaulinho/painel-ferias"
                    path = f"{FERIAS_DIR}/{filename}"
                    commit_message = f"Marca processado para {email} via sistema automático"
                    github_token = os.environ.get("GITHUB_TOKEN")
                    print("🔐 GITHUB_TOKEN definido:", bool(github_token))

                    sucesso = commit_json_to_github(repo, path, dados, commit_message, github_token)
                    print("📌 commit_json_to_github retornou:", sucesso)
                    if sucesso:
                        print(f"✅ JSON atualizado no GitHub: {path}")
                    else:
                        print(f"❌ Erro ao atualizar JSON no GitHub: {path}")
                        print("‼️ Verifique se o token, branch e permissões estão corretos.")

                    assunto = f"Senha de {nome} alterada com sucesso"
                    corpo = f"A senha de {nome} foi alterada automaticamente hoje ({hoje})."
                else:
                    assunto = f"[ERRO] Falha ao alterar senha de {nome}"
                    corpo = f"Erro ao tentar alterar senha de {email}. Status: {resp.status_code}\nResposta: {resp.text}"

                if not send_email_gmail_api(service, to=GMAIL_RECIPIENT, subject=assunto, body=corpo):
                    print("⚠️ Falha ao enviar e-mail de notificação.")
            except Exception as e:
                print(f"❌ Erro geral para {email}:")
                traceback.print_exc()

if __name__ == "__main__":
    backend_healthcheck_url = f"{BACKEND_URL}/healthcheck"
    if wait_for_service_ready(backend_healthcheck_url):
        main()
    else:
        print("⛔ Backend não respondeu. Saindo.")
