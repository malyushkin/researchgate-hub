import argparse

from config import Config
from citations import process_citations_for_publications
from publications import export_raw_publications
from publications_metadata import process_publication_metadata


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

    metadata_parser = subparsers.add_parser("metadata", help="Fetch metadata for a list of specific publication IDs.")
    metadata_parser.add_argument(
        "--input",
        type=str,
        default="all_unique_ids.csv",
        help="Path to the input CSV file containing 'publication_id' column."
    )
    metadata_parser.add_argument(
        "--output",
        type=str,
        default="publications_metadata.csv",
        help="Path for the output CSV file to save metadata."
    )
    metadata_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,  # Новый аргумент для пакетной обработки
        help="Number of articles to process before saving data incrementally."
    )
    metadata_parser.add_argument(
        "--num-workers",
        type=int,
        default=4, # Новый аргумент для задания количества потоков
        help="Number of concurrent threads/workers to use for fetching metadata."
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
        process_citations_for_publications()

    elif args.command == "metadata":
        process_publication_metadata(
            f"{Config.processed_data_path}/{args.input}",
            f"{Config.processed_data_path}/{args.output}",
            args.batch_size,
            args.num_workers,
        )

    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
