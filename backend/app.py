import os
import json
import logging
import io
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, send_file, Response
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from backend.validades_bp import validades_bp

# Importação do WhatsApp (Caminho correto)
try:
    from backend.whatsapp_service import enviar_alerta_compras
except ImportError:
    try:
        from backend.services.whatsapp_service import enviar_alerta_compras
    except ImportError:
        enviar_alerta_compras = None

# Importação do Sankhya
from backend.services.sankhya_service import buscar_dados_estoque_vendas

# WebAuthn
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    UserVerificationRequirement,
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
)

# Carrega variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instância do Flask (APENAS UMA VEZ)
app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta-sankhya-compras-2026")

# Blueprint
app.register_blueprint(validades_bp)

ADMIN_USER = os.getenv("APP_USER", "admin")
ADMIN_PASS = os.getenv("APP_PASSWORD", "123456")
RP_ID = os.getenv("RP_ID", "comprasinteligentes.onrender.com")
RP_NAME = "Compras Inteligentes"

CREDENTIALS_FILE = Path(__file__).resolve().parent / "user_credentials.json"

def load_credentials():
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_credentials(data):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)

db_credentials = load_credentials()

# --- AGENDADOR AUTOMÁTICO ---
class SchedulerConfig:
    SCHEDULER_API_ENABLED = False

app.config.from_object(SchedulerConfig())
scheduler = APScheduler()

def job_verificacao_automatica_whatsapp():
    with app.app_context():
        try:
            logger.info("🤖 [AUTOMÁTICO] Verificando estoque no Sankhya...")
            if not enviar_alerta_compras:
                return
            dados = buscar_dados_estoque_vendas()
            enviar_alerta_compras(dados)
        except Exception as e:
            logger.error(f"🤖 Erro na verificação: {e}")

scheduler.init_app(app)
scheduler.add_job(
    id="alerta_whatsapp_automatico",
    func=job_verificacao_automatica_whatsapp,
    trigger="interval",
    hours=2,
    replace_existing=True
)

@app.before_request
def iniciar_scheduler():
    if not scheduler.running:
        scheduler.start()

# --- MIDDLEWARE E ROTAS ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Não autorizado"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return app.send_static_file("login.html")

@app.route("/api/login/password", methods=["POST"])
def login_password():
    data = request.json or {}
    if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
        session["logged_in"] = True
        session["user"] = ADMIN_USER
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# --- WEBAUTHN ---
@app.route("/api/webauthn/register-options", methods=["GET"])
@login_required
def webauthn_register_options():
    user_id = session.get("user", ADMIN_USER).encode("utf-8")
    options = generate_registration_options(
        rp_id=request.host.split(":")[0],
        rp_name=RP_NAME,
        user_id=user_id,
        user_name=session.get("user", ADMIN_USER),
        user_display_name="Usuário de Compras",
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment=AuthenticatorAttachment.PLATFORM
        ),
    )
    session["webauthn_challenge"] = options.challenge.hex()
    return Response(options_to_json(options), mimetype="application/json")

@app.route("/api/webauthn/register-verify", methods=["POST"])
@login_required
def webauthn_register_verify():
    challenge_hex = session.get("webauthn_challenge")
    if not challenge_hex:
        return jsonify({"error": "Desafio expirado"}), 400
    body = request.json
    try:
        verification = verify_registration_response(
            credential=body,
            expected_challenge=bytes.fromhex(challenge_hex),
            expected_rp_id=request.host.split(":")[0],
            expected_origin=request.origin or f"https://{request.host}",
        )
        username = session.get("user", ADMIN_USER)
        db_credentials[username] = {
            "credential_id": verification.credential_id.hex(),
            "public_key": verification.credential_public_key.hex(),
            "sign_count": verification.sign_count,
        }
        save_credentials(db_credentials)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/webauthn/login-options", methods=["GET"])
def webauthn_login_options():
    options = generate_authentication_options(
        rp_id=request.host.split(":")[0],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session["webauthn_challenge"] = options.challenge.hex()
    return Response(options_to_json(options), mimetype="application/json")

@app.route("/api/webauthn/login-verify", methods=["POST"])
def webauthn_login_verify():
    challenge_hex = session.get("webauthn_challenge")
    if not challenge_hex:
        return jsonify({"error": "Desafio expirado"}), 400
    body = request.json
    cred_id = body.get("id")
    target_cred = None
    for uname, cred in db_credentials.items():
        if cred.get("credential_id") == cred_id or cred.get("credential_id") == bytes.fromhex(cred_id).hex():
            target_cred = cred
            break
    if not target_cred:
        return jsonify({"error": "Credencial não encontrada"}), 400
    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=bytes.fromhex(challenge_hex),
            expected_rp_id=request.host.split(":")[0],
            expected_origin=request.origin or f"https://{request.host}",
            credential_public_key=bytes.fromhex(target_cred["public_key"]),
            credential_current_sign_count=target_cred["sign_count"],
        )
        session["logged_in"] = True
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- ROTAS PRINCIPAIS ---
@app.route("/")
@login_required
def index():
    return app.send_static_file("index.html")

@app.route("/validades")
@login_required
def validades_page():
    return app.send_static_file("validades.html")

@app.route("/api/validades", methods=["GET"])
@login_required
def get_validades():
    try:
        dados = buscar_dados_estoque_vendas()
        dados_padronizados = []
        for item in dados:
            novo_item = {
                "codigo": item.get("CODIGO") or item.get("codigo") or "-",
                "ean": item.get("EAN") or item.get("ean") or "-",
                "complemento": item.get("COMPLEMENTO") or item.get("complemento") or "-",
                "descricao": item.get("DESCRICAO") or item.get("descricao") or "-",
                "separador": item.get("SEPARADOR") or item.get("separador") or "-",
                "estoque": item.get("ESTOQUE") or item.get("estoque") or 0,
                "reservado": item.get("RESERVADO") or item.get("reservado") or 0
            }
            dados_padronizados.append(novo_item)
        return jsonify({"data": dados_padronizados})
    except Exception as e:
        logger.error(f"Erro na rota /api/validades: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/estoque", methods=["GET"])
@login_required
def get_estoque():
    try:
        return jsonify(buscar_dados_estoque_vendas())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/whatsapp/disparar-alerta", methods=["POST", "GET"])
@login_required
def disparar_alerta_whatsapp():
    try:
        if not enviar_alerta_compras:
            return jsonify({"erro": "WhatsApp não configurado"}), 500
        return jsonify(enviar_alerta_compras(buscar_dados_estoque_vendas()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/estoque/exportar-excel", methods=["GET"])
@login_required
def exportar_excel():
    try:
        apenas_repor = request.args.get("apenas_repor", "false").lower() == "true"
        dados = buscar_dados_estoque_vendas()
        if not dados:
            return jsonify({"error": "Sem dados"}), 404
        df = pd.DataFrame(dados)
        if apenas_repor and "STATUS" in df.columns:
            df = df[df["STATUS"] == "REPOR"]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sugestao_Compras", index=False)
        output.seek(0)
        filename = "sugestao_compras_repor.xlsx" if apenas_repor else "sugestao_compras_completo.xlsx"
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)