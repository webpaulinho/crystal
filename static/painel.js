// Variáveis globais de cache
let gruposCache = [];
let usuariosCache = [];
let vacationAtivado = false;
let carregandoVacation = false;

// Funções auxiliares de formatação
function hojeStr() {
    const hoje = new Date();
    const yyyy = hoje.getFullYear();
    const mm = String(hoje.getMonth() + 1).padStart(2, '0');
    const dd = String(hoje.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function formatarDataBR(dataISO) {
    if (!dataISO) return "";
    const [yyyy, mm, dd] = dataISO.split('-');
    return `${dd}/${mm}/${yyyy}`;
}

// Corrigida: Retorna segunda-feira se último dia for sexta/sábado/domingo, senão retorna dia seguinte
function proximoDiaUtil(dataISO) {
    if (!dataISO) return "";
    let d = new Date(dataISO);
    let diaSemana = d.getDay(); // 0: domingo, 5: sexta, 6: sábado

    if (diaSemana === 6) { // sexta
        d.setDate(d.getDate() + 3); // sexta + 3 = segunda
    } else if (diaSemana === 7) { // sábado
        d.setDate(d.getDate() + 2); // sábado + 2 = segunda
    } else if (diaSemana === 1) { // domingo
        d.setDate(d.getDate() + 1); // domingo + 1 = segunda
    } else {
        d.setDate(d.getDate() + 1); // dia seguinte
    }
    return formatarDataBR(d.toISOString().split('T')[0]);
}

// Inicialização do editor Quill
const quill = new Quill('#editor', {
    theme: 'snow',
    modules: {
        toolbar: [
            [{ 'font': [] }, { 'size': [] }],
            ['bold', 'italic', 'underline', 'strike'],
            [{ 'color': [] }, { 'background': [] }],
            [{ 'align': [] }],
            ['link', 'image'],
            [{ 'list': 'ordered' }, { 'list': 'bullet' }],
            ['clean']
        ]
    }
});

// Carrega usuários e preenche selects
fetch('/api/users')
    .then(r => r.json())
    .then(usuarios => {
        usuariosCache = usuarios;
        const usuarioSelect = document.getElementById('usuario');
        usuarioSelect.innerHTML = "";
        document.getElementById('responsavel').innerHTML = '<option value="" selected>Selecione Responsável...</option>';
        if (!usuarios.length) {
            const opt = document.createElement('option');
            opt.value = "";
            opt.textContent = "Nenhum usuário encontrado";
            usuarioSelect.appendChild(opt);
        } else {
            usuarios.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.email;
                opt.textContent = `${u.nome} (${u.email})`;
                usuarioSelect.appendChild(opt);

                const optResp = document.createElement('option');
                optResp.value = u.email;
                optResp.textContent = `${u.nome} (${u.email})`;
                document.getElementById('responsavel').appendChild(optResp);
            });
            limparCamposFormulario();
            carregarVacation(usuarioSelect.value);
        }
        usuarioSelect.onchange = () => {
            limparCamposFormulario();
            carregarVacation(usuarioSelect.value);
            atualizarAssuntoNome();
        };
        atualizarAssuntoNome();
    });

// Carrega grupos do workspace e preenche select
fetch('/api/groups')
    .then(r => r.json())
    .then(grupos => {
        gruposCache = grupos;
        const grupoSelect = document.getElementById('grupo-responsavel');
        grupoSelect.innerHTML = '<option value="" selected>Selecione Grupo Responsável...</option>';
        grupos.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.email;
            opt.textContent = `${g.nome} (${g.email})`;
            grupoSelect.appendChild(opt);
        });
    });

function getResponsavelSelecionado() {
    const val = document.getElementById('responsavel').value;
    if (!val) return null;
    const u = usuariosCache.find(u => u.email === val);
    if (!u) return null;
    return { nome: u.nome, email: u.email, telefone: u.telefone || "" };
}

function getGrupoSelecionado() {
    const val = document.getElementById('grupo-responsavel').value;
    if (!val) return null;
    const g = gruposCache.find(g => g.email === val);
    if (!g) return null;
    let telefone = "";
    if (g.descricao) {
        const match = g.descricao.match(/(\(?\d{2}\)?\s?\d{4,5}-\d{4})/);
        if (match) telefone = match[1];
    }
    return { nome: g.nome, email: g.email, telefone: telefone };
}

function atualizarAssuntoNome() {
    const usuarioSelect = document.getElementById('usuario');
    const usuarioSel = usuarioSelect.options[usuarioSelect.selectedIndex];
    let nome = "Funcionário";
    if (usuarioSel && usuarioSel.textContent) {
        const idx1 = usuarioSel.textContent.indexOf('(');
        nome = idx1 > 0 ? usuarioSel.textContent.slice(0, idx1).trim() : usuarioSel.textContent.trim();
    }
    const assuntoSelect = document.getElementById('assunto');
    if (assuntoSelect.options.length > 2) {
        assuntoSelect.options[2].textContent = `${nome} não faz mais parte da empresa`;
    }
    return nome;
}

function mensagemSaidaDelta(nome, responsavelDetalhes, grupoDetalhes) {
    let responsavelTexto = '[Nome, e-mail e contato do novo responsável]';
    if(responsavelDetalhes) {
        responsavelTexto = responsavelDetalhes.nome;
        if(responsavelDetalhes.email) responsavelTexto += ' ('+responsavelDetalhes.email+')';
        if(responsavelDetalhes.telefone) responsavelTexto += ' - ' + responsavelDetalhes.telefone;
    } else if(grupoDetalhes) {
        responsavelTexto = grupoDetalhes.nome;
        if(grupoDetalhes.email) responsavelTexto += ' ('+grupoDetalhes.email+')';
        if(grupoDetalhes.telefone) responsavelTexto += ' - ' + grupoDetalhes.telefone;
    }

    return [
        { insert: 'Olá,\n\n' },
        { insert: 'Agradecemos seu contato. Informamos que ' },
        { insert: nome, attributes: { bold: true } },
        { insert: ' não faz mais parte da equipe da Teca Frio.\n\n' },
        { insert: 'Para continuar seu atendimento ou tratar de assuntos relacionados, por favor, entre em contato com ' },
        { insert: responsavelTexto, attributes: { bold: true } },
        { insert: '.\n\nContinuamos à disposição.\n\nAtenciosamente,\n' },
        { insert: 'Teca Frio', attributes: { bold: true } }
    ];
}

function mensagemFeriasDelta(nome, primeiroDia, ultimoDia, proximoUtil, responsavelDetalhes, grupoDetalhes) {
    let responsavelNome = '[Nome do substituto]';
    let responsavelEmail = '[email@exemplo.com]';
    let responsavelFone = '[telefone]';
    if(responsavelDetalhes) {
        responsavelNome = responsavelDetalhes.nome;
        responsavelEmail = responsavelDetalhes.email || responsavelEmail;
        responsavelFone = responsavelDetalhes.telefone || responsavelFone;
    } else if(grupoDetalhes) {
        responsavelNome = grupoDetalhes.nome;
        responsavelEmail = grupoDetalhes.email || responsavelEmail;
        responsavelFone = grupoDetalhes.telefone || responsavelFone;
    }
    return [
        { insert: 'Prezado(a),\n\n' },
        { insert: 'Agradecemos seu contato. Informamos que o(a) colaborador(a) ' },
        { insert: nome, attributes: { bold: true } },
        { insert: ' estará em período de férias entre ' },
        { insert: primeiroDia, attributes: { bold: true } },
        { insert: ' e ' },
        { insert: ultimoDia, attributes: { bold: true } },
        { insert: ', retornando às atividades em ' },
        { insert: proximoUtil, attributes: { bold: true } },
        { insert: '.\n\n' },
        { insert: 'Durante esse período, para assuntos urgentes ou que demandem atenção imediata, por gentileza, entre em contato com ' },
        { insert: responsavelNome, attributes: { bold: true } },
        { insert: ', pelo e-mail ' },
        { insert: responsavelEmail, attributes: { bold: true } },
        { insert: ' ou telefone ' },
        { insert: responsavelFone, attributes: { bold: true } },
        { insert: '.\n\n' },
        { insert: 'Agradecemos pela compreensão.\n\n' },
        { insert: 'Atenciosamente,\n' },
        { insert: 'Teca Frio', attributes: { bold: true } }
    ];
}

function limparCamposFormulario() {
    document.getElementById('primeiro-dia').value = hojeStr();
    document.getElementById('ultimo-dia').value = hojeStr();
    document.getElementById('assunto').selectedIndex = 0;
    document.getElementById('responsavel').selectedIndex = 0;
    document.getElementById('grupo-responsavel').selectedIndex = 0;
    quill.setText('');
    document.getElementById('so-contatos').checked = false;
    document.getElementById('so-teca').checked = false;
    atualizarCampoAlterarSenha();
}

function hojeDentroDoRange(startTime, endTime) {
    const hoje = new Date();
    const hojeUTC = Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
    return startTime && endTime && hojeUTC >= Number(startTime) && hojeUTC <= Number(endTime);
}

function carregarVacation(email) {
    if (!email) return;
    carregandoVacation = true;
    limparCamposFormulario();
    fetch('/api/vacation/' + encodeURIComponent(email))
        .then(r => r.json())
        .then(data => {
            const hoje = new Date();
            const hojeUTC = Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
            const ativado = !!(data.responseBodyPlainText && (data.enableAutoReply === undefined || data.enableAutoReply));
            const hojeNoRange = hojeDentroDoRange(data.startTime, data.endTime);
            vacationAtivado = ativado && hojeNoRange;

            const assuntoSelect = document.getElementById('assunto');
            if (vacationAtivado) {
                if (data.responseSubject) {
                    if (data.responseSubject === "Férias") {
                        assuntoSelect.selectedIndex = 1;
                    } else if (data.responseSubject.includes("não faz mais parte da empresa")) {
                        assuntoSelect.selectedIndex = 2;
                    } else {
                        assuntoSelect.selectedIndex = 0;
                    }
                } else {
                    assuntoSelect.selectedIndex = 0;
                }
                atualizarAssuntoNome();

                // Se vier como Quill Delta, tenta converter para texto
                try {
                    const parsed = JSON.parse(data.responseBodyPlainText);
                    if (Array.isArray(parsed)) {
                        quill.setContents(parsed);
                    } else {
                        quill.root.innerHTML = data.responseBodyPlainText || "";
                    }
                } catch(e) {
                    quill.root.innerHTML = data.responseBodyPlainText || "";
                }
                if (data.startTime) {
                    document.getElementById('primeiro-dia').value = new Date(Number(data.startTime)).toISOString().split('T')[0];
                }
                if (data.endTime) {
                    document.getElementById('ultimo-dia').value = new Date(Number(data.endTime)).toISOString().split('T')[0];
                }
                document.getElementById('so-contatos').checked = !!data.restrictToContacts;
                document.getElementById('so-teca').checked = !!data.restrictToDomain;
            } else {
                assuntoSelect.selectedIndex = 0;
                atualizarAssuntoNome();
            }
            document.getElementById('msg').textContent = "";
            carregandoVacation = false;
            atualizarCampoAlterarSenha();
        });
}

// Atualização das mensagens padrão conforme assunto
function preencherMensagemPadrao() {
    if (vacationAtivado) return;
    const assuntoSelect = document.getElementById('assunto');
    const assunto = assuntoSelect.value;
    const nome = atualizarAssuntoNome();
    const responsavelDetalhes = getResponsavelSelecionado();
    const grupoDetalhes = !responsavelDetalhes ? getGrupoSelecionado() : null;

    if (assunto === "ferias") {
        const primeiroDia = formatarDataBR(document.getElementById('primeiro-dia').value);
        const ultimoDia = formatarDataBR(document.getElementById('ultimo-dia').value);
        const proximoUtil = proximoDiaUtil(document.getElementById('ultimo-dia').value);
        quill.setContents(mensagemFeriasDelta(nome, primeiroDia, ultimoDia, proximoUtil, responsavelDetalhes, grupoDetalhes));
    } else if (assunto === "saida") {
        quill.setContents(mensagemSaidaDelta(nome, responsavelDetalhes, grupoDetalhes));
    } else {
        quill.setText('');
    }
}

function atualizarMensagemSePadrao() {
    const assuntoSelect = document.getElementById('assunto');
    if ((assuntoSelect.value === "ferias" || assuntoSelect.value === "saida") && !vacationAtivado) {
        preencherMensagemPadrao();
    }
}

// Campo de alteração de senha conforme o assunto selecionado
function atualizarCampoAlterarSenha() {
    const assunto = document.getElementById('assunto').value;
    const wrapper = document.getElementById('alterar-senha-wrapper');
    const checkbox = document.getElementById('alterar-senha');
    const label = document.getElementById('alterar-senha-label');
    if (assunto === "ferias") {
        wrapper.style.display = '';
        checkbox.checked = true;
        checkbox.disabled = false;
        label.textContent = "Alterar senha do usuário para padrão e solicitar uma nova no primeiro login";
    } else if (assunto === "saida") {
        wrapper.style.display = '';
        checkbox.checked = true;
        checkbox.disabled = true;
        label.textContent = "Alterar senha do usuário para padrão (sem solicitar alteração)";
    } else {
        wrapper.style.display = 'none';
    }
}

// Listeners para campos do formulário
document.getElementById('assunto').onchange = function() {
    atualizarCampoAlterarSenha();
    preencherMensagemPadrao();
};
document.getElementById('primeiro-dia').onchange = atualizarMensagemSePadrao;
document.getElementById('ultimo-dia').onchange = atualizarMensagemSePadrao;
document.getElementById('responsavel').onchange = function() {
    if (this.value) document.getElementById('grupo-responsavel').selectedIndex = 0;
    atualizarMensagemSePadrao();
};
document.getElementById('grupo-responsavel').onchange = function() {
    if (this.value) document.getElementById('responsavel').selectedIndex = 0;
    atualizarMensagemSePadrao();
};

function toUTCtimestamp(dateStr, isEnd) {
    if (!dateStr) return 0;
    const [ano, mes, dia] = dateStr.split('-').map(Number);
    if (isEnd) {
        return Date.UTC(ano, mes - 1, dia, 23, 59, 59);
    } else {
        return Date.UTC(ano, mes - 1, dia, 3, 0, 0);
    }
}

// Submissão do formulário
document.getElementById('vacationForm').onsubmit = function(e) {
    e.preventDefault();
    if (carregandoVacation) return;
    const email = document.getElementById('usuario').value;
    const assuntoSelect = document.getElementById('assunto');
    let assunto = assuntoSelect.options[assuntoSelect.selectedIndex].textContent;
    if (assuntoSelect.value === "") {
        document.getElementById('msg').textContent = "Selecione um assunto para continuar.";
        return;
    }
    const responsavelDetalhes = getResponsavelSelecionado();
    const grupoDetalhes = getGrupoSelecionado();
    if (!responsavelDetalhes && !grupoDetalhes) {
        document.getElementById('msg').textContent = "Selecione um Responsável ou Grupo Responsável.";
        return;
    }

    // ENVIA TEXTO SIMPLES (getText) para o backend!
    const mensagem = quill.getText().trim();

    const primeiroDia = document.getElementById('primeiro-dia').value;
    const ultimoDia = document.getElementById('ultimo-dia').value;
    const startTime = toUTCtimestamp(primeiroDia, false);
    const endTime = toUTCtimestamp(ultimoDia, true);
    const restrictToContacts = document.getElementById('so-contatos').checked;
    const restrictToDomain = document.getElementById('so-teca').checked;

    // Campo de senha
    const alterarSenhaWrapper = document.getElementById('alterar-senha-wrapper');
    let alterarSenha = false;
    let tipoAlteracaoSenha = "";
    if (alterarSenhaWrapper.style.display !== 'none') {
        alterarSenha = document.getElementById('alterar-senha').checked;
        tipoAlteracaoSenha = document.getElementById('assunto').value; // "ferias" ou "saida"
    }

    fetch('/api/vacation/' + encodeURIComponent(email), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            responseSubject: assunto,
            responseBodyPlainText: mensagem,
            startTime,
            endTime,
            restrictToContacts,
            restrictToDomain,
            alterarSenha: alterarSenha,
            tipoAlteracaoSenha: tipoAlteracaoSenha
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            document.getElementById('msg').textContent = "Alterações salvas com sucesso!";
        } else {
            document.getElementById('msg').textContent = data.error || "Erro ao salvar";
        }
    });
};

function limparFormulario() {
    if (!usuariosCache.length) return;
    document.getElementById('usuario').selectedIndex = 0;
    limparCamposFormulario();
    carregarVacation(document.getElementById('usuario').value);
    atualizarAssuntoNome();
    document.getElementById('msg').textContent = "";
}

document.getElementById('btn-limpar').onclick = limparFormulario;
