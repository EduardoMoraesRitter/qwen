# main.py - Versao text-only para GCP/Docker
import os
import re
import json
import uuid
import time
import requests as http_requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llama_cpp import Llama
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="API Qwen Local")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelo de Texto ---
TEXT_MODEL_PATH = str(BASE_DIR / "models" / "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf")
llm_text = Llama(
    model_path=TEXT_MODEL_PATH,
    n_ctx=32768,
    n_threads=int(os.environ.get("N_THREADS", "4")),
    n_gpu_layers=0,
    verbose=False
)
print("Modelo de texto carregado!")

# --- Config ---
DEFAULT_CONFIG = {
    "system_prompt": "Voce e um assistente util e inteligente. Responda sempre em portugues.",
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 0.9,
    "tools": [
        {
            "name": "clima_tempo",
            "description": "Consulta a previsao do tempo atual de qualquer cidade. Use quando o usuario perguntar sobre clima, tempo, temperatura ou previsao. Responda com [TOOL: clima_tempo] nome_da_cidade",
            "enabled": True
        }
    ]
}

config = dict(DEFAULT_CONFIG)
CONFIG_FILE = str(BASE_DIR / "config.json")


def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    else:
        config = dict(DEFAULT_CONFIG)
        save_config()


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


load_config()


# --- Tool Executors ---
def execute_clima_tempo(cidade):
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_resp = http_requests.get(geo_url, params={"name": cidade, "count": 1, "language": "pt"}, timeout=10)
        geo_data = geo_resp.json()
        if not geo_data.get("results"):
            return "Cidade '{}' nao encontrada.".format(cidade)
        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        nome, pais = loc.get("name", cidade), loc.get("country", "")
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_resp = http_requests.get(weather_url, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto"
        }, timeout=10)
        current = weather_resp.json().get("current", {})
        conditions = {
            0: "Ceu limpo", 1: "Parcialmente limpo", 2: "Parcialmente nublado",
            3: "Nublado", 45: "Nevoeiro", 48: "Nevoeiro com geada",
            51: "Garoa leve", 53: "Garoa moderada", 55: "Garoa forte",
            61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte",
            71: "Neve leve", 73: "Neve moderada", 75: "Neve forte",
            80: "Pancadas leves", 81: "Pancadas moderadas", 82: "Pancadas fortes",
            95: "Tempestade", 96: "Tempestade com granizo", 99: "Tempestade forte com granizo"
        }
        cond = conditions.get(current.get("weather_code", 0), "Desconhecido")
        return "Clima atual em {}, {}:\n- Condicao: {}\n- Temperatura: {} C\n- Umidade: {}%\n- Vento: {} km/h".format(
            nome, pais, cond, current.get("temperature_2m", "?"),
            current.get("relative_humidity_2m", "?"), current.get("wind_speed_10m", "?")
        )
    except Exception as e:
        return "Erro ao consultar clima: {}".format(str(e))


TOOL_EXECUTORS = {"clima_tempo": execute_clima_tempo}


def detect_and_execute_tools(response_text):
    matches = re.findall(r'\[TOOL:\s*(\w+)\]\s*(.*?)(?:\n|$)', response_text)
    if not matches:
        return None, None
    tool_name, tool_param = matches[0][0].strip(), matches[0][1].strip()
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor:
        return tool_name, executor(tool_param)
    return tool_name, "Tool '{}' nao implementada.".format(tool_name)


# --- Sessions ---
def get_session(session_id):
    path = SESSIONS_DIR / "{}.json".format(session_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"id": session_id, "title": "Nova conversa", "messages": []}


def save_session(session):
    path = SESSIONS_DIR / "{}.json".format(session["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def list_sessions():
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            sessions.append({
                "id": data["id"],
                "title": data.get("title", "Nova conversa"),
                "count": len(data.get("messages", []))
            })
    return sessions


# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str
    history: list = []
    session_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    tools: Optional[list] = None


# --- Helper: build system prompt with tools ---
def build_system_prompt():
    system_content = config["system_prompt"]
    active_tools = [t for t in config.get("tools", []) if t.get("enabled", True)]
    if active_tools:
        tools_text = "\n\nVoce tem acesso as seguintes ferramentas:\n"
        for tool in active_tools:
            tools_text += "- {}: {}\n".format(tool["name"], tool["description"])
        tools_text += "\nQuando precisar usar uma ferramenta, responda APENAS com o formato:\n"
        tools_text += "[TOOL: nome_da_ferramenta] parametro\n"
        tools_text += "Exemplo: [TOOL: clima_tempo] Sao Paulo\n"
        tools_text += "NAO escreva mais nada alem da chamada da tool quando for usa-la."
        system_content += tools_text
    return system_content


# --- Routes ---
@app.get("/health")
def health_check():
    try:
        output = llm_text.create_chat_completion(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0.1
        )
        return {"status": "ok", "model": "loaded", "response": output["choices"][0]["message"]["content"]}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "error", "model": "failed", "detail": str(e)})


@app.get("/")
def serve_frontend():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/config")
def get_config():
    return config


@app.post("/config")
def update_config(update: ConfigUpdate):
    if update.system_prompt is not None:
        config["system_prompt"] = update.system_prompt
    if update.temperature is not None:
        config["temperature"] = max(0.0, min(2.0, update.temperature))
    if update.max_tokens is not None:
        config["max_tokens"] = max(1, min(4096, update.max_tokens))
    if update.top_p is not None:
        config["top_p"] = max(0.0, min(1.0, update.top_p))
    if update.tools is not None:
        config["tools"] = update.tools
    save_config()
    return config


# --- Sessions API ---
@app.get("/sessions")
def get_sessions():
    return list_sessions()


@app.post("/sessions")
def create_session():
    sid = str(uuid.uuid4())[:8]
    session = {"id": sid, "title": "Nova conversa", "messages": []}
    save_session(session)
    return session


@app.get("/sessions/{session_id}")
def get_session_detail(session_id: str):
    return get_session(session_id)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    path = SESSIONS_DIR / "{}.json".format(session_id)
    if path.exists():
        os.remove(path)
    return {"ok": True}


# --- Chat (texto only) ---
@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    try:
        system_content = build_system_prompt()
        messages = [{"role": "system", "content": system_content}]
        for msg in request.history:
            messages.append(msg)
        messages.append({"role": "user", "content": request.message})

        t0 = time.time()
        output = llm_text.create_chat_completion(
            messages=messages,
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
            top_p=config["top_p"]
        )
        elapsed = round(time.time() - t0, 2)
        usage = output.get("usage", {})
        resposta = output["choices"][0]["message"]["content"]

        tool_name, tool_result = detect_and_execute_tools(resposta)
        if tool_result:
            messages.append({"role": "assistant", "content": resposta})
            messages.append({
                "role": "user",
                "content": "[Resultado da ferramenta {}]:\n{}\n\nAgora responda ao usuario de forma natural usando essas informacoes.".format(tool_name, tool_result)
            })
            t0b = time.time()
            output2 = llm_text.create_chat_completion(
                messages=messages,
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                top_p=config["top_p"]
            )
            elapsed += round(time.time() - t0b, 2)
            usage2 = output2.get("usage", {})
            usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0) + usage2.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0) + usage2.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0) + usage2.get("total_tokens", 0),
            }
            resposta_final = output2["choices"][0]["message"]["content"]

            if request.session_id:
                session = get_session(request.session_id)
                session["messages"].append({"role": "user", "content": request.message})
                session["messages"].append({"role": "assistant", "content": resposta_final})
                if session["title"] == "Nova conversa" and len(session["messages"]) == 2:
                    session["title"] = request.message[:40]
                save_session(session)

            return {"resposta": resposta_final, "tool_used": tool_name, "tool_result": tool_result,
                    "elapsed_seconds": elapsed, "usage": usage}

        if request.session_id:
            session = get_session(request.session_id)
            session["messages"].append({"role": "user", "content": request.message})
            session["messages"].append({"role": "assistant", "content": resposta})
            if session["title"] == "Nova conversa" and len(session["messages"]) == 2:
                session["title"] = request.message[:40]
            save_session(session)

        return {"resposta": resposta, "elapsed_seconds": elapsed, "usage": usage}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoints desabilitados (imagem/audio) retornam erro amigavel ---
@app.post("/chat/image")
async def chat_image_disabled():
    raise HTTPException(status_code=501, detail="Modo imagem desabilitado nesta versao (text-only).")


@app.post("/chat/audio")
async def chat_audio_disabled():
    raise HTTPException(status_code=501, detail="Modo audio desabilitado nesta versao (text-only).")


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    print(f"Iniciando API Qwen (text-only) na porta {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
