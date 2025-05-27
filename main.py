import os
import json
import tempfile
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account

# ====== INÍCIO: Configuração dinâmica da conta de serviço ======
# Salva o JSON da conta de serviço vindo da variável de ambiente em um arquivo temporário
if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in os.environ:
    creds_json = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write(creds_json)
        service_account_path = f.name
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
else:
    service_account_path = "service-account.json"  # fallback para desenvolvimento local

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
    client_secrets_path = "client_secret.json"  # fallback para desenvolvimento local

# ====== FIM: Configuração dinâmica do client_secret.json ======

CLIENT_SECRETS_FILE = client_secrets_path
SERVICE_ACCOUNT_FILE = service_account_path
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic"
]
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://msgferias.onrender.com/callback")

def is_domain_user(email):
    """Checa se é do domínio tecafrio.com.br (fallback simples)."""
    return email.endswith('@tecafrio.com.br')

def is_gsuite_admin(user_email, creds):
    """Checa se o usuário é administrador real do Google Workspace."""
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
            "https://www.googleapis.com/auth/admin.directory.user.readonly",
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
    # hd força login apenas para contas do domínio
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

        # Checagem aprimorada: admin real OU fallback de domínio
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
    # Prints para depuração
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
                "descricao": g.get("description", ""),   # <-- este campo é usado no painel.js para buscar o telefone
                "telefone": ""  # opcional, pode ser removido se não for usar diretamente
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
    creds = get_service_account_creds(email)
    gmail_service = build('gmail', 'v1', credentials=creds)
    if request.method == "GET":
        try:
            print("Consultando vacation para:", email)
            settings = gmail_service.users().settings().getVacation(userId=email).execute()
            return jsonify(settings)
        except Exception as e:
            print("Erro ao consultar vacation:", e)
            return jsonify({"error": str(e)}), 400
    else:
        data = request.get_json()
        vacation_settings = {
            "enableAutoReply": data.get("enableAutoReply", True),
            "responseSubject": data.get("responseSubject", ""),
            "responseBodyPlainText": data.get("responseBodyPlainText", ""),
            "restrictToDomain": data.get("restrictToDomain", False),
            "restrictToContacts": data.get("restrictToContacts", False),
            "startTime": int(data.get("startTime", 0)),
            "endTime": int(data.get("endTime", 0))
        }
        try:
            print("Alterando vacation para:", email, vacation_settings)
            gmail_service.users().settings().updateVacation(userId=email, body=vacation_settings).execute()
            return jsonify({"ok": True})
        except Exception as e:
            print("Erro ao alterar vacation:", e)
            return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
