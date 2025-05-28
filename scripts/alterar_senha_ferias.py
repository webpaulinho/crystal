import os
import json
import requests
from datetime import datetime
import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build

FERIAS_DIR = 'ferias'
BACKEND_URL = os.environ['BACKEND_URL']  # Exemplo: https://msgferias.onrender.com/api/vacation/
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')  # Só se precisar

# --- Configurar Gmail API ---
SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'service-account.json')
GMAIL_SENDER = os.environ.get('GMAIL_SENDER', 'noreply@tecafrio.com.br')  # Precisa ser autorizado na delegação
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service(user_email):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES, subject=user_email
    )
    return build('gmail', 'v1', credentials=creds)

def send_email_gmail_api(service, to, subject, body, cc=None):
    message = MIMEText(body, 'plain')
    message['to'] = to
    message['subject'] = subject
    message['from'] = GMAIL_SENDER
    if cc:
        message['cc'] = cc
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={'raw': raw}).execute()

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
        nome = dados.get('nome', email)
        processado = dados.get('processado', False)

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
                    # --- Envia notificação por e-mail ---
                    try:
                        service = get_gmail_service(GMAIL_SENDER)
                        assunto = "Sua conta entrou em férias"
                        corpo = (
                            f"Olá {nome},\n\n"
                            "Sua senha foi alterada para o período de férias.\n"
                            "Caso você não reconheça esta ação, entre em contato com o TI imediatamente.\n\n"
                            "Atenciosamente,\nEquipe T.I. Teca Frio"
                        )
                        send_email_gmail_api(service, to=email, subject=assunto, body=corpo)
                        print(f"Notificação enviada para {email}")
                        # Se quiser notificar o RH/admin, basta adicionar um send_email_gmail_api extra aqui
                    except Exception as e:
                        print(f"Erro ao enviar e-mail para {email}: {e}")
                else:
                    print(f"Erro ao alterar senha de {email}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"Erro de requisição para {email}: {e}")

if __name__ == "__main__":
    main()
