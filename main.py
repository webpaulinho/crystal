import os
import json
import tempfile
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from github_commit import commit_json_to_github  # Importa a função do github_commit.py

# ====== INÍCIO: Configuração dinâmica da conta de serviço ======
if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in os.environ:
    creds_json = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(creds_json)
        service_account_path = f.name
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
else:
    service_account_path = "service-account.json"
# ====== FIM: Configuração dinâmica da conta de serviço ======

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ====== INÍCIO: Configuração dinâmica do client_secret.json ======
if "GOOGLE_CLIENT_SECRET_JSON" in os.environ:
    client_secret_json = os.environ["GOOGLE_CLIENT_SECRET_JSON"]
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(client_secret_json)
        client_secrets_path = f.name
else:
    client_secrets_path = "client_secret.json"
# ====== FIM: Configuração dinâmica do client_secret.json ======

CLIENT_SECRETS_FILE = client_secrets_path
SERVICE_ACCOUNT_FILE = service_account_path
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/admin.directory.group.readonly"
]
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://msgferias.onrender.com/callback")

# Configuração do GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "webpaulinho/painel-ferias"  # Nome do repositório no formato owner/repo
GITHUB_BRANCH = "main"  # Branch onde os arquivos serão salvos

def is_domain_user(email):
    return email.endswith('@tecafrio.com.br')

def is_gsuite_admin(user_email, creds):
    try:
        service = build('admin', 'directory_v1', credentials=creds)
        user = service.users().get(userKey=user_email).execute()
        return user.get('isAdmin', False) or user.get('isDelegatedAdmin', False)
    except Exception as e:
        print("Erro ao verificar admin:", e)
        return False

def get_service_account_creds(subject_email):
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=[
            "https://www.googleapis.com/auth/admin.directory.user",
            "https://www.googleapis.com/auth/gmail.settings.basic",
            "https://www.googleapis.com/auth/admin.directory.group.readonly"
        ],
        subject=subject_email
    )

@app.route("/")
def index():
    if "credentials" not in session:
        return render_template("login.html")
    return redirect(url_for("painel"))

@app.route("/login")
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        hd='tecafrio.com.br'
    )
    session["state"] = state
    return redirect(auth_url)

@app.route("/callback")
def callback():
    try:
        state = session["state"]
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session["credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        creds = Credentials(**session["credentials"])
        oauth2_service = build('oauth2', 'v2', credentials=creds)
        userinfo = oauth2_service.userinfo().get().execute()
        user_email = userinfo["email"]

        admin_creds = get_service_account_creds(user_email)
        if not (is_domain_user(user_email) and is_gsuite_admin(user_email, admin_creds)):
            session.clear()
            return "Acesso restrito a administradores reais do domínio.", 403

        session["user_email"] = user_email
        return redirect(url_for("painel"))
    except Exception as e:
        print("Erro no callback:", e)
        session.clear()
        return f"Erro interno: {e}", 500

@app.route("/painel")
def painel():
    if "credentials" not in session:
        return redirect(url_for("index"))
    return render_template("painel.html", user_email=session.get("user_email"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/users")
def list_users():
    if "credentials" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    admin_email = session.get("user_email")
    creds = get_service_account_creds(admin_email)
    service = build('admin', 'directory_v1', credentials=creds)
    users = []
    page_token = None
    while True:
        results = service.users().list(
            domain='tecafrio.com.br',
            maxResults=200,
            orderBy='email',
            pageToken=page_token
        ).execute()
        batch = results.get('users', [])
        for u in batch:
            users.append({
                "email": u['primaryEmail'],
                "nome": u.get("name", {}).get("fullName", u['primaryEmail']),
                "telefone": u.get("phones", [{}])[0].get("value", "") if u.get("phones") else ""
            })
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    print("Usuários retornados:", users)
    print("Total de usuários:", len(users))
    return jsonify(users)

@app.route("/api/groups")
def list_groups():
    if "credentials" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    admin_email = session.get("user_email")
    creds = get_service_account_creds(admin_email)
    service = build('admin', 'directory_v1', credentials=creds)
    groups = []
    page_token = None
    while True:
        results = service.groups().list(
            customer='my_customer',
            maxResults=200,
            pageToken=page_token
        ).execute()
        batch = results.get('groups', [])
        for g in batch:
            groups.append({
                "email": g['email'],
                "nome": g.get("name", g['email']),
                "descricao": g.get("description", ""),
                "telefone": ""
            })
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    print("Grupos retornados:", groups)
    print("Total de grupos:", len(groups))
    return jsonify(groups)

@app.route("/api/vacation/<email>", methods=["GET", "POST"])
def vacation_settings(email):
    if "credentials" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # DEVE delegar como o usuário alvo
    creds = get_service_account_creds(email)
    gmail_service = build('gmail', 'v1', credentials=creds)
    if request.method == "GET":
        try:
            print("Consultando vacation para:", email)
            # ALTERE userId=email PARA userId="me"
            settings = gmail_service.users().settings().getVacation(userId="me").execute()
            return jsonify(settings)
        except Exception as e:
            print("Erro ao consultar vacation:", e)
            return jsonify({"error": str(e)}), 400
    else:
        data = request.get_json()
        vacation_settings = {
            "enableAutoReply": data.get("enableAutoReply", True),
            "responseSubject": data.get("responseSubject", ""),
            "responseBodyHtml": data.get("responseBodyHtml", ""),      # <-- HTML
            "responseBodyPlainText": "",                               # <-- Opcional: pode deixar vazio
            "restrictToDomain": data.get("restrictToDomain", False),
            "restrictToContacts": data.get("restrictToContacts", False),
            "startTime": int(data.get("startTime", 0)),
            "endTime": int(data.get("endTime", 0))
        }

        import datetime
        print("==== DEBUG - Dados recebidos para vacation ====")
        print("startTime (ms):", vacation_settings["startTime"], "->", datetime.datetime.utcfromtimestamp(vacation_settings["startTime"]/1000))
        print("endTime (ms):", vacation_settings["endTime"], "->", datetime.datetime.utcfromtimestamp(vacation_settings["endTime"]/1000))
        print("Dados completos:", vacation_settings)

        # --- INÍCIO: AGENDAMENTO DE EXCLUSÃO DE CONTA ---
        if data.get("agendarExclusao") and data.get("dataExclusao"):
            # Substituído pelo commit no GitHub
            path = f"agendamentos/exclusao_{email}_{data['dataExclusao']}.json"
            agendamento_exclusao = {
                "tipo": "exclusao",
                "email": email,
                "data_acao": data["dataExclusao"],  # yyyy-mm-dd
                "registrado_em": datetime.datetime.utcnow().isoformat() + "Z",
                "motivo": data.get("responseSubject", ""),
                "ultimo_dia": data.get("endTime"),  # timestamp ms
            }
            commit_message = f"Agendar exclusão de conta para {email} em {data['dataExclusao']}"
            try:
                success = commit_json_to_github(GITHUB_REPO, path, agendamento_exclusao, commit_message, GITHUB_TOKEN)
                if success:
                    print(f"Exclusão agendada para {email} em {data['dataExclusao']}")
                else:
                    print(f"Falha ao agendar exclusão para {email}")
            except Exception as e:
                print("Erro ao agendar exclusão:", e)
        # --- FIM: AGENDAMENTO DE EXCLUSÃO DE CONTA ---

        try:
            print("Alterando vacation para:", email, vacation_settings)
            gmail_service.users().settings().updateVacation(userId="me", body=vacation_settings).execute()
            return jsonify({"status": "Férias registradas", "message": "Alterações e registro de férias salvos com sucesso!"}), 200
        except Exception as e:
            print("Erro ao alterar vacation:", e)
            return jsonify({"status": "Erro", "error": "Falha ao salvar no GitHub"}), 500

# --- INÍCIO: REGISTRO AUTOMÁTICO DE FÉRIAS EM JSON ---
@app.route('/api/registrar-ferias', methods=['POST'])
def registrar_ferias():
    if "credentials" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    email = data.get("email")
    data_inicio = data.get("data_inicio")
    data_fim = data.get("data_fim")
    nome = data.get("nome", "")
    if not email or not data_inicio or not data_fim:
        return jsonify({"erro": "Dados obrigatórios faltando"}), 400

    # Substituído pelo commit no GitHub
    path = f"ferias/{email}_{data_inicio}.json"
    content_dict = {
        "email": email,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "nome": nome
    }
    commit_message = f"Registrar férias para {email} de {data_inicio} a {data_fim}"

    try:
        success = commit_json_to_github(GITHUB_REPO, path, content_dict, commit_message, GITHUB_TOKEN)
        if success:
            return jsonify({"status": "Férias registradas no GitHub"}), 200
        else:
            return jsonify({"error": "Falha ao salvar no GitHub"}), 500
    except Exception as e:
        print("Erro ao registrar férias:", e)
        return jsonify({"error": str(e)}), 500
# --- FIM: REGISTRO AUTOMÁTICO DE FÉRIAS EM JSON ---

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
