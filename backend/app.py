import os
import json
import logging
import io
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, send_file
from dotenv import load_dotenv

from backend.services.sankhya_service import buscar_dados_estoque_vendas
from whatsapp_service import enviar_alerta_compras

# WebAuthn para Face ID / Biometria
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
)

# Carrega variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta-sankhya-compras-2026")

# Usuário e Senha Padrão de Acesso (configurável no .env)
ADMIN_USER = os.getenv("APP_USER", "admin")
ADMIN_PASS = os.getenv("APP_PASSWORD", "123456")

# Nome de exibição do App para a chave de segurança
RP_ID = os.getenv("RP_ID", "comprasinteligentes.onrender.com")
RP_NAME = "Compras Inteligentes"

# Banco em memória/arquivo simples para credenciais salvas do Face ID
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


# Middleware de Checagem de Autenticação
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
    username = data.get("username", "")
    password = data.get("password", "")

    if username == ADMIN_USER and password == ADMIN_PASS:
        session["logged_in"] = True
        session["user"] = username
        return jsonify({"success": True})
    
    return jsonify({"success": False, "message": "Usuário ou senha inválidos."}), 401


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# --- ROTAS WEBAUTHN (FACE ID / BIOMETRIA) ---

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
    return options.to_json()


@app.route("/api/webauthn/register-verify", methods=["POST"])
@login_required
def webauthn_register_verify():
    challenge_hex = session.get("webauthn_challenge")
    if not challenge_hex:
        return jsonify({"success": False, "message": "Desafio de segurança expirado"}), 400

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
        
        return jsonify({"success": True, "message": "Face ID / Biometria cadastrado com sucesso!"})
    except Exception as e:
        logger.error(f"Erro ao verificar registro WebAuthn: {e}")
        return jsonify({"success": False, "message": str(e)}), 400


@app.route("/api/webauthn/login-options", methods=["GET"])
def webauthn_login_options():
    options = generate_authentication_options(
        rp_id=request.host.split(":")[0],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session["webauthn_challenge"] = options.challenge.hex()
    return options.to_json()


@app.route("/api/webauthn/login-verify", methods=["POST"])
def webauthn_login_verify():
    challenge_hex = session.get("webauthn_challenge")
    if not challenge_hex:
        return jsonify({"success": False, "message": "Desafio expirado"}), 400

    body = request.json
    cred_id = body.get("id")

    target_user = None
    target_cred = None
    for uname, cred in db_credentials.items():
        if cred.get("credential_id") == cred_id or cred.get("credential_id") == bytes.fromhex(cred_id).hex():
            target_user = uname
            target_cred = cred
            break

    if not target_cred:
        return jsonify({"success": False, "message": "Dispositivo ou Face ID não reconhecido neste servidor."}), 400

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=bytes.fromhex(challenge_hex),
            expected_rp_id=request.host.split(":")[0],
            expected_origin=request.origin or f"https://{request.host}",
            credential_public_key=bytes.fromhex(target_cred["public_key"]),
            credential_current_sign_count=target_cred["sign_count"],
        )

        db_credentials[target_user]["sign_count"] = verification.new_sign_count
        save_credentials(db_credentials)

        session["logged_in"] = True
        session["user"] = target_user
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Erro ao autenticar Face ID: {e}")
        return jsonify({"success": False, "message": "Falha no reconhecimento do Face ID."}), 400


# --- ROTAS PRINCIPAIS PROTEGIDAS ---

@app.route("/")
@login_required
def index():
    return app.send_static_file("index.html")


@app.route("/api/estoque", methods=["GET"])
@login_required
def get_estoque():
    try:
        dados = buscar_dados_estoque_vendas()
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro na rota /api/estoque: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sankhya", methods=["GET"])
@login_required
def get_sankhya():
    try:
        dados = buscar_dados_estoque_vendas()
        return jsonify({"sucesso": True, "produtos": dados})
    except Exception as e:
        logger.error(f"Erro na rota /api/sankhya: {str(e)}")
        return jsonify({"sucesso": False, "error": str(e)}), 500


# --- ROTA DE ALERTA VIA WHATSAPP ---

@app.route("/api/whatsapp/disparar-alerta", methods=["POST"])
@login_required
def disparar_alerta_whatsapp():
    try:
        dados = buscar_dados_estoque_vendas()
        produtos = dados.get("produtos", []) if isinstance(dados, dict) else dados

        produtos_repor = [
            p for p in produtos
            if float(p.get("SUGESTAO_COMPRA", p.get("sugestao_compra", 0))) > 0
            or str(p.get("STATUS", p.get("status", ""))).upper() == "REPOR"
        ]

        resultado = enviar_alerta_compras(produtos_repor)
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro no disparo de WhatsApp: {str(e)}")
        return jsonify({"sucesso": False, "error": str(e)}), 500


# --- ROTA DE EXPORTAÇÃO PARA EXCEL ---

@app.route("/api/estoque/exportar-excel", methods=["GET"])
@login_required
def exportar_excel():
    try:
        # Se 'apenas_repor' for true na URL, filtra apenas itens que precisam de compra
        apenas_repor = request.args.get("apenas_repor", "false").lower() == "true"
        
        dados = buscar_dados_estoque_vendas()
        if not dados:
            return jsonify({"error": "Nenhum dado retornado do Sankhya"}), 404

        df = pd.DataFrame(dados)

        # Filtra os dados caso necessário
        if apenas_repor and "STATUS" in df.columns:
            df = df[df["STATUS"] == "REPOR"]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sugestao_Compras", index=False)
        output.seek(0)

        filename = "sugestao_compras_repor.xlsx" if apenas_repor else "sugestao_compras_completo.xlsx"

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Erro ao gerar relatório Excel: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)