"""Parses PICT TSV output and formats it."""
import csv
import io
import json
from typing import List, Dict, Tuple

class PictOutputParser:
    @staticmethod
    def parse_tsv(content: str, safe_to_display: Dict[str, str], canonical_headers: List[str] = None) -> Tuple[List[str], List[List[str]]]:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            if canonical_headers:
                return canonical_headers, []
            return [], []

        raw_headers = lines[0].split('\t')
        display_headers = [safe_to_display.get(h, h) for h in raw_headers]
        
        rows = []
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) < len(display_headers):
                parts.extend([''] * (len(display_headers) - len(parts)))
            elif len(parts) > len(display_headers):
                parts = parts[:len(display_headers)]
            rows.append(parts)
            
        if canonical_headers:
            header_idx = {h: i for i, h in enumerate(display_headers)}
            reordered_rows = []
            for row in rows:
                new_row = []
                for ch in canonical_headers:
                    if ch in header_idx:
                        new_row.append(row[header_idx[ch]])
                    else:
                        new_row.append("")
                reordered_rows.append(new_row)
            return canonical_headers, reordered_rows
            
        return display_headers, rows

def format_table(headers: List[str], rows: List[List[str]]) -> str:
    if not headers:
        return ""
    
    widths = [len(h) for h in headers]
    for row in rows:
        for col_idx, val in enumerate(row):
            widths[col_idx] = max(widths[col_idx], len(val))
            
    header_str = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    lines = [header_str]
    for row in rows:
        lines.append("  ".join(v.ljust(w) for v, w in zip(row, widths)))
        
    return "\n".join(lines)

def format_csv(headers: List[str], rows: List[List[str]]) -> str:
    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)
    return f.getvalue()

def format_json(headers: List[str], rows: List[List[str]]) -> str:
    result = []
    for row in rows:
        obj = {headers[i]: v for i, v in enumerate(row)}
        result.append(obj)
    return json.dumps(result, indent=2)
