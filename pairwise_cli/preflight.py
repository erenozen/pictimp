"""Shared structural preflight validation for generation paths."""
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    message: str
    field: Optional[str] = None


@dataclass
class PreflightReport:
    issues: List[PreflightIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def validate_generation_preflight(
    model: Any,
    max_params: int = 50,
    max_values_per_param: int = 50,
    max_total_values: int = 500,
) -> PreflightReport:
    """Validates structural generation preconditions without raising."""
    report = PreflightReport()
    seen_keys = set()

    def add_issue(code: str, message: str, field_name: Optional[str] = None) -> None:
        key = (code, field_name)
        if key in seen_keys:
            return
        seen_keys.add(key)
        report.issues.append(PreflightIssue(code=code, message=message, field=field_name))

    if model is None:
        add_issue("model_missing", "Input Error: Model is missing.", "model")
        return report

    params = getattr(model, "parameters", None)
    if params is None:
        add_issue("model_malformed", "Input Error: Model is malformed (missing parameters).", "model.parameters")
        return report

    if isinstance(params, (str, bytes)):
        add_issue("model_malformed", "Input Error: Model is malformed (invalid parameters container).", "model.parameters")
        return report

    if not isinstance(params, (list, tuple)):
        try:
            params = list(params)
        except TypeError:
            add_issue("model_malformed", "Input Error: Model is malformed (invalid parameters container).", "model.parameters")
            return report

    param_count = len(params)
    if param_count < 2:
        add_issue("too_few_params", "Input Error: At least 2 parameters are required.", "model.parameters")
    if param_count > max_params:
        add_issue(
            "limit_max_params",
            f"Model Safety Violation: Model has {param_count} parameters, exceeding limit of {max_params}.",
            "model.parameters",
        )

    seen_param_names = set()
    total_values = 0

    for p_idx, param in enumerate(params):
        p_field = f"model.parameters[{p_idx}]"
        name = getattr(param, "display_name", None)
        if not isinstance(name, str) or not name.strip():
            add_issue("empty_param_name", f"Input Error: Parameter #{p_idx + 1} has an empty name.", f"{p_field}.display_name")
            name_key = None
        else:
            name_key = name.strip().lower()
            if name_key in seen_param_names:
                add_issue(
                    "duplicate_param_name",
                    f"Input Error: Duplicate parameter name detected: '{name.strip()}'.",
                    f"{p_field}.display_name",
                )
            else:
                seen_param_names.add(name_key)

        values = getattr(param, "values", None)
        if values is None or isinstance(values, (str, bytes)):
            add_issue(
                "values_missing",
                f"Input Error: Parameter #{p_idx + 1} has an invalid values list.",
                f"{p_field}.values",
            )
            continue

        if not isinstance(values, (list, tuple)):
            try:
                values = list(values)
            except TypeError:
                add_issue(
                    "values_missing",
                    f"Input Error: Parameter #{p_idx + 1} has an invalid values list.",
                    f"{p_field}.values",
                )
                continue

        value_count = len(values)
        total_values += value_count

        if value_count < 2:
            add_issue(
                "too_few_values",
                f"Input Error: Parameter #{p_idx + 1} must have at least 2 values.",
                f"{p_field}.values",
            )
        if value_count > max_values_per_param:
            add_issue(
                "limit_max_values_per_param",
                (
                    f"Model Safety Violation: Parameter #{p_idx + 1} has {value_count} values, "
                    f"exceeding limit of {max_values_per_param}."
                ),
                f"{p_field}.values",
            )

        seen_values = set()
        for v_idx, value in enumerate(values):
            v_field = f"{p_field}.values[{v_idx}]"
            if not isinstance(value, str) or not value.strip():
                add_issue("empty_value", f"Input Error: Parameter #{p_idx + 1} contains an empty value.", v_field)
                continue

            lower_value = value.strip().lower()
            if lower_value in seen_values:
                add_issue(
                    "duplicate_value",
                    (
                        f"Input Error: Parameter #{p_idx + 1} contains duplicate values "
                        "(case-insensitive)."
                    ),
                    f"{p_field}.values",
                )
            else:
                seen_values.add(lower_value)

    if total_values > max_total_values:
        add_issue(
            "limit_max_total_values",
            f"Model Safety Violation: Model has {total_values} total values, exceeding limit of {max_total_values}.",
            "model.parameters",
        )

    return report
