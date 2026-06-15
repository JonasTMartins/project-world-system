# =========================================================
# SISTEMA
# =========================================================
# Sessões da Categoria "Sistema" aqui.

# Imports =====================================================================================================================================
""" Documentação dos IMPORTS

    Responsabilidade:
        Importar módulos e bibliotecas necessários para o funcionamento
        do servidor.

    Esta seção deve conter apenas:
        - bibliotecas padrão do Python
        - bibliotecas externas utilizadas pelo projeto
        - dependências compartilhadas entre múltiplas seções

    Evitar:
        - lógica de negócio
        - inicializações complexas
        - código executável

    Observação:
        Sempre que possível, manter os imports organizados por categoria:

            1. Bibliotecas padrão
            2. Bibliotecas externas
            3. Módulos internos do projeto

    Expansões Futuras:
        - separação em múltiplos módulos
        - organização por pacotes
"""

import hashlib
import fastapi
import fastapi.responses
import pydantic
import fastapi.middleware.cors
import uuid
import time
# Fim de Imports


# Conexões permitidas =========================================================================================================================
""" Documentação das CONEXÕES PERMITIDAS

    Responsabilidade:
        Configurar o servidor FastAPI e definir quais origens podem
        se comunicar com a API.

    Controla:
        - CORS
        - métodos HTTP permitidos
        - cabeçalhos aceitos
        - credenciais

    Importante:
        Esta seção define apenas regras de comunicação.
        Não possui relação com autenticação de usuários.

    Expansões Futuras:
        - restrição de domínios específicos
        - ambientes separados (desenvolvimento/produção)
        - HTTPS obrigatório
        - políticas avançadas de segurança
"""

app = fastapi.FastAPI()
app.add_middleware(
    fastapi.middleware.cors.CORSMiddleware,
    allow_origins=["*"],  # permite qualquer origem (ok para desenvolvimento)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Fim de Conexões permitidas


# Configuração de Sessão ======================================================================================================================
""" Documentação das CONFIGURAÇÃO DE SESSÃO

    Responsabilidade:
        Definir parâmetros globais relacionados ao gerenciamento
        de sessões.

    Controla:
        - tempo de expiração
        - frequência de limpeza
        - políticas de atividade

    Objetivo:
        Evitar acúmulo de sessões abandonadas.

    Importante:
        Alterações nesta seção afetam todas as conexões do sistema.

    Expansões Futuras:
        - configuração por ambiente
        - reconexão automática
        - múltiplas sessões por conta
        - persistência de sessões
"""

SESSION_TIMEOUT = 15  # 15 segundos (em segundos)
#SESSION_TIMEOUT = 900  # 15 minutos (em segundos)
SESSION_CLEANUP_INTERVAL = 300  # tempo mínimo entre limpezas (segundos)
last_cleanup = 0
# Fim de Configuração de Sessão


# Sessões (controle de conexões) ==============================================================================================================
""" Documentação das SESSÕES DO SISTEMA

    Responsabilidade:
    Controlar conexões ativas entre clientes e servidor.

    Armazena:
        session_id
        estado atual da sessão
        player associado
        dados temporários de autenticação
        controle de atividade

    Não deve armazenar:
        atributos permanentes do personagem
        informações do mundo
        NPCs
        inventários

    Dependências:
        connect()
        get_session()
        processar_entrada_sessao()
        handle_command()

    Expansões Futuras:
        persistência em banco de dados
        reconexão automática
        autenticação avançada

"""

sessions = {}

def get_session(session_id):
    return sessions.get(session_id)


def limpar_sessoes():
    agora = time.time()

    # usamos list() para evitar erro ao remover itens durante iteração
    for sid in list(sessions.keys()):
        if agora - sessions[sid]["last_active"] > SESSION_TIMEOUT:
            del sessions[sid]

def processar_entrada_sessao(session, texto):
    estado = session["estado"]

    # ===== ESTADO: ESPERANDO NOME =====
    if estado == "esperando_nome":
        nome = texto

        valido, motivo = validar_nome(nome)
        
        if not valido:
            return motivo or "Nome inválido. Tente novamente."

        session["nome_temp"] = nome

        if nome in players:
            session["estado"] = "esperando_senha"
            return {
                "response": "Personagem existe. Digite a senha:",
                "mode": "senha"
            }
        else:
            session["estado"] = "criando_senha"
            return {
                "response": "Novo personagem. Crie uma senha:",
                "mode": "senha"
            }

    # ===== ESTADO: CRIANDO SENHA =====
    elif estado == "criando_senha":
        senha = texto

        valido, motivo = validar_senha(senha)
        
        if not valido:
            return motivo or "Senha inválida."

        nome = session["nome_temp"]

        session["senha_temp"] = senha
        session["estado"] = "confirmando_senha"
        return {
            "response": "Confirme sua senha:",
            "mode": "confirmacao"
        }

    # ===== ESTADO: CONFIRMANDO SENHA =====
    elif estado == "confirmando_senha":
        senha_confirmada = texto
      
        if senha_confirmada != session["senha_temp"]:
            session["senha_temp"] = None
            session["estado"] = "criando_senha"
            return {
                "response": "Senhas não coincidem. Crie novamente a senha:",
                "mode": "senha"
            }

        nome = session["nome_temp"]
        
        criar_personagem(nome, hash_senha(session["senha_temp"]))
        
        session["senha_temp"] = None
        session["player_id"] = nome
        session["estado"] = "logado"
      
        return {
            "response": f"Personagem '{nome}' criado com sucesso. Você entrou no mundo.",
            "mode": "normal"
        }
      
    # ===== ESTADO: ESPERANDO SENHA =====
    elif estado == "esperando_senha":
        senha = texto
        nome = session["nome_temp"]

        if not autenticar_personagem(nome, senha):
            return {
                "response": "Senha incorreta.",
                "mode": "senha"
            }

        session["player_id"] = nome
        session["estado"] = "logado"

        return {
            "response": f"Bem-vindo de volta, {nome}.",
            "mode": "normal"
        }

    return "Erro de sessão."
# Fim de Sessões


# Modelos de Dados: (entrada/saída da API) ====================================================================================================
""" Documentação dos MODELOS DE DADOS (ENTRADA/SAÍDA DA API)

    Responsabilidade:
        Definir a estrutura dos dados trocados entre frontend e backend.

    Objetivo:
        Garantir validação e consistência dos dados recebidos.

    Exemplos:
        - comandos enviados pelo jogador
        - respostas estruturadas
        - eventos futuros

    Importante:
        Modelos não executam regras de negócio.

    Sua função é apenas:
            validar
            organizar
            transportar dados

    Expansões Futuras:
        - respostas padronizadas
        - eventos em lote
        - mensagens do sistema
        - comunicação em tempo real
"""

class Command(pydantic.BaseModel):
    session_id: str
    command: str
# Fim de Modelos de Dados: (entrada/saída da API):


# Endpoints do Sistema ========================================================================================================================
""" Documentação dos ENDPOINTS DO SISTEMA

    Responsabilidade:
        Expor funcionalidades do servidor através da API.

    Funções Atuais:
        - conexão inicial
        - entrega do frontend

    Princípio:
        Endpoints recebem requisições e delegam trabalho para outras
        camadas do sistema.

    Evitar:
        - regras complexas diretamente nos endpoints
        - lógica de jogo extensa
        - processamento excessivo

    Objetivo:
        Manter os endpoints simples e previsíveis.

    Expansões Futuras:
        - autenticação
        - persistência
        - administração
        - monitoramento
        - APIs auxiliares
"""

@app.get("/connect")                                                                # Endpoint de conexão
def connect():                                                                      #Função executada quando um cliente se conecta ao servidor.
  
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "estado": "esperando_nome",
        "player_id": None,
        "senha_temp": None,
        "last_active": time.time()
    }

    return {
        "session_id": session_id,
        "message": "Seja bem-vindo ao MUD\nNome do personagem:"
    }

@app.get("/")
def serve_frontend():
    return fastapi.responses.FileResponse("../frontend/index.html")
# Fim de Endpoints do Sistema
# Fim da Categoria SISTEMA









  
# =========================================================
# MOTOR
# =========================================================
# Sessões da Categoria "Motor" aqui.

# Estado do Sistema (memória do jogo) =========================================================================================================
""" Documentação do ESTADO DO SISTEMA

    Responsabilidade:
        Armazenar informações persistentes do mundo carregadas na memória
        do servidor.

    Atualmente:
        - personagens
        - Entidades

    Futuramente:
        - salas
        - itens
        - NPCs
        - estruturas do mundo
        - economia
        - eventos globais

    Importante:
        Esta seção representa o estado do mundo.

    Não deve armazenar:
        - sessões
        - conexões
        - estados temporários de login

    Essas responsabilidades pertencem ao sistema de sessões.

    Observação:
        Atualmente os dados existem apenas em memória.
        Reiniciar o servidor apaga todas as informações.
"""

players = {}
entities = {}

def get_player(player_id):
    return players.get(player_id)

def criar_personagem(nome, senha_hash):
    player = {
        "energia": 100,
        "fome": 0,
        "temperatura": 50,
        "medo": 0,
        "vivo": True,
        "consciente": True,
        "senha": senha_hash
    }
    players[nome] = player

    return player

def autenticar_personagem(nome, senha):
    player = players.get(nome)
    if not player:
        return False
      
    return player["senha"] == hash_senha(senha)  
# Fim de Estado do Sistema (memória do jogo)   

# Modelos do Motor ============================================================================================================================
""" Documentação dos MODELOS DO MOTOR

    Responsabilidade:
        Definir as estruturas-base utilizadas pelos sistemas internos
        do motor do jogo.

    Atualmente:
        - ENTITY_TEMPLATE

    Futuramente:
        - ROOM_TEMPLATE
        - ITEM_TEMPLATE
        - NPC_TEMPLATE
        - QUEST_TEMPLATE
        - EVENT_TEMPLATE

    Importante:
        Esta seção define o formato esperado das estruturas
        utilizadas pelo motor.

    Não deve conter:
        - lógica de jogo
        - regras de negócio
        - processamento de comandos
        - estados dinâmicos do mundo

    Essas responsabilidades pertencem aos sistemas que utilizam
    os modelos.

    Princípio:
        Os modelos funcionam como contratos estruturais.

        Eles definem quais informações uma determinada estrutura
        deve possuir, permitindo que todos os sistemas trabalhem
        sobre um formato previsível e padronizado.

    Objetivo:
        Garantir consistência entre entidades, salas, itens,
        NPCs e demais componentes do mundo.

    Observação:
        Alterações nos modelos podem impactar múltiplos sistemas,
        devendo ser realizadas com cautela.
"""

ENTITY_TEMPLATE = {
    "id": "",
    "nome": "",
    "aliases": [],
    "tags": []
}
# Fim de Modelos do Motor

# Sistema de Entidades ========================================================================================================================
""" Documentação do SISTEMA DE ENTIDADES

    Responsabilidade:
        Gerenciar todas as entidades existentes no mundo.

    Atualmente:
        - criação de entidades
        - registro global de entidades

    Futuramente:
        - busca de entidades
        - localização por contexto
        - estados das entidades
        - capacidades (tags)
        - interações
        - inventários
        - NPCs
        - objetos do mundo

    Importante:
        Toda entidade do jogo deve ser criada através das funções
        deste sistema.

        Evitar criar entidades manualmente em outras partes do código.

    Princípio:
        O sistema de entidades funciona como a base do mundo.

        Tudo que pode existir no jogo tende a ser representado
        como uma entidade:

            - jogadores
            - NPCs
            - objetos
            - estruturas
            - elementos do ambiente

    Objetivo:
        Centralizar a criação e o gerenciamento das entidades,
        mantendo uma estrutura consistente para todo o sistema.

    Observação:
        O código desta seção é carregado durante a inicialização
        da aplicação.

        Deve-se evitar executar operações críticas ou irreversíveis
        diretamente durante o carregamento do módulo.

        Em ambientes com reload automático, o módulo pode ser
        carregado mais de uma vez.

        Funcionalidades sensíveis devem ser executadas através
        de rotinas de inicialização controladas.
"""

def create_entity(nome, aliases=None, tags=None):
    if aliases is None:
        aliases = []
    if tags is None:
        tags = []
      
    entity_id = f"{nome}_{len(entities) + 1}"
    entity = {
        "id": entity_id,
        "nome": nome,
        "aliases": aliases,
        "tags": tags
    }

    entities[entity_id] = entity
    return entity

def find_entity(nome):
    nome = nome.lower()
    for entidade in entities.values():
        aliases = entidade["aliases"]
        if nome in aliases:
            return entidade
    return None

def listar_entidades():
    for entidade in entities.values():
        print(entidade["id"], "-", entidade["nome"])
# Fim de Sistema de Entidades

# Entidades Iniciais do Mundo =================================================================================================================
""" Documentação das ENTIDADES INICIAIS DO MUNDO

    Responsabilidade:
        Registrar entidades básicas utilizadas para testes e
        validação do sistema de entidades.

    Atualmente:
        - pedra
        - tronco
        - árvore
        - placa

    Objetivo:
        Validar o funcionamento do registro global de entidades
        e das rotinas de criação.

    Importante:
        Esta seção existe principalmente para desenvolvimento
        e testes do motor.

        As entidades aqui cadastradas representam exemplos
        mínimos de objetos do mundo.

    Futuramente:
        As entidades iniciais poderão ser substituídas por:

            - carregamento de salas
            - carregamento de mapas
            - carregamento de NPCs
            - carregamento de objetos persistentes

    Observação:
        O conteúdo desta seção é executado durante o carregamento
        da aplicação.

        Em ambientes utilizando reload automático, as rotinas aqui
        presentes podem ser executadas mais de uma vez durante a
        inicialização.

        Atualmente isso não representa problema, pois as entidades
        são recriadas em memória a cada carregamento.

        Conforme o sistema evoluir, recomenda-se migrar esta
        responsabilidade para rotinas dedicadas de carregamento
        do mundo.
"""

create_entity(
    nome="pedra",
    aliases=["pedra"],
    tags=[]
)
create_entity(
    nome="tronco",
    aliases=["tronco"],
    tags=[]
)
create_entity(
    nome="árvore",
    aliases=["árvore", "arvore"],
    tags=[]
)
create_entity(
    nome="placa",
    aliases=["placa"],
    tags=[]
)
listar_entidades()
# Fim de Entidades Iniciais do Mundo

# Mecânicas do Jogo (lógica interna) ==========================================================================================================
""" Documentação das REGRAS DO JOGO (LÓGICA INTERNA)

    Responsabilidade:
        Implementar regras fundamentais que governam o funcionamento
        do mundo.

    Exemplos:
        - atualização de atributos
        - validações
        - cálculos
        - mecânicas centrais

    Importante:
        Esta seção não deve conter:
            - comunicação HTTP
            - lógica de interface
            - código de frontend

    Princípio:
        O mundo deve funcionar independentemente da forma como é exibido.

    Expansões Futuras:
        - combate
        - crafting
        - sobrevivência
        - progressão
        - economia
        - sistemas sociais
"""

def update_player(player):
    player["fome"] += 1
    player["energia"] -= 1

    if player["energia"] <= 0:
        player["consciente"] = False

    if player["fome"] >= 100:
        player["vivo"] = False

def describe(player):
    return (
        f"Energia: {player['energia']} | "
        f"Fome: {player['fome']} | "
        f"Temperatura: {player['temperatura']} | "
        f"Medo: {player['medo']}"
    )

def validar_nome(nome):
    return True, None


def validar_senha(senha):
    return True, None


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()
# Fim de Mecânicas do Jogo (lógica interna)


# Interpretador de Comandos ===================================================================================================================
""" Documentação do SISTEMA DE COMANDOS

    ```
    Responsabilidade:
        Interpretar entradas textuais do jogador e convertê-las em ações.

    Arquitetura Atual:

        Texto
            ↓
        Parser
            ↓
        Verbo + Argumentos
            ↓
        Dispatcher
            ↓
        Handler
            ↓
        Resultado

    Exemplo de Comando: SENTAR CADEIRA

        Será interpretado como:
            verbo = "sentar"
            args = ["cadeira"]
        
        Fluxo Atual:
            interpretar_comando()
                ↓
            executa parser
                ↓
            retorna estrutura padronizada
                ↓
            executar_comando()
                ↓
            localiza handler no registry
                ↓
            executa comando
                ↓
            retorna resposta
        
        Estrutura Retornada pelo Parser:
            {
                "tipo": "comando",
                "verbo": "sentar",
                "args": ["cadeira"]
            }
        
        Registry de Comandos:
        
            commands = {
                "status": cmd_status,
                "descansar": cmd_descansar
            }

    Dispatcher:

        O executor não possui conhecimento da lógica dos comandos.

        Sua única responsabilidade é:

            1. localizar o handler
            2. validar existência
            3. executar o handler

    Assinatura Padrão dos Comandos:

        def cmd_exemplo(player, args, session=None):

    Onde:

        player
            Estado atual do personagem.

        args
            Lista de argumentos fornecidos pelo jogador.

        session
            Dados da sessão atual.
            Opcional para comandos que não utilizam sessão.

    Como Criar um Novo Comando:

        PASSO 1 — Criar o handler

            def cmd_sentar(player, args, session=None):
                return "Você se senta."

        PASSO 2 — Registrar o comando

            commands["sentar"] = cmd_sentar

        PASSO 3 — Pronto

            O sistema reconhecerá automaticamente:

                SENTAR

            sem necessidade de alterar:

                interpretar_comando()
                executar_comando()
                handle_command()

    Objetivo:

        Permitir crescimento do sistema para centenas ou milhares
        de comandos sem aumentar a complexidade do núcleo.

    Próximas Etapas:

        [x] Parser de verbo + argumentos
        [x] Registry de comandos
        [x] Dispatcher dinâmico
        [ ] Aliases
        [ ] Entidades
        [ ] Capacidades (tags)
        [ ] Contexto de mundo
        [ ] Resolução semântica de alvos
        [ ] Sistema de permissões
        [ ] Comandos compostos

    Princípios:

        Comandos devem ser desacoplados.

        Cada verbo possui seu próprio handler.

        O núcleo não conhece a lógica interna dos verbos.

        O dispatcher apenas localiza e executa handlers.

        Novos comandos não devem exigir alterações
        no núcleo do sistema.

        Objetos definirão capacidades através de tags
        e não através de condicionais espalhadas pelo código.
    ```
"""


def interpretar_comando(texto):
    texto = texto.strip()

    if texto and texto == texto.upper():
        texto = texto.lower()
        partes = texto.split()
        verbo = partes[0]
        args = partes[1:]
      
        return {
            "tipo": "comando",
            "verbo": verbo,
            "args": args
        }
    else:
        return {
            "tipo": "fala",
            "texto": texto
        }
    
def executar_comando(player, verbo, args, session):

    funcao = commands.get(verbo)
    update_player(player)

    if funcao is None:
        return "Você não sabe como fazer isso."
    
    return funcao(player, args, session)

## Definição de Comandos
def cmd_status(player, args, session=None):
    return describe(player)

def cmd_descansar(player, args, session=None):
    player["energia"] += 10
    player["fome"] += 2
    return "Você descansa por um tempo."

def cmd_olhar(player, args, session=None):
    if not args:
        return "Olhar o que?"
    nome = args[0]
    entidade = find_entity(nome)
    if not entidade:
        return "Você olha em volta e não vê isso por perto."
    return f"Você olha para {entidade['nome']}."

#def cmd_Nome do Comando(player, args):

# Registro de Comandos:
commands = {
    "status": cmd_status,
    "descansar": cmd_descansar,
    "olhar": cmd_olhar
    #"Nome do Comando": cmd_Nome do Comando
}
## Fim de Definição de Comandos

@app.post("/command")
def handle_command(cmd: Command):

    # =========================================================
    # 1. RECUPERAÇÃO DA SESSÃO
    # =========================================================
    session = get_session(cmd.session_id)

    if not session:
        return {"response": "Sessão inválida."}

    agora = time.time()

    global last_cleanup
    
    if agora - last_cleanup > SESSION_CLEANUP_INTERVAL:
        limpar_sessoes()
        last_cleanup = agora
    
    if agora - session["last_active"] > SESSION_TIMEOUT:
        del sessions[cmd.session_id]
        return {"response": "Sessão expirada. Conecte-se novamente."}
        #Incluir chamada para reconexão com senha.
  
    session["last_active"] = agora

    # =========================================================
    # 2. FLUXO DE ENTRADA (LOGIN / CRIAÇÃO)
    # Se ainda não está logado, tratamos a entrada aqui
    # =========================================================
    if session["estado"] != "logado":
        resposta = processar_entrada_sessao(session, cmd.command.strip())
        
        if isinstance(resposta, dict):
            return resposta
        
        return {"response": resposta, "mode": "normal"}

    # =========================================================
    # 3. RECUPERAÇÃO DO PLAYER (agora via sessão)
    # =========================================================
    player_id = session["player_id"]
    player = get_player(player_id)

    if not player:
        return {"response": "Personagem não existe."}

    # =========================================================
    # 4. INTERPRETAÇÃO DO TEXTO (fala vs comando)
    # =========================================================
    entrada = interpretar_comando(cmd.command)
    tipo = entrada["tipo"]
  
    if tipo == "fala":
        fala = entrada["texto"]
        return {"response": f"{player_id} diz: {fala}"}

    # =========================================================
    # 5. EXECUÇÃO DO COMANDO
    # =========================================================
    verbo = entrada["verbo"]
    args = entrada["args"]
    resultado = executar_comando(player, verbo, args, session)

    return {"response": resultado}
# Fim de Interpretador de Comandos
# Fim da Categoria MOTOR










# =========================================================
# JOGO
# =========================================================
# Sessões da Categoria "Jogo" aqui.



# Fim da Categoria JOGO

# Editado pela ultima vez em: 30/05/26
