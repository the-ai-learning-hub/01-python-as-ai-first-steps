"""Pequenas funções úteis, usadas no notebook 04 · Módulos, Erros e Classes.

Este ficheiro é um *módulo*: qualquer ficheiro .py pode ser importado
noutro programa com `import utilidades`.
"""


def saudacao(nome):
    """Devolve uma saudação personalizada para `nome`."""
    return f"Olá, {nome}! Bem-vindo(a) ao Python."


def media(numeros):
    """Devolve a média de uma lista de números (0 se a lista estiver vazia)."""
    if not numeros:
        return 0
    return sum(numeros) / len(numeros)


def celsius_para_fahrenheit(celsius):
    """Converte uma temperatura de graus Celsius para Fahrenheit."""
    return celsius * 9 / 5 + 32


# Este bloco só corre quando executas o ficheiro diretamente
# (por exemplo, `uv run python utilidades.py`), e NÃO quando o importas.
if __name__ == "__main__":
    print("A testar o módulo utilidades...")
    print(saudacao("Ana"))
    print(media([10, 15, 20]))
    print(celsius_para_fahrenheit(100))
