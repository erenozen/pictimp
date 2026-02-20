"""Command-line interface."""
import sys
import argparse
import os
from .wizard import run_wizard
from .model import PairwiseModel
from .pict import run_pict, extract_pict_if_needed, get_platform_info, get_vendor_target
from .output import format_table, format_csv, format_json
from .generate import generate_suite, OrderingMode

def cmd_generate(args):
    if not os.path.exists(args.model):
        print(f"File not found: {args.model}", file=sys.stderr)
        sys.exit(1)
        
    with open(args.model, "r", encoding="utf-8") as f:
        content = f.read()
        
    model = PairwiseModel.from_pict_model(content)
    ordering = OrderingMode.KEEP if args.keep_order else OrderingMode(args.ordering)
    
    try:
        res = generate_suite(
            model,
            ordering_mode=ordering,
            tries=args.tries,
            base_seed=args.seed,
            strength=args.strength,
            early_stop=args.early_stop,
            verify=args.verify,
            verbose=args.verbose
        )
    except Exception as e:
        print(f"Generation error: {e}", file=sys.stderr)
        sys.exit(1)
        
    if args.format == 'table':
        out_str = format_table(res.canonical_headers, res.rows)
    elif args.format == 'csv':
        out_str = format_csv(res.canonical_headers, res.rows)
    elif args.format == 'json':
        out_str = format_json(res.canonical_headers, res.rows)
        
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_str)
            if args.format != 'json':
                f.write('\n')
    else:
        print(out_str)
        
    if args.verify and args.strength == 2:
        if not res.passed_verification:
            print("Error: Coverage verification failed.", file=sys.stderr)
            for pair in res.missing_pairs[:20]:
                print(f" Missing pair: {pair}", file=sys.stderr)
            sys.exit(1)

def cmd_doctor(args):
    print("Pairwise-CLI Doctor")
    print("-" * 20)
    system, machine = get_platform_info()
    target = get_vendor_target()
    print(f"Detected Platform   : {system} {machine}")
    print(f"Vendor Target       : {target}")
    
    try:
        path = extract_pict_if_needed()
        print(f"PICT Extracted To   : {path}")
        print("PICT Extract        : OK")
        
        out = run_pict("a: A1, A2\nb: B1, B2\n", strength=2)
        if "A1" in out and "B1" in out:
            print("PICT Execution      : OK")
        else:
            print("PICT Execution      : UNEXPECTED OUTPUT")
    except Exception as e:
        print(f"Doctor Failed       : {e}")
        sys.exit(1)

def cmd_licenses(args):
    if hasattr(sys, "_MEIPASS"):
        search_paths = [sys._MEIPASS]
    else:
        search_paths = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
        
    search_paths.append(os.path.dirname(sys.executable))
    
    for base in search_paths:
        p = os.path.join(base, "THIRD_PARTY_NOTICES.txt")
        if os.path.exists(p):
            print(f"Found licenses at: {p}\n")
            with open(p, "r", encoding="utf-8") as f:
                print(f.read())
            return
            
    print("THIRD_PARTY_NOTICES.txt not found.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Pairwise-CLI: Combinatorial test generator using Microsoft PICT.")
    subparsers = parser.add_subparsers(dest="command")
    
    wiz_parser = subparsers.add_parser("wizard", help="Run the interactive wizard (default)")
    
    gen_parser = subparsers.add_parser("generate", help="Generate tests from a PICT model file")
    gen_parser.add_argument("--model", required=True, help="Path to the model file")
    gen_parser.add_argument("--format", choices=["table", "csv", "json"], default="table", help="Output format")
    gen_parser.add_argument("--out", help="Output file (prints to standard output if not provided)")
    gen_parser.add_argument("--ordering", choices=["keep", "auto"], default="auto", help="Parameter ordering mode (default: auto)")
    gen_parser.add_argument("--keep-order", action="store_true", help="Shorthand for --ordering keep")
    gen_parser.add_argument("--tries", type=int, default=50, help="Number of seeds to try to find the smallest suite (default: 50)")
    gen_parser.add_argument("--seed", type=int, default=0, help="Base random seed (default: 0)")
    gen_parser.add_argument("--strength", type=int, default=2, help="Combinatorial strength (default: 2)")
    
    # Booleans
    gen_parser.add_argument("--no-early-stop", action="store_false", dest="early_stop", help="Do not stop early if LB is reached")
    gen_parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable pair coverage verification")
    gen_parser.add_argument("--verbose", action="store_true", help="Print detailed attempt logs")
    
    args = parser.parse_args()
    
    if args.command is None or args.command == "wizard":
        run_wizard()
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "version":
        print("pairwise-cli 1.0.0")
    elif args.command == "licenses":
        cmd_licenses(args)

if __name__ == "__main__":
    main()
