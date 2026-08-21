import os
import json
import logging
import base64
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, request, session, redirect, send_file, Response
from dotenv import load_dotenv

from validacoes_bp import validades_bp
from services.sankhya_service import buscar_dados_estoque_vendas

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
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instância do Flask
app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta-sankhya-compras-2026")

# Blueprint
app.register_blueprint(validades_bp)

ADMIN_USER = os.getenv("APP_USER", "admin")
ADMIN_PASS = os.getenv("APP_PASSWORD", "123456")
RP_ID = os.getenv("RP_ID", "comprasinteligentes.onrender.com")
RP_NAME = "Compras Inteligentes"
DEBUG_MODE = os.getenv("FLASK_DEBUG", "false").lower() == "true"

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


def b64url_to_hex(b64url_str: str) -> str:
    padding = "=" * (-len(b64url_str) % 4)
    raw_bytes = base64.urlsafe_b64decode(b64url_str + padding)
    return raw_bytes.hex()


# --- MIDDLEWARE ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Não autorizado"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# --- ROTAS DE AUTENTICAÇÃO ---
@app.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect("/")
    return app.send_static_file("login.html")


@app.route("/api/login/password", methods=["POST"])
def login_password():
    data = request.json or {}
    if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
        session["logged_in"] = True
        session["user"] = ADMIN_USER
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Usuário ou senha inválidos."}), 401


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect("/login")


# --- WEBAUTHN ---
@app.route("/api/webauthn/register-options", methods=["GET"])
@login_required
def webauthn_register_options():
    user_id = session.get("user", ADMIN_USER).encode("utf-8")
    options = generate_registration_options(
        rp_id=RP_ID,
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
            expected_rp_id=RP_ID,
            expected_origin=request.origin or f"https://{request.host}",
        )
        username = session.get("user", ADMIN_USER)
        db_credentials[username] = {
            "credential_id": verification.credential_id.hex(),
            "public_key": verification.credential_public_key.hex(),
            "sign_count": verification.sign_count,
        }
        save_credentials(db_credentials)
        return jsonify({"success": True, "message": "Face ID cadastrado com sucesso!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/webauthn/login-options", methods=["GET"])
def webauthn_login_options():
    options = generate_authentication_options(
        rp_id=RP_ID,
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
    cred_id_b64url = body.get("id")

    try:
        cred_id_hex = b64url_to_hex(cred_id_b64url)
    except Exception:
        return jsonify({"error": "ID de credencial inválido"}), 400

    target_cred = None
    for uname, cred in db_credentials.items():
        if cred.get("credential_id") == cred_id_hex:
            target_cred = cred
            break

    if not target_cred:
        return jsonify({"error": "Credencial não encontrada"}), 400

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=bytes.fromhex(challenge_hex),
            expected_rp_id=RP_ID,
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


@app.route("/api/produtos", methods=["GET"])
@login_required
def get_produtos():
    """Rota unificada para buscar produtos do Sankhya"""
    try:
        dados = buscar_dados_estoque_vendas()
        return jsonify({"sucesso": True, "produtos": dados})
    except Exception as e:
        logger.error(f"Erro na rota /api/produtos: {str(e)}")
        return jsonify({"sucesso": False, "error": str(e)}), 500


@app.route("/api/estoque", methods=["GET"])
@login_required
def get_estoque():
    """Alias para /api/produtos (mantido para compatibilidade)"""
    return get_produtos()


@app.route("/api/estoque/exportar-excel", methods=["GET"])
@login_required
def exportar_excel():
    try:
        apenas_repor = request.args.get("apenas_repor", "false").lower() == "true"
        dados = buscar_dados_estoque_vendas()
        if not dados:
            return jsonify({"error": "Sem dados"}), 404
        df = pd.DataFrame(dados)
        if apenas_repor and "status" in df.columns:
            df = df[df["status"] == "REPOR"]
        output = Path("/tmp") / f"sugestao_compras_{'repor' if apenas_repor else 'completo'}.xlsx"
        df.to_excel(output, index=False)
        return send_file(output, as_attachment=True, download_name=output.name)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=DEBUG_MODE)