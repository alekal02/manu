"""Cria as 20 filiais com usuários gerente/fiscal no SQLite."""
import sys

from services import migrar_json_legacy, seed_bases


def main():
    resultado = seed_bases(20)
    print(resultado["mensagem"])

    if "--migrar-json" in sys.argv:
        mig = migrar_json_legacy("01")
        print(mig["mensagem"])


if __name__ == "__main__":
    main()
