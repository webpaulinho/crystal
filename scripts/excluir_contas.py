import os
import json
import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account

AGENDAMENTOS_DIR = "agendamentos"
PROCESSED_DIR = "agendamentos_processados"
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user"
]

def get_service_account():
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not creds_json:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS_JSON não definido.")
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(creds_json)
        temp_path = f.name
    creds = service_account.Credentials.from_service_account_file(
        temp_path,
        scopes=SCOPES
    )
    return creds

def excluir_usuario(email, creds):
    service = build('admin', 'directory_v1', credentials=creds)
    try:
        service.users().delete(userKey=email).execute()
        print(f"Conta {email} excluída com sucesso.")
        return True
    except Exception as e:
        print(f"Falha ao excluir {email}: {e}")
        return False

def processar_agendamentos():
    if not os.path.isdir(AGENDAMENTOS_DIR):
        print("Nenhum diretório de agendamentos encontrado.")
        return

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    hoje = datetime.date.today().isoformat()  # yyyy-mm-dd
    arquivos = [f for f in os.listdir(AGENDAMENTOS_DIR) if f.startswith("exclusao_") and f.endswith(".json")]

    creds = get_service_account()

    for filename in arquivos:
        filepath = os.path.join(AGENDAMENTOS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            dados = json.load(f)
        data_acao = dados.get("data_acao")
        email = dados.get("email")
        if not data_acao or not email:
            print(f"Arquivo {filename} ignorado: dados incompletos.")
            continue
        # Executa somente na data programada
        if data_acao > hoje:
            print(f"Agendamento para {email} é futuro ({data_acao}), ignorando hoje.")
            continue
        if data_acao < hoje:
            print(f"Agendamento para {email} era para {data_acao}, processando mesmo assim.")

        sucesso = excluir_usuario(email, creds)
        # Move arquivo para processados
        destino = os.path.join(PROCESSED_DIR, filename)
        os.rename(filepath, destino)
        # Opcional: salvar status/resultado
        if sucesso:
            print(f"Agendamento processado: {email} ({data_acao}) OK.")
        else:
            print(f"Agendamento processado: {email} ({data_acao}) FALHOU.")

if __name__ == "__main__":
    processar_agendamentos()
