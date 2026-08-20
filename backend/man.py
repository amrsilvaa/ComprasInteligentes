import os
from app import app

if __name__ == "__main__":
    print("===================================")
    print("COMPRAS INTELIGENTES")
    print("===================================")
    print(f"Backend: {os.path.abspath(os.path.dirname(__file__))}")
    print("Iniciando servidor web na porta 8000...")
    print("===================================")

    app.run(host="0.0.0.0", port=8000, debug=True)