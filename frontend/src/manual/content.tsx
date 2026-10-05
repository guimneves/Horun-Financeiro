import type { ReactNode } from 'react'

/* Conteúdo do Manual (aba "Manual") — separado do layout (routes/ManualPage.tsx)
   para ser fácil de atualizar. Mudou uma tela? Atualize aqui no mesmo commit
   (Prompt_Horun_Modulo.md, seção 12). Nomes de botões em negrito, exatamente
   como aparecem na tela. Sem dados reais nos exemplos. */

export interface ManualSection {
  id: string
  title: string
  body: ReactNode
}

export const MANUAL_TITLE = 'Manual do Horun · Financeiro'

export const MANUAL_INTRO = (
  <p>
    Passo a passo para quem usa o módulo no dia a dia: alunos, técnicos e coordenadores de projeto. Use o índice
    abaixo ou digite uma palavra na busca para achar o assunto.
  </p>
)

const Steps = ({ children }: { children: ReactNode }) => <ol className="ml-5 list-decimal space-y-1">{children}</ol>
const Bullets = ({ children }: { children: ReactNode }) => <ul className="ml-5 list-disc space-y-1">{children}</ul>
const Tip = ({ children }: { children: ReactNode }) => (
  <p className="rounded-md px-3 py-2 text-sm" style={{ background: 'var(--color-surface)' }}>
    {children}
  </p>
)

export const MANUAL_SECTIONS: ManualSection[] = [
  {
    id: 'para-que-serve',
    title: 'Para que serve',
    body: (
      <>
        <p>
          O Financeiro controla o dinheiro dos projetos financiados do laboratório (por exemplo, projetos com a
          Petrobras pela COPPETEC): o <strong>orçamento</strong> aprovado, item por item; os{' '}
          <strong>processos de compra</strong>, da cotação até o recebimento; e a <strong>Equipe Executora</strong>{' '}
          (bolsas e pagamentos mensais).
        </p>
        <p>
          Ele faz as mesmas contas da planilha de acompanhamento do projeto: para cada item mostra o planejado, o
          comprometido (compras ainda não autorizadas), o realizado (compras autorizadas em diante) e o saldo. Cada
          projeto é independente — nada passa de um projeto para outro.
        </p>
      </>
    ),
  },
  {
    id: 'quem-pode',
    title: 'Quem pode fazer o quê',
    body: (
      <>
        <p>Para entrar num projeto, a pessoa precisa estar cadastrada nele (aba Membros). Há dois papéis:</p>
        <Bullets>
          <li>
            <strong>Colaborador</strong> — vê só a aba <strong>Compras</strong> do projeto. Abre processos de compra,
            anexa documentos, avança as etapas que não exigem decisão (cotação, pedido de autorização, nota fiscal,
            recebimento, conclusão) e pode cancelar um processo enquanto ele ainda não foi autorizado. Não vê valores
            em R$: no lugar do saldo aparece <strong>Há saldo disponível</strong> ou{' '}
            <strong>Sem saldo disponível</strong>.
          </li>
          <li>
            <strong>Coordenador</strong> — vê todas as abas (Resumo, Orçamento, Compras, Equipe, Revisões, Membros,
            Drive, Configurações) e todos os valores. Só ele <strong>autoriza</strong> ou <strong>rejeita</strong> uma
            compra, edita ou cancela um processo já autorizado, mexe no orçamento, na equipe, nos membros e nas
            configurações, e pode liberar uma etapa sem o documento exigido (com justificativa).
          </li>
          <li>
            <strong>Administrador do Horun</strong> — além do que o papel dele no projeto permite, é o único que cria um
            projeto novo (<strong>+ Novo projeto</strong>); quem cria entra como coordenador.
          </li>
          <li>
            <strong>Modo coordenador</strong> — quem conhece a senha de coordenador do módulo pode clicar em{' '}
            <strong>Entrar como coordenador</strong> e passar a agir como coordenador em todos os projetos em que já
            está cadastrado (veja "Modo coordenador e senha").
          </li>
        </Bullets>
      </>
    ),
  },
  {
    id: 'entrar',
    title: 'Como abrir um projeto',
    body: (
      <>
        <Steps>
          <li>
            Na barra lateral, em <strong>Projetos</strong>, clique no nome do projeto (ou no cartão dele na página
            inicial). No celular, toque em <strong>☰</strong> no alto da tela para abrir a barra lateral.
          </li>
          <li>
            Abaixo do nome do projeto aparecem as abas que o seu papel permite. O cabeçalho da página mostra o nº do
            processo COPPETEC do projeto e o seu papel (Coordenador ou Colaborador).
          </li>
        </Steps>
        <Tip>
          Não aparece nenhum projeto? Você ainda não foi cadastrado. Peça ao coordenador do projeto para incluir você
          na aba Membros — você só aparece na lista dele depois de abrir o Financeiro pelo menos uma vez.
        </Tip>
      </>
    ),
  },
  {
    id: 'nova-compra',
    title: 'Como abrir um processo de compra',
    body: (
      <>
        <Steps>
          <li>
            Abra o projeto e vá em <strong>Compras</strong>. Clique em <strong>+ Novo processo</strong>. (Na página de
            um item do Orçamento há o mesmo botão, já com o item escolhido.)
          </li>
          <li>
            Em <strong>Item de orçamento</strong>, escolha o item que vai pagar a compra.
          </li>
          <li>
            Preencha <strong>Título / descrição da compra</strong>, <strong>Quantidade</strong> e{' '}
            <strong>Valor unitário estimado</strong>.
          </li>
          <li>
            Se quiser, clique em <strong>Verificar disponibilidade</strong>: a resposta é só "há valor disponível" ou
            "não há" — o saldo em si não aparece para colaboradores.
          </li>
          <li>
            Clique em <strong>Criar processo</strong>. O processo começa na etapa{' '}
            <strong>Verificação de orçamento</strong> e o valor estimado já passa a contar como comprometido.
          </li>
        </Steps>
        <Tip>
          Se o valor não cabe no saldo do item, o que acontece depende da configuração do projeto: em "Bloquear" o
          processo não é criado (reduza o valor ou escolha outro item); em "Só avisar" ele é criado com um aviso e o
          saldo do item fica negativo.
        </Tip>
      </>
    ),
  },
  {
    id: 'etapas',
    title: 'Como avançar as etapas de uma compra',
    body: (
      <>
        <p>
          Na lista de <strong>Compras</strong>, clique no processo. À direita (no celular, logo acima dos documentos) fica o quadro{' '}
          <strong>Ações</strong> com os botões da etapa atual. Ao clicar num botão aparece um pequeno formulário:
          preencha o que for pedido e clique em <strong>Confirmar</strong> (ou <strong>Voltar</strong> para desistir).
        </p>
        <Steps>
          <li>
            <strong>Avançar para cotação</strong> — exige pelo menos uma <strong>Cotação</strong> anexada.
          </li>
          <li>
            <strong>Solicitar autorização à COPPETEC</strong> — também exige cotação. O processo fica{' '}
            <strong>Aguardando autorização</strong> e os coordenadores recebem um aviso.
          </li>
          <li>
            <strong>Autorizar compra</strong> (só coordenador) — exige o documento{' '}
            <strong>Solicitação enviada à COPPETEC</strong> e pede o <strong>Fornecedor vencedor</strong>. A partir
            daqui o valor conta como realizado. Ou <strong>Rejeitar</strong>, informando o motivo. Quem criou o processo
            recebe um aviso nos dois casos.
          </li>
          <li>
            <strong>Registrar nota fiscal</strong> — exige a <strong>Nota fiscal / recibo</strong> anexada e pede o
            valor final da compra.
          </li>
          <li>
            <strong>Confirmar recebimento</strong> — exige o <strong>Comprovante de recebimento</strong> anexado.
          </li>
          <li>
            <strong>Concluir processo</strong> — encerra a compra. Processo encerrado não aceita mais edição nem
            documentos novos.
          </li>
        </Steps>
        <p>
          Abaixo do processo fica o histórico: quem fez cada passo e quando, com motivos e justificativas.
        </p>
      </>
    ),
  },
  {
    id: 'documentos',
    title: 'Como anexar, ver e remover documentos',
    body: (
      <>
        <Bullets>
          <li>
            Na tela do processo, em <strong>Documentos</strong>, cada tipo (Cotação, Solicitação enviada à COPPETEC,
            Nota fiscal / recibo, Comprovante de recebimento, Outro) tem o link <strong>+ Anexar arquivo</strong>.
            Toque nele e escolha o arquivo (no celular dá para usar a câmera ou os arquivos do aparelho).
          </li>
          <li>São no máximo 3 cotações por processo.</li>
          <li>
            Clique no nome de um PDF ou imagem para ler sem baixar; use <strong>baixar</strong> para salvar uma cópia.
          </li>
          <li>
            Arquivo no tipo errado? Troque o tipo na listinha ao lado dele — fica registrado no histórico.
          </li>
          <li>
            <strong>remover</strong> apaga um arquivo enviado (só quem enviou ou o coordenador).{' '}
            <strong>desvincular</strong> aparece nos arquivos marcados "drive": só tira o vínculo, o arquivo continua
            no drive.
          </li>
          <li>Em processo concluído, cancelado ou rejeitado os documentos ficam guardados e não podem ser removidos.</li>
        </Bullets>
      </>
    ),
  },
  {
    id: 'cancelar',
    title: 'Como cancelar uma compra (ou o que fazer se foi rejeitada)',
    body: (
      <>
        <Steps>
          <li>
            Na tela do processo, clique em <strong>Cancelar processo</strong>, escreva o motivo e clique em{' '}
            <strong>Confirmar</strong>.
          </li>
          <li>
            Antes da autorização, qualquer membro pode cancelar. Depois de autorizado, só o coordenador.
          </li>
        </Steps>
        <p>
          Processo cancelado ou rejeitado não é reaberto. Se ainda for preciso comprar, abra um novo processo em{' '}
          <strong>+ Novo processo</strong>. Para ver os encerrados na lista, marque{' '}
          <strong>Mostrar concluídos/cancelados/rejeitados</strong>.
        </p>
      </>
    ),
  },
  {
    id: 'nota-acima',
    title: 'Nota fiscal acima do saldo do item',
    body: (
      <>
        <p>
          Se o valor final da nota passa do saldo do item, aparece o aviso <strong>Nota fiscal acima do saldo do
          item</strong>. Escolha <strong>Corrigir valor</strong> (se digitou errado) ou{' '}
          <strong>Registrar mesmo assim</strong> (a nota é um fato e precisa ser registrada).
        </p>
        <p>
          Registrada assim, o processo ganha o sinal <strong>Acima do saldo</strong> na lista, com quem confirmou e
          quando, e os coordenadores recebem um aviso para decidir o que fazer com o item.
        </p>
      </>
    ),
  },
  {
    id: 'sem-documento',
    title: 'Coordenador: avançar sem o documento exigido',
    body: (
      <p>
        Quando falta o documento que uma etapa exige, o coordenador vê no formulário da ação o campo{' '}
        <strong>Faltou o documento? Justifique para avançar mesmo assim (opcional)</strong>. Escrevendo a justificativa
        e clicando em <strong>Confirmar</strong>, a etapa avança e a justificativa fica no histórico do processo.
      </p>
    ),
  },
  {
    id: 'resumo',
    title: 'Como ler o Resumo (coordenador)',
    body: (
      <Bullets>
        <li>
          <strong>Indicadores</strong> no topo: orçamento + rendimentos, realizado, comprometido e quanto do prazo do
          projeto já passou (com a comparação "acima/abaixo do ritmo do prazo").
        </li>
        <li>
          <strong>Uso do orçamento por categoria</strong>: cada barra é uma categoria — realizado, comprometido, saldo
          e estouro, em % do previsto.
        </li>
        <li>
          <strong>Ritmo de execução</strong>: o realizado acumulado mês a mês comparado com o ritmo linear do prazo e
          com as parcelas previstas. Compras importadas do drive entram no mês estimado pelo nº de processo.
        </li>
        <li>
          <strong>Quadro resumo</strong>: a mesma tabela da planilha, por categoria, com subtotais. Clique numa
          categoria para abrir os itens dela no Orçamento.
        </li>
        <li>
          <strong>Parcelas recebidas × usadas</strong> e <strong>Precisa de atenção</strong> (itens estourados, perto
          do fim, compras paradas) — clique num alerta para ir direto ao item ou processo.
        </li>
      </Bullets>
    ),
  },
  {
    id: 'orcamento',
    title: 'Como consultar o Orçamento (coordenador)',
    body: (
      <>
        <Bullets>
          <li>
            A aba <strong>Orçamento</strong> mostra primeiro as categorias, com os totais, quantos itens estão com
            saldo negativo e a % usada. Clique numa categoria para ver os itens; <strong>Expandir todas</strong> abre
            todas de uma vez. No celular cada categoria e cada item aparecem como um cartão.
          </li>
          <li>
            Clique num item para ver os números dele e o <strong>Histórico de compras deste item</strong>.
          </li>
          <li>
            "verba" na quantidade disponível: item de quantidade 1 gasto em várias compras — vale o saldo em R$.
          </li>
        </Bullets>
        <p>
          Para mudar o orçamento: <strong>+ Criar itens de orçamento</strong> (projeto novo) ou{' '}
          <strong>+ Editar itens (nova reformulação)</strong>. Isso cria um rascunho: use <strong>+ item</strong> em
          cada categoria, preencha e clique em <strong>salvar</strong>; quando terminar, clique em{' '}
          <strong>Ativar orçamento</strong>. Até lá, os saldos continuam pela versão anterior.
        </p>
      </>
    ),
  },
  {
    id: 'revisoes',
    title: 'Revisões do orçamento (coordenador)',
    body: (
      <Bullets>
        <li>
          <strong>Importar da planilha</strong>: escolha a planilha de acompanhamento (.xlsx), clique em{' '}
          <strong>Pré-visualizar</strong>, confira os totais e clique em <strong>Importar … itens como rascunho</strong>.
        </li>
        <li>
          <strong>+ Nova reformulação</strong>: dê um rótulo e a data de vigência e clique em{' '}
          <strong>Criar rascunho</strong> — os itens da revisão ativa são copiados como ponto de partida.
        </li>
        <li>
          Depois de conferir os itens do rascunho, clique em <strong>Ativar revisão</strong>. A revisão anterior fica
          guardada como "Substituída".
        </li>
      </Bullets>
    ),
  },
  {
    id: 'equipe',
    title: 'Equipe Executora (coordenador)',
    body: (
      <Bullets>
        <li>
          <strong>+ Nova atribuição</strong>: escolha o item de Equipe Executora, a pessoa (ou{' '}
          <strong>+ Nova pessoa…</strong>), o cargo, o valor mensal e o início; clique em{' '}
          <strong>Criar atribuição</strong>.
        </li>
        <li>
          <strong>Importar da planilha</strong>: lê a aba de Equipe Executora, mostra o que seria criado (
          <strong>Pré-visualizar</strong>) e só grava ao clicar em <strong>Importar … atribuição(ões)</strong>.
        </li>
        <li>
          <strong>Recibos (n)</strong>: anexa um recibo mensal à atribuição.
        </li>
        <li>
          <strong>Encerrar</strong>: informe a data de fim e clique em <strong>ok</strong>. Os meses contam pela regra
          da planilha (mês de calendário, mês final incluído).
        </li>
      </Bullets>
    ),
  },
  {
    id: 'membros',
    title: 'Membros do projeto (coordenador)',
    body: (
      <Steps>
        <li>
          Em <strong>Membros</strong>, escolha a <strong>Pessoa</strong>. Só aparece quem já abriu o Financeiro pelo
          menos uma vez; se a pessoa não estiver lá, peça para ela abrir o módulo e recarregue a página.
        </li>
        <li>
          Escolha o <strong>Papel</strong> (Colaborador ou Coordenador) e clique em <strong>+ Adicionar</strong>.
        </li>
        <li>
          Para tirar alguém do projeto, clique em <strong>remover</strong> na linha dela.
        </li>
      </Steps>
    ),
  },
  {
    id: 'drive',
    title: 'Drive do projeto (coordenador)',
    body: (
      <>
        <p>
          O módulo <strong>só lê</strong> a pasta do projeto no drive — nunca grava, move ou apaga arquivos lá.
        </p>
        <Steps>
          <li>
            Em <strong>Drive</strong>, clique em <strong>Ler pastas</strong>. O programa mostra o que encontrou e o que
            criaria, sem gravar nada. Feche a planilha de acompanhamento no Excel antes.
          </li>
          <li>
            Confira a lista e clique em <strong>Sincronizar (… processos, … arquivos)</strong> para criar os processos e
            vincular os arquivos.
          </li>
          <li>Depois, confira o estado de cada processo criado (ele é deduzido pelos arquivos da pasta).</li>
        </Steps>
        <p>Mais abaixo, a navegação pelas pastas permite abrir qualquer arquivo para ler ou baixar.</p>
      </>
    ),
  },
  {
    id: 'configuracoes',
    title: 'Configurações do projeto (coordenador)',
    body: (
      <Bullets>
        <li>
          <strong>Vigência do projeto</strong>: início e fim, usados no Resumo. Clique em <strong>Salvar</strong>.
        </li>
        <li>
          <strong>Pasta do projeto no drive</strong>: o caminho da pasta a partir da raiz do drive do servidor.
        </li>
        <li>
          <strong>Quando um valor não cabe no saldo do item</strong>: <strong>Bloquear</strong> ou{' '}
          <strong>Só avisar</strong> (vale na hora, ao marcar).
        </li>
        <li>
          <strong>Parcelas de repasse</strong>: <strong>+ Adicionar parcela</strong>, valor e data prevista, e{' '}
          <strong>Salvar parcelas</strong>.
        </li>
      </Bullets>
    ),
  },
  {
    id: 'modo-coordenador',
    title: 'Modo coordenador e senha',
    body: (
      <>
        <Steps>
          <li>
            No alto da tela, clique em <strong>🔒 Entrar como coordenador</strong> (no celular o botão mostra só{' '}
            <strong>Coordenador</strong>), digite a senha de coordenador do módulo e clique em{' '}
            <strong>Entrar</strong>.
          </li>
          <li>
            Aparece <strong>🔓 Modo coordenador</strong>: você age como coordenador em todos os projetos em que já
            está cadastrado. Clique em <strong>Sair</strong> para voltar ao seu papel normal.
          </li>
          <li>
            Em modo coordenador aparece também <strong>Organização</strong>, onde se troca a senha (
            <strong>Senha atual</strong>, <strong>Nova senha</strong>, <strong>Confirmar nova senha</strong> e{' '}
            <strong>Trocar senha</strong>). A senha é uma só para o módulo inteiro.
          </li>
        </Steps>
      </>
    ),
  },
  {
    id: 'celular',
    title: 'Usando no celular',
    body: (
      <Bullets>
        <li>
          Toque em <strong>☰</strong> (alto, à esquerda) para abrir a barra lateral com os projetos e as abas. Ela
          fecha ao escolher uma aba, ao tocar fora dela ou no <strong>✕</strong>.
        </li>
        <li>
          Compras, Orçamento e Equipe aparecem como cartões. Tabelas largas (Drive, Revisões, Quadro resumo) deslizam
          para o lado com o dedo.
        </li>
        <li>Para anexar a foto de um documento, use <strong>+ Anexar arquivo</strong> e escolha a câmera.</li>
      </Bullets>
    ),
  },
  {
    id: 'avisos',
    title: 'Avisos por e-mail',
    body: (
      <>
        <p>
          O Financeiro avisa pelo sininho do Horun e por e-mail (para quem tem e-mail cadastrado no Horun) quando
          alguém precisa agir ou está esperando uma resposta:
        </p>
        <Bullets>
          <li>
            <strong>Compra aguardando autorização</strong> — para os coordenadores do projeto, quando alguém clica em{' '}
            <strong>Solicitar autorização à COPPETEC</strong>.
          </li>
          <li>
            <strong>Compra autorizada</strong> ou <strong>Compra rejeitada</strong> — para quem criou o processo (com o
            motivo, se rejeitada).
          </li>
          <li>
            <strong>Nota fiscal acima do saldo do item</strong> — para os coordenadores, quando alguém registra a nota
            mesmo assim.
          </li>
        </Bullets>
        <p>
          Ninguém recebe aviso da própria ação. Os avisos não trazem valores em R$ — o link abre o processo no
          Horun. Para não receber e-mails, desligue em "Meu perfil" no Horun (o sininho continua).
        </p>
      </>
    ),
  },
  {
    id: 'faq',
    title: 'Dúvidas frequentes',
    body: (
      <dl className="space-y-3">
        <div>
          <dt className="font-semibold">Por que não vejo os valores em R$?</dt>
          <dd>
            Colaboradores não veem valores — só se há saldo ou não. Se você precisa ver, peça ao coordenador para
            mudar o seu papel.
          </dd>
        </div>
        <div>
          <dt className="font-semibold">O botão de avançar dá erro dizendo para anexar um documento.</dt>
          <dd>
            Cada etapa exige um documento (veja "Como avançar as etapas"). Anexe o arquivo no tipo certo e tente de
            novo. Só o coordenador pode avançar sem ele, com justificativa.
          </dd>
        </div>
        <div>
          <dt className="font-semibold">Não consigo criar o processo: "saldo insuficiente".</dt>
          <dd>
            O projeto está configurado para bloquear valores acima do saldo do item. Reduza o valor, escolha outro item
            ou fale com o coordenador.
          </dd>
        </div>
        <div>
          <dt className="font-semibold">Errei o título, a quantidade ou o valor estimado de um processo.</dt>
          <dd>
            A tela ainda não tem um botão para editar o processo. Antes da autorização, cancele (
            <strong>Cancelar processo</strong>, explicando o motivo) e abra outro com os dados certos. Depois da
            autorização, fale com o coordenador.
          </dd>
        </div>
        <div>
          <dt className="font-semibold">Cancelei sem querer.</dt>
          <dd>Processo cancelado não volta. Abra um novo processo com os mesmos dados; o cancelado fica no histórico.</dd>
        </div>
        <div>
          <dt className="font-semibold">Os números são diferentes dos da planilha.</dt>
          <dd>
            A Equipe Executora é contada até hoje (a planilha pode estar parada num mês). Fora isso, os números devem
            bater; se não baterem, avise o responsável.
          </dd>
        </div>
      </dl>
    ),
  },
  {
    id: 'contato',
    title: 'Quem procurar',
    body: (
      <p>
        Dúvidas sobre um projeto (acesso, papel, valores, orçamento): o <strong>coordenador do projeto</strong>.
        Problemas no programa, senha de coordenador ou sugestões: <strong>o responsável pelo módulo no
        laboratório</strong>.
      </p>
    ),
  },
]
