import os
import json
import requests
from datetime import datetime
import time
import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']
print(f"BACKEND_URL: {BACKEND_URL}")
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')

FERIAS_SENHA_PADRAO = os.environ["FERIAS_SENHA_PADRAO"]
SAIDA_SENHA_PADRAO = os.environ["SAIDA_SENHA_PADRAO"]

SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON', 'service-account.json')
GMAIL_SENDER = "administrador@tecafrio.com.br"
GMAIL_RECIPIENT = "paulo.quintino@tecafrio.com.br"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service(user_email):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES, subject=user_email
    )
    return build('gmail', 'v1', credentials=creds)

def send_email_gmail_api(service, to, subject, body):
    message = MIMEText(body, 'plain')
    message['to'] = to
    message['subject'] = subject
    message['from'] = GMAIL_SENDER
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={'raw': raw}).execute()

def wait_for_service_ready(url, timeout=300):
    """Espera até que o serviço backend esteja pronto."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Serviço está pronto!")
                return True
        except requests.ConnectionError:
            pass
        print("Aguardando o serviço ficar pronto...")
        time.sleep(5)
    print("Timeout ao esperar o serviço.")
    return False

def main():
    hoje = datetime.utcnow().date().isoformat()
    for filename in os.listdir(FERIAS_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(FERIAS_DIR, filename)
        with open(filepath) as f:
            dados = json.load(f)

        data_inicio = dados.get('data_inicio')
        email = dados.get('email')
        nome = dados.get('nome', email)
        processado = dados.get('processado', False)

        if data_inicio == hoje and not processado:
            print(f'Alterando senha para: {email}')
            tipo_alteracao = "ferias"
            if tipo_alteracao == "ferias":
                nova_senha = FERIAS_SENHA_PADRAO
                change_at_next_login = True
            elif tipo_alteracao == "saida":
                nova_senha = SAIDA_SENHA_PADRAO
                change_at_next_login = False
            else:
                nova_senha = ""
                change_at_next_login = False

            payload = {
                "alterarSenha": True,
                "tipoAlteracaoSenha": tipo_alteracao,
                "novaSenha": nova_senha,
                "changeAtNextLogin": change_at_next_login
            }
            headers = {'Content-Type': 'application/json'}
            if AUTH_TOKEN:
                headers['Authorization'] = f'Bearer {AUTH_TOKEN}'
            try:
                # URL corrigida para o endpoint de alteração de senha
                print(f"Enviando POST para: {BACKEND_URL}/api/alterar-senha/{email}")
                resp = requests.post(f"{BACKEND_URL}/api/alterar-senha/{email}", json=payload, headers=headers)
                print(f"Resposta para {email}: {resp.status_code} {resp.text}")
                try:
                    resposta_json = resp.json()
                except ValueError:
                    print(f"⚠️ Resposta inválida (não é JSON). Conteúdo bruto: {resp.text}")
                    resposta_json = {}

                service = get_gmail_service(GMAIL_SENDER)
                if resp.status_code == 200 and resposta_json.get("ok") is not False:
                    dados['processado'] = True
                    with open(filepath, "w") as f:
                        json.dump(dados, f, ensure_ascii=False, indent=2)
                    assunto = f"Senha de {nome} alterada com sucesso"
                    corpo = (
                        f"Olá, a senha de {nome} foi alterada com sucesso conforme agendamento na data de hoje."
                    )
                else:
                    assunto = f"[ERRO] Falha ao alterar senha de {nome}"
                    corpo = (
                        f"Ocorreu um erro ao tentar alterar a senha de {nome} ({email}) na data de hoje.\n"
                        f"Status: {resp.status_code}\n"
                        f"Resposta: {resp.text}\n"
                    )
                try:
                    send_email_gmail_api(service, to=GMAIL_RECIPIENT, subject=assunto, body=corpo)
                    print(f"Notificação enviada para {GMAIL_RECIPIENT}")
                except Exception as e:
                    print(f"Erro ao enviar e-mail para {GMAIL_RECIPIENT}: {e}")
            except Exception as e:
                print(f"Erro de requisição para {email}: {e}")
                # Notifica erro de requisição também
                try:
                    service = get_gmail_service(GMAIL_SENDER)
                    assunto = f"[ERRO] Falha ao alterar senha de {nome}"
                    corpo = (
                        f"Ocorreu um erro de requisição ao tentar alterar a senha de {nome} ({email}) na data de hoje.\n"
                        f"Erro: {e}\n"
                    )
                    send_email_gmail_api(service, to=GMAIL_RECIPIENT, subject=assunto, body=corpo)
                    print(f"Notificação de erro enviada para {GMAIL_RECIPIENT}")
                except Exception as e2:
                    print(f"Erro ao enviar notificação de erro para {GMAIL_RECIPIENT}: {e2}")

if __name__ == "__main__":
    backend_healthcheck_url = f"{BACKEND_URL}/healthcheck"  # Ajuste conforme necessário
    if wait_for_service_ready(backend_healthcheck_url):
        main()
    else:
        print("O serviço não iniciou a tempo. Saindo...")
