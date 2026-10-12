// Estado global
let processos = {};
let processosConteudo = {}; // Cache de conteudo para busca
let processosMeta = {}; // Cache de metadados (tema, urgencia, etc)
let temasDisponiveis = {}; // Temas disponiveis para filtro
let ordenacaoAtiva = 'antigo'; // Ordenacao ativa: 'antigo', 'tema', 'conclusao', 'prioridade'
let processoSelecionado = null;
let conteudoCache = {};
let ultimaAcao = null; // Armazena a ultima acao para UNDO
let favoritos = new Set(); // Processos marcados como favoritos
let minutaAtiva = 'minuta'; // Aba ativa: key da minuta (ex: 'minuta', 'embargos_minuta')
let filtroTipoAtivo = ''; // Filtro de tipo: 'sentenca', 'decisao', 'despacho' ou '' (todos)
let sortableInstances = {}; // Instancias de Sortable por coluna (evita memory leak)

// Labels das colunas (fixos no estilo decisao)
const LABELS_COLUNAS = {
    'por-analisar': 'Por Analisar',
    'analisando': 'Pesquisar',
    'pendencias': 'Complexo',
    'validado': 'Validado'
};

// Elementos DOM
const busca = document.getElementById('busca');
const btnDesfazer = document.getElementById('btn-desfazer');
const btnAtualizar = document.getElementById('btn-atualizar');
const btnTema = document.getElementById('btn-tema');
const contador = document.getElementById('contador');
const previewModal = document.getElementById('preview-modal');
const previewTitulo = document.getElementById('preview-titulo');
const previewAnalise = document.getElementById('preview-analise');
const previewMinuta = document.getElementById('preview-minuta');
const btnFecharPreview = document.getElementById('btn-fechar-preview');
const btnCopiarMinuta = document.getElementById('btn-copiar-minuta');
const btnCopiarAnalise = document.getElementById('btn-copiar-analise');
const btnAbrirPasta = document.getElementById('btn-abrir-pasta');
const btnCopiarNumero = document.getElementById('btn-copiar-numero');
const btnArquivarModal = document.getElementById('btn-arquivar-modal');
const btnMoverToggle = document.getElementById('btn-mover-toggle');
const moverMenu = document.getElementById('mover-menu');
const moverDropdown = document.querySelector('.mover-dropdown');

// Inicializacao
document.addEventListener('DOMContentLoaded', () => {
    carregarTema();
    carregarFavoritos();
    carregarOrdenacaoSalva();
    atualizarLabelsColunas();
    configurarFiltroTipo();
    carregarProcessos();
    configurarEventos();
});

// Configurar filtro de tipo
function configurarFiltroTipo() {
    const filtroTipo = document.getElementById('filtro-tipo');
    if (!filtroTipo) return;

    // Carregar filtro salvo
    const tipoSalvo = localStorage.getItem('jurista-filtro-tipo');
    if (tipoSalvo !== null) {
        filtroTipoAtivo = tipoSalvo;
        filtroTipo.value = tipoSalvo;
    }

    // Escutar mudancas
    filtroTipo.addEventListener('change', () => {
        filtroTipoAtivo = filtroTipo.value;
        localStorage.setItem('jurista-filtro-tipo', filtroTipoAtivo);
        renderizarKanban();
        atualizarContador();
    });
}

// Carregar ordenacao salva do localStorage
function carregarOrdenacaoSalva() {
    const ordenacaoSalva = localStorage.getItem('jurista-ordenacao');
    if (ordenacaoSalva && ['antigo', 'tema', 'conclusao', 'prioridade'].includes(ordenacaoSalva)) {
        ordenacaoAtiva = ordenacaoSalva;
        const selectOrdenacao = document.getElementById('filtro-ordenacao');
        if (selectOrdenacao) {
            selectOrdenacao.value = ordenacaoAtiva;
        }
    }
}

// Salvar ordenacao no localStorage
function salvarOrdenacao() {
    localStorage.setItem('jurista-ordenacao', ordenacaoAtiva);
}

// Atualizar labels das colunas do Kanban (fixos no estilo decisao)
function atualizarLabelsColunas() {
    document.querySelectorAll('.kanban-coluna').forEach(coluna => {
        const estado = coluna.dataset.estado;
        const h2 = coluna.querySelector('.coluna-titulo h2');
        if (h2 && LABELS_COLUNAS[estado]) {
            h2.textContent = LABELS_COLUNAS[estado];
        }
    });
}

// Gerenciamento de Tema
function carregarTema() {
    const temaSalvo = localStorage.getItem('jurista-tema') || 'escuro';
    document.body.className = temaSalvo === 'claro' ? 'tema-claro' : 'tema-escuro';
}

function alternarTema() {
    const isClaro = document.body.classList.contains('tema-claro');
    document.body.className = isClaro ? 'tema-escuro' : 'tema-claro';
    localStorage.setItem('jurista-tema', isClaro ? 'escuro' : 'claro');
}

// Gerenciamento de Favoritos
function carregarFavoritos() {
    const salvos = localStorage.getItem('jurista-favoritos');
    if (salvos) {
        favoritos = new Set(JSON.parse(salvos));
    }
}

function salvarFavoritos() {
    localStorage.setItem('jurista-favoritos', JSON.stringify([...favoritos]));
}

function toggleFavorito(numero) {
    if (favoritos.has(numero)) {
        favoritos.delete(numero);
    } else {
        favoritos.add(numero);
    }
    salvarFavoritos();
}

function isFavorito(numero) {
    return favoritos.has(numero);
}

// Carregar processos da API
async function carregarProcessos() {
    try {
        const response = await fetch('/api/processos');
        processos = await response.json();

        // Carregar conteudo para busca
        await carregarConteudoParaBusca();

        // Carregar metadados e temas
        await carregarMetadados();

        renderizarKanban();
        atualizarContador();
    } catch (error) {
        console.error('Erro ao carregar processos:', error);
    }
}

// Carregar metadados dos processos (tema, urgencia, dias_conclusos, prioridade_legal)
async function carregarMetadados() {
    processosMeta = {};
    temasDisponiveis = {};

    // Carregar metadados individuais de cada processo
    const promises = [];
    for (const estado of Object.keys(processos)) {
        for (const proc of processos[estado]) {
            promises.push(
                fetch(`/api/meta/${proc.tipo}/${estado}/${proc.numero}`)
                    .then(r => r.ok ? r.json() : null)
                    .then(meta => {
                        if (meta) {
                            // Extrair campos relevantes (suporta ambos formatos de metadados)
                            const tema = meta.tema || meta.classificacao?.tema_id || '';
                            const temaNome = meta.tema_nome || meta.classificacao?.tema_nome || tema || '';
                            const urgencia = meta.analise?.urgencia || 'normal';
                            const diasConclusos = meta.datas?.dias_concluso || 0;
                            const prioridadeLegal = meta.prioridade_legal || {};

                            processosMeta[proc.numero] = {
                                tema: tema,
                                tema_nome: temaNome,
                                urgencia: urgencia,
                                dias_conclusos: diasConclusos,
                                prioridade_legal: prioridadeLegal,
                                origem: meta.origem || '',
                                revisao: meta.revisao || null
                            };

                            // Adicionar tema ao dropdown
                            if (tema && !temasDisponiveis[tema]) {
                                temasDisponiveis[tema] = temaNome;
                            }
                        }
                    })
                    .catch(() => null)
            );
        }
    }

    await Promise.all(promises);

    // Atualizar dropdown de temas
    atualizarDropdownTemas();
}

// Atualizar dropdown de temas no painel de filtros
async function atualizarDropdownTemas() {
    const select = document.getElementById('filtro-tema');
    if (!select) return;

    // Preservar selecao atual
    const valorAtual = select.value;

    // Limpar e reconstruir opcoes
    select.innerHTML = '<option value="">Todos os Temas</option>';

    // Se temos temas carregados dos metadados
    if (Object.keys(temasDisponiveis).length > 0) {
        Object.entries(temasDisponiveis)
            .sort((a, b) => String(a[1] || '').localeCompare(String(b[1] || '')))
            .forEach(([id, nome]) => {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = encurtarNomeTema(nome);
                select.appendChild(option);
            });
    }

    // Restaurar selecao se ainda existir
    if (valorAtual) {
        select.value = valorAtual;
    }
}

// Encurtar nome do tema para exibicao
function encurtarNomeTema(nome) {
    if (nome.length <= 25) return nome;

    // Extrair parte principal (antes do " - ")
    const partes = nome.split(' - ');
    let nomeExibicao = partes[0];

    // Se tiver Tema XXX, adicionar
    const matchTema = nome.match(/Tema \d+/);
    if (matchTema) {
        nomeExibicao = `${partes[0]} (${matchTema[0]})`;
    }

    return nomeExibicao;
}

// Carregar conteudo dos documentos para permitir busca
async function carregarConteudoParaBusca() {
    processosConteudo = {};

    for (const estado of Object.keys(processos)) {
        for (const proc of processos[estado]) {
            try {
                const response = await fetch(`/api/processo/${proc.tipo}/${estado}/${proc.numero}`);
                const conteudo = await response.json();
                processosConteudo[proc.numero] = {
                    analise: (conteudo.analise || '').toLowerCase(),
                    minuta: (conteudo.minuta || '').toLowerCase()
                };
            } catch (e) {
                processosConteudo[proc.numero] = { analise: '', minuta: '' };
            }
        }
    }
}

// Obter valores dos filtros do DOM (uma unica vez)
function obterFiltrosAtivos() {
    return {
        tema: document.getElementById('filtro-tema')?.value || '',
        urgencia: document.getElementById('filtro-urgencia')?.value || '',
        prioridade: document.getElementById('filtro-prioridade')?.value || '',
        dias: document.getElementById('filtro-dias')?.value || ''
    };
}

// Verificar se processo corresponde aos filtros ativos
function processoCorrespondeAoFiltro(proc, filtroTexto, filtros) {
    // Filtro por tipo (sentenca, decisao, despacho)
    if (filtroTipoAtivo && proc.tipo !== filtroTipoAtivo) {
        return false;
    }

    const meta = processosMeta[proc.numero] || {};

    // Filtro por tema
    if (filtros.tema && (!meta.tema || meta.tema !== filtros.tema)) {
        return false;
    }

    // Filtro por urgencia
    if (filtros.urgencia && (!meta.urgencia || meta.urgencia !== filtros.urgencia)) {
        return false;
    }

    // Filtro por prioridade legal
    if (filtros.prioridade) {
        const prioridadeLegal = meta.prioridade_legal || {};
        if (!prioridadeLegal[filtros.prioridade]) {
            return false;
        }
    }

    // Filtro por dias concluso
    if (filtros.dias) {
        const diasMinimo = parseInt(filtros.dias) || 0;
        const diasConclusos = meta.dias_conclusos || 0;
        if (diasConclusos < diasMinimo) {
            return false;
        }
    }

    // Filtro por texto (busca)
    if (!filtroTexto) return true;

    // Busca no numero do processo
    if (proc.numero.toLowerCase().includes(filtroTexto)) return true;

    // Busca no conteudo
    const conteudo = processosConteudo[proc.numero];
    if (conteudo) {
        if (conteudo.analise.includes(filtroTexto)) return true;
        if (conteudo.minuta.includes(filtroTexto)) return true;
    }

    return false;
}

// Extrair ano do numero do processo (formato CNJ: 0000000-00.AAAA.0.00.0000)
function extrairAnoProcesso(numero) {
    const match = numero.match(/\d{7}-\d{2}\.(\d{4})\.\d\.\d{2}\.\d{4}/);
    return match ? parseInt(match[1]) : 9999;
}

// Ordenar lista de processos conforme criterio ativo
function ordenarProcessos(lista) {
    if (!lista || lista.length === 0) return lista;

    const listaOrdenada = [...lista];

    switch (ordenacaoAtiva) {
        case 'antigo':
            // Ordenar por ano do processo (mais antigo primeiro)
            listaOrdenada.sort((a, b) => {
                const anoA = extrairAnoProcesso(a.numero);
                const anoB = extrairAnoProcesso(b.numero);
                if (anoA !== anoB) return anoA - anoB;
                // Se mesmo ano, ordenar pelo numero completo
                return a.numero.localeCompare(b.numero);
            });
            break;

        case 'tema':
            // Agrupar por tema (ordenar alfabeticamente por nome do tema)
            listaOrdenada.sort((a, b) => {
                const metaA = processosMeta[a.numero] || {};
                const metaB = processosMeta[b.numero] || {};
                const temaA = (metaA.tema_nome || metaA.tema || 'zzz').toLowerCase();
                const temaB = (metaB.tema_nome || metaB.tema || 'zzz').toLowerCase();
                if (temaA !== temaB) return temaA.localeCompare(temaB);
                // Dentro do mesmo tema, ordenar por numero
                return a.numero.localeCompare(b.numero);
            });
            break;

        case 'conclusao':
            // Ordenar por dias concluso (mais tempo primeiro)
            listaOrdenada.sort((a, b) => {
                const metaA = processosMeta[a.numero] || {};
                const metaB = processosMeta[b.numero] || {};
                const diasA = metaA.dias_conclusos || 0;
                const diasB = metaB.dias_conclusos || 0;
                return diasB - diasA; // Decrescente
            });
            break;

        case 'prioridade':
            // Processos com prioridade legal primeiro
            listaOrdenada.sort((a, b) => {
                const metaA = processosMeta[a.numero] || {};
                const metaB = processosMeta[b.numero] || {};
                const prioridadeA = metaA.prioridade_legal ? 1 : 0;
                const prioridadeB = metaB.prioridade_legal ? 1 : 0;
                if (prioridadeA !== prioridadeB) return prioridadeB - prioridadeA;
                // Se mesma prioridade, ordenar por dias concluso
                const diasA = metaA.dias_conclusos || 0;
                const diasB = metaB.dias_conclusos || 0;
                return diasB - diasA;
            });
            break;

        default:
            // Padrao: ordenar por numero
            listaOrdenada.sort((a, b) => a.numero.localeCompare(b.numero));
    }

    return listaOrdenada;
}

// Renderizar Kanban
function renderizarKanban() {
    const filtroTexto = busca.value.toLowerCase().trim();
    const filtros = obterFiltrosAtivos(); // Obter filtros uma unica vez

    Object.keys(processos).forEach(estado => {
        const coluna = document.querySelector(`[data-estado="${estado}"] .kanban-cards`);
        const countSpan = document.querySelector(`[data-estado="${estado}"] .count`);

        if (!coluna) return;

        // Filtrar processos
        const processosFiltrados = processos[estado].filter(p =>
            processoCorrespondeAoFiltro(p, filtroTexto, filtros)
        );

        // Ordenar processos
        const processosOrdenados = ordenarProcessos(processosFiltrados);

        // Atualizar contador da coluna
        countSpan.textContent = processosOrdenados.length;

        // Limpar e renderizar cards
        coluna.innerHTML = '';
        processosOrdenados.forEach(proc => {
            const card = criarCard(proc);
            coluna.appendChild(card);
        });

        // Destruir instancia anterior de Sortable (evita memory leak)
        if (sortableInstances[estado]) {
            sortableInstances[estado].destroy();
        }

        // Inicializar drag-and-drop e armazenar instancia
        sortableInstances[estado] = new Sortable(coluna, {
            group: 'kanban',
            animation: 150,
            ghostClass: 'dragging',
            onEnd: handleDragEnd
        });
    });
}

// Criar card com metadados enriquecidos
function criarCard(processo) {
    const card = document.createElement('div');
    card.className = 'kanban-card';
    card.dataset.numero = processo.numero;
    card.dataset.estado = processo.estado;
    card.dataset.caminho = processo.caminho;
    card.dataset.tipo = processo.tipo;

    // Obter metadados do processo
    const meta = processosMeta[processo.numero] || {};
    const tema = meta.tema_nome || meta.tema || '';
    const urgencia = meta.urgencia || 'normal';
    const diasConclusos = meta.dias_conclusos || 0;

    // Extrair primeira prioridade ativa do objeto prioridade_legal
    const prioridadeLegal = meta.prioridade_legal || {};
    const prioridade = Object.keys(prioridadeLegal).find(k => prioridadeLegal[k]) || '';

    // Adicionar classe de urgencia para border-left
    if (urgencia === 'critica') card.classList.add('urgencia-critica');
    else if (urgencia === 'alta') card.classList.add('urgencia-alta');
    else card.classList.add('urgencia-normal');

    // Nao mostrar botao de validar se ja esta validado
    const btnValidarHtml = processo.estado !== 'validado'
        ? `<button class="btn-card-validar" title="Mover para Validado">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
        </button>`
        : '';

    // Botao de arquivar (lixeira) - aparece em todos os cards
    const btnArquivarHtml = `<button class="btn-card-arquivar" title="Arquivar processo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>
    </button>`;

    // Botao de favorito (estrela) - a esquerda do numero
    const favoritoAtivo = isFavorito(processo.numero) ? 'ativo' : '';
    const estrela = isFavorito(processo.numero) ? '★' : '☆';

    // Extrair origem do processo (despacho, sentenca, etc)
    const origem = meta.origem || '';

    // Badge de revisao
    const revisao = meta.revisao || null;
    let badgeRevisaoHtml = '';
    if (revisao && revisao.revisada) {
        if (revisao.has_alerta_critico) {
            card.classList.add('has-alerta-critico');
            badgeRevisaoHtml = `<span class="card-badge-revisao alerta-critico" title="ALERTA CRITICO - Revisao humana obrigatoria">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
            </span>`;
        } else {
            badgeRevisaoHtml = `<span class="card-badge-revisao ok" title="Minuta revisada">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
            </span>`;
        }
    }

    // Selos de rota v3.1 (triagem) e de fontes verbatim
    let rotaHtml = '';
    if (Array.isArray(processo.rota)) {
        if (processo.rota.length === 0) {
            rotaHtml += `<span class="card-tag rota-direta" title="Triagem: rota direta (rotina certificada)">🟢 rota direta</span>`;
        } else {
            if (processo.rota.includes('pesquisa')) {
                rotaHtml += `<span class="card-tag rota-pesquisa" title="Triagem: trilho de pesquisa de precedentes">🔎 pesquisa</span>`;
            }
            if (processo.rota.includes('probatica')) {
                rotaHtml += `<span class="card-tag rota-probatica" title="Triagem: trilho de análise probática">⚖️ probática</span>`;
            }
        }
    }
    if (processo.tem_fontes) {
        rotaHtml += `<span class="card-tag rota-fontes" title="Fontes verbatim registradas (fontes.json)">📚 fontes</span>`;
    }

    // Construir tags de metadados
    let metaHtml = '';
    if (origem || tema || diasConclusos > 0 || prioridade || rotaHtml) {
        metaHtml = '<div class="card-meta">';
        // Tag de origem (Despacho)
        if (origem === 'despacho') {
            metaHtml += `<span class="card-tag origem-despacho" title="Processo do Pipeline Despacho">Despacho</span>`;
        }
        if (tema) {
            // Extrair nome curto do tema (primeira parte antes do " - ")
            const temaStr = String(tema || '');
            const temaCurto = temaStr.split(' - ')[0].substring(0, 18);
            metaHtml += `<span class="card-tag tema" title="${temaStr}">${temaCurto}</span>`;
        }
        if (diasConclusos > 0) {
            const diasClass = diasConclusos > 100 ? 'alerta' : '';
            metaHtml += `<span class="card-tag dias ${diasClass}">${diasConclusos}d</span>`;
        }
        if (prioridade) {
            const prioridadeMap = { idoso: 'Idoso', deficiente: 'PcD', doenca_grave: 'DG', reu_preso: 'Preso' };
            metaHtml += `<span class="card-tag prioridade">${prioridadeMap[prioridade] || prioridade}</span>`;
        }
        metaHtml += rotaHtml;
        metaHtml += '</div>';
    }

    card.innerHTML = `
        <div class="card-header">
            <button class="btn-favorito ${favoritoAtivo}" title="Marcar como favorito">${estrela}</button>
            <span class="numero">${processo.numero}</span>
            ${badgeRevisaoHtml}
        </div>
        ${metaHtml}
        <div class="card-actions">
            ${btnValidarHtml}
            ${btnArquivarHtml}
        </div>
    `;

    // Evento de clique no card
    card.addEventListener('click', (e) => {
        if (!e.target.classList.contains('btn-card-validar') &&
            !e.target.classList.contains('btn-card-arquivar') &&
            !e.target.classList.contains('btn-favorito')) {
            selecionarProcesso(processo);
        }
    });

    // Evento do botao favorito
    const btnFavorito = card.querySelector('.btn-favorito');
    if (btnFavorito) {
        btnFavorito.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFavorito(processo.numero);
            // Atualizar visual
            btnFavorito.classList.toggle('ativo');
            btnFavorito.textContent = btnFavorito.classList.contains('ativo') ? '★' : '☆';
        });
    }

    // Evento do botao validar no card
    const btnCardValidar = card.querySelector('.btn-card-validar');
    if (btnCardValidar) {
        btnCardValidar.addEventListener('click', (e) => {
            e.stopPropagation();
            validarProcesso(processo.numero, processo.estado, processo.tipo);
        });
    }

    // Evento do botao arquivar no card
    const btnCardArquivar = card.querySelector('.btn-card-arquivar');
    if (btnCardArquivar) {
        btnCardArquivar.addEventListener('click', (e) => {
            e.stopPropagation();
            arquivarProcesso(processo.numero, processo.estado, processo.tipo);
        });
    }

    return card;
}

// Validar processo (mover para validado)
async function validarProcesso(numero, estadoOrigem, tipo, sobrescrever = false) {
    if (estadoOrigem === 'validado') return;

    try {
        const response = await fetch('/api/mover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: numero,
                estado_origem: estadoOrigem,
                estado_destino: 'validado',
                tipo: tipo,
                sobrescrever: sobrescrever
            })
        });

        if (!response.ok) {
            const err = await response.json();

            // Conflito: processo ja existe no destino
            if (response.status === 409) {
                const confirmar = confirm(
                    `Ja existe o processo ${numero} na coluna Validado.\n\n` +
                    `Deseja sobrescrever? Os arquivos novos substituirao os antigos, ` +
                    `mas arquivos unicos da versao anterior serao mantidos.`
                );
                if (confirmar) {
                    return validarProcesso(numero, estadoOrigem, tipo, true);
                }
                return;
            }

            throw new Error(err.detail || 'Erro ao validar processo');
        }

        // Salvar acao para UNDO
        ultimaAcao = {
            numero: numero,
            origem: 'validado',    // Invertido: para desfazer, origem vira destino
            destino: estadoOrigem, // Invertido: destino vira origem
            tipo: tipo
        };
        atualizarBotaoDesfazer();

        // Fechar modal se o processo validado estava aberto
        if (processoSelecionado && processoSelecionado.numero === numero) {
            fecharModal();
        }

        // Recarregar
        await carregarProcessos();

    } catch (error) {
        console.error('Erro ao validar:', error);
        alert('Erro ao validar processo: ' + error.message);
    }
}

// Arquivar processo (mover para arquivados)
async function arquivarProcesso(numero, estadoOrigem, tipo, sobrescrever = false) {
    try {
        const response = await fetch('/api/arquivar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: numero,
                estado_origem: estadoOrigem,
                tipo: tipo,
                sobrescrever: sobrescrever
            })
        });

        if (!response.ok) {
            const err = await response.json();

            // Conflito: processo ja existe no destino
            if (response.status === 409) {
                const confirmar = confirm(
                    `Ja existe uma versao arquivada do processo ${numero}.\n\n` +
                    `Deseja sobrescrever? Os arquivos novos substituirao os antigos, ` +
                    `mas arquivos unicos da versao anterior serao mantidos.`
                );
                if (confirmar) {
                    // Tentar novamente com sobrescrita
                    return arquivarProcesso(numero, estadoOrigem, tipo, true);
                }
                return; // Usuario cancelou
            }

            throw new Error(err.detail || 'Erro ao arquivar processo');
        }

        const resultado = await response.json();

        // Salvar acao para UNDO
        ultimaAcao = {
            numero: numero,
            origem: 'arquivado',   // Para desfazer, mover de arquivado
            destino: estadoOrigem, // Para o estado original
            tipo: tipo
        };
        atualizarBotaoDesfazer();

        // Fechar modal se o processo arquivado estava aberto
        if (processoSelecionado && processoSelecionado.numero === numero) {
            fecharModal();
        }

        // Recarregar
        await carregarProcessos();

        // Mostrar feedback se houve mesclagem
        if (resultado.mesclado) {
            console.log('Processo mesclado:', resultado);
        }

    } catch (error) {
        console.error('Erro ao arquivar:', error);
        alert('Erro ao arquivar processo: ' + error.message);
    }
}

// Arquivar todos os processos validados
async function arquivarTodos() {
    try {
        // Se ha filtro ativo, arquivar apenas desse tipo; senao, arquivar todos
        const tipoParam = filtroTipoAtivo || null;
        const response = await fetch('/api/arquivar-todos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo: tipoParam })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Erro ao arquivar todos');
        }

        const resultado = await response.json();

        if (resultado.erros && resultado.erros.length > 0) {
            alert('Alguns processos nao puderam ser arquivados.');
        }

        // Limpar UNDO (arquivar todos nao tem undo individual)
        ultimaAcao = null;
        atualizarBotaoDesfazer();

        // Recarregar
        await carregarProcessos();

    } catch (error) {
        console.error('Erro ao arquivar todos:', error);
        alert('Erro ao arquivar processos: ' + error.message);
    }
}

// Handle drag end
async function handleDragEnd(evt, sobrescrever = false) {
    const card = evt.item;
    const numero = card.dataset.numero;
    const estadoOrigem = card.dataset.estado;
    const tipo = card.dataset.tipo;
    const estadoDestino = evt.to.closest('.kanban-coluna').dataset.estado;

    if (estadoOrigem === estadoDestino) return;

    try {
        const response = await fetch('/api/mover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: numero,
                estado_origem: estadoOrigem,
                estado_destino: estadoDestino,
                tipo: tipo,
                sobrescrever: sobrescrever
            })
        });

        if (!response.ok) {
            const err = await response.json();

            // Conflito: processo ja existe no destino
            if (response.status === 409) {
                const confirmar = confirm(
                    `Ja existe o processo ${numero} na coluna de destino.\n\n` +
                    `Deseja sobrescrever? Os arquivos novos substituirao os antigos, ` +
                    `mas arquivos unicos da versao anterior serao mantidos.`
                );
                if (confirmar) {
                    // Tentar novamente com sobrescrita
                    return handleDragEnd(evt, true);
                }
                // Usuario cancelou - reverter visual
                await carregarProcessos();
                return;
            }

            throw new Error(err.detail || 'Erro ao mover processo');
        }

        // Salvar acao para UNDO
        ultimaAcao = {
            numero: numero,
            origem: estadoDestino,  // Invertido: para desfazer, origem vira destino
            destino: estadoOrigem,  // Invertido: destino vira origem
            tipo: tipo
        };
        atualizarBotaoDesfazer();

        // Atualizar estado local
        card.dataset.estado = estadoDestino;

        // Atualizar dados
        await carregarProcessos();

        // Se o processo movido estava selecionado, atualizar
        if (processoSelecionado && processoSelecionado.numero === numero) {
            processoSelecionado.estado = estadoDestino;
        }

    } catch (error) {
        console.error('Erro ao mover:', error);
        alert('Erro ao mover processo: ' + error.message);
        carregarProcessos();
    }
}

// Selecionar processo para preview
// Estado das abas de artefatos
let artefatoAtivo = 'analise';

// Icones SVG para tipos de artefatos
const ARTEFATO_ICONS = {
    mapeamento: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    relatorio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    analise: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
    analise_complexa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/><line x1="12" y1="22" x2="12" y2="15.5"/><polyline points="22 8.5 12 15.5 2 8.5"/></svg>',
    probatica: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>',
    precedentes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>',
    pesquisa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>',
    organizacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    minuta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    embargos_analise: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/></svg>',
    embargos_minuta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M12 18v-6"/><path d="M9 15l3 3 3-3"/></svg>',
    revisao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>',
    'linha-tempo': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    fundamentacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
};

// Icone de checkmark para status revisada
const CHECKMARK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>';

// Icones para checklist de revisao v2.0
const CHECKLIST_ICONS = {
    OK: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>',
    CORRIGIDO: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    ALERTA: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    ALERTA_CRITICO: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>',
    NAO_APLICAVEL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>',
    ERRO: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
};

// Mapa de nomes para exibicao no checklist
const CHECKLIST_LABELS = {
    fase: 'Fase',
    qualidade: 'Qualidade',
    fontes: 'Fontes',
    embargabilidade: 'Embarg.',
    honorarios: 'Honor.',
    calculos: 'Calculos',
    temas: 'Temas'
};

// Detecta status de revisao no conteudo da minuta (v2.0 com checklist)
function detectarStatusRevisao(conteudo) {
    if (!conteudo) return { revisada: false, data: null, checklist: null };

    // Detectar selo de revisao <!-- status: revisada -->
    const seloMatch = conteudo.match(/<!--\s*status:\s*revisada\s*-->/i);
    if (seloMatch) {
        // Tentar extrair data do bloco de revisao
        const dataMatch = conteudo.match(/Data:\s*(\d{2}\/\d{2}\/\d{4}\s*\d{2}:\d{2})/);

        // Extrair checklist v2.0: <!-- checklist: fase=OK qualidade=OK ... -->
        const checklist = parseChecklist(conteudo);

        return {
            revisada: true,
            data: dataMatch ? dataMatch[1] : null,
            tipo: 'revisada',
            checklist: checklist
        };
    }

    // Detectar [REVISADA] no comentario (formato legado)
    if (conteudo.includes('[REVISADA]') || conteudo.includes('ROBUSTECIDA')) {
        const dataMatch = conteudo.match(/Data:\s*(\d{2}\/\d{2}\/\d{4})/);
        return {
            revisada: true,
            data: dataMatch ? dataMatch[1] : null,
            tipo: 'robustecida',
            checklist: null
        };
    }

    return { revisada: false, data: null, checklist: null };
}

// Parse do checklist HTML v2.0
function parseChecklist(conteudo) {
    if (!conteudo) return null;

    // Formato multilinhas: <!-- checklist:\n  fase=OK\n  qualidade=OK\n  ... -->
    const multilineMatch = conteudo.match(/<!--\s*checklist:\s*([\s\S]*?)-->/i);
    if (multilineMatch) {
        const checklistText = multilineMatch[1];
        const checklist = {};

        // Parse cada linha: dimensao=STATUS
        const linhas = checklistText.split('\n');
        for (const linha of linhas) {
            const match = linha.trim().match(/^(\w+)=(\w+)$/);
            if (match) {
                checklist[match[1].toLowerCase()] = match[2].toUpperCase();
            }
        }

        // Verificar se tem pelo menos uma dimensao
        if (Object.keys(checklist).length > 0) {
            return checklist;
        }
    }

    // Formato inline legado: <!-- checklist: qualidade=OK fontes=OK ... -->
    const inlineMatch = conteudo.match(/<!--\s*checklist:\s*([^>]+)-->/i);
    if (inlineMatch) {
        const checklistText = inlineMatch[1];
        const checklist = {};

        // Parse inline: dimensao=STATUS
        const matches = checklistText.matchAll(/(\w+)=(\w+)/g);
        for (const match of matches) {
            checklist[match[1].toLowerCase()] = match[2].toUpperCase();
        }

        if (Object.keys(checklist).length > 0) {
            return checklist;
        }
    }

    return null;
}

// Verifica se ha alerta critico no checklist
function temAlertaCritico(checklist) {
    if (!checklist) return false;
    return Object.values(checklist).some(status => status === 'ALERTA_CRITICO');
}

// Gera HTML visual do checklist para exibicao em cards
function gerarChecklistCompacto(checklist) {
    if (!checklist) return '';

    const dimensoes = ['fase', 'qualidade', 'fontes', 'embargabilidade', 'honorarios', 'calculos', 'temas'];
    let html = '<div class="checklist-compacto">';

    for (const dim of dimensoes) {
        const status = checklist[dim] || 'NAO_APLICAVEL';
        const icon = CHECKLIST_ICONS[status] || CHECKLIST_ICONS.NAO_APLICAVEL;
        const label = CHECKLIST_LABELS[dim] || dim;
        const statusClass = status.toLowerCase().replace('_', '-');

        html += `<span class="checklist-item ${statusClass}" title="${label}: ${status}">${icon}</span>`;
    }

    html += '</div>';
    return html;
}

// Gera HTML detalhado do checklist para modal
function gerarChecklistDetalhado(checklist) {
    if (!checklist) return '';

    const dimensoes = ['fase', 'qualidade', 'fontes', 'embargabilidade', 'honorarios', 'calculos', 'temas'];
    let html = '<div class="checklist-detalhado">';
    html += '<div class="checklist-titulo">Checklist de Revisao</div>';

    for (const dim of dimensoes) {
        const status = checklist[dim] || 'NAO_APLICAVEL';
        const icon = CHECKLIST_ICONS[status] || CHECKLIST_ICONS.NAO_APLICAVEL;
        const label = CHECKLIST_LABELS[dim] || dim;
        const statusClass = status.toLowerCase().replace('_', '-');

        html += `<div class="checklist-linha ${statusClass}">`;
        html += `<span class="checklist-icone">${icon}</span>`;
        html += `<span class="checklist-label">${label}</span>`;
        html += `<span class="checklist-status">${status}</span>`;
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Extrai comentarios de revisao detalhados do conteudo da minuta
function extrairComentariosRevisao(conteudo) {
    if (!conteudo) return null;

    // Busca o bloco de comentarios no final do arquivo
    // Formato: <!-- REVISAO AUTOMATICA: ... -->
    const comentarioMatch = conteudo.match(/<!--\s*(REVISAO AUTOMATICA:[\s\S]*?)-->\s*$/i);
    if (comentarioMatch) {
        return comentarioMatch[1].trim();
    }

    return null;
}

// Gera conteudo completo da aba de revisao
function gerarConteudoRevisao(checklist, comentarios, hasAlertaCritico) {
    let html = '<div class="revisao-container">';

    // Header com status geral
    if (hasAlertaCritico) {
        html += `
            <div class="revisao-header alerta-critico">
                <span class="revisao-header-icon">${CHECKLIST_ICONS.ALERTA_CRITICO}</span>
                <div class="revisao-header-content">
                    <h3>ALERTA CRITICO</h3>
                    <p>Esta minuta requer revisao humana obrigatoria antes da publicacao.</p>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="revisao-header ok">
                <span class="revisao-header-icon">${CHECKLIST_ICONS.OK}</span>
                <div class="revisao-header-content">
                    <h3>Revisao Concluida</h3>
                    <p>Minuta revisada automaticamente. Verifique os alertas abaixo.</p>
                </div>
            </div>
        `;
    }

    // Checklist detalhado
    html += gerarChecklistDetalhado(checklist);

    // Comentarios detalhados (se existirem)
    if (comentarios) {
        html += '<div class="revisao-comentarios">';
        html += '<div class="revisao-comentarios-titulo">Detalhes da Revisao</div>';
        html += '<pre class="revisao-comentarios-texto">' + escapeHtml(comentarios) + '</pre>';
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Escape HTML para exibicao segura
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Gera badge HTML baseado no status (v2.0 com suporte a checklist)
function gerarBadgeStatus(status, tipo = 'artefato') {
    if (!status || !status.revisada) return '';

    const classe = tipo === 'minuta' ? 'minuta-badge' : 'artefato-badge';

    // Se tem checklist v2.0, mostrar indicador visual
    if (status.checklist) {
        const hasAlertaCritico = temAlertaCritico(status.checklist);
        const alertaClasse = hasAlertaCritico ? ' alerta-critico' : '';
        const titulo = hasAlertaCritico
            ? 'ALERTA CRITICO - Revisao humana obrigatoria'
            : `Revisada${status.data ? ' em ' + status.data : ''}`;

        return `<span class="${classe} revisada${alertaClasse}" title="${titulo}">${CHECKMARK_ICON}</span>`;
    }

    // Formato legado
    return `<span class="${classe} revisada" title="Revisada${status.data ? ' em ' + status.data : ''}">${CHECKMARK_ICON}</span>`;
}

async function selecionarProcesso(processo) {
    processoSelecionado = processo;

    // Destacar card selecionado
    document.querySelectorAll('.kanban-card').forEach(c => c.classList.remove('selected'));
    document.querySelector(`[data-numero="${processo.numero}"]`)?.classList.add('selected');

    // Mostrar modal
    previewModal.classList.remove('hidden');
    previewTitulo.textContent = processo.numero;

    // Resetar botao copiar (nova estrutura com SVG + span)
    const copiarSpan = btnCopiarMinuta.querySelector('span');
    if (copiarSpan) copiarSpan.textContent = 'Copiar';
    btnCopiarMinuta.classList.remove('copiado');

    // Popular meta bar com metadados do processo
    popularMetaBar(processo);

    // Carregar conteudo
    try {
        const response = await fetch(`/api/processo/${processo.tipo}/${processo.estado}/${processo.numero}`);
        conteudoCache = await response.json();

        // Renderizar abas de artefatos dinamicamente
        renderizarAbasArtefatos();

        // Renderizar abas de minutas dinamicamente
        renderizarAbasMinutas();

    } catch (error) {
        console.error('Erro ao carregar preview:', error);
        const previewAnalise = document.getElementById('preview-analise');
        if (previewAnalise) previewAnalise.innerHTML = '<p>Erro ao carregar conteudo.</p>';
        previewMinuta.innerHTML = '<p>Erro ao carregar conteudo.</p>';
    }
}

// Renderiza o dropdown de artefatos dinamicamente
function renderizarAbasArtefatos() {
    const dropdown = document.getElementById('artefatos-dropdown');
    const toggleBtn = document.getElementById('artefatos-toggle');
    const iconSpan = document.getElementById('artefatos-icon');
    const labelSpan = document.getElementById('artefatos-label');
    const menu = document.getElementById('artefatos-menu');
    const contentContainer = document.getElementById('artefatos-container');

    if (!dropdown || !contentContainer) return;

    // Verificar se ha artefatos disponiveis (novo formato)
    let artefatosDisponiveis = conteudoCache.artefatos_disponiveis || [];

    // Se nao ha artefatos no novo formato, usar fallback para formato legado
    if (artefatosDisponiveis.length === 0) {
        // Construir lista de artefatos a partir dos campos legados
        if (conteudoCache.analise) {
            artefatosDisponiveis.push({
                key: 'analise',
                nome: 'Analise',
                ordem: 1
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.analise = conteudoCache.analise;
        }
        if (conteudoCache.analise_complexa) {
            artefatosDisponiveis.push({
                key: 'analise_complexa',
                nome: 'Marmelstein',
                ordem: 2
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.analise_complexa = conteudoCache.analise_complexa;
        }
        if (conteudoCache.precedentes) {
            artefatosDisponiveis.push({
                key: 'precedentes',
                nome: 'Precedentes',
                ordem: 3
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.precedentes = conteudoCache.precedentes;
        }
        if (conteudoCache.probatica) {
            artefatosDisponiveis.push({
                key: 'probatica',
                nome: 'Probatica',
                ordem: 4
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.probatica = conteudoCache.probatica;
        }
        if (conteudoCache.relatorio) {
            artefatosDisponiveis.push({
                key: 'relatorio',
                nome: 'Relatorio',
                ordem: 0
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.relatorio = conteudoCache.relatorio;
        }

        // Verificar se a minuta tem checklist de revisao
        if (conteudoCache.minuta) {
            const statusRevisao = detectarStatusRevisao(conteudoCache.minuta);
            if (statusRevisao.revisada && statusRevisao.checklist) {
                const comentarios = extrairComentariosRevisao(conteudoCache.minuta);
                const hasAlertaCritico = temAlertaCritico(statusRevisao.checklist);
                const conteudoRevisao = gerarConteudoRevisao(statusRevisao.checklist, comentarios, hasAlertaCritico);

                artefatosDisponiveis.push({
                    key: 'revisao',
                    nome: hasAlertaCritico ? 'Revisao (!!)' : 'Revisao',
                    ordem: 99, // Sempre por ultimo
                    isRevisao: true,
                    hasAlertaCritico: hasAlertaCritico
                });
                if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
                conteudoCache.artefatos.revisao = conteudoRevisao;
            }
        }

        // Ordenar por ordem
        artefatosDisponiveis.sort((a, b) => a.ordem - b.ordem);
        // Atualizar o cache com a lista construida
        conteudoCache.artefatos_disponiveis = artefatosDisponiveis;
    }

    // SEMPRE verificar se a minuta tem checklist de revisao (mesmo se artefatos ja existem)
    const jaTemRevisao = artefatosDisponiveis.some(a => a.key === 'revisao');

    if (!jaTemRevisao && conteudoCache.minuta) {
        const statusRevisao = detectarStatusRevisao(conteudoCache.minuta);

        if (statusRevisao.revisada && statusRevisao.checklist) {
            const comentarios = extrairComentariosRevisao(conteudoCache.minuta);
            const hasAlertaCritico = temAlertaCritico(statusRevisao.checklist);
            const conteudoRevisao = gerarConteudoRevisao(statusRevisao.checklist, comentarios, hasAlertaCritico);

            artefatosDisponiveis.push({
                key: 'revisao',
                nome: hasAlertaCritico ? 'Revisao (!!)' : 'Revisao',
                ordem: 99,
                isRevisao: true,
                hasAlertaCritico: hasAlertaCritico
            });
            if (!conteudoCache.artefatos) conteudoCache.artefatos = {};
            conteudoCache.artefatos.revisao = conteudoRevisao;

            // Reordenar apos adicionar revisao
            artefatosDisponiveis.sort((a, b) => a.ordem - b.ordem);
        }
    }

    // Se nenhum artefato, esconder dropdown e mostrar mensagem
    if (artefatosDisponiveis.length === 0) {
        dropdown.classList.add('hidden');
        contentContainer.innerHTML = '<div class="preview-content preview-analise"><p>Nenhum artefato encontrado para este processo.</p></div>';
        return;
    }

    // Se apenas 1 artefato, esconder dropdown (nao faz sentido)
    if (artefatosDisponiveis.length === 1) {
        dropdown.classList.add('hidden');
    } else {
        dropdown.classList.remove('hidden');
    }

    // Atualizar botao toggle com primeiro artefato
    const primeiro = artefatosDisponiveis[0];
    const primeiroIcone = primeiro.icone || ARTEFATO_ICONS[primeiro.key] || ARTEFATO_ICONS.analise;
    iconSpan.innerHTML = primeiroIcone;
    labelSpan.textContent = primeiro.nome;
    toggleBtn.dataset.activeKey = primeiro.key;

    // Renderizar menu dropdown
    let menuHtml = '';
    artefatosDisponiveis.forEach((artefato, index) => {
        const isActive = index === 0 ? 'active' : '';
        const icone = artefato.icone || ARTEFATO_ICONS[artefato.key] || ARTEFATO_ICONS.analise;
        menuHtml += `
            <button class="artefato-item ${isActive}" data-key="${artefato.key}">
                <span class="artefato-item-icon">${icone}</span>
                <span class="artefato-item-label">${artefato.nome}</span>
            </button>
        `;
    });

    // Relatorio de precedentes: pagina propria (1180px), abre em aba nova.
    const relPrec = conteudoCache.relatorio_precedentes;
    if (relPrec && relPrec.url) {
        menuHtml += `
            <a class="artefato-item" data-externo="1" href="${relPrec.url}" target="_blank" rel="noopener">
                <span class="artefato-item-icon">${ARTEFATO_ICONS.relatorio || ''}</span>
                <span class="artefato-item-label">Precedentes (abre em aba) &nearr;</span>
            </a>
        `;
    }
    menu.innerHTML = menuHtml;

    // Renderizar container de conteudo (apenas o primeiro ativo)
    let contentHtml = '';
    artefatosDisponiveis.forEach((artefato, index) => {
        const isHidden = index === 0 ? '' : 'hidden';
        const conteudo = conteudoCache.artefatos?.[artefato.key] || `*Conteudo de ${artefato.nome} nao encontrado*`;
        // Revisao ja vem como HTML, nao precisa de marked.parse
        const conteudoRenderizado = artefato.isRevisao ? conteudo : marked.parse(conteudo);
        const classeExtra = artefato.hasAlertaCritico ? ' has-alerta-critico' : '';
        contentHtml += `
            <div id="artefato-${artefato.key}" class="artefato-content preview-content ${isHidden}${classeExtra}">
                ${conteudoRenderizado}
            </div>
        `;
    });
    contentContainer.innerHTML = contentHtml;

    // Event listener para toggle do dropdown (substitui anterior)
    toggleBtn.onclick = function(e) {
        e.stopPropagation();
        dropdown.classList.toggle('open');
        menu.classList.toggle('hidden');
    };

    // Event listener para itens do menu (substitui anterior)
    menu.onclick = function(e) {
        const item = e.target.closest('.artefato-item');
        if (item) {
            // Link externo (relatorio de precedentes em HTML): deixa o anchor
            // abrir a aba propria, nao troca de painel.
            if (item.dataset.externo) return;
            const key = item.dataset.key;
            alternarAbaArtefato(key);
            // Fechar menu
            dropdown.classList.remove('open');
            menu.classList.add('hidden');
        }
    };

    // Fechar dropdown ao clicar fora
    document.addEventListener('click', function closeArtefatosDropdown(e) {
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
            menu.classList.add('hidden');
        }
    });

    // Atualizar estado
    artefatoAtivo = artefatosDisponiveis[0].key;
}

// Alterna para uma aba de artefato especifica
function alternarAbaArtefato(key) {
    const dropdown = document.getElementById('artefatos-dropdown');
    const menu = document.getElementById('artefatos-menu');
    const iconSpan = document.getElementById('artefatos-icon');
    const labelSpan = document.getElementById('artefatos-label');
    const toggleBtn = document.getElementById('artefatos-toggle');
    const contentContainer = document.getElementById('artefatos-container');

    if (!contentContainer) return;

    // Encontrar artefato selecionado
    const artefatosDisponiveis = conteudoCache.artefatos_disponiveis || [];
    const artefatoSelecionado = artefatosDisponiveis.find(a => a.key === key);

    if (artefatoSelecionado && dropdown) {
        // Atualizar botao toggle com artefato selecionado
        const icone = artefatoSelecionado.icone || ARTEFATO_ICONS[key] || ARTEFATO_ICONS.analise;
        iconSpan.innerHTML = icone;
        labelSpan.textContent = artefatoSelecionado.nome;
        toggleBtn.dataset.activeKey = key;

        // Atualizar estado visual no menu
        menu.querySelectorAll('.artefato-item').forEach(item => {
            if (item.dataset.key === key) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // Ocultar todos os conteudos
    contentContainer.querySelectorAll('.artefato-content').forEach(content => {
        content.classList.add('hidden');
    });

    // Mostrar conteudo selecionado
    const contentAtivo = document.getElementById(`artefato-${key}`);
    if (contentAtivo) {
        contentAtivo.classList.remove('hidden');
    }

    artefatoAtivo = key;
}

// Renderiza as abas de minutas dinamicamente (painel direito)
function renderizarAbasMinutas() {
    const tabsContainer = document.getElementById('minuta-tabs');

    if (!tabsContainer) return;

    // Verificar se ha minutas disponiveis (novo formato)
    const minutasDisponiveis = conteudoCache.minutas_disponiveis || [];

    // Se nao ha minutas, esconder abas e mostrar mensagem
    if (minutasDisponiveis.length === 0) {
        tabsContainer.classList.add('hidden');
        previewMinuta.innerHTML = '<p class="empty-state">Nenhuma minuta encontrada</p>';
        return;
    }

    // Detectar status de revisao para cada minuta
    minutasDisponiveis.forEach(minuta => {
        const conteudo = conteudoCache.minutas?.[minuta.key];
        minuta.status = detectarStatusRevisao(conteudo);
    });

    // Se ha apenas 1 minuta, esconder abas mas mostrar conteudo com selo de revisao
    if (minutasDisponiveis.length === 1) {
        tabsContainer.classList.add('hidden');
        const key = minutasDisponiveis[0].key;
        const conteudo = conteudoCache.minutas[key] || '*Arquivo nao encontrado*';
        const status = minutasDisponiveis[0].status;

        // Adicionar selo visual de revisao se aplicavel
        let htmlConteudo = '';
        if (status && status.revisada) {
            htmlConteudo += `<div class="revisao-selo">
                ${CHECKMARK_ICON}
                <span class="revisao-selo-texto">${status.tipo === 'robustecida' ? 'Robustecida' : 'Revisada'}</span>
                ${status.data ? `<span class="revisao-selo-data">${status.data}</span>` : ''}
            </div>`;
        }
        htmlConteudo += marked.parse(conteudo);
        previewMinuta.innerHTML = htmlConteudo;
        minutaAtiva = key;
        return;
    }

    // Multiplas minutas: mostrar abas com badges de status
    tabsContainer.classList.remove('hidden');

    // Gerar HTML das abas com icones e badges
    let tabsHtml = '';
    minutasDisponiveis.forEach((minuta, index) => {
        const isActive = index === 0 ? 'active' : '';
        const icone = minuta.icone || ARTEFATO_ICONS[minuta.key] || ARTEFATO_ICONS.minuta;
        const badge = gerarBadgeStatus(minuta.status, 'minuta');

        tabsHtml += `
            <button class="minuta-tab ${isActive}" data-key="${minuta.key}">
                ${icone}
                ${minuta.nome}
                ${badge}
            </button>
        `;
    });
    tabsContainer.innerHTML = tabsHtml;

    // Renderizar primeira minuta com selo de revisao
    minutaAtiva = minutasDisponiveis[0].key;
    const conteudo = conteudoCache.minutas[minutaAtiva] || '*Arquivo nao encontrado*';
    const status = minutasDisponiveis[0].status;

    let htmlConteudo = '';
    if (status && status.revisada) {
        htmlConteudo += `<div class="revisao-selo">
            ${CHECKMARK_ICON}
            <span class="revisao-selo-texto">${status.tipo === 'robustecida' ? 'Robustecida' : 'Revisada'}</span>
            ${status.data ? `<span class="revisao-selo-data">${status.data}</span>` : ''}
        </div>`;
    }
    htmlConteudo += marked.parse(conteudo);
    previewMinuta.innerHTML = htmlConteudo;

    // Event delegation para cliques nas abas
    tabsContainer.onclick = function(e) {
        const tab = e.target.closest('.minuta-tab');
        if (tab) {
            const key = tab.dataset.key;
            alternarAbaMinutaNova(key);
        }
    };
}

// Alterna para uma aba de minuta especifica (novo sistema)
function alternarAbaMinutaNova(key) {
    const tabsContainer = document.getElementById('minuta-tabs');

    if (!tabsContainer) return;

    // Atualizar estado visual das abas
    tabsContainer.querySelectorAll('.minuta-tab').forEach(tab => {
        if (tab.dataset.key === key) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Renderizar conteudo da minuta selecionada com selo de revisao
    const conteudo = conteudoCache.minutas[key] || '*Arquivo nao encontrado*';
    const status = detectarStatusRevisao(conteudo);

    let htmlConteudo = '';
    if (status && status.revisada) {
        htmlConteudo += `<div class="revisao-selo">
            ${CHECKMARK_ICON}
            <span class="revisao-selo-texto">${status.tipo === 'robustecida' ? 'Robustecida' : 'Revisada'}</span>
            ${status.data ? `<span class="revisao-selo-data">${status.data}</span>` : ''}
        </div>`;
    }
    htmlConteudo += marked.parse(conteudo);
    previewMinuta.innerHTML = htmlConteudo;

    minutaAtiva = key;
}

// Popular meta bar no header do preview com metadados do processo
function popularMetaBar(processo) {
    const metaBar = document.getElementById('preview-meta-bar');
    if (!metaBar) return;

    const meta = processosMeta[processo.numero] || {};
    let html = '';

    // Tema
    if (meta.tema_nome || meta.tema) {
        const tema = meta.tema_nome || meta.tema;
        html += `
            <div class="meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
                <span class="meta-value" title="${tema}">${encurtarNomeTema(tema)}</span>
            </div>
        `;
    }

    // Urgencia
    if (meta.urgencia && meta.urgencia !== 'normal') {
        const urgClass = meta.urgencia === 'critica' ? 'urgencia-critica' : 'urgencia-alta';
        const urgLabel = meta.urgencia === 'critica' ? 'Critica' : 'Alta';
        html += `
            <div class="meta-separator"></div>
            <div class="meta-item ${urgClass}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <span class="meta-value">${urgLabel}</span>
            </div>
        `;
    }

    // Dias conclusos
    if (meta.dias_conclusos && meta.dias_conclusos > 0) {
        html += `
            <div class="meta-separator"></div>
            <div class="meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span class="meta-value">${meta.dias_conclusos}d concluso</span>
            </div>
        `;
    }

    // Prioridade legal (pode ser objeto ou string)
    if (meta.prioridade_legal) {
        const prioLabels = {
            'idoso': 'Idoso',
            'deficiente': 'PcD',
            'doenca_grave': 'Doenca Grave',
            'reu_preso': 'Reu Preso',
            'crianca_adolescente': 'Crianca'
        };

        let prioAtivas = [];

        // Se for objeto, extrair as prioridades ativas (valor true)
        if (typeof meta.prioridade_legal === 'object') {
            for (const [key, value] of Object.entries(meta.prioridade_legal)) {
                if (value === true && prioLabels[key]) {
                    prioAtivas.push(prioLabels[key]);
                }
            }
        } else {
            // Se for string (formato antigo), usar diretamente
            const label = prioLabels[meta.prioridade_legal] || meta.prioridade_legal;
            prioAtivas.push(label);
        }

        // Exibir apenas se houver prioridades ativas
        if (prioAtivas.length > 0) {
            html += `
                <div class="meta-separator"></div>
                <div class="meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    <span class="meta-value">${prioAtivas.join(', ')}</span>
                </div>
            `;
        }
    }

    metaBar.innerHTML = html;
}

// Atualizar visual das abas de minuta
function atualizarAbasMinuta() {
    const tabs = document.querySelectorAll('.minuta-tab');
    tabs.forEach(tab => {
        if (tab.dataset.tab === minutaAtiva) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Atualizar conteudo exibido
    const minuta = minutaAtiva === 'original'
        ? (conteudoCache.minuta_original || '*Arquivo original nao encontrado*')
        : (conteudoCache.minuta || '*Arquivo de minuta nao encontrado*');
    previewMinuta.innerHTML = marked.parse(minuta);
}

// Alternar aba de minuta
function alternarAbaMinuta(aba) {
    minutaAtiva = aba;
    atualizarAbasMinuta();
}

// Fechar modal
function fecharModal() {
    previewModal.classList.add('hidden');
    processoSelecionado = null;
    document.querySelectorAll('.kanban-card').forEach(c => c.classList.remove('selected'));
}

// Copiar numero do processo para clipboard
async function copiarNumeroProcesso() {
    if (!processoSelecionado) return;

    try {
        await navigator.clipboard.writeText(processoSelecionado.numero);

        // Feedback visual
        btnCopiarNumero.textContent = 'Copiado!';
        btnCopiarNumero.classList.add('copiado');

        // Resetar apos 2 segundos
        setTimeout(() => {
            btnCopiarNumero.textContent = 'Copiar';
            btnCopiarNumero.classList.remove('copiado');
        }, 2000);

    } catch (error) {
        console.error('Erro ao copiar:', error);
    }
}

// Copiar minuta para clipboard
async function copiarMinuta() {
    // Copiar a versao atualmente visivel (suporta novo sistema de abas)
    let minuta = '';

    if (minutaAtiva === 'original') {
        // Minuta original (backup antes de revisao)
        minuta = conteudoCache.minuta_original || '';
    } else if (conteudoCache.minutas && conteudoCache.minutas[minutaAtiva]) {
        // Novo sistema: buscar no dict de minutas pela key ativa
        minuta = conteudoCache.minutas[minutaAtiva];
    } else {
        // Fallback legado
        minuta = conteudoCache.minuta || '';
    }

    if (!minuta) {
        alert('Nenhuma minuta para copiar.');
        return;
    }

    try {
        await navigator.clipboard.writeText(minuta);

        // Feedback visual (nova estrutura com SVG + span)
        const copiarSpan = btnCopiarMinuta.querySelector('span');
        if (copiarSpan) copiarSpan.textContent = 'Copiado!';
        btnCopiarMinuta.classList.add('copiado');

        // Resetar apos 2 segundos
        setTimeout(() => {
            if (copiarSpan) copiarSpan.textContent = 'Copiar';
            btnCopiarMinuta.classList.remove('copiado');
        }, 2000);

    } catch (error) {
        console.error('Erro ao copiar:', error);
        alert('Erro ao copiar. Tente selecionar o texto manualmente.');
    }
}

// Copiar analise/artefato ativo para clipboard
async function copiarAnalise() {
    // Buscar conteudo do artefato atualmente visivel
    let conteudo = '';

    if (conteudoCache.artefatos && conteudoCache.artefatos[artefatoAtivo]) {
        conteudo = conteudoCache.artefatos[artefatoAtivo];
    } else if (artefatoAtivo === 'analise') {
        // Fallback para campo legado
        conteudo = conteudoCache.analise || '';
    }

    if (!conteudo) {
        alert('Nenhum conteudo para copiar.');
        return;
    }

    try {
        await navigator.clipboard.writeText(conteudo);

        // Feedback visual
        const copiarSpan = btnCopiarAnalise.querySelector('span');
        if (copiarSpan) copiarSpan.textContent = 'Copiado!';
        btnCopiarAnalise.classList.add('copiado');

        // Resetar apos 2 segundos
        setTimeout(() => {
            if (copiarSpan) copiarSpan.textContent = 'Copiar';
            btnCopiarAnalise.classList.remove('copiado');
        }, 2000);

    } catch (error) {
        console.error('Erro ao copiar analise:', error);
        alert('Erro ao copiar. Tente selecionar o texto manualmente.');
    }
}

// Configurar eventos
function configurarEventos() {
    // Busca em tempo real (com debounce)
    let buscaTimeout;
    busca.addEventListener('input', () => {
        clearTimeout(buscaTimeout);
        buscaTimeout = setTimeout(renderizarKanban, 300);
    });

    // Desfazer
    btnDesfazer.addEventListener('click', desfazerAcao);

    // Atualizar
    btnAtualizar.addEventListener('click', carregarProcessos);

    // Tema visual
    btnTema.addEventListener('click', alternarTema);

    // Fechar preview
    btnFecharPreview.addEventListener('click', fecharModal);

    // Botao home (voltar ao kanban)
    const btnHome = document.getElementById('btn-home');
    if (btnHome) {
        btnHome.addEventListener('click', (e) => {
            e.preventDefault();
            fecharModal();
        });
    }

    // Copiar minuta
    btnCopiarMinuta.addEventListener('click', copiarMinuta);

    // Copiar analise/artefato ativo
    btnCopiarAnalise.addEventListener('click', copiarAnalise);

    // Copiar numero do processo
    btnCopiarNumero.addEventListener('click', copiarNumeroProcesso);

    // Arquivar do modal
    btnArquivarModal.addEventListener('click', () => {
        if (processoSelecionado) {
            arquivarProcesso(processoSelecionado.numero, processoSelecionado.estado, processoSelecionado.tipo);
        }
    });

    // Abrir pasta no Explorer
    btnAbrirPasta.addEventListener('click', () => {
        if (processoSelecionado && processoSelecionado.caminho) {
            navigator.clipboard.writeText(processoSelecionado.caminho).then(() => {
                alert('Caminho copiado para a area de transferencia:\n\n' + processoSelecionado.caminho);
            }).catch(() => {
                alert('Caminho da pasta:\n\n' + processoSelecionado.caminho);
            });
        }
    });

    // Arquivar todos os validados
    const btnArquivarTodos = document.querySelector('.btn-arquivar-todos');
    if (btnArquivarTodos) {
        btnArquivarTodos.addEventListener('click', arquivarTodos);
    }

    // Atalho de teclado: Escape fecha modal, Ctrl+K foca busca
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !previewModal.classList.contains('hidden')) {
            fecharModal();
        }
        // Ctrl+K ou Cmd+K para focar na busca
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            busca.focus();
            busca.select();
        }
    });

    // Abas de minuta (robustecida/original)
    document.querySelectorAll('.minuta-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            alternarAbaMinuta(tab.dataset.tab);
        });
    });

    // Toggle do painel de filtros
    const btnToggleFilters = document.getElementById('btn-toggle-filters');
    const filtersPanel = document.getElementById('filters-panel');
    if (btnToggleFilters && filtersPanel) {
        btnToggleFilters.addEventListener('click', () => {
            btnToggleFilters.classList.toggle('active');
            filtersPanel.classList.toggle('active');
        });
    }

    // Botao limpar foco (na barra de filtro ativo)
    const btnLimparFoco = document.getElementById('btn-limpar-foco');
    if (btnLimparFoco) {
        btnLimparFoco.addEventListener('click', () => {
            // Limpar todos os filtros
            document.getElementById('filtro-tema').value = '';
            document.getElementById('filtro-urgencia').value = '';
            document.getElementById('filtro-prioridade').value = '';
            document.getElementById('filtro-dias').value = '';
            document.getElementById('foco-ativo').classList.add('hidden');
            renderizarKanban();
            atualizarContadorFiltros();
        });
    }

    // Filtros do painel
    ['filtro-tema', 'filtro-urgencia', 'filtro-prioridade', 'filtro-dias'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                aplicarFiltros();
            });
        }
    });

    // Ordenacao
    const selectOrdenacao = document.getElementById('filtro-ordenacao');
    if (selectOrdenacao) {
        selectOrdenacao.addEventListener('change', () => {
            ordenacaoAtiva = selectOrdenacao.value;
            salvarOrdenacao();
            renderizarKanban();
        });
    }

    // Dropdown de mover processo
    configurarDropdownMover();
}

// Atualizar contador total (novo formato)
function atualizarContador() {
    let total = 0;
    Object.values(processos).forEach(lista => total += lista.length);
    contador.textContent = total;
}

// Aplicar filtros e atualizar UI
function aplicarFiltros() {
    const tema = document.getElementById('filtro-tema').value;
    const urgencia = document.getElementById('filtro-urgencia').value;
    const prioridade = document.getElementById('filtro-prioridade').value;
    const dias = document.getElementById('filtro-dias').value;

    // Contar filtros ativos
    const filtrosAtivos = [tema, urgencia, prioridade, dias].filter(f => f).length;

    // Atualizar contador de filtros no botao
    atualizarContadorFiltros();

    // Mostrar/esconder barra de foco ativo
    const focoAtivo = document.getElementById('foco-ativo');
    const focoLabel = document.getElementById('foco-label');

    if (filtrosAtivos > 0) {
        let label = [];
        if (tema) label.push(temasDisponiveis[tema] || tema);
        if (urgencia) label.push(`Urgencia: ${urgencia}`);
        if (prioridade) label.push(`Prioridade: ${prioridade}`);
        if (dias) label.push(`+${dias} dias`);

        focoLabel.textContent = label.join(' | ');
        focoAtivo.classList.remove('hidden');
    } else {
        focoAtivo.classList.add('hidden');
    }

    renderizarKanban();
}

// Atualizar contador de filtros ativos
function atualizarContadorFiltros() {
    const tema = document.getElementById('filtro-tema').value;
    const urgencia = document.getElementById('filtro-urgencia').value;
    const prioridade = document.getElementById('filtro-prioridade').value;
    const dias = document.getElementById('filtro-dias').value;

    const count = [tema, urgencia, prioridade, dias].filter(f => f).length;
    const filterCount = document.getElementById('filter-count');
    const focoCount = document.getElementById('foco-count');

    if (filterCount) {
        filterCount.textContent = count;
        filterCount.classList.toggle('hidden', count === 0);
    }
    if (focoCount) {
        focoCount.textContent = `${count} filtro${count !== 1 ? 's' : ''}`;
    }
}

// ============================================
// DROPDOWN MOVER - Transferir entre colunas
// ============================================

// Nomes amigaveis das colunas (usa labels fixos)
function obterNomeColuna(estado) {
    return LABELS_COLUNAS[estado] || estado;
}

// Configurar dropdown de mover processo
function configurarDropdownMover() {
    if (!btnMoverToggle || !moverMenu || !moverDropdown) return;

    // Toggle do menu
    btnMoverToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMenuMover();
    });

    // Clicar nos itens do menu
    moverMenu.addEventListener('click', (e) => {
        const item = e.target.closest('.mover-item');
        if (item && !item.classList.contains('current')) {
            const destino = item.dataset.destino;
            moverProcessoPara(destino);
            fecharMenuMover();
        }
    });

    // Fechar menu ao clicar fora
    document.addEventListener('click', (e) => {
        if (!moverDropdown.contains(e.target)) {
            fecharMenuMover();
        }
    });

    // Fechar menu com Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && moverDropdown.classList.contains('open')) {
            e.stopPropagation();
            fecharMenuMover();
        }
    });
}

// Abrir/fechar menu de mover
function toggleMenuMover() {
    const isOpen = moverDropdown.classList.contains('open');
    if (isOpen) {
        fecharMenuMover();
    } else {
        abrirMenuMover();
    }
}

// Abrir menu e marcar coluna atual
function abrirMenuMover() {
    if (!processoSelecionado) return;

    // Marcar coluna atual como desabilitada
    moverMenu.querySelectorAll('.mover-item').forEach(item => {
        item.classList.remove('current');
        if (item.dataset.destino === processoSelecionado.estado) {
            item.classList.add('current');
        }
    });

    moverDropdown.classList.add('open');
    moverMenu.classList.remove('hidden');
}

// Fechar menu
function fecharMenuMover() {
    moverDropdown.classList.remove('open');
    moverMenu.classList.add('hidden');
}

// Mover processo para destino escolhido
async function moverProcessoPara(estadoDestino, sobrescrever = false) {
    if (!processoSelecionado) return;
    if (processoSelecionado.estado === estadoDestino) return;

    const numero = processoSelecionado.numero;
    const estadoOrigem = processoSelecionado.estado;

    try {
        const response = await fetch('/api/mover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: numero,
                estado_origem: estadoOrigem,
                estado_destino: estadoDestino,
                tipo: processoSelecionado.tipo,
                sobrescrever: sobrescrever
            })
        });

        if (!response.ok) {
            const err = await response.json();

            // Conflito: processo ja existe no destino
            if (response.status === 409) {
                const nomeDestino = obterNomeColuna(estadoDestino);
                const confirmar = confirm(
                    `Ja existe o processo ${numero} na coluna "${nomeDestino}".\n\n` +
                    `Deseja sobrescrever? Os arquivos novos substituirao os antigos, ` +
                    `mas arquivos unicos da versao anterior serao mantidos.`
                );
                if (confirmar) {
                    return moverProcessoPara(estadoDestino, true);
                }
                return;
            }

            throw new Error(err.detail || 'Erro ao mover processo');
        }

        // Salvar acao para UNDO
        ultimaAcao = {
            numero: numero,
            origem: estadoDestino,  // Invertido para desfazer
            destino: estadoOrigem,
            tipo: processoSelecionado.tipo
        };
        atualizarBotaoDesfazer();

        // Fechar modal apos mover
        fecharModal();

        // Recarregar
        await carregarProcessos();

    } catch (error) {
        console.error('Erro ao mover:', error);
        alert('Erro ao mover processo: ' + error.message);
    }
}

// Atualizar estado do botao Desfazer
function atualizarBotaoDesfazer() {
    if (ultimaAcao) {
        btnDesfazer.disabled = false;
    } else {
        btnDesfazer.disabled = true;
    }
}

// Desfazer ultima acao
async function desfazerAcao(sobrescrever = false) {
    if (!ultimaAcao) return;

    try {
        const response = await fetch('/api/mover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: ultimaAcao.numero,
                estado_origem: ultimaAcao.origem,
                estado_destino: ultimaAcao.destino,
                tipo: ultimaAcao.tipo,
                sobrescrever: sobrescrever
            })
        });

        if (!response.ok) {
            const err = await response.json();

            // Conflito: processo ja existe no destino
            if (response.status === 409) {
                const confirmar = confirm(
                    `Ja existe o processo ${ultimaAcao.numero} na coluna de destino.\n\n` +
                    `Deseja sobrescrever para desfazer a acao?`
                );
                if (confirmar) {
                    return desfazerAcao(true);
                }
                return;
            }

            throw new Error(err.detail || 'Erro ao desfazer acao');
        }

        // Limpar acao e desabilitar botao
        ultimaAcao = null;
        atualizarBotaoDesfazer();

        // Recarregar processos
        await carregarProcessos();

    } catch (error) {
        console.error('Erro ao desfazer:', error);
        alert('Erro ao desfazer: ' + error.message);
    }
}

// ============================================================================
// SISTEMA DE NOTAS
// ============================================================================

// Estado da nota
let notaOriginal = null;
const notaModal = document.getElementById('nota-modal');
const notaTextarea = document.getElementById('nota-textarea');
const notaChars = document.getElementById('nota-chars');
const notaIndicator = document.getElementById('nota-indicator');
const btnNota = document.getElementById('btn-nota');
const btnFecharNota = document.getElementById('btn-fechar-nota');
const btnCancelarNota = document.getElementById('btn-cancelar-nota');
const btnSalvarNota = document.getElementById('btn-salvar-nota');
const btnApagarNota = document.getElementById('btn-apagar-nota');

// Configurar eventos do modal de notas
function configurarModalNotas() {
    if (!notaModal) return;

    // Abrir modal
    btnNota?.addEventListener('click', abrirModalNota);

    // Fechar modal
    btnFecharNota?.addEventListener('click', fecharModalNota);
    btnCancelarNota?.addEventListener('click', fecharModalNota);
    notaModal.querySelector('.nota-modal-overlay')?.addEventListener('click', fecharModalNota);

    // Salvar nota
    btnSalvarNota?.addEventListener('click', salvarNota);

    // Apagar nota
    btnApagarNota?.addEventListener('click', apagarNota);

    // Contador de caracteres
    notaTextarea?.addEventListener('input', () => {
        if (notaChars) {
            notaChars.textContent = notaTextarea.value.length;
        }
    });

    // Fechar com Escape (se o modal de nota estiver aberto)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && notaModal && !notaModal.classList.contains('hidden')) {
            e.stopPropagation();
            fecharModalNota();
        }
    });
}

// Abrir modal de nota
async function abrirModalNota() {
    if (!processoSelecionado || !notaModal) return;

    // Carregar nota existente
    try {
        const response = await fetch(
            `/api/nota/${processoSelecionado.tipo}/${processoSelecionado.estado}/${processoSelecionado.numero}`
        );
        const data = await response.json();

        notaOriginal = data.nota || '';
        notaTextarea.value = notaOriginal;
        if (notaChars) notaChars.textContent = notaOriginal.length;

        // Mostrar/esconder botao apagar
        if (notaOriginal) {
            btnApagarNota?.classList.remove('hidden');
        } else {
            btnApagarNota?.classList.add('hidden');
        }

    } catch (error) {
        console.error('Erro ao carregar nota:', error);
        notaOriginal = '';
        notaTextarea.value = '';
        if (notaChars) notaChars.textContent = '0';
        btnApagarNota?.classList.add('hidden');
    }

    // Mostrar modal
    notaModal.classList.remove('hidden');
    notaTextarea?.focus();
}

// Fechar modal de nota
function fecharModalNota() {
    if (!notaModal) return;

    // Verificar se ha alteracoes nao salvas
    if (notaTextarea && notaTextarea.value !== notaOriginal) {
        if (!confirm('Descartar alteracoes na nota?')) {
            return;
        }
    }

    notaModal.classList.add('hidden');
    notaOriginal = null;
}

// Salvar nota
async function salvarNota() {
    if (!processoSelecionado || !notaTextarea) return;

    const conteudo = notaTextarea.value.trim();

    // Desabilitar botao durante salvamento
    if (btnSalvarNota) {
        btnSalvarNota.disabled = true;
        const span = btnSalvarNota.querySelector('span') || btnSalvarNota;
        if (span.textContent) span.textContent = 'Salvando...';
    }

    try {
        const response = await fetch('/api/nota', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: processoSelecionado.numero,
                estado: processoSelecionado.estado,
                tipo: processoSelecionado.tipo,
                conteudo: conteudo
            })
        });

        if (!response.ok) {
            throw new Error('Erro ao salvar nota');
        }

        // Atualizar indicador de nota no botao
        atualizarIndicadorNota(conteudo !== '');

        // Atualizar estado original
        notaOriginal = conteudo;

        // Fechar modal
        notaModal?.classList.add('hidden');

    } catch (error) {
        console.error('Erro ao salvar nota:', error);
        alert('Erro ao salvar nota. Tente novamente.');
    } finally {
        if (btnSalvarNota) {
            btnSalvarNota.disabled = false;
            btnSalvarNota.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                Salvar
            `;
        }
    }
}

// Apagar nota
async function apagarNota() {
    if (!processoSelecionado) return;

    if (!confirm('Apagar esta nota?')) return;

    try {
        const response = await fetch('/api/nota', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: processoSelecionado.numero,
                estado: processoSelecionado.estado,
                tipo: processoSelecionado.tipo,
                conteudo: null
            })
        });

        if (!response.ok) {
            throw new Error('Erro ao apagar nota');
        }

        // Limpar textarea
        if (notaTextarea) notaTextarea.value = '';
        notaOriginal = '';
        if (notaChars) notaChars.textContent = '0';

        // Esconder botao apagar
        btnApagarNota?.classList.add('hidden');

        // Atualizar indicador
        atualizarIndicadorNota(false);

        // Fechar modal
        notaModal?.classList.add('hidden');

    } catch (error) {
        console.error('Erro ao apagar nota:', error);
        alert('Erro ao apagar nota. Tente novamente.');
    }
}

// Atualizar indicador visual de nota existente
function atualizarIndicadorNota(temNota) {
    if (notaIndicator) {
        if (temNota) {
            notaIndicator.classList.remove('hidden');
        } else {
            notaIndicator.classList.add('hidden');
        }
    }
}

// Carregar estado da nota ao selecionar processo
async function carregarEstadoNota(processo) {
    try {
        const response = await fetch(
            `/api/nota/${processo.tipo}/${processo.estado}/${processo.numero}`
        );
        const data = await response.json();
        atualizarIndicadorNota(data.nota && data.nota.trim() !== '');
    } catch (error) {
        atualizarIndicadorNota(false);
    }
}

// Inicializar modal de notas
configurarModalNotas();

// ============================================================================
// SISTEMA DE ANEXOS
// ============================================================================

const anexosPanel = document.getElementById('anexos-panel');
const anexosDropzone = document.getElementById('anexos-dropzone');
const anexosLista = document.getElementById('anexos-lista');
const anexosBadge = document.getElementById('anexos-badge');
const anexosVazio = document.getElementById('anexos-vazio');
const inputAnexo = document.getElementById('input-anexo');
const btnAnexos = document.getElementById('btn-anexos');
const btnFecharAnexos = document.getElementById('btn-fechar-anexos');

// Configurar eventos de anexos
function configurarAnexos() {
    if (!anexosPanel) return;

    // Toggle painel
    btnAnexos?.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePainelAnexos();
    });

    // Fechar painel
    btnFecharAnexos?.addEventListener('click', () => {
        anexosPanel.classList.add('hidden');
    });

    // Drag & Drop
    if (anexosDropzone) {
        anexosDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            anexosDropzone.classList.add('dragover');
        });

        anexosDropzone.addEventListener('dragleave', () => {
            anexosDropzone.classList.remove('dragover');
        });

        anexosDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            anexosDropzone.classList.remove('dragover');

            const files = e.dataTransfer.files;
            for (const file of files) {
                uploadAnexo(file);
            }
        });
    }

    // Input de arquivo
    inputAnexo?.addEventListener('change', () => {
        for (const file of inputAnexo.files) {
            uploadAnexo(file);
        }
        inputAnexo.value = '';
    });

    // Fechar painel ao clicar fora
    document.addEventListener('click', (e) => {
        if (anexosPanel && btnAnexos &&
            !anexosPanel.contains(e.target) &&
            !btnAnexos.contains(e.target)) {
            anexosPanel.classList.add('hidden');
        }
    });

    // Event delegation para botoes de deletar anexo
    anexosLista?.addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-delete-anexo]');
        if (btn) {
            const nome = btn.dataset.deleteAnexo;
            await deletarAnexo(nome);
        }
    });
}

// Toggle painel de anexos
function togglePainelAnexos() {
    if (!anexosPanel || !btnAnexos) return;

    if (anexosPanel.classList.contains('hidden')) {
        // Posicionar proximo ao botao
        const rect = btnAnexos.getBoundingClientRect();
        anexosPanel.style.top = (rect.bottom + 8) + 'px';
        anexosPanel.classList.remove('hidden');
        carregarAnexos();
    } else {
        anexosPanel.classList.add('hidden');
    }
}

// Carregar lista de anexos
async function carregarAnexos() {
    if (!processoSelecionado) return;

    try {
        const response = await fetch(
            `/api/anexos/${processoSelecionado.tipo}/${processoSelecionado.estado}/${processoSelecionado.numero}`
        );
        const data = await response.json();

        if (data.sucesso) {
            renderizarAnexos(data.anexos);
            atualizarBadgeAnexos(data.total);
        }
    } catch (error) {
        console.error('Erro ao carregar anexos:', error);
    }
}

// Renderizar lista de anexos
function renderizarAnexos(anexos) {
    if (!anexosLista || !anexosVazio) return;

    if (anexos.length === 0) {
        anexosLista.innerHTML = '';
        anexosVazio.classList.remove('hidden');
        return;
    }

    anexosVazio.classList.add('hidden');
    anexosLista.innerHTML = anexos.map(anexo => {
        const nomeEscapado = escapeHtml(anexo.nome);
        const extensao = anexo.extensao ? escapeHtml(anexo.extensao.toUpperCase()) : 'ARQUIVO';
        const tamanho = escapeHtml(anexo.tamanho_formatado);
        return `
            <div class="anexo-item" data-nome="${nomeEscapado}">
                <div class="anexo-icon">
                    ${getIconeArquivo(anexo.extensao)}
                </div>
                <div class="anexo-info">
                    <span class="anexo-nome" title="${nomeEscapado}">${escapeHtml(truncarNome(anexo.nome, 28))}</span>
                    <span class="anexo-meta">${extensao} - ${tamanho}</span>
                </div>
                <button class="btn-anexo-deletar" title="Remover anexo" data-delete-anexo="${nomeEscapado}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

// Icone por tipo de arquivo
function getIconeArquivo(extensao) {
    const ext = (extensao || '').toLowerCase();
    const icones = {
        pdf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        jpg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
        jpeg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
        png: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
        doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        docx: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
    };
    return icones[ext] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>';
}

// Upload de arquivo
async function uploadAnexo(file) {
    if (!processoSelecionado) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(
            `/api/anexos/${processoSelecionado.tipo}/${processoSelecionado.estado}/${processoSelecionado.numero}`,
            {
                method: 'POST',
                body: formData
            }
        );

        const data = await response.json();

        if (data.sucesso) {
            carregarAnexos();
        } else {
            alert('Erro ao enviar arquivo: ' + (data.erro || 'Erro desconhecido'));
        }
    } catch (error) {
        console.error('Erro no upload:', error);
        alert('Erro ao enviar arquivo');
    }
}

// Deletar anexo
async function deletarAnexo(nome) {
    if (!processoSelecionado) return;

    if (!confirm(`Deseja remover o anexo "${nome}"?`)) return;

    try {
        const response = await fetch(
            `/api/anexos/${processoSelecionado.tipo}/${processoSelecionado.estado}/${encodeURIComponent(processoSelecionado.numero)}/${encodeURIComponent(nome)}`,
            { method: 'DELETE' }
        );

        const data = await response.json();

        if (data.sucesso) {
            carregarAnexos();
        } else {
            alert('Erro ao remover: ' + data.erro);
        }
    } catch (error) {
        console.error('Erro ao deletar:', error);
    }
}

// Atualizar badge de anexos
function atualizarBadgeAnexos(total) {
    if (anexosBadge) {
        if (total > 0) {
            anexosBadge.textContent = total;
            anexosBadge.classList.remove('hidden');
        } else {
            anexosBadge.classList.add('hidden');
        }
    }
}

// Truncar nome longo de arquivo
function truncarNome(nome, max) {
    if (!nome || nome.length <= max) return nome;

    const partes = nome.split('.');
    if (partes.length > 1) {
        const ext = partes.pop();
        const base = partes.join('.');
        const maxBase = max - ext.length - 4;
        if (maxBase > 0 && base.length > maxBase) {
            return base.slice(0, maxBase) + '...' + ext;
        }
    }

    return nome.slice(0, max - 3) + '...';
}

// Inicializar anexos
configurarAnexos();

// ============================================================================
// BOTAO DE FAVORITO NO PREVIEW
// ============================================================================

const btnFavoritoPreview = document.getElementById('btn-favorito-preview');

// Configurar evento do botao de favorito
if (btnFavoritoPreview) {
    btnFavoritoPreview.addEventListener('click', () => {
        if (!processoSelecionado) return;

        // Toggle favorito
        toggleFavorito(processoSelecionado.numero);

        // Atualizar estado do botao no preview
        atualizarBotaoFavoritoPreview();

        // Atualizar o card no Kanban
        atualizarCardFavorito(processoSelecionado.numero);
    });
}

// Atualiza o estado visual do botao de favorito no preview
function atualizarBotaoFavoritoPreview() {
    if (!btnFavoritoPreview || !processoSelecionado) return;

    if (isFavorito(processoSelecionado.numero)) {
        btnFavoritoPreview.classList.add('favorito-ativo');
    } else {
        btnFavoritoPreview.classList.remove('favorito-ativo');
    }
}

// Atualiza o card no Kanban quando favorito e alterado no preview
function atualizarCardFavorito(numero) {
    const card = document.querySelector(`.kanban-card[data-numero="${numero}"]`);
    if (!card) return;

    const btnFavorito = card.querySelector('.btn-favorito');
    if (btnFavorito) {
        if (isFavorito(numero)) {
            btnFavorito.classList.add('ativo');
            btnFavorito.textContent = '★';
        } else {
            btnFavorito.classList.remove('ativo');
            btnFavorito.textContent = '☆';
        }
    }
}

// Guardar referencia a funcao original
const selecionarProcessoOriginal = selecionarProcesso;

// Sobrescrever para adicionar carregamento de notas, anexos e favorito
selecionarProcesso = async function(processo) {
    // Chamar funcao original
    await selecionarProcessoOriginal(processo);

    // Carregar estado da nota
    carregarEstadoNota(processo);

    // Carregar contagem de anexos (para badge)
    carregarAnexos();

    // Atualizar estado do botao de favorito
    atualizarBotaoFavoritoPreview();

    // Resetar modo edicao ao abrir novo processo
    resetarModoEdicao('analise');
    resetarModoEdicao('minuta');
};


// ============================================================================
// SISTEMA DE EDICAO DE ARQUIVOS MARKDOWN
// ============================================================================

// Estado de edicao
let edicaoAtiva = {
    analise: false,
    minuta: false
};
let conteudoOriginal = {
    analise: '',
    minuta: ''
};

// Elementos de edicao
const btnEditarAnalise = document.getElementById('btn-editar-analise');
const btnSalvarAnalise = document.getElementById('btn-salvar-analise');
const btnCancelarAnalise = document.getElementById('btn-cancelar-analise');
const btnEditarMinuta = document.getElementById('btn-editar-minuta');
const btnSalvarMinuta = document.getElementById('btn-salvar-minuta');
const btnCancelarMinuta = document.getElementById('btn-cancelar-minuta');

// Configurar eventos de edicao
if (btnEditarAnalise) {
    btnEditarAnalise.addEventListener('click', () => entrarModoEdicao('analise'));
}
if (btnSalvarAnalise) {
    btnSalvarAnalise.addEventListener('click', () => salvarEdicao('analise'));
}
if (btnCancelarAnalise) {
    btnCancelarAnalise.addEventListener('click', () => cancelarEdicao('analise'));
}
if (btnEditarMinuta) {
    btnEditarMinuta.addEventListener('click', () => entrarModoEdicao('minuta'));
}
if (btnSalvarMinuta) {
    btnSalvarMinuta.addEventListener('click', () => salvarEdicao('minuta'));
}
if (btnCancelarMinuta) {
    btnCancelarMinuta.addEventListener('click', () => cancelarEdicao('minuta'));
}

/**
 * Obtem informacoes do artefato ativo em um painel
 * @param {string} painel - 'analise' ou 'minuta'
 * @returns {object} - {key, nome, arquivo, conteudo}
 */
function obterArtefatoAtivo(painel) {
    if (painel === 'analise') {
        // Verificar qual artefato esta ativo no dropdown
        const toggleBtn = document.getElementById('artefatos-toggle');
        const activeKey = toggleBtn?.dataset.activeKey || 'analise';

        // Buscar nas listas de artefatos disponiveis
        const artefatos = conteudoCache.artefatos_disponiveis || [];
        const artefato = artefatos.find(a => a.key === activeKey);

        if (artefato) {
            return {
                key: artefato.key,
                nome: artefato.nome,
                arquivo: artefato.arquivo,
                conteudo: conteudoCache.artefatos?.[artefato.key] || ''
            };
        }

        // Fallback para campo legado
        return {
            key: 'analise',
            nome: 'Analise',
            arquivo: `${processoSelecionado.numero}-analise.md`,
            conteudo: conteudoCache.analise || ''
        };
    } else {
        // Para minuta, verificar qual aba esta ativa
        const minutas = conteudoCache.minutas_disponiveis || [];

        // Por enquanto usar a primeira minuta disponivel
        if (minutas.length > 0) {
            const minuta = minutas[0];
            return {
                key: minuta.key,
                nome: minuta.nome,
                arquivo: minuta.arquivo,
                conteudo: conteudoCache.minutas?.[minuta.key] || ''
            };
        }

        // Fallback para campo legado
        return {
            key: 'sentenca',
            nome: 'Sentenca',
            arquivo: `${processoSelecionado.numero}-sentenca.md`,
            conteudo: conteudoCache.minuta || ''
        };
    }
}

/**
 * Entra no modo de edicao para um painel
 * @param {string} painel - 'analise' ou 'minuta'
 */
function entrarModoEdicao(painel) {
    if (!processoSelecionado) return;

    const artefato = obterArtefatoAtivo(painel);

    if (!artefato.conteudo && !artefato.arquivo) {
        console.warn(`Nenhum arquivo para editar no painel ${painel}`);
        return;
    }

    edicaoAtiva[painel] = true;
    conteudoOriginal[painel] = artefato.conteudo;

    // Obter container de conteudo
    let container;
    if (painel === 'analise') {
        // Para analise, encontrar o artefato ativo
        const activeKey = document.getElementById('artefatos-toggle')?.dataset.activeKey || 'analise';
        container = document.getElementById(`artefato-${activeKey}`) || document.getElementById('artefatos-container');
    } else {
        container = document.getElementById('preview-minuta');
    }

    if (!container) return;

    // Salvar altura atual para manter consistencia
    const alturaAtual = container.offsetHeight;

    // Criar textarea
    const textarea = document.createElement('textarea');
    textarea.id = `editor-${painel}`;
    textarea.className = 'editor-markdown';
    textarea.value = artefato.conteudo;
    textarea.style.minHeight = `${Math.max(alturaAtual, 400)}px`;
    textarea.placeholder = `Editando: ${artefato.arquivo}`;

    // Substituir conteudo por textarea
    container.innerHTML = '';
    container.appendChild(textarea);
    container.classList.add('modo-edicao');

    // Focar no textarea
    textarea.focus();

    // Atualizar visibilidade dos botoes
    atualizarBotoesEdicao(painel, true);
}

/**
 * Salva as alteracoes feitas no editor
 * @param {string} painel - 'analise' ou 'minuta'
 */
async function salvarEdicao(painel) {
    if (!processoSelecionado || !edicaoAtiva[painel]) return;

    const textarea = document.getElementById(`editor-${painel}`);
    if (!textarea) return;

    const novoConteudo = textarea.value;
    const artefato = obterArtefatoAtivo(painel);

    // Mostrar indicador de salvamento
    const btnSalvar = painel === 'analise' ? btnSalvarAnalise : btnSalvarMinuta;
    const spanTexto = btnSalvar.querySelector('span');
    const textoOriginal = spanTexto.textContent;
    spanTexto.textContent = 'Salvando...';
    btnSalvar.disabled = true;

    try {
        const response = await fetch('/api/arquivo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                numero: processoSelecionado.numero,
                estado: processoSelecionado.estado,
                tipo: processoSelecionado.tipo,
                nome_arquivo: artefato.arquivo,
                conteudo: novoConteudo
            })
        });

        const resultado = await response.json();

        if (response.ok && resultado.sucesso) {
            // Atualizar cache local
            if (painel === 'analise') {
                if (conteudoCache.artefatos) {
                    conteudoCache.artefatos[artefato.key] = novoConteudo;
                }
                if (artefato.key === 'analise') {
                    conteudoCache.analise = novoConteudo;
                }
            } else {
                if (conteudoCache.minutas) {
                    conteudoCache.minutas[artefato.key] = novoConteudo;
                }
                if (artefato.key === 'sentenca') {
                    conteudoCache.minuta = novoConteudo;
                }
            }

            // Sair do modo edicao e renderizar novo conteudo
            sairModoEdicao(painel, novoConteudo);

            // Feedback visual
            spanTexto.textContent = 'Salvo!';
            setTimeout(() => {
                spanTexto.textContent = textoOriginal;
            }, 1500);
        } else {
            throw new Error(resultado.detail || resultado.erro || 'Erro ao salvar');
        }
    } catch (error) {
        console.error('Erro ao salvar:', error);
        alert(`Erro ao salvar arquivo: ${error.message}`);
        spanTexto.textContent = textoOriginal;
    } finally {
        btnSalvar.disabled = false;
    }
}

/**
 * Cancela a edicao e restaura o conteudo original
 * @param {string} painel - 'analise' ou 'minuta'
 */
function cancelarEdicao(painel) {
    if (!edicaoAtiva[painel]) return;

    const conteudo = conteudoOriginal[painel];
    sairModoEdicao(painel, conteudo);
}

/**
 * Sai do modo de edicao e renderiza o conteudo
 * @param {string} painel - 'analise' ou 'minuta'
 * @param {string} conteudo - Conteudo MD a ser renderizado
 */
function sairModoEdicao(painel, conteudo) {
    edicaoAtiva[painel] = false;
    conteudoOriginal[painel] = '';

    // Obter container
    let container;
    if (painel === 'analise') {
        const activeKey = document.getElementById('artefatos-toggle')?.dataset.activeKey || 'analise';
        container = document.getElementById(`artefato-${activeKey}`) || document.getElementById('artefatos-container');
    } else {
        container = document.getElementById('preview-minuta');
    }

    if (!container) return;

    // Renderizar markdown
    container.innerHTML = marked.parse(conteudo || '*Sem conteudo*');
    container.classList.remove('modo-edicao');

    // Atualizar botoes
    atualizarBotoesEdicao(painel, false);
}

/**
 * Reseta o modo de edicao para um painel
 * @param {string} painel - 'analise' ou 'minuta'
 */
function resetarModoEdicao(painel) {
    // Se estava editando, sair do modo edicao primeiro para limpar o DOM
    if (edicaoAtiva[painel]) {
        // Usar conteudo original para restaurar o estado
        const conteudo = conteudoOriginal[painel];
        edicaoAtiva[painel] = false;
        conteudoOriginal[painel] = '';

        // Limpar textarea se existir
        const textarea = document.getElementById(`editor-${painel}`);
        if (textarea) {
            const container = textarea.parentElement;
            if (container) {
                container.classList.remove('modo-edicao');
                // O conteudo sera re-renderizado pelo selecionarProcesso
            }
        }
    }

    edicaoAtiva[painel] = false;
    conteudoOriginal[painel] = '';
    atualizarBotoesEdicao(painel, false);
}

/**
 * Atualiza a visibilidade dos botoes de edicao
 * @param {string} painel - 'analise' ou 'minuta'
 * @param {boolean} emEdicao - Se esta em modo de edicao
 */
function atualizarBotoesEdicao(painel, emEdicao) {
    const btnEditar = painel === 'analise' ? btnEditarAnalise : btnEditarMinuta;
    const btnSalvar = painel === 'analise' ? btnSalvarAnalise : btnSalvarMinuta;
    const btnCancelar = painel === 'analise' ? btnCancelarAnalise : btnCancelarMinuta;

    if (emEdicao) {
        btnEditar?.classList.add('hidden');
        btnSalvar?.classList.remove('hidden');
        btnCancelar?.classList.remove('hidden');
    } else {
        btnEditar?.classList.remove('hidden');
        btnSalvar?.classList.add('hidden');
        btnCancelar?.classList.add('hidden');
    }
}
