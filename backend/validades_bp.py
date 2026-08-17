import os
import io
import logging
import pandas as pd
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from backend.services.sankhya_service import buscar_dados_estoque_vendas

logger = logging.getLogger(__name__)

validades_bp = Blueprint("validades", __name__, url_prefix="/api/validades")

@validades_bp.route("/produtos", methods=["GET"])
def listar_produtos_validades():
    try:
        dados = buscar_dados_estoque_vendas()
        return jsonify({"sucesso": True, "produtos": dados})
    except Exception as e:
        logger.error(f"Erro ao carregar produtos para validades: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500

@validades_bp.route("/exportar-excel", methods=["POST"])
def exportar_validades_excel():
    try:
        dados = request.json or []
        linhas = []
        for p in dados:
            cod = p.get("cod", "")
            ean = p.get("ean", "")
            complemento = p.get("complemento", "")
            desc = p.get("desc", "")
            separador = p.get("separador", "")
            estoque_atual = p.get("estoque", 0)

            for lote in p.get("lotes", []):
                qtd_coletada = lote.get("qtd")
                validade_raw = lote.get("validade", "")

                # Formata a data para DD/MM/AAAA
                validade_fmt = validade_raw
                if validade_raw:
                    try:
                        validade_fmt = datetime.strptime(validade_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except ValueError:
                        validade_fmt = validade_raw

                if qtd_coletada or validade_fmt:
                    try:
                        qtd_num = float(qtd_coletada) if qtd_coletada else 0
                        est_num = float(estoque_atual) if estoque_atual else 0
                        diferenca = qtd_num - est_num
                    except (ValueError, TypeError):
                        diferenca = "-"

                    linhas.append({
                        "Código": cod,
                        "EAN": ean,
                        "Complemento": complemento,
                        "Descrição do Produto": desc,
                        "Separador": separador,
                        "Estoque Atual (Sankhya)": estoque_atual,
                        "Quantidade Coletada": qtd_coletada,
                        "Diferença (Coletado - Estoque)": diferenca,
                        "Data de Validade": validade_fmt
                    })

        if not linhas:
            return jsonify({"error": "Nenhum lote preenchido."}), 400

        df = pd.DataFrame(linhas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Coleta_Validades", index=False)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="coleta_validades_analise.xlsx"
        )
    except Exception as e:
        logger.error(f"Erro ao exportar Excel de validades: {e}")
        return jsonify({"error": str(e)}), 500