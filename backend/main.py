# Imports
import fastapi
import fastapi.responses
import pydantic
import fastapi.middleware.cors
import uuid
import time
# Fim de Imports


# Conexões permitidas
app = fastapi.FastAPI()
app.add_middleware(
    fastapi.middleware.cors.CORSMiddleware,
    allow_origins=["*"],  # permite qualquer origem (ok para desenvolvimento)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Fim de Conexões permitidas


# Estado do Sistema (memória do jogo)
players = {}
# Fim de Estado do Sistema (memória do jogo)    


# Sessões (controle de conexões)
sessions = {}
# Fim de Sessões


# Configuração de Sessão
SESSION_TIMEOUT = 15  # 15 segundos (em segundos)
#SESSION_TIMEOUT = 900  # 15 minutos (em segundos)

SESSION_CLEANUP_INTERVAL = 300  # tempo mínimo entre limpezas (segundos)
last_cleanup = 0
# Fim de Configuração de Sessão


# Regras do Jogo (lógica interna):
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
    return True


def validar_senha(senha):
    return True
# Fim de Regras do Jogo (lógica interna)


# Modelos de Dados: (entrada/saída da API):
class Command(pydantic.BaseModel):
    session_id: str
    command: str
# Fim de Modelos de Dados: (entrada/saída da API):


# Endpoints do Sistema:
@app.get("/connect")
def connect():
  
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "estado": "esperando_nome",
        "player_id": None,
        "last_active": time.time()
    }

    return {
        "session_id": session_id,
        "message": "Seja bem-vindo ao MUD\nNome do personagem:"
    }

@app.get("/")
def serve_frontend():
    return fastapi.responses.FileResponse("frontend/index.html")
# Fim de Endpoints do Sistema


# Interpretador de Comandos:
def get_player(player_id):
    return players.get(player_id)

def interpretar_comando(texto):
    texto = texto.strip()

    if texto and texto == texto.upper():
        return "comando", texto.lower()
    else:
        return "fala", texto
    
def executar_comando(player, comando):

    update_player(player)

    if comando == "descansar":
        player["energia"] += 10
        player["fome"] += 2
        return "Você descansa por um tempo."

    elif comando == "status":
        return describe(player)

    else:
        return "Você não sabe como fazer isso."

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

        if not validar_nome(nome):
            return "Nome inválido. Tente novamente."

        session["nome_temp"] = nome

        if nome in players:
            session["estado"] = "esperando_senha"
            return "Personagem existe. Digite a senha:"
        else:
            session["estado"] = "criando_senha"
            return "Novo personagem. Crie uma senha:"

    # ===== ESTADO: CRIANDO SENHA =====
    elif estado == "criando_senha":
        senha = texto

        if not validar_senha(senha):
            return "Senha inválida."

        nome = session["nome_temp"]

        players[nome] = {
            "energia": 100,
            "fome": 0,
            "temperatura": 50,
            "medo": 0,
            "vivo": True,
            "consciente": True,
            "senha": senha
        }

        session["player_id"] = nome
        session["estado"] = "logado"

        return f"Personagem '{nome}' criado. Você entrou no mundo."

    # ===== ESTADO: ESPERANDO SENHA =====
    elif estado == "esperando_senha":
        senha = texto
        nome = session["nome_temp"]

        if players[nome]["senha"] != senha:
            return "Senha incorreta."

        session["player_id"] = nome
        session["estado"] = "logado"

        return f"Bem-vindo de volta, {nome}."

    return "Erro de sessão."

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
  
    session["last_active"] = agora

    # =========================================================
    # 2. FLUXO DE ENTRADA (LOGIN / CRIAÇÃO)
    # Se ainda não está logado, tratamos a entrada aqui
    # =========================================================
    if session["estado"] != "logado":
        resposta = processar_entrada_sessao(session, cmd.command.strip())
        return {"response": resposta}

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
    tipo, comando = interpretar_comando(cmd.command)

    if tipo == "fala":
        return {"response": f"{player_id} diz: {comando}"}

    # =========================================================
    # 5. EXECUÇÃO DO COMANDO
    # =========================================================
    resultado = executar_comando(player, comando)

    return {"response": resultado}
# Fim de Interpretador de Comandos

# Editado pela ultima vez em: 26/05/26
