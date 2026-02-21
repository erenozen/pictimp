"""Interactive wizard flow."""
import sys
from .model import PairwiseModel
from .output import format_table, format_csv
from .generate import generate_suite, OrderingMode, GenerationVerificationError
from .preflight import validate_generation_preflight


class WizardCancelled(Exception):
    """Raised when interactive input is cancelled by user."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason

def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError as e:
        raise WizardCancelled("eof") from e
    except KeyboardInterrupt as e:
        raise WizardCancelled("interrupt") from e

def run_wizard():
    try:
        print("Welcome to Pairwise-CLI!")
        print("This tool uses Microsoft PICT to generate pairwise (2-way) combinatorial test suites.")
        print("When strength=2, it can verify if the output achieves the theoretical minimum test count.")
        print("You can exit anytime with Ctrl+C.")
        print("Parameter: a configurable category being tested (example: Display Mode).")
        print("Value: one option under a parameter (examples: full-graphics, text-only, limited-bandwith).")
        print("-" * 60)
        
        while True:
            model = PairwiseModel()
            _gather_parameters(model)
            
            if len(model.parameters) < 2:
                print("Need at least 2 parameters for pairwise generation. Exiting.")
                return

            action = _menu_loop(model)
            if action == "restart":
                continue
            if action == "generated":
                again = prompt("\nWould you like to try another set of values? (y/N): ").lower()
                if again == "y":
                    continue
                return
            return
    except WizardCancelled as e:
        if e.reason == "eof":
            print("\nInput cancelled (EOF).")
        else:
            print("\nCancelled by user.")
        return


def _parse_comma_values(values_input: str):
    raw_parts = values_input.split(",")
    if any(not part.strip() for part in raw_parts):
        return None, "Malformed value list: values cannot be empty. Remove trailing or repeated commas."
    values = [part.strip() for part in raw_parts]
    return values, None

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
            vals, parse_error = _parse_comma_values(vals_input)
            if parse_error:
                print(f"Error: {parse_error}")
                continue
        else:
            vals = []
            seen = set()
            while True:
                v = prompt(f"  Value {len(vals)+1} (blank to finish values): ")
                if not v:
                    break
                v_key = v.lower()
                if v_key in seen:
                    print("  Value already exists (case-insensitive).")
                    continue
                seen.add(v_key)
                vals.append(v)
                    
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
            if _generate_and_present(model):
                return "generated"
            continue
        elif choice == '2':
            _edit_parameter(model)
        elif choice == '3':
            _delete_parameter(model)
        elif choice == '4':
            return "restart"
        elif choice == '5':
            return "quit"
        else:
            print("Invalid choice.")
            
def _edit_parameter(model: PairwiseModel):
    idx_str = prompt("Parameter number to edit: ")
    try:
        idx = int(idx_str)
        if idx <= 0 or idx > len(model.parameters):
            raise ValueError()
        idx -= 1
    except ValueError:
        print("Input Error: Invalid parameter number.")
        return
        
    p = model.parameters[idx]
    print(f"\nEditing: {p.display_name}")
    print(" 1) Rename parameter")
    print(" 2) Add value")
    print(" 3) Replace all values")
    
    c = prompt("Choice: ")
    if c == '1':
        new_name = prompt("New name: ")
        if not new_name:
            print("Input Error: Parameter name cannot be empty.")
            return
        existing = {x.display_name.lower() for i, x in enumerate(model.parameters) if i != idx}
        if new_name.lower() in existing:
            print(f"Input Error: Duplicate parameter name detected: '{new_name}'.")
            return
        p.display_name = new_name
    elif c == '2':
        v = prompt("New value: ")
        if not v:
            print("Input Error: Value cannot be empty.")
            return
        if ',' in v or '\t' in v or '\n' in v:
            print("Input Error: Value contains invalid characters (comma, tab, newline).")
            return
        existing_values = {x.lower() for x in p.values}
        if v.lower() in existing_values:
            print(f"Input Error: Duplicate value detected: '{v}'.")
            return
        p.values.append(v)
    elif c == '3':
        vals_input = prompt("Enter all values comma-separated: ")
        if vals_input:
            vals, parse_error = _parse_comma_values(vals_input)
            if parse_error:
                print(f"Input Error: {parse_error}")
                return
            lower_vals = set()
            for val in vals:
                if ',' in val or '\t' in val or '\n' in val:
                    print("Input Error: Value contains invalid characters (comma, tab, newline).")
                    return
                key = val.lower()
                if key in lower_vals:
                    print(f"Input Error: Duplicate value detected: '{val}'.")
                    return
                lower_vals.add(key)
            if len(vals) < 2:
                print("Input Error: Need at least 2 values.")
                return
            p.values = vals
        else:
            print("Input Error: Value list cannot be empty.")
    else:
        print("Input Error: Invalid edit choice.")

def _delete_parameter(model: PairwiseModel):
    idx_str = prompt("Parameter number to delete: ")
    try:
        idx = int(idx_str)
        if idx <= 0 or idx > len(model.parameters):
            raise ValueError()
        idx -= 1
        model.parameters.pop(idx)
    except (ValueError, IndexError):
        print("Input Error: Invalid parameter number.")

def _generate_and_present(model: PairwiseModel):
    preflight = validate_generation_preflight(
        model,
        max_params=50,
        max_values_per_param=50,
        max_total_values=500
    )
    if not preflight.ok:
        print("\nInput Error:")
        for issue in preflight.issues:
            print(f" - {issue.message}")
        return False

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
        return False
    except GenerationVerificationError as e:
        print("Error: Could not generate a test suite that satisfies pairwise coverage.")
        for p in e.missing_pairs[:20]:
            print(f" Missing pair: {p}")
        return False
    except Exception as e:
        print(f"Error running generation:\n{e}")
        return False
        
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
        m_path = "pairwise_model.txt"
        m_reordered_path = "pairwise_model.reordered.txt"
        c_path = "pairwise_cases.txt"

        try:
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
        except OSError as e:
            print(f"Save Error: {e}")
            return False

    return True
