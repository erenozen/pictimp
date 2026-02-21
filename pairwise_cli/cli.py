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
    from . import EXIT_SUCCESS, EXIT_VALIDATION, EXIT_PICT_ERR, EXIT_VERIF_ERR, EXIT_TIMEOUT
    
    if args.dry_run:
        print("Dry run requested.", file=sys.stderr)
        
    if not os.path.exists(args.model):
        print(f"Error: File not found: {args.model}", file=sys.stderr)
        sys.exit(EXIT_VALIDATION)
        
    with open(args.model, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        model = PairwiseModel.from_pict_model(content)
        model.validate_limits(
            max_params=args.max_params,
            max_values_per_param=args.max_values_per_param,
            max_total_values=args.max_total_values
        )
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(EXIT_VALIDATION)
        
    ordering = OrderingMode.KEEP if args.keep_order else OrderingMode(args.ordering)
    
    if args.dry_run:
        if ordering == OrderingMode.AUTO:
            run_params = model.get_reordered_parameters()
        else:
            run_params = model.parameters
        print("Model parsing valid.", file=sys.stderr)
        print("Generating following internal PICT model:", file=sys.stderr)
        print("-" * 40, file=sys.stderr)
        print(model.to_pict_model(run_params).strip(), file=sys.stderr)
        print("-" * 40, file=sys.stderr)
        print(f"Would invoke tries: {args.tries}", file=sys.stderr)
        print(f"Planned seed range: {args.seed} through {args.seed + args.tries - 1}", file=sys.stderr)
        sys.exit(EXIT_SUCCESS)
    
    try:
        res = generate_suite(
            model,
            ordering_mode=ordering,
            tries=args.tries,
            base_seed=args.seed,
            strength=args.strength,
            early_stop=args.early_stop,
            verify=args.verify,
            require_verified=args.require_verified,
            pict_timeout_sec=args.pict_timeout_sec,
            deterministic=args.deterministic,
            verbose=args.verbose
        )
    except TimeoutError as e:
        print(f"Generation timeout error: {e}", file=sys.stderr)
        sys.exit(EXIT_TIMEOUT)
    except Exception as e:
        print(f"Generation error: {e}", file=sys.stderr)
        sys.exit(EXIT_PICT_ERR)
        
    # Check verification bounds
    if args.verify and args.strength == 2 and not res.passed_verification:
        print("Error: Coverage verification failed.", file=sys.stderr)
        for pair in res.missing_pairs[:20]:
            print(f" Missing pair: {pair}", file=sys.stderr)
        sys.exit(EXIT_VERIF_ERR)
        
    # Formatting
    n = len(res.rows)
    print_output = True
    
    if not args.out and args.format != 'json' and n > args.max_output_cases and not args.print_all:
        print(f"Warning: Generated {n} tests exceeding --max-output-cases limit of {args.max_output_cases}.", file=sys.stderr)
        print("To see this output to console, pass --print-all or write to a file using --out FILE", file=sys.stderr)
        print_output = False
        
    out_str = ""
    if print_output or args.out:
        if args.format == 'table':
            out_str = format_table(res.canonical_headers, res.rows)
        elif args.format == 'csv':
            out_str = format_csv(res.canonical_headers, res.rows)
        elif args.format == 'json':
            metadata = {
                "ordering_mode": res.ordering_mode.value,
                "tries_attempted": res.attempts,
                "best_seed": res.seed,
                "lb": res.lb if args.strength == 2 else 0,
                "n": n,
                "verified": res.passed_verification
            }
            out_str = format_json(res.canonical_headers, res.rows, metadata=metadata)
            
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_str)
            if args.format != 'json':
                f.write('\n')
    elif print_output:
        print(out_str)
        
    sys.exit(EXIT_SUCCESS)

def cmd_doctor(args):
    from . import EXIT_SUCCESS, EXIT_PICT_ERR
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
        
        out = run_pict("a: A1, A2\nb: B1, B2\n", strength=2, timeout=5.0)
        if "A1" in out and "B1" in out:
            print("PICT Execution      : OK")
        else:
            print("PICT Execution      : UNEXPECTED OUTPUT")
            sys.exit(EXIT_PICT_ERR)
    except Exception as e:
        print(f"Doctor Failed       : {e}")
        sys.exit(EXIT_PICT_ERR)
        
    print("Doctor checks passed successfully.")
    sys.exit(EXIT_SUCCESS)

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

def cmd_verify(args):
    from . import EXIT_SUCCESS, EXIT_VALIDATION, EXIT_VERIF_ERR
    import csv
    import json
    
    if not os.path.exists(args.model):
        print(f"Error: File not found: {args.model}", file=sys.stderr)
        sys.exit(EXIT_VALIDATION)
        
    if not os.path.exists(args.cases):
        print(f"Error: File not found: {args.cases}", file=sys.stderr)
        sys.exit(EXIT_VALIDATION)
        
    with open(args.model, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        model = PairwiseModel.from_pict_model(content)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(EXIT_VALIDATION)
        
    # parse cases
    rows = []
    canonical_headers = [p.display_name for p in model.parameters]
    with open(args.cases, "r", encoding="utf-8") as f:
        if args.cases.endswith(".json"):
            data = json.load(f)
            # handle both {"metadata": ..., "test_cases": [...]} and [...]
            if isinstance(data, dict) and "test_cases" in data:
                cases = data["test_cases"]
            else:
                cases = data
                
            for test_case in cases:
                row = []
                for h in canonical_headers:
                    row.append(str(test_case.get(h, "")))
                rows.append(row)
        else:
            # Assume CSV
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers:
                print("Error: Cases file is empty", file=sys.stderr)
                sys.exit(EXIT_VALIDATION)
                
            header_idx = {h: i for i, h in enumerate(headers)}
            for line in reader:
                row = []
                for h in canonical_headers:
                    if h in header_idx and header_idx[h] < len(line):
                        row.append(line[header_idx[h]])
                    else:
                        row.append("")
                rows.append(row)
                
    from .verify import verify_pairwise_coverage
    passed, missing = verify_pairwise_coverage(model, rows)
    if not passed:
        print("Error: Coverage verification failed.", file=sys.stderr)
        for pair in missing[:20]:
            print(f" Missing pair: {pair}", file=sys.stderr)
        sys.exit(EXIT_VERIF_ERR)
        
    print("Coverage verified successfully.", file=sys.stderr)
    sys.exit(EXIT_SUCCESS)

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
    
    # Limits and Boundaries
    gen_parser.add_argument("--max-params", type=int, default=50, help="Maximum number of parameters allowed (default: 50)")
    gen_parser.add_argument("--max-values-per-param", type=int, default=50, help="Maximum number of values per parameter allowed (default: 50)")
    gen_parser.add_argument("--max-total-values", type=int, default=500, help="Maximum total sum of all values allowed (default: 500)")
    gen_parser.add_argument("--max-output-cases", type=int, default=100000, help="Output block limit on table format prints (default: 100000)")
    gen_parser.add_argument("--pict-timeout-sec", type=float, default=10.0, help="Subprocess timeout per PICT execution (default: 10.0s)")

    # Booleans
    gen_parser.add_argument("--print-all", action="store_true", help="Force print table output even if exceeding max bounds")
    gen_parser.add_argument("--dry-run", action="store_true", help="Parse the model, resolve parameters, and plan seeds but do not execute PICT")
    gen_parser.add_argument("--deterministic", action="store_true", help="Force mathematically deterministic seed selection when output boundaries are identical between run ties")
    gen_parser.add_argument("--no-early-stop", action="store_false", dest="early_stop", help="Do not stop early if LB is reached")
    gen_parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable pair coverage verification")
    gen_parser.add_argument("--no-require-verified", action="store_false", dest="require_verified", help="Do not drop generation attempts that fail coverage mathematically")
    gen_parser.add_argument("--verbose", action="store_true", help="Print detailed attempt logs")
    
    ver_parser = subparsers.add_parser("verify", help="Verify coverage of a generated suite")
    ver_parser.add_argument("--model", required=True, help="Path to the PICT model file")
    ver_parser.add_argument("--cases", required=True, help="Path to the cases file (CSV or JSON)")
    
    doc_parser = subparsers.add_parser("doctor", help="Run self-diagnostics on the PICT integration")
    lic_parser = subparsers.add_parser("licenses", help="Display third-party licenses")
    version_parser = subparsers.add_parser("version", help="Print version information")
    
    args = parser.parse_args()
    
    if args.command is None or args.command == "wizard":
        run_wizard()
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "version":
        print("pairwise-cli 1.0.0")
    elif args.command == "licenses":
        cmd_licenses(args)

if __name__ == "__main__":
    main()
