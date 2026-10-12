"""
Script de Migracao de Dados para SuperJurista Kanban

Migra processos da estrutura flat para estrutura de estados:
  data/sentenca/<processo>/  ->  data/sentenca/01-por-analisar/<processo>/

Uso:
  python migrar_dados.py                    # Modo dry-run (mostra o que faria)
  python migrar_dados.py --executar         # Executa a migracao
  python migrar_dados.py --reverter         # Reverte para estrutura flat
"""

import argparse
import shutil
import re
from pathlib import Path


# Configuracao
BASE_PATH = Path(__file__).parent.parent / "data"

TIPOS_PROCESSO = ["sentenca", "decisao", "despacho"]

ESTADOS = {
    "por-analisar": "01-por-analisar",
    "analisando": "02-analisando",
    "pendencias": "03-pendencias",
    "validado": "04-validado",
    "arquivado": "05-arquivados",
}

# Padrao para identificar pastas de processo (numero CNJ)
PADRAO_PROCESSO = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")


def eh_pasta_processo(nome: str) -> bool:
    """Verifica se o nome segue o padrao de numero de processo CNJ."""
    return bool(PADRAO_PROCESSO.match(nome))


def criar_estrutura_estados(tipo_path: Path, dry_run: bool = True) -> None:
    """Cria as pastas de estado se nao existirem."""
    for estado_nome in ESTADOS.values():
        estado_path = tipo_path / estado_nome
        if not estado_path.exists():
            if dry_run:
                print(f"  [CRIAR] {estado_path}")
            else:
                estado_path.mkdir(parents=True, exist_ok=True)
                print(f"  [CRIADO] {estado_path}")


def migrar_tipo(tipo: str, dry_run: bool = True) -> dict:
    """
    Migra processos de um tipo para estrutura de estados.

    Returns:
        Dict com estatisticas da migracao
    """
    tipo_path = BASE_PATH / tipo
    stats = {"total": 0, "migrados": 0, "ja_migrados": 0, "ignorados": 0, "erros": []}

    if not tipo_path.exists():
        print(f"\n[SKIP] Pasta {tipo_path} nao existe")
        return stats

    print(f"\n{'='*60}")
    print(f"Migrando: {tipo}")
    print(f"{'='*60}")

    # Criar estrutura de estados
    criar_estrutura_estados(tipo_path, dry_run)

    # Listar itens na pasta do tipo
    for item in tipo_path.iterdir():
        stats["total"] += 1

        # Ignorar arquivos
        if item.is_file():
            print(f"  [IGNORAR] {item.name} (arquivo)")
            stats["ignorados"] += 1
            continue

        # Ignorar pastas de estado ja existentes
        if item.name in ESTADOS.values():
            stats["ignorados"] += 1
            continue

        # Verificar se ja esta dentro de uma pasta de estado
        if item.parent.name in ESTADOS.values():
            print(f"  [JA MIGRADO] {item.name}")
            stats["ja_migrados"] += 1
            continue

        # Verificar se e uma pasta de processo
        if not eh_pasta_processo(item.name):
            print(f"  [IGNORAR] {item.name} (nao e processo)")
            stats["ignorados"] += 1
            continue

        # Destino: 01-por-analisar
        destino = tipo_path / ESTADOS["por-analisar"] / item.name

        if destino.exists():
            print(f"  [JA EXISTE] {item.name} -> {destino}")
            stats["ja_migrados"] += 1
            continue

        # Mover pasta
        if dry_run:
            print(f"  [MOVER] {item.name} -> {ESTADOS['por-analisar']}/")
            stats["migrados"] += 1
        else:
            try:
                shutil.move(str(item), str(destino))
                print(f"  [MOVIDO] {item.name} -> {ESTADOS['por-analisar']}/")
                stats["migrados"] += 1
            except Exception as e:
                print(f"  [ERRO] {item.name}: {e}")
                stats["erros"].append((item.name, str(e)))

    return stats


def reverter_tipo(tipo: str, dry_run: bool = True) -> dict:
    """
    Reverte processos de estrutura de estados para flat.

    Returns:
        Dict com estatisticas da reversao
    """
    tipo_path = BASE_PATH / tipo
    stats = {"total": 0, "revertidos": 0, "erros": []}

    if not tipo_path.exists():
        print(f"\n[SKIP] Pasta {tipo_path} nao existe")
        return stats

    print(f"\n{'='*60}")
    print(f"Revertendo: {tipo}")
    print(f"{'='*60}")

    # Percorrer pastas de estado
    for estado_nome in ESTADOS.values():
        estado_path = tipo_path / estado_nome

        if not estado_path.exists():
            continue

        for item in estado_path.iterdir():
            if not item.is_dir():
                continue

            if not eh_pasta_processo(item.name):
                continue

            stats["total"] += 1
            destino = tipo_path / item.name

            if destino.exists():
                print(f"  [JA EXISTE] {item.name} em {tipo_path}")
                continue

            if dry_run:
                print(f"  [MOVER] {estado_nome}/{item.name} -> {tipo}/")
                stats["revertidos"] += 1
            else:
                try:
                    shutil.move(str(item), str(destino))
                    print(f"  [MOVIDO] {estado_nome}/{item.name} -> {tipo}/")
                    stats["revertidos"] += 1
                except Exception as e:
                    print(f"  [ERRO] {item.name}: {e}")
                    stats["erros"].append((item.name, str(e)))

    # Remover pastas de estado vazias
    for estado_nome in ESTADOS.values():
        estado_path = tipo_path / estado_nome
        if estado_path.exists() and not any(estado_path.iterdir()):
            if dry_run:
                print(f"  [REMOVER] {estado_path} (vazia)")
            else:
                estado_path.rmdir()
                print(f"  [REMOVIDO] {estado_path}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migra dados do SuperJurista para estrutura Kanban"
    )
    parser.add_argument(
        "--executar",
        action="store_true",
        help="Executa a migracao (sem isso, apenas mostra o que faria)"
    )
    parser.add_argument(
        "--reverter",
        action="store_true",
        help="Reverte para estrutura flat"
    )
    parser.add_argument(
        "--tipo",
        choices=TIPOS_PROCESSO,
        help="Migrar apenas um tipo especifico"
    )

    args = parser.parse_args()
    dry_run = not args.executar

    if dry_run:
        print("\n" + "="*60)
        print("MODO DRY-RUN - Nenhuma alteracao sera feita")
        print("Use --executar para aplicar as mudancas")
        print("="*60)

    tipos = [args.tipo] if args.tipo else TIPOS_PROCESSO
    total_stats = {"migrados": 0, "ignorados": 0, "erros": []}

    for tipo in tipos:
        if args.reverter:
            stats = reverter_tipo(tipo, dry_run)
            total_stats["migrados"] += stats["revertidos"]
        else:
            stats = migrar_tipo(tipo, dry_run)
            total_stats["migrados"] += stats["migrados"]
            total_stats["ignorados"] += stats["ignorados"]
        total_stats["erros"].extend(stats.get("erros", []))

    # Resumo
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)

    if args.reverter:
        print(f"Processos revertidos: {total_stats['migrados']}")
    else:
        print(f"Processos migrados: {total_stats['migrados']}")
        print(f"Itens ignorados: {total_stats['ignorados']}")

    if total_stats["erros"]:
        print(f"\nErros ({len(total_stats['erros'])}):")
        for nome, erro in total_stats["erros"]:
            print(f"  - {nome}: {erro}")

    if dry_run and total_stats["migrados"] > 0:
        print("\n>>> Execute com --executar para aplicar as mudancas <<<")


if __name__ == "__main__":
    main()
