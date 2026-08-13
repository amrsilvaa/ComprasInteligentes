from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from backend.services.sankhya_service import buscar_dados_estoque_vendas

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Painel de Compras - Sankhya</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    th.sortable { cursor: pointer; user-select: none; }
    th.sortable:hover { background-color: #374151; }
  </style>
</head>
<body class="bg-gray-100 p-6">
  <div class="max-w-7xl mx-auto bg-white p-6 rounded-xl shadow-lg">
    
    <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">Sugestão de Compras (Giro 15 Dias)</h1>
        <p class="text-sm text-gray-500">Clique no título das colunas para ordenar</p>
      </div>
      <input 
        type="text" 
        id="searchInput" 
        placeholder="Buscar por código ou descrição..." 
        class="border border-gray-300 rounded-lg px-4 py-2 w-full md:w-80 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
    </div>

    <div class="overflow-x-auto rounded-lg border border-gray-200">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="bg-gray-800 text-white uppercase text-xs tracking-wider">
            <th class="p-3 sortable" onclick="ordenarPor('codigo')">Código ⇕</th>
            <th class="p-3 sortable" onclick="ordenarPor('descricao')">Descrição do Produto ⇕</th>
            <th class="p-3">Unid.</th>
            <th class="p-3 text-right sortable" onclick="ordenarPor('estoque')">Estoque ⇕</th>
            <th class="p-3 text-right sortable" onclick="ordenarPor('estoque_minimo')">Est. Mín. ⇕</th>
            <th class="p-3 text-right sortable" onclick="ordenarPor('venda_30d')">Vendas (15d) ⇕</th>
            <th class="p-3 text-right sortable" onclick="ordenarPor('sugestao_compra')">Sugestão Compra ⇕</th>
            <th class="p-3 text-center">Status</th>
          </tr>
        </thead>
        <tbody id="tableBody" class="divide-y divide-gray-200 text-sm">
          <tr>
            <td colspan="8" class="p-6 text-center text-gray-500">Carregando dados do Sankhya...</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>

  <script>
    let todosProdutos = [];
    let produtosFiltrados = [];
    let colunaAtual = 'sugestao_compra';
    let ordemAsc = false;

    async function carregarProdutos() {
      const tbody = document.getElementById('tableBody');
      try {
        const response = await fetch('/api/sankhya');
        const data = await response.json();

        if (data.sucesso && Array.isArray(data.produtos)) {
          todosProdutos = data.produtos;
          produtosFiltrados = [...todosProdutos];
          renderizarTabela(produtosFiltrados);
        } else {
          tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-red-500 font-semibold">Erro ao carregar dados.</td></tr>`;
        }
      } catch (error) {
        tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-red-500 font-semibold">Falha de comunicação com o servidor.</td></tr>`;
      }
    }

    function ordenarPor(coluna) {
      if (colunaAtual === coluna) {
        ordemAsc = !ordemAsc;
      } else {
        colunaAtual = coluna;
        ordemAsc = (coluna === 'descricao');
      }

      produtosFiltrados.sort((a, b) => {
        let valA = a[coluna] ?? 0;
        let valB = b[coluna] ?? 0;

        if (typeof valA === 'string') {
          return ordemAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return ordemAsc ? valA - valB : valB - valA;
      });

      renderizarTabela(produtosFiltrados);
    }

    function renderizarTabela(produtos) {
      const tbody = document.getElementById('tableBody');

      if (produtos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-gray-500">Nenhum produto encontrado.</td></tr>`;
        return;
      }

      tbody.innerHTML = produtos.map(p => {
        const precisaComprar = p.sugestao_compra > 0;
        const badgeStatus = precisaComprar
          ? `<span class="bg-red-100 text-red-800 font-bold px-3 py-1 rounded-full text-xs">REPOR</span>`
          : `<span class="bg-green-100 text-green-800 font-bold px-3 py-1 rounded-full text-xs">OK</span>`;

        // Pega vendas 15d vindo do backend (com fallback caso venha via chave antiga)
        const vendas15 = p.venda_15d ?? p.venda_30d ?? 0;

        return `
          <tr class="hover:bg-blue-50 transition-colors ${precisaComprar ? 'bg-red-50/40' : ''}">
            <td class="p-3 font-mono text-gray-600">${p.codigo}</td>
            <td class="p-3 font-medium text-gray-900">${p.descricao}</td>
            <td class="p-3 text-gray-500">${p.unidade}</td>
            <td class="p-3 text-right font-semibold text-gray-800">${(p.estoque || 0).toLocaleString('pt-BR')}</td>
            <td class="p-3 text-right text-gray-500">${(p.estoque_minimo || 0).toLocaleString('pt-BR')}</td>
            <td class="p-3 text-right font-semibold text-blue-600">${vendas15.toLocaleString('pt-BR')}</td>
            <td class="p-3 text-right font-bold ${precisaComprar ? 'text-red-600' : 'text-gray-700'}">
              ${(p.sugestao_compra || 0).toLocaleString('pt-BR')}
            </td>
            <td class="p-3 text-center">${badgeStatus}</td>
          </tr>
        `;
      }).join('');
    }

    document.getElementById('searchInput').addEventListener('input', (e) => {
      const termo = e.target.value.toLowerCase();
      produtosFiltrados = todosProdutos.filter(p => 
        (p.descricao && p.descricao.toLowerCase().includes(termo)) || 
        String(p.codigo).includes(termo)
      );
      renderizarTabela(produtosFiltrados);
    });

    carregarProdutos();
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def read_index():
    return HTML_CONTENT

@app.get("/api/sankhya")
def get_sankhya_data():
    produtos = buscar_dados_estoque_vendas()
    return {"sucesso": True, "produtos": produtos}