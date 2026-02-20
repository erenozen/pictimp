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
        safe_name = make_safe_name(display_name, self._safe_name_cache)
        self._safe_name_cache.add(safe_name)
        
        param = Parameter(display_name, values, safe_name)
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
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
                
            name_part, vals_part = line.split(':', 1)
            name = name_part.strip()
            values = [v.strip() for v in vals_part.split(',') if v.strip()]
            
            if values:
                param = model.add_parameter(name, values)
                param.display_name = name
                
        return model
