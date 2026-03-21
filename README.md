# Qwen Chat - Text-Only (Docker / GCP)

Chatbot local usando o modelo **Qwen 2.5 1.5B Instruct** (quantizado Q4_K_M) rodando 100% em CPU via `llama.cpp`. Versao leve, sem visao e sem audio, otimizada para deploy em containers Docker e Google Cloud Platform (Cloud Run).

---

## Indice

- [Visao Geral](#visao-geral)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Modelo GGUF](#modelo-gguf)
- [Rodando Local (sem Docker)](#rodando-local-sem-docker)
- [Rodando com Docker](#rodando-com-docker)
- [Deploy no GCP Cloud Run](#deploy-no-gcp-cloud-run)
- [API - Endpoints](#api---endpoints)
- [Frontend](#frontend)
- [Configuracoes](#configuracoes)
- [Sistema de Tools](#sistema-de-tools)
- [Sessoes de Conversa](#sessoes-de-conversa)
- [Variaveis de Ambiente](#variaveis-de-ambiente)
- [Limitacoes](#limitacoes)
- [Solucao de Problemas](#solucao-de-problemas)

---

## Visao Geral

Este projeto e um assistente de chat completo que roda inteiramente em CPU, sem depender de APIs externas pagas. Ele usa:

- **Modelo**: Qwen 2.5 1.5B Instruct (quantizado Q4_K_M, ~941MB)
- **Backend**: FastAPI + llama-cpp-python
- **Frontend**: HTML/CSS/JS puro (single page, sem frameworks)
- **Inferencia**: 100% CPU, sem necessidade de GPU
- **Container**: Docker pronto para Cloud Run

### O que esta incluido

| Funcionalidade | Status |
|---|---|
| Chat de texto | Ativo |
| System prompt customizavel | Ativo |
| Controle de temperatura/top_p/max_tokens | Ativo |
| Sistema de tools (funcoes externas) | Ativo |
| Tool de clima (Open-Meteo) | Ativo |
| Sessoes de conversa persistentes | Ativo |
| Frontend web responsivo | Ativo |
| Analise de imagem (visao) | Desabilitado |
| Transcricao de audio (Whisper) | Desabilitado |

### Por que desabilitar visao e audio?

- **Visao** (Qwen2.5-VL-3B) consome ~2GB de RAM extra e modelo de ~2.5GB
- **Audio** (Whisper) consome ~500MB de RAM extra
- Para rodar em instancias pequenas do GCP (2GB-4GB RAM), apenas texto e viavel
- Reduz a imagem Docker de ~4GB para ~881MB (sem o modelo)

---

## Arquitetura

```
Navegador (Frontend)
    |
    | HTTP (porta 8080)
    |
FastAPI (main.py)
    |
    |-- POST /chat ---------> llama-cpp-python ---------> Qwen 2.5 1.5B (.gguf)
    |                              |
    |                              |-- detecta [TOOL: x] --> executa tool --> segunda inferencia
    |
    |-- GET/POST /sessions --> arquivos JSON em /sessions/
    |-- GET/POST /config ----> config.json
    |-- GET / ---------------> static/index.html
```

### Fluxo de uma mensagem

1. Usuario digita mensagem no frontend
2. Frontend envia `POST /chat` com mensagem + historico
3. Backend monta o prompt: system prompt + tools + historico + mensagem
4. `llama-cpp-python` faz inferencia no modelo GGUF
5. Se a resposta contem `[TOOL: nome] parametro`:
   - Executa a tool (ex: consulta API de clima)
   - Injeta o resultado no contexto
   - Faz segunda inferencia para resposta natural
6. Resposta e retornada ao frontend e salva na sessao

---

## Requisitos

### Para rodar local (sem Docker)

- Python 3.10+
- ~3GB de RAM livre (modelo + inferencia)
- Compilador C++ (para compilar llama-cpp-python)
  - **Windows**: Visual Studio Build Tools ou MinGW
  - **Linux**: `build-essential cmake`
  - **macOS**: Xcode Command Line Tools

### Para rodar com Docker

- Docker Desktop (Windows/Mac) ou Docker Engine (Linux)
- ~3GB de RAM alocado para o Docker
- ~2GB de disco (881MB imagem + 941MB modelo)

### Para deploy no GCP

- Conta no Google Cloud Platform
- `gcloud` CLI instalado e configurado
- Artifact Registry habilitado
- Cloud Run habilitado
- Instancia com minimo **4GB de RAM** (recomendado)

---

## Estrutura do Projeto

```
docker-gcp/
├── .dockerignore       # Arquivos ignorados no build Docker
├── .gitignore          # Arquivos ignorados no Git (modelos, sessions)
├── Dockerfile          # Imagem Docker (python:3.11-slim + deps)
├── main.py             # Servidor FastAPI (backend completo)
├── requirements.txt    # Dependencias Python
├── static/
│   └── index.html      # Frontend completo (HTML + CSS + JS)
├── models/             # Pasta para o modelo GGUF (nao versionada)
│   └── Qwen2.5-1.5B-Instruct-Q4_K_M.gguf  (~941MB)
├── sessions/           # Sessoes de conversa salvas (nao versionado)
│   └── *.json
└── config.json         # Configuracoes do modelo (nao versionado)
```

---

## Modelo GGUF

O modelo **nao esta incluido no repositorio** (941MB). Voce precisa baixar manualmente.

### Download

Baixe do Hugging Face:

```bash
# Opcao 1: wget
wget https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  -O models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf

# Opcao 2: huggingface-cli
pip install huggingface_hub
huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --local-dir models/

# Opcao 3: curl
curl -L https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  -o models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
```

### Especificacoes do modelo

| Propriedade | Valor |
|---|---|
| Nome | Qwen 2.5 1.5B Instruct |
| Quantizacao | Q4_K_M (4-bit) |
| Tamanho em disco | ~941MB |
| RAM necessaria | ~1.5GB |
| Contexto maximo | 32768 tokens |
| Contexto configurado | 4096 tokens |
| Idiomas | Chines, Ingles, Portugues, +27 idiomas |
| Licenca | Apache 2.0 |

---

## Rodando Local (sem Docker)

### 1. Clonar o repositorio

```bash
git clone https://github.com/EduardoMoraesRitter/qwen.git
cd qwen
```

### 2. Criar ambiente virtual

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
# Linux (precisa de compilador C++)
sudo apt-get install build-essential cmake

# Instalar pacotes Python
pip install -r requirements.txt
```

### 4. Baixar o modelo

```bash
mkdir -p models
wget https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  -O models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
```

### 5. Rodar

```bash
python main.py
```

Acesse: **http://localhost:8080**

---

## Rodando com Docker

### 1. Build da imagem

```bash
docker build -t qwen-text .
```

Tempo estimado: 3-5 minutos (compilacao do llama-cpp-python).

### 2. Rodar o container

```bash
docker run -d \
  --name qwen-text \
  -p 8080:8080 \
  -v $(pwd)/models:/app/models \
  qwen-text
```

**Windows (PowerShell):**

```powershell
docker run -d `
  --name qwen-text `
  -p 8080:8080 `
  -v "${PWD}\models:/app/models" `
  qwen-text
```

### 3. Verificar

```bash
# Ver logs
docker logs qwen-text

# Testar endpoint
curl http://localhost:8080/sessions -X POST

# Testar chat
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Ola, quem e voce?"}'
```

### 4. Parar e remover

```bash
docker stop qwen-text
docker rm qwen-text
```

---

## Deploy no GCP Cloud Run

### 1. Configurar projeto GCP

```bash
# Login
gcloud auth login

# Definir projeto
gcloud config set project SEU_PROJETO_ID

# Habilitar servicos necessarios
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
```

### 2. Criar repositorio no Artifact Registry

```bash
gcloud artifacts repositories create qwen-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="Qwen Chat Docker images"
```

### 3. Build e push da imagem

```bash
# Configurar Docker para Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Tag da imagem
docker tag qwen-text us-central1-docker.pkg.dev/SEU_PROJETO_ID/qwen-repo/qwen-text:latest

# Push
docker push us-central1-docker.pkg.dev/SEU_PROJETO_ID/qwen-repo/qwen-text:latest
```

**Importante**: O modelo GGUF (~941MB) precisa estar dentro da imagem para o Cloud Run. Modifique o Dockerfile para incluir:

```dockerfile
# Adicione esta linha no Dockerfile antes do CMD
COPY models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf models/
```

Depois rebuild:

```bash
docker build -t us-central1-docker.pkg.dev/SEU_PROJETO_ID/qwen-repo/qwen-text:latest .
docker push us-central1-docker.pkg.dev/SEU_PROJETO_ID/qwen-repo/qwen-text:latest
```

### 4. Deploy no Cloud Run

```bash
gcloud run deploy qwen-chat \
  --image us-central1-docker.pkg.dev/SEU_PROJETO_ID/qwen-repo/qwen-text:latest \
  --region us-central1 \
  --platform managed \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 1 \
  --min-instances 0 \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars "N_THREADS=2"
```

### Parametros recomendados para Cloud Run

| Parametro | Valor | Motivo |
|---|---|---|
| `--memory` | 4Gi | Modelo usa ~1.5GB + overhead |
| `--cpu` | 2 | Inferencia usa threads paralelas |
| `--timeout` | 300 | Inferencia pode demorar ate 60s |
| `--max-instances` | 1 | Evitar custos (cada instancia consome RAM) |
| `--min-instances` | 0 | Escala para zero quando sem uso |
| `N_THREADS` | 2 | Igual ao numero de CPUs |

### Estimativa de custo GCP

- **Cloud Run (2 vCPU, 4GB RAM)**: ~$0.00005/s ativo
- **Modelo ocioso (min-instances=0)**: $0.00/mes
- **Artifact Registry**: ~$0.10/GB/mes (~$0.19/mes para imagem de 1.9GB)
- **Uso leve (1h/dia)**: ~$5-10/mes estimado

---

## API - Endpoints

### `GET /`

Retorna o frontend (static/index.html).

### `POST /chat`

Chat de texto com o modelo.

**Request:**

```json
{
  "message": "Qual a capital do Brasil?",
  "history": [
    {"role": "user", "content": "Ola"},
    {"role": "assistant", "content": "Ola! Como posso ajudar?"}
  ],
  "session_id": "abc12345"
}
```

| Campo | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `message` | string | Sim | Mensagem do usuario |
| `history` | array | Nao | Historico de mensagens (ate 20) |
| `session_id` | string | Nao | ID da sessao para persistir conversa |

**Response (sem tool):**

```json
{
  "resposta": "A capital do Brasil e Brasilia."
}
```

**Response (com tool):**

```json
{
  "resposta": "O clima em Sao Paulo esta parcialmente nublado com 28.9 C.",
  "tool_used": "clima_tempo",
  "tool_result": "Clima atual em Sao Paulo, Brasil:\n- Condicao: Parcialmente nublado\n- Temperatura: 28.9 C\n- Umidade: 48%\n- Vento: 9.1 km/h"
}
```

### `POST /chat/image`

**Desabilitado.** Retorna HTTP 501.

### `POST /chat/audio`

**Desabilitado.** Retorna HTTP 501.

### `GET /config`

Retorna configuracoes atuais do modelo.

**Response:**

```json
{
  "system_prompt": "Voce e um assistente util e inteligente.",
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 0.9,
  "tools": [
    {
      "name": "clima_tempo",
      "description": "Consulta a previsao do tempo...",
      "enabled": true
    }
  ]
}
```

### `POST /config`

Atualiza configuracoes. Todos os campos sao opcionais.

**Request:**

```json
{
  "system_prompt": "Voce e um pirata.",
  "temperature": 1.2,
  "max_tokens": 1024,
  "top_p": 0.95,
  "tools": []
}
```

### `GET /sessions`

Lista todas as sessoes de conversa.

**Response:**

```json
[
  {"id": "abc12345", "title": "Capital do Brasil", "count": 4},
  {"id": "def67890", "title": "Nova conversa", "count": 0}
]
```

### `POST /sessions`

Cria nova sessao.

**Response:**

```json
{"id": "abc12345", "title": "Nova conversa", "messages": []}
```

### `GET /sessions/{session_id}`

Retorna detalhes de uma sessao com todo o historico.

### `DELETE /sessions/{session_id}`

Deleta uma sessao.

---

## Frontend

O frontend e um arquivo HTML unico (`static/index.html`) com CSS e JavaScript inline. Nao usa frameworks.

### Funcionalidades

- **Barra lateral esquerda**: Lista de sessoes de conversa (criar, trocar, deletar)
- **Area de chat**: Mensagens do usuario e do assistente com animacao de digitacao
- **Campo de entrada**: Textarea com suporte a Enter para enviar e Shift+Enter para nova linha
- **Painel de configuracao**: Sidebar direita com controles de system prompt, temperatura, max tokens, top_p e tools

### Design

- Tema escuro (dark mode)
- Cores principais: `#6c63ff` (roxo), `#3b82f6` (azul), `#0f0f0f` (fundo)
- Responsivo (funciona em desktop e mobile)
- Sem dependencias externas (nenhum CDN)

---

## Configuracoes

As configuracoes podem ser alteradas pelo frontend (botao Config) ou via API `POST /config`.

| Parametro | Default | Range | Descricao |
|---|---|---|---|
| `system_prompt` | "Voce e um assistente util..." | texto livre | Instrucoes de comportamento do modelo |
| `temperature` | 0.7 | 0.0 - 2.0 | Criatividade. 0 = deterministico, 2 = muito aleatorio |
| `max_tokens` | 512 | 1 - 4096 | Limite de tokens na resposta |
| `top_p` | 0.9 | 0.0 - 1.0 | Nucleus sampling. 1.0 = todas as opcoes |
| `tools` | [clima_tempo] | array | Lista de ferramentas disponiveis |

As configuracoes sao salvas em `config.json` e persistem entre restarts.

---

## Sistema de Tools

O sistema de tools permite que o modelo "chame" funcoes externas. O fluxo funciona assim:

1. As tools ativas sao injetadas no system prompt
2. Quando o modelo decide usar uma tool, responde com: `[TOOL: nome] parametro`
3. O backend detecta esse padrao, executa a funcao correspondente
4. O resultado e injetado como contexto e o modelo gera uma resposta natural

### Tool incluida: clima_tempo

Consulta o clima atual de qualquer cidade usando a API gratuita do [Open-Meteo](https://open-meteo.com/).

**Exemplo de uso:**
- Usuario: "Como esta o tempo em Tokyo?"
- Modelo detecta: `[TOOL: clima_tempo] Tokyo`
- Backend consulta Open-Meteo API
- Modelo responde: "Em Tokyo esta ensolarado com 22 C..."

### Adicionando novas tools

#### Pelo frontend

1. Clique em "Config" no header
2. Va para aba "Tools"
3. Clique em "+ Adicionar Ferramenta"
4. Preencha nome e descricao
5. Clique "Salvar"

#### Pelo codigo (main.py)

1. Crie a funcao executora:

```python
def execute_minha_tool(parametro):
    # Sua logica aqui
    return "Resultado da tool"
```

2. Registre no dicionario:

```python
TOOL_EXECUTORS["minha_tool"] = execute_minha_tool
```

3. Adicione na config default:

```python
DEFAULT_CONFIG["tools"].append({
    "name": "minha_tool",
    "description": "Descricao do que a tool faz. Instrua o modelo quando usar.",
    "enabled": True
})
```

---

## Sessoes de Conversa

As sessoes sao salvas como arquivos JSON na pasta `sessions/`.

### Estrutura de uma sessao

```json
{
  "id": "abc12345",
  "title": "Qual a capital do Brasil",
  "messages": [
    {"role": "user", "content": "Qual a capital do Brasil?"},
    {"role": "assistant", "content": "A capital do Brasil e Brasilia."}
  ]
}
```

- O titulo e gerado automaticamente a partir da primeira mensagem (primeiros 40 caracteres)
- As sessoes sao ordenadas por data de modificacao (mais recente primeiro)
- No Cloud Run com `min-instances=0`, as sessoes sao perdidas quando a instancia escala para zero (use banco de dados externo se precisar persistir)

---

## Variaveis de Ambiente

| Variavel | Default | Descricao |
|---|---|---|
| `PORT` | 8080 | Porta do servidor HTTP |
| `N_THREADS` | 4 | Numero de threads para inferencia (ideal = numero de CPUs) |

---

## Limitacoes

- **Modelo pequeno (1.5B)**: Respostas podem ser imprecisas ou superficiais em temas complexos. Para melhor qualidade, use modelos maiores (7B, 14B) com mais RAM.
- **Apenas CPU**: Inferencia leva 5-30 segundos por resposta dependendo do tamanho. GPU aceleraria 10-50x.
- **Contexto de 4096 tokens**: Conversas longas podem perder contexto. O historico e limitado a 20 mensagens.
- **Sem streaming**: A resposta e retornada inteira, nao token por token. O frontend mostra animacao de "digitando" enquanto espera.
- **Sessoes em disco**: No Cloud Run, sessoes sao perdidas ao escalar para zero. Use Redis/Firestore para persistencia.
- **Sem autenticacao**: Qualquer pessoa com a URL pode acessar. Adicione autenticacao se expor publicamente.

---

## Solucao de Problemas

### Container nao inicia

```bash
docker logs qwen-text
```

Se aparecer erro de modelo nao encontrado, verifique se o volume esta montado:

```bash
docker run -v /caminho/completo/models:/app/models qwen-text
```

### Respostas muito lentas

- Aumente `N_THREADS` para o numero de CPUs disponiveis
- Reduza `max_tokens` nas configuracoes
- Reduza `n_ctx` no main.py (menos contexto = mais rapido)

### Erro de memoria (OOMKilled no Cloud Run)

- Aumente `--memory` no deploy (minimo 4Gi)
- Reduza `n_ctx` de 4096 para 2048 no main.py

### Modelo nao encontrado

```
Error: Model file not found: /app/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
```

Baixe o modelo e coloque na pasta `models/`. Veja a secao [Modelo GGUF](#modelo-gguf).

### Tool de clima nao funciona

A tool usa a API gratuita do Open-Meteo. Verifique se o container tem acesso a internet:

```bash
docker exec qwen-text curl -s https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m
```

---

## Licenca

- **Codigo**: MIT
- **Modelo Qwen 2.5**: Apache 2.0 (Alibaba Cloud)
