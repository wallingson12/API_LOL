from config import FILAS


def selecionar_fila() -> tuple[str, int | None]:
    print("\n📌 Selecione o tipo de partida:")
    for k, (nome, _) in FILAS.items():
        print(f"   [{k}] {nome}")
    while True:
        escolha = input("\n   Opção: ").strip()
        if escolha in FILAS:
            nome, queue_id = FILAS[escolha]
            print(f"   ✅ Selecionado: {nome}")
            return nome, queue_id
        print("   ❌ Opção inválida, tente novamente.")


def selecionar_modo() -> str:
    print("\n🎮 Selecione o modo de análise:")
    print("   [1] Modo Pessoal   — apenas seus dados")
    print("   [2] Modo Completo  — todos os 10 jogadores de cada partida")
    while True:
        escolha = input("\n   Opção: ").strip()
        if escolha in ("1", "2"):
            modo = "pessoal" if escolha == "1" else "completo"
            print(f"   ✅ Modo: {modo}")
            return modo
        print("   ❌ Opção inválida, tente novamente.")
