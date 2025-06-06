import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# CONFIGURAÇÕES
SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON', 'service-account.json')
USER_EMAIL = 'administrador@tecafrio.com.br'   # o e-mail real que você delegou
TO_EMAIL = 'paulo.quintino@tecafrio.com.br'    # destinatário

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service(user_email):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES, subject=user_email
    )
    return build('gmail', 'v1', credentials=creds)

def send_test_email():
    service = get_gmail_service(USER_EMAIL)

    subject = '🔧 Teste de envio com conta de serviço'
    body = 'Este é um teste isolado via Gmail API usando conta de serviço delegada.'

    message = MIMEText(body)
    message['to'] = TO_EMAIL
    message['from'] = USER_EMAIL
    message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()

        print("✅ E-mail enviado com sucesso.")
        print("📨 Resultado:", result)

    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")

if __name__ == '__main__':
    send_test_email()
