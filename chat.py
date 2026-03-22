# chat.py
import requests

API_URL = "http://localhost:8080/chat"


def conversar():
    print("Conectando ao Qwen Local... (Ctrl+C para sair)")
    print("Certifique-se de que o main.py esta rodando em outro terminal!\n")

    historico = []

    while True:
        try:
            usuario = input("Voce: ")
            if usuario.lower() in ["sair", "exit", "quit"]:
                print("Encerrando chat...")
                break

            if not usuario.strip():
                continue

            # Enviar para API com historico
            payload = {"message": usuario, "history": historico}
            response = requests.post(API_URL, json=payload, timeout=120)

            if response.status_code == 200:
                dados = response.json()
                resposta = dados["resposta"]
                print(f"Qwen: {resposta}\n")

                # Salvar no historico
                historico.append({"role": "user", "content": usuario})
                historico.append({"role": "assistant", "content": resposta})

                # Limitar historico para nao estourar contexto
                if len(historico) > 20:
                    historico = historico[-20:]
            else:
                print(f"Erro na API: {response.text}\n")

        except requests.exceptions.ConnectionError:
            print("Erro: Nao foi possivel conectar na API. Verifique se o main.py esta rodando.\n")
        except KeyboardInterrupt:
            print("\nEncerrando chat...")
            break
        except Exception as e:
            print(f"Erro inesperado: {e}\n")


if __name__ == "__main__":
    conversar()
