

import argparse
import sys 

from janis_core.ingestion import SupportedIngestion 
from janis_core.translation_deps.supportedtranslations import SupportedTranslation
from janis_core.ingestion import ingest
from janis_core.translations import translate


def main() -> None:
    sysargs = sys.argv[1:]
    args = parse_args(sysargs)
    do_translate(args)

def do_translate(args: argparse.Namespace) -> None:
    internal = ingest(args.infile, args.__dict__['from']) # shitty workaround to access args.from
    return translate(
        internal, 
        dest_fmt=args.to, 
        nocmd=args.nocmd, 
        simplification=args.simplification,
        export_path=args.outdir, 
        as_workflow=args.as_workflow
    )

def parse_args(sysargs: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Translate a janis workflow to CWL, WDL or Nextflow')

    parser.add_argument(
        "infile", 
        help="Path to input file",
    )
    parser.add_argument(
        "-f", "--from",
        help="Language of infile. Will be autodetected if not supplied",
        choices=SupportedIngestion.all(),
        type=str,
        required=True
    )
    parser.add_argument(
        "-t", "--to",
        help="Language to translate to.",
        choices=SupportedTranslation.all(),
        type=str,
        required=True
    )
    parser.add_argument(
        "-o",
        "--outdir",
        help="Output directory to write output to (default: translated).",
        type=str,
        default="translated"
    )
    parser.add_argument(
        "--as-workflow",
        action="store_true",
        help="For tool translation: wraps output tool in workflow.",
    )
    parser.add_argument(
        '--simplification',
        help="Simplify the translated workflow by removing unused inputs and outputs.",
        type=str,
        choices=["off", "on", "aggressive"],
        default="on",
    )
    parser.add_argument(
        "--nocmd",
        help="Don't generate command section for translated tools",
        action="store_true",
    )
    return parser.parse_args(sysargs)

