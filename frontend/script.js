// ============================================================
// COMPRAS INTELIGENTES - SCRIPT UNIFICADO E CORRIGIDO
// ============================================================

// CONFIGURAÇÃO (deixe vazio se a API estiver no mesmo domínio/porta do frontend)
const API = "";

// VARIÁVEIS GLOBAIS
let produtosMaisVendidos = [];
let analiseEstoque = [];
let planilha = [];
let produtosParaComprar = [];

// ============================================================
// FORMATAÇÃO E TRATAMENTO DE DADOS
// ============================================================

function numero(valor) {
    if (valor === null || valor === undefined || valor === "") {
        return 0;
    }

    if (typeof valor === "number") {
        return Number.isFinite(valor) ? valor : 0;
    }

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

// ============================================================
// STATUS DO SISTEMA E BADGES
// ============================================================

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

    if (texto.toLowerCase().includes("urgente")) {
        classe = "status-urgente";
    } else if (texto.toLowerCase().includes("comprar")) {
        classe = "status-comprar";
    } else if (texto.toLowerCase().includes("sem venda")) {
        classe = "status-sem-venda";
    }

    return `<span class="badge-status ${classe}">${escaparHTML(texto)}</span>`;
}

// ============================================================
// REQUISIÇÕES E CARREGAMENTO DE DADOS
// ============================================================

async function carregarPlanilha() {
    try {
        const resposta = await fetch(`${API}/planilha`);
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);

        const dados = await resposta.json();
        if (Array.isArray(dados)) {
            planilha = dados;
            const totalProdutos = document.getElementById("totalProdutos");
            if (totalProdutos) {
                totalProdutos.textContent = formatarInteiro(dados.length);
            }
        }
        sistemaOnline();
    } catch (erro) {
        console.error("ERRO /planilha:", erro);
        sistemaOffline();
    }
}

async function carregarMaisVendidos() {
    try {
        const resposta = await fetch(`${API}/mais-vendidos`);
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);

        const dados = await resposta.json();
        if (!Array.isArray(dados)) {
            throw new Error("A API /mais-vendidos não retornou uma lista.");
        }

        produtosMaisVendidos = dados;
        produtosMaisVendidos.sort((a, b) => numero(b.volume) - numero(a.volume));

        const produtoMaisVendido = document.getElementById("produtoMaisVendido");
        const volumeLider = document.getElementById("volumeLider");

        if (produtosMaisVendidos.length > 0) {
            const lider = produtosMaisVendidos[0];
            if (produtoMaisVendido) produtoMaisVendido.textContent = lider.produto ?? "-";
            if (volumeLider) volumeLider.textContent = formatarNumero(lider.volume);
        }

        let totalVolume = produtosMaisVendidos.reduce((acc, item) => acc + numero(item.volume), 0);
        const volumeVendido = document.getElementById("volumeVendido");
        if (volumeVendido) volumeVendido.textContent = formatarNumero(totalVolume);

        renderizarMaisVendidos();
        sistemaOnline();
    } catch (erro) {
        console.error("ERRO /mais-vendidos:", erro);
        const tabela = document.getElementById("tabelaProdutos");
        if (tabela) {
            tabela.innerHTML = `<tr><td colspan="3">Erro ao carregar produtos.</td></tr>`;
        }
        sistemaOffline();
    }
}

async function carregarAnaliseEstoque() {
    try {
        const tabela = document.getElementById("tabelaEstoque");
        if (tabela) {
            tabela.innerHTML = `<tr><td colspan="11">Carregando análise...</td></tr>`;
        }

        const resposta = await fetch(`${API}/analise-estoque`);
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);

        const dados = await resposta.json();
        if (!Array.isArray(dados)) {
            throw new Error("A API /analise-estoque não retornou uma lista.");
        }

        analiseEstoque = dados;
        renderizarEstoque();
        carregarOQueComprar();
        sistemaOnline();
    } catch (erro) {
        console.error("ERRO /analise-estoque:", erro);
        const tabela = document.getElementById("tabelaEstoque");
        if (tabela) {
            tabela.innerHTML = `<tr><td colspan="11">Erro ao carregar análise de estoque.</td></tr>`;
        }
        sistemaOffline();
    }
}

// ============================================================
// RENDERIZAÇÃO DE TABELAS
// ============================================================

function renderizarMaisVendidos() {
    const tabela = document.getElementById("tabelaProdutos");
    if (!tabela) return;

    if (!produtosMaisVendidos.length) {
        tabela.innerHTML = `<tr><td colspan="3">Nenhum produto encontrado.</td></tr>`;
        return;
    }

    tabela.innerHTML = produtosMaisVendidos.map((item, indice) => `
        <tr>
            <td>${indice + 1}</td>
            <td>${escaparHTML(item.produto ?? "-")}</td>
            <td>${formatarNumero(item.volume)}</td>
        </tr>
    `).join("");
}

function renderizarEstoque(dados = analiseEstoque) {
    const tabela = document.getElementById("tabelaEstoque");
    if (!tabela) return;

    if (!dados.length) {
        tabela.innerHTML = `<tr><td colspan="11">Nenhum produto encontrado.</td></tr>`;
        return;
    }

    tabela.innerHTML = dados.map(item => `
        <tr>
            <td>${escaparHTML(item.produto ?? "-")}</td>
            <td>${escaparHTML(item.unidade ?? item.UNIDADE ?? "-")}</td>
            <td>${formatarNumero(item.estoque)}</td>
            <td>${formatarNumero(item.separado)}</td>
            <td>${formatarNumero(item.estoque_disponivel)}</td>
            <td>${formatarNumero(item.vendas_mes)}</td>
            <td>${formatarNumero(item.media_diaria)}</td>
            <td>${formatarNumero(item.dias_estoque)}</td>
            <td>${formatarNumero(item.estoque_meta)}</td>
            <td>${formatarNumero(item.sugestao_compra)}</td>
            <td>${badgeStatus(item.status ?? "Sem venda")}</td>
        </tr>
    `).join("");
}

function filtrarEstoque() {
    const busca = document.getElementById("buscaProduto");
    const filtro = document.getElementById("filtroStatus");

    const textoBusca = busca ? busca.value.toLowerCase().trim() : "";
    const statusFiltro = filtro ? filtro.value : "";

    const resultado = analiseEstoque.filter(item => {
        const produto = String(item.produto ?? "").toLowerCase();
        const status = String(item.status ?? "");

        const correspondeProduto = !textoBusca || produto.includes(textoBusca);
        const correspondeStatus = !statusFiltro || status === statusFiltro;

        return correspondeProduto && correspondeStatus;
    });

    renderizarEstoque(resultado);
}

// ============================================================
// MÓDULO O QUE COMPRAR
// ============================================================

function carregarOQueComprar() {
    produtosParaComprar = analiseEstoque.filter(item => {
        const status = String(item.status ?? "");
        return status === "Comprar urgente" || status === "Comprar";
    });

    produtosParaComprar.sort((a, b) => {
        const prioridadeA = a.status === "Comprar urgente" ? 0 : 1;
        const prioridadeB = b.status === "Comprar urgente" ? 0 : 1;

        if (prioridadeA !== prioridadeB) {
            return prioridadeA - prioridadeB;
        }

        return numero(b.sugestao_compra) - numero(a.sugestao_compra);
    });

    const urgentes = produtosParaComprar.filter(i => i.status === "Comprar urgente");
    const normais = produtosParaComprar.filter(i => i.status === "Comprar");
    const quantidadeTotal = produtosParaComprar.reduce((acc, i) => acc + numero(i.sugestao_compra), 0);

    // Atualiza contadores do painel/modal
    const totalUrgentes = document.getElementById("totalUrgentes");
    const totalComprar = document.getElementById("totalComprar");
    const quantidadeCompra = document.getElementById("quantidadeCompra");

    if (totalUrgentes) totalUrgentes.textContent = formatarInteiro(urgentes.length);
    if (totalComprar) totalComprar.textContent = formatarInteiro(normais.length);
    if (quantidadeCompra) quantidadeCompra.textContent = formatarNumero(quantidadeTotal);

    // Atualiza o texto do Card no Rodapé
    const cardOQueComprar = document.getElementById("cardOQueComprar") || document.getElementById("statusCardComprar");
    if (cardOQueComprar) {
        cardOQueComprar.textContent = `${produtosParaComprar.length} produtos para comprar`;
    }

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
        const produto = item.produto ?? "-";
        const estoque = numero(item.estoque);
        const disponivel = numero(item.estoque_disponivel);
        const vendasMes = numero(item.vendas_mes);
        const mediaDiaria = numero(item.media_diaria);
        const diasEstoque = numero(item.dias_estoque);
        const meta = numero(item.estoque_meta);
        const sugestao = numero(item.sugestao_compra);
        const status = item.status ?? "-";

        return `
            <tr>
                <td>${indice + 1}</td>
                <td><strong>${escaparHTML(produto)}</strong></td>
                <td>${formatarNumero(estoque)}</td>
                <td>${formatarNumero(disponivel)}</td>
                <td>${formatarNumero(vendasMes)}</td>
                <td>${formatarNumero(mediaDiaria)}</td>
                <td>${formatarNumero(diasEstoque)}</td>
                <td>${formatarNumero(meta)}</td>
                <td><strong>${formatarNumero(sugestao)}</strong></td>
                <td>${badgeStatus(status)}</td>
            </tr>
        `;
    }).join("");
}

function abrirOQueComprar() {
    const painel = document.getElementById("painelComprar");
    if (!painel) return;

    painel.style.display = "block";
    carregarOQueComprar();

    setTimeout(() => {
        painel.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
}

function fecharOQueComprar() {
    const painel = document.getElementById("painelComprar");
    if (painel) painel.style.display = "none";
}

// ============================================================
// IMPRESSÃO E EXPORTAÇÃO DE LISTA
// ============================================================

function gerarTextoListaCompras() {
    if (!produtosParaComprar.length) {
        return "Nenhum produto precisa de compra no momento.";
    }

    let texto = "LISTA DE COMPRAS\n==============================\n\n";
    texto += `Total de produtos: ${produtosParaComprar.length}\n\n`;

    const urgentes = produtosParaComprar.filter(item => item.status === "Comprar urgente");
    const normais = produtosParaComprar.filter(item => item.status === "Comprar");

    if (urgentes.length > 0) {
        texto += "🔴 COMPRA URGENTE\n------------------------------\n\n";
        urgentes.forEach((item, indice) => {
            texto += `${indice + 1}. ${item.produto || "-"}\n`;
            texto += `   Disponível: ${formatarNumero(item.estoque_disponivel)}\n`;
            texto += `   Vendas/mês: ${formatarNumero(item.vendas_mes)}\n`;
            texto += `   Dias de estoque: ${formatarNumero(item.dias_estoque)}\n`;
            texto += `   Comprar: ${formatarNumero(item.sugestao_compra)}\n\n`;
        });
    }

    if (normais.length > 0) {
        texto += "🟠 COMPRA\n------------------------------\n\n";
        normais.forEach((item, indice) => {
            texto += `${indice + 1}. ${item.produto || "-"}\n`;
            texto += `   Disponível: ${formatarNumero(item.estoque_disponivel)}\n`;
            texto += `   Vendas/mês: ${formatarNumero(item.vendas_mes)}\n`;
            texto += `   Dias de estoque: ${formatarNumero(item.dias_estoque)}\n`;
            texto += `   Comprar: ${formatarNumero(item.sugestao_compra)}\n\n`;
        });
    }

    texto += "==============================\nCompras Inteligentes\n";
    return texto;
}

async function copiarListaCompras() {
    const texto = gerarTextoListaCompras();
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(texto);
            alert("✅ Lista de compras copiada!");
        } else {
            // Fallback para contextos não-HTTPS ou navegadores antigos
            const textarea = document.createElement("textarea");
            textarea.value = texto;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);
            alert("✅ Lista de compras copiada!");
        }
    } catch (erro) {
        console.error("Erro ao copiar lista:", erro);
        alert("Não foi possível copiar a lista.");
    }
}

function imprimirListaCompras() {
    if (!produtosParaComprar.length) {
        alert("Não existem produtos para comprar.");
        return;
    }

    const texto = gerarTextoListaCompras();
    const janela = window.open("", "_blank");

    if (!janela) {
        alert("O navegador bloqueou a janela de impressão.");
        return;
    }

    const html = texto
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");

    janela.document.write(`
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Lista de Compras</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 30px; line-height: 1.6; font-size: 14px; }
                h1 { margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <h1>🛒 Lista de Compras</h1>
            <div>${html}</div>
        </body>
        </html>
    `);

    janela.document.close();
    janela.focus();

    setTimeout(() => {
        if (!janela.closed) janela.print();
    }, 500);
}

// ============================================================
// INICIALIZAÇÃO
// ============================================================

async function carregarDados() {
    console.log("Atualizando Compras Inteligentes...");
    await Promise.all([
        carregarPlanilha(),
        carregarMaisVendidos(),
        carregarAnaliseEstoque()
    ]);
    console.log("Dados atualizados.");
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("Compras Inteligentes iniciado.");
    carregarDados();
});