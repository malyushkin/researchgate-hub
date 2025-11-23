import argparse

from publications import export_raw_publications
from config import Config


# from citations import process_citations_for_publications


def build_parser() -> argparse.ArgumentParser:
    """
    Creates command-line interface for the ResearchGate toolkit.
    """

    parser = argparse.ArgumentParser(
        prog="researchgate-hub",
        description="Lightweight ResearchGate data extraction tool",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- publications command ---
    sp_top = subparsers.add_parser(
        "publications",
        help="Parse a saved ResearchGate search JSON and update publications.csv",
    )
    sp_top.add_argument(
        "--topic",
        required=True,
        help="Topic name used in the CSV (e.g. 'ai-and-sociology_2.json-and-sociology').",
    )
    sp_top.add_argument(
        "--json-file",
        required=True,
        help="Path to the saved ResearchGate search JSON.",
    )

    # --- citations command ---
    subparsers.add_parser(
        "citations",
        help="Fetch citations for all publications in publications.csv",
    )

    return parser


def main() -> None:
    """
    Entry point for CLI commands.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "publications":
        export_raw_publications(
            topic=args.topic,
            json_file_path=args.json_file,
            export_folder_path=Config.processed_data_path,
        )

    elif args.command == "citations":
        # process_citations_for_publications()
        print("Citations mode is not enabled yet.")

    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
