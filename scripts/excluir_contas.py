import os
import json
import datetime
import base64
import tempfile
from googleapiclient.discovery import build
from google.oauth2 import service_account
from email.mime.text import MIMEText

AGENDAMENTOS_DIR = "agendamentos"
PROCESSED_DIR = "agendamentos_processados"
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/gmail.send"
]

# Variáveis de ambiente para e-mail
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "administrador@tecafrio.com.br")
GMAIL_RECIPIENT = os.environ.get("GMAIL_RECIPIENT", "paulo.quintino@tecafrio.com.br")

def get_service_account():
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_EXCLUSAO")
    if not creds_json:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS_JSON_EXCLUSAO não definido.")
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(creds_json)
        temp_path = f.name
    creds = service_account.Credentials.from_service_account_file(
        temp_path,
        scopes=SCOPES
    )
    return creds

def send_email_gmail_api(service, to, subject, body):
    message = MIMEText(body, 'plain')
    message['to'] = to
    message['subject'] = subject
    message['from'] = GMAIL_SENDER
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={'raw': raw}).execute()

def excluir_usuario(email, creds):
    service = build('admin', 'directory_v1', credentials=creds)
    try:
        service.users().delete(userKey=email).execute()
        print(f"[OK] Conta {email} excluída com sucesso.")
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao excluir {email}: {e}")
        return False

def processar_agendamentos():
    if not os.path.isdir(AGENDAMENTOS_DIR):
        print("Nenhum diretório de agendamentos encontrado.")
        return

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    hoje = datetime.datetime.now().astimezone().date().isoformat()  # yyyy-mm-dd
    arquivos = [f for f in os.listdir(AGENDAMENTOS_DIR) if f.endswith(".json")]

    creds = get_service_account()
    gmail_service = build('gmail', 'v1', credentials=creds.with_subject(GMAIL_SENDER))

    for filename in arquivos:
        filepath = os.path.join(AGENDAMENTOS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            dados = json.load(f)
        data_acao = dados.get("data_acao")
        email = dados.get("email")
        nome = dados.get("nome", email)
        processado = dados.get("processado", False)
        if not data_acao or not email:
            print(f"[IGNORADO] Arquivo {filename}: dados incompletos.")
            continue
        if processado:
            print(f"[IGNORADO] {email}: já processado anteriormente.")
            continue
        # Executa somente na data programada ou anterior
        if data_acao > hoje:
            print(f"[FUTURO] Agendamento para {email} é futuro ({data_acao}), ignorando hoje.")
            continue
        if data_acao < hoje:
            print(f"[ATRASADO] Agendamento para {email} era para {data_acao}, processando mesmo assim.")

        sucesso = excluir_usuario(email, creds)
        dados["processado"] = True
        # Atualiza arquivo antes de mover para processados
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        # Enviar e-mail de notificação
        if sucesso:
            assunto = f"Conta Google {nome} ({email}) excluída com sucesso"
            corpo = (
                f"Olá,\n\n"
                f"A conta Google do usuário {nome} ({email}) foi excluída conforme agendamento para a data {data_acao}.\n\n"
                f"Atenciosamente,\n"
                f"Painel RH/Automação"
            )
        else:
            assunto = f"[ERRO] Falha ao excluir conta Google de {nome}"
            corpo = (
                f"Olá,\n\n"
                f"Falha ao excluir a conta Google do usuário {nome} ({email}) agendada para {data_acao}.\n"
                f"Verifique o log da automação para detalhes.\n\n"
                f"Atenciosamente,\n"
                f"Painel RH/Automação"
            )
        try:
            send_email_gmail_api(gmail_service, GMAIL_RECIPIENT, assunto, corpo)
            print(f"[EMAIL] Notificação enviada para {GMAIL_RECIPIENT}")
        except Exception as e:
            print(f"[ERRO] Falha ao enviar e-mail de notificação: {e}")

        # Move arquivo para processados
        destino = os.path.join(PROCESSED_DIR, filename)
        os.rename(filepath, destino)
        if sucesso:
            print(f"[OK] Agendamento processado: {email} ({data_acao})")
        else:
            print(f"[FALHOU] Agendamento processado: {email} ({data_acao})")

if __name__ == "__main__":
    processar_agendamentos()
