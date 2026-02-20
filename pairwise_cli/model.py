"""Defines the pairwise model, parameters, and serialization."""
from typing import List, Dict, Set
from .util import make_safe_name

class Parameter:
    def __init__(self, display_name: str, values: List[str], safe_name: str = ""):
        self.display_name = display_name
        self.values = values
        self.safe_name = safe_name

class PairwiseModel:
    def __init__(self):
        self.parameters: List[Parameter] = []
        self._safe_name_cache: Set[str] = set()
        
    def add_parameter(self, display_name: str, values: List[str]) -> Parameter:
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Parameter name cannot be empty.")
        
        # Check unique parameter names (case-insensitive)
        existing_lower = {p.display_name.lower() for p in self.parameters}
        if display_name.lower() in existing_lower:
            raise ValueError(f"Duplicate parameter name detected: '{display_name}'")
            
        cleaned_values = []
        seen_values = set()
        for v in values:
            v_clean = v.strip()
            if not v_clean:
                raise ValueError(f"Parameter '{display_name}' contains an empty value.")
            if ',' in v_clean or '\t' in v_clean or '\n' in v_clean:
                raise ValueError(f"Parameter '{display_name}' value '{v_clean}' contains invalid characters (comma, tab, newline).")
            v_lower = v_clean.lower()
            if v_lower in seen_values:
                raise ValueError(f"Parameter '{display_name}' contains duplicate value (case-insensitive): '{v_clean}'")
            seen_values.add(v_lower)
            cleaned_values.append(v_clean)
            
        if len(cleaned_values) < 2:
            raise ValueError(f"Parameter '{display_name}' must have at least 2 distinct values.")

        safe_name = make_safe_name(display_name, self._safe_name_cache)
        self._safe_name_cache.add(safe_name)
        
        param = Parameter(display_name, cleaned_values, safe_name)
        self.parameters.append(param)
        return param
        
    def get_counts(self) -> List[int]:
        return [len(p.values) for p in self.parameters]
        
    def to_pict_model(self, parameters: List[Parameter] = None) -> str:
        params = parameters if parameters is not None else self.parameters
        lines = []
        for p in params:
            vals_str = ", ".join(p.values)
            lines.append(f"{p.safe_name}: {vals_str}")
        return "\n".join(lines) + "\n"
        
    def get_reordered_parameters(self) -> List[Parameter]:
        """Returns parameters sorted by value count descending, stable tie-break."""
        return sorted(self.parameters, key=lambda p: len(p.values), reverse=True)
        
    def get_safe_to_display_map(self) -> Dict[str, str]:
        return {p.safe_name: p.display_name for p in self.parameters}

    @classmethod
    def from_pict_model(cls, content: str) -> "PairwiseModel":
        model = cls()
        for i, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            if ':' not in line:
                raise ValueError(f"Line {i}: Missing colon in parameter definition: '{line}'")
                
            name_part, vals_part = line.split(':', 1)
            name = name_part.strip()
            if not name:
                raise ValueError(f"Line {i}: Parameter name is empty.")
                
            values = [v.strip() for v in vals_part.split(',')]
            # add_parameter handles empty value checks, duplicate checks, etc.
            try:
                model.add_parameter(name, values)
            except ValueError as e:
                raise ValueError(f"Line {i}: {str(e)}")
                
        if len(model.parameters) < 2:
             raise ValueError("Model must contain at least 2 parameters.")
                
        return model

    def validate_limits(self, max_params: int = 50, max_values_per_param: int = 50, max_total_values: int = 500):
        """Throws ValueError if model size exceeds limits."""
        if len(self.parameters) > max_params:
            raise ValueError(f"Model has {len(self.parameters)} parameters, exceeding limit of {max_params}. Use --max-params to override.")
            
        total_vals = 0
        for p in self.parameters:
            count = len(p.values)
            if count > max_values_per_param:
                 raise ValueError(f"Parameter '{p.display_name}' has {count} values, exceeding limit of {max_values_per_param}. Use --max-values-per-param to override.")
            total_vals += count
            
        if total_vals > max_total_values:
            raise ValueError(f"Model has {total_vals} total values, exceeding limit of {max_total_values}. Use --max-total-values to override.")
