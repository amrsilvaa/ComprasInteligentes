// ============================================================
// COMPRAS INTELIGENTES - SCRIPT UNIFICADO E CORRIGIDO
// ============================================================

// Utiliza o mesmo domínio/porta do backend (Render)
const API = "";

// VARIÁVEIS GLOBAIS
let produtosMaisVendidos = [];
let analiseEstoque = [];
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
// REQUISIÇÕES E CARREGAMENTO DE DADOS (ROTA ÚNICA /api/estoque)
// ============================================================

async function carregarDados() {
    const tabelaEstoque = document.getElementById("tabelaEstoque");
    if (tabelaEstoque) {
        tabelaEstoque.innerHTML = `<tr><td colspan="11">Carregando dados do Sankhya...</td></tr>`;
    }

    try {
        const resposta = await fetch(`${API}/api/estoque`);
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);

        const dados = await resposta.json();
        
        if (dados.error) {
            throw new Error(dados.error);
        }

        // Caso o backend retorne uma lista de produtos
        analiseEstoque = Array.isArray(dados) ? dados : (dados.produtos || []);

        // Atualiza os cartões informativos do painel
        const totalProdutos = document.getElementById("totalProdutos");
        if (totalProdutos) {
            totalProdutos.textContent = formatarInteiro(analiseEstoque.length);
        }

        // Processa produtos mais vendidos
        produtosMaisVendidos = [...analiseEstoque].sort((a, b) => numero(b.vendas_mes) - numero(a.vendas_mes));
        
        if (produtosMaisVendidos.length > 0) {
            const lider = produtosMaisVendidos[0];
            const produtoMaisVendido = document.getElementById("produtoMaisVendido");
            const volumeLider = document.getElementById("volumeLider");
            
            if (produtoMaisVendido) produtoMaisVendido.textContent = lider.produto ?? "-";
            if (volumeLider) volumeLider.textContent = formatarNumero(lider.vendas_mes);
        }

        let totalVolume = analiseEstoque.reduce((acc, item) => acc + numero(item.vendas_mes), 0);
        const volumeVendido = document.getElementById("volumeVendido");
        if (volumeVendido) volumeVendido.textContent = formatarNumero(totalVolume);

        // Renderiza as tabelas
        renderizarEstoque();
        renderizarMaisVendidos();
        carregarOQueComprar();
        sistemaOnline();

    } catch (erro) {
        console.error("ERRO /api/estoque:", erro);
        if (tabelaEstoque) {
            tabelaEstoque.innerHTML = `<tr><td colspan="11" style="color:red; text-align:center;">Falha na conexão com o servidor.</td></tr>`;
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

    tabela.innerHTML = produtosMaisVendidos.slice(0, 10).map((item, indice) => `
        <tr>
            <td>${indice + 1}</td>
            <td>${escaparHTML(item.produto ?? "-")}</td>
            <td>${formatarNumero(item.vendas_mes)}</td>
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

    // Atualiza contadores
    const totalUrgentes = document.getElementById("totalUrgentes");
    const totalComprar = document.getElementById("totalComprar");
    const quantidadeCompra = document.getElementById("quantidadeCompra");

    if (totalUrgentes) totalUrgentes.textContent = formatarInteiro(urgentes.length);
    if (totalComprar) totalComprar.textContent = formatarInteiro(normais.length);
    if (quantidadeCompra) quantidadeCompra.textContent = formatarNumero(quantidadeTotal);

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
// IMPRESSÃO E EXPORTAÇÃO
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
// INTEGRAÇÃO WHATSAPP E ALERTAS (NOVO)
// ============================================================

async function dispararAlertaWhatsApp() {
    if (!confirm("Deseja enviar o resumo dos itens para reposição no WhatsApp (33 99931-7139)?")) {
        return;
    }

    try {
        const res = await fetch(`${API}/api/whatsapp/disparar-alerta`, { method: "POST" });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        
        if (data.sucesso) {
            alert("✅ Alerta de compras enviado com sucesso para o WhatsApp!");
        } else {
            alert("⚠️ Aviso: " + (data.erro || data.mensagem || "Erro ao conectar com a API de envio."));
        }
    } catch (err) {
        console.error("Erro ao disparar WhatsApp:", err);
        alert("❌ Erro de comunicação com o servidor ao tentar enviar o WhatsApp. Verifique se o backend está rodando.");
    }
}

// ============================================================
// INICIALIZAÇÃO
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log("Compras Inteligentes iniciado.");
    carregarDados();
});
// ============================================================
// EXPORTAÇÃO DE VALIDADES COM AS DATAS PREENCHIDAS
// ============================================================

function exportarValidadesParaExcel() {
    // Busca a tabela da tela (ajuste o ID se a sua tabela tiver um ID específico)
    const tabela = document.querySelector("table"); 
    if (!tabela) {
        alert("Tabela não encontrada na tela.");
        return;
    }

    let csv = [];
    const linhas = tabela.querySelectorAll("tr");

    for (let i = 0; i < linhas.length; i++) {
        let linhaCSV = [];
        const celulas = linhas[i].querySelectorAll("th, td");

        // Ignora a última coluna (que são os botões de + e -) para deixar o Excel limpo
        const limiteColunas = i === 0 ? celulas.length : celulas.length - 1; 

        for (let j = 0; j < limiteColunas; j++) {
            let celula = celulas[j];
            
            // Verifica se a célula tem inputs (caixas de quantidade e data)
            const inputs = celula.querySelectorAll("input");
            
            if (inputs.length > 0) {
                let valoresColetados = [];
                // Os inputs vêm em pares: [Quantidade, Data]
                for (let k = 0; k < inputs.length; k += 2) {
                    const qtd = inputs[k] ? inputs[k].value : "";
                    const data = inputs[k+1] ? inputs[k+1].value : "";
                    
                    // Só adiciona se o usuário tiver preenchido pelo menos um dos dois
                    if (qtd || data) {
                        valoresColetados.push(`${qtd} UN -> ${data}`);
                    }
                }
                
                // Junta os lotes com um "|" para ficar na mesma célula do Excel
                if (valoresColetados.length > 0) {
                    linhaCSV.push(`"${valoresColetados.join(" | ")}"`);
                } else {
                    linhaCSV.push('""'); // Célula vazia se não preencheu nada
                }
            } else {
                // Se for uma célula normal (Nome do Produto, etc)
                let texto = celula.innerText.replace(/"/g, '""').trim();
                linhaCSV.push(`"${texto}"`);
            }
        }
        // Junta as colunas separando por ponto e vírgula
        csv.push(linhaCSV.join(";"));
    }

    // Cria o arquivo Excel/CSV e força o download
    let csvContent = "\uFEFF" + csv.join("\n"); // \uFEFF força o padrão do Excel
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    
    // Nome do arquivo
    link.setAttribute("href", url);
    link.setAttribute("download", "Coleta_de_Validades.csv");
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}