// ============================================================
// COMPRAS INTELIGENTES - SCRIPT COMPATÍVEL E UNIFICADO
// ============================================================

const API = "";

let produtosMaisVendidos = [];
let analiseEstoque = [];
let produtosParaComprar = [];

function numero(valor) {
    if (valor === null || valor === undefined || valor === "") return 0;
    if (typeof valor === "number") return Number.isFinite(valor) ? valor : 0;
    let texto = String(valor).trim().replace(/\s/g, "");
    if (texto.includes(".") && texto.includes(",")) {
        texto = texto.replace(/\./g, "").replace(",", ".");
    } else if (texto.includes(",")) {
        texto = texto.replace(",", ".");
    }
    const resultado = Number(texto);
    return Number.isFinite(resultado) ? resultado : 0;
}

function formatarNumero(valor) {
    return numero(valor).toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatarInteiro(valor) {
    return Math.round(numero(valor)).toLocaleString("pt-BR");
}

function escaparHTML(valor) {
    return String(valor ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function sistemaOnline() {
    const bolinha = document.getElementById("status");
    const texto = document.getElementById("statusTexto");
    if (bolinha) bolinha.style.background = "#16a34a";
    if (texto) texto.textContent = "Sistema online";
}

function sistemaOffline() {
    const bolinha = document.getElementById("status");
    const texto = document.getElementById("statusTexto");
    if (bolinha) bolinha.style.background = "#dc2626";
    if (texto) texto.textContent = "Erro de conexão";
}

function badgeStatus(status) {
    const texto = String(status);
    let classe = "status-normal";
    if (texto.toLowerCase().includes("urgente")) classe = "status-urgente";
    else if (texto.toLowerCase().includes("comprar") || texto.toLowerCase().includes("repor")) classe = "status-comprar";
    else if (texto.toLowerCase().includes("sem venda")) classe = "status-sem-venda";
    return `<span class="badge-status ${classe}">${escaparHTML(texto)}</span>`;
}

async function carregarDados() {
    const tabelaEstoque = document.getElementById("tabelaEstoque");
    if (tabelaEstoque) {
        tabelaEstoque.innerHTML = `<tr><td colspan="12">Carregando dados do Sankhya...</td></tr>`;
    }
    try {
        const resposta = await fetch(`${API}/api/produtos`);
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
        const dados = await resposta.json();
        
        // Garante suporte tanto se a API retornar um objeto { sucesso: true, produtos: [...] } quanto um array direto [...]
        analiseEstoque = dados.sucesso && Array.isArray(dados.produtos) ? dados.produtos : (Array.isArray(dados) ? dados : []);
        
        const totalProdutos = document.getElementById("totalProdutos");
        if (totalProdutos) totalProdutos.textContent = formatarInteiro(analiseEstoque.length);
        
        produtosMaisVendidos = [...analiseEstoque].sort((a, b) => numero(b.vendas_15d || b.vendas_mes) - numero(a.vendas_15d || a.vendas_mes));
        
        if (produtosMaisVendidos.length > 0) {
            const lider = produtosMaisVendidos[0];
            const produtoMaisVendido = document.getElementById("produtoMaisVendido");
            const volumeLider = document.getElementById("volumeLider");
            if (produtoMaisVendido) produtoMaisVendido.textContent = lider.descricao || lider.produto || "-";
            if (volumeLider) volumeLider.textContent = formatarNumero(lider.vendas_15d || lider.vendas_mes);
        }

        let totalVolume = analiseEstoque.reduce((acc, item) => acc + numero(item.vendas_15d || item.vendas_mes), 0);
        const volumeVendido = document.getElementById("volumeVendido");
        if (volumeVendido) volumeVendido.textContent = formatarNumero(totalVolume);
        
        renderizarEstoque();
        renderizarMaisVendidos();
        carregarOQueComprar();
        sistemaOnline();
    } catch (erro) {
        console.error("ERRO /api/produtos:", erro);
        if (tabelaEstoque) {
            tabelaEstoque.innerHTML = `<tr><td colspan="12" style="color:red; text-align:center;">Falha na conexão com o servidor.</td></tr>`;
        }
        sistemaOffline();
    }
}

function renderizarMaisVendidos() {
    const tabela = document.getElementById("tabelaProdutos");
    if (!tabela) return;
    if (!produtosMaisVendidos.length) {
        tabela.innerHTML = `<tr><td colspan="3">Nenhum produto encontrado.</td></tr>`;
        return;
    }
    tabela.innerHTML = produtosMaisVendidos.slice(0, 10).map((item, indice) => `
        <tr>
            <td>${indice + 1}</td>
            <td>${escaparHTML(item.descricao || item.produto || "-")}</td>
            <td>${formatarNumero(item.vendas_15d || item.vendas_mes)}</td>
        </tr>
    `).join("");
}

function renderizarEstoque(dados = analiseEstoque) {
    const tabela = document.getElementById("tabelaEstoque");
    if (!tabela) return;
    if (!dados.length) {
        tabela.innerHTML = `<tr><td colspan="12">Nenhum produto encontrado.</td></tr>`;
        return;
    }
    tabela.innerHTML = dados.map(item => `
        <tr>
            <td>${escaparHTML(item.codigo ?? "-")}</td>
            <td>${escaparHTML(item.descricao || item.produto || "-")}</td>
            <td>${escaparHTML(item.unidade ?? item.UNIDADE ?? "-")}</td>
            <td>${formatarNumero(item.estoque)}</td>
            <td>${formatarNumero(item.separado || item.reservado)}</td>
            <td>${formatarNumero(item.estoque_disponivel || (numero(item.estoque) - numero(item.reservado)))}</td>
            <td>${formatarNumero(item.vendas_15d || item.vendas_mes)}</td>
            <td>${formatarNumero(item.media_diaria)}</td>
            <td>${formatarNumero(item.dias_estoque)}</td>
            <td>${formatarNumero(item.sugestao_compra)}</td>
            <td>${escaparHTML(item.fornecedor ?? "-")}</td>
            <td>${badgeStatus(item.status ?? "OK")}</td>
        </tr>
    `).join("");
}

function carregarOQueComprar() {
    produtosParaComprar = analiseEstoque.filter(item => {
        const sugestao = numero(item.sugestao_compra);
        const status = String(item.status ?? "").toUpperCase();
        return sugestao > 0 || status === "REPOR" || status.includes("COMPRAR");
    });
    
    const quantidadeTotal = produtosParaComprar.reduce((acc, i) => acc + numero(i.sugestao_compra), 0);
    const totalComprar = document.getElementById("totalComprar");
    const quantidadeCompra = document.getElementById("quantidadeCompra");
    
    if (totalComprar) totalComprar.textContent = formatarInteiro(produtosParaComprar.length);
    if (quantidadeCompra) quantidadeCompra.textContent = formatarNumero(quantidadeTotal);
    
    renderizarOQueComprar();
}

function renderizarOQueComprar() {
    const tabela = document.getElementById("tabelaCompras") || document.getElementById("tabelaComprar");
    if (!tabela) return;
    if (!produtosParaComprar || produtosParaComprar.length === 0) {
        tabela.innerHTML = `
            <tr>
                <td colspan="10" style="text-align: center; padding: 20px;">
                    🟢 Nenhum produto precisa de reposição no momento.
                </td>
            </tr>
        `;
        return;
    }
    tabela.innerHTML = produtosParaComprar.map((item, indice) => {
        const produto = item.descricao || item.produto || "-";
        const estoque = numero(item.estoque);
        const disponivel = numero(item.estoque_disponivel || (numero(item.estoque) - numero(item.reservado)));
        const vendas = numero(item.vendas_15d || item.vendas_mes);
        const sugestao = numero(item.sugestao_compra);
        const status = item.status ?? "REPOR";
        return `
            <tr>
                <td>${indice + 1}</td>
                <td><strong>${escaparHTML(produto)}</strong></td>
                <td>${formatarNumero(estoque)}</td>
                <td>${formatarNumero(disponivel)}</td>
                <td>${formatarNumero(vendas)}</td>
                <td><strong>${formatarNumero(sugestao)}</strong></td>
                <td>${badgeStatus(status)}</td>
            </tr>
        `;
    }).join("");
}

document.addEventListener("DOMContentLoaded", () => {
    carregarDados();
});