"""Interactive wizard flow."""
import os
import sys
from .model import PairwiseModel
from .output import format_table, format_csv
from .generate import generate_suite, OrderingMode, GenerationVerificationError

def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        print()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

def run_wizard():
    print("Welcome to Pairwise-CLI!")
    print("This tool uses Microsoft PICT to generate pairwise (2-way) combinatorial test suites.")
    print("When strength=2, it can verify if the output achieves the theoretical minimum test count.")
    print("-" * 60)
    
    while True:
        model = PairwiseModel()
        _gather_parameters(model)
        
        if len(model.parameters) < 2:
            print("Need at least 2 parameters for pairwise generation. Exiting.")
            return
            
        _menu_loop(model)

def _gather_parameters(model: PairwiseModel):
    print("\nAdd parameters for your model.")
    while True:
        pname = prompt("\nParameter name (blank to finish): ")
        if not pname:
            if len(model.parameters) < 2:
                print("Error: You must provide at least 2 parameters.")
                continue
            else:
                break
                
        vals_input = prompt("Enter values comma-separated (or press Enter for one-by-one): ")
        if vals_input:
            vals = [v.strip() for v in vals_input.split(',')]
            vals = [v for v in vals if v]
            vals = list(dict.fromkeys(vals))
        else:
            vals = []
            while True:
                v = prompt(f"  Value {len(vals)+1} (blank to finish values): ")
                if not v:
                    break
                if v not in vals:
                    vals.append(v)
                else:
                    print("  Value already exists.")
                    
        try:
            model.add_parameter(pname, vals)
            print(f"Added parameter '{pname}' with {len(vals)} values.")
        except ValueError as e:
            print(f"Error: {e}")
            continue

def _print_summary(model: PairwiseModel):
    print("\nModel Summary:")
    for i, p in enumerate(model.parameters, 1):
        print(f" {i}. {p.display_name} ({len(p.values)} values): {', '.join(p.values)}")

def _menu_loop(model: PairwiseModel):
    while True:
        _print_summary(model)
        print("\nOptions:")
        print(" 1) Generate pairwise test suite")
        print(" 2) Edit a parameter")
        print(" 3) Delete a parameter")
        print(" 4) Restart wizard")
        print(" 5) Quit")
        
        choice = prompt("Choice (1-5): ")
        if choice == '1':
            _generate_and_present(model)
            break
        elif choice == '2':
            _edit_parameter(model)
        elif choice == '3':
            _delete_parameter(model)
        elif choice == '4':
            return
        elif choice == '5':
            sys.exit(0)
        else:
            print("Invalid choice.")
            
def _edit_parameter(model: PairwiseModel):
    idx_str = prompt("Parameter number to edit: ")
    try:
        idx = int(idx_str) - 1
        if idx < 0 or idx >= len(model.parameters):
            raise ValueError()
    except ValueError:
        print("Invalid number.")
        return
        
    p = model.parameters[idx]
    print(f"\nEditing: {p.display_name}")
    print(" 1) Rename parameter")
    print(" 2) Add value")
    print(" 3) Replace all values")
    
    c = prompt("Choice: ")
    if c == '1':
        new_name = prompt("New name: ")
        if new_name:
            p.display_name = new_name
    elif c == '2':
        v = prompt("New value: ")
        if v and v not in p.values:
            p.values.append(v)
    elif c == '3':
        vals_input = prompt("Enter all values comma-separated: ")
        if vals_input:
            vals = [v.strip() for v in vals_input.split(',')]
            vals = [v for v in vals if v]
            vals = list(dict.fromkeys(vals))
            if len(vals) >= 2:
                p.values = vals
            else:
                print("Need at least 2 values.")

def _delete_parameter(model: PairwiseModel):
    idx_str = prompt("Parameter number to delete: ")
    try:
        idx = int(idx_str) - 1
        model.parameters.pop(idx)
    except (ValueError, IndexError):
        print("Invalid number.")

def _generate_and_present(model: PairwiseModel):
    from . import EXIT_SUCCESS, EXIT_PICT_ERR, EXIT_VERIF_ERR, EXIT_TIMEOUT
    
    # Try validate limits first before bothering user
    try:
        model.validate_limits(max_params=50, max_values_per_param=50, max_total_values=500)
    except ValueError as e:
        print(f"\nModel Safety Violation: {e}")
        print("To override limits, please use the non-interective CLI 'generate' command.")
        return

    print("\nParameter ordering for generation:")
    print(" 1) Keep my order (as entered)")
    print(" 2) Auto-reorder (descending by #values) [Recommended]")
    o_choice = prompt("Choice (1-2) [default 2]: ")
    ordering = OrderingMode.KEEP if o_choice == '1' else OrderingMode.AUTO
    
    t_choice = prompt("Number of tries to find smallest suite (default 50): ")
    try:
        tries = int(t_choice) if t_choice else 50
    except ValueError:
        print("Invalid number, defaulting to 50.")
        tries = 50
        
    v_choice = prompt("Verify combinatorial pairwise coverage mathematically? (Y/n): ").lower()
    verify = False if v_choice == 'n' else True
    
    print("\nGenerating...")
    try:
        res = generate_suite(
            model,
            ordering_mode=ordering,
            tries=tries,
            verify=verify,
            require_verified=verify,
            verbose=True
        )
    except TimeoutError as e:
        print(f"Generation Timeout Error:\n{e}")
        sys.exit(EXIT_TIMEOUT)
    except GenerationVerificationError as e:
        print("Error: Could not generate a test suite that satisfies pairwise coverage.")
        for p in e.missing_pairs[:20]:
            print(f" Missing pair: {p}")
        sys.exit(EXIT_VERIF_ERR)
    except Exception as e:
        print(f"Error running generation:\n{e}")
        sys.exit(EXIT_PICT_ERR)
        
    n = len(res.rows)
    print_out = True
    
    if n > 100000:
        print(f"\nWarning: Generated dataset contains {n} rows, exceeding stdout display limits!")
        p_choice = prompt("Print to console anyway? (y/N): ").lower()
        if p_choice != 'y':
            print_out = False
            
    if print_out:
        print("-" * 60)
        print(format_table(res.canonical_headers, res.rows))
        print("-" * 60)
    print(f"Parameter Counts   : {', '.join(str(c) for c in model.get_counts())}")
    
    if res.ordering_mode == OrderingMode.AUTO:
        print(f"Ordering Mode      : Auto")
        print(f"Internal Reorder   : {', '.join(p.display_name for p in res.reordered_params)}")
    else:
        print(f"Ordering Mode      : Keep")
    print(f"Internal Reorder   : (Matches original)")
        
    print(f"Attempts Tried     : {res.attempts}")
    print(f"Best Seed Used     : {res.seed}")
    if res.lb is not None:
        print(f"Lower Bound (LB)   : {res.lb}")
    else:
        print("Lower Bound (LB)   : N/A")
    print(f"Generated Size (N) : {res.n}")
    
    if res.lb is not None and res.passed_verification and res.n == res.lb:
        print("Result: PROVABLY MINIMUM")
    elif res.passed_verification:
        print("Result: COVERAGE VERIFIED (NOT MINIMUM)")
    else:
        print("Result: COVERAGE NOT VERIFIED")
        
    print("-" * 60)
    
    s = prompt("\nSave model and cases to current directory? (y/N): ").lower()
    if s == 'y':
        m_path = "pairwise_model.pict"
        m_reordered_path = "pairwise_model.reordered.pict"
        c_path = "pairwise_cases.csv"
        
        with open(m_path, "w", encoding="utf-8") as f:
            for p in model.parameters:
                f.write(f"{p.display_name}: {', '.join(p.values)}\n")
                
        if res.ordering_mode == OrderingMode.AUTO:
            with open(m_reordered_path, "w", encoding="utf-8") as f:
                f.write(res.internal_pict_model_str)
            print(f"Saved: {m_path}, {m_reordered_path}, and {c_path}")
        else:
            print(f"Saved: {m_path} and {c_path}")
                
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(format_csv(res.canonical_headers, res.rows))
            
    sys.exit(0)
