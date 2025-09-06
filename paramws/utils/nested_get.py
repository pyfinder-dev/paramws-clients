# -*- coding: utf-8 -*-
"""
General nested accessor utility (dicts + lists) that supports dotted paths and 
bracket indices. This can be reused elsewhere in the codebase.

Example paths:
  "time"                          -> top-level key
  "features.time"                 -> nested dict path
  "features.0.properties.mag"     -> list index via dot-number
  "features[0].properties.time"   -> list index via bracket syntax
  "features[0]"                    -> top-level list indexing
"""

def nested_get(data, field_path, default=None, *, required=False):
    """Access *data* using a dotted path that can include list indices.

    Parameters
    ----------
    data : dict | list
        The nested structure to read from.
    field_path : str
        Dotted path; parts may include bracket indices like "name[2]".
    default : Any, optional
        Value returned if the path does not exist (unless *required*).
    required : bool, optional (keyword-only)
        If True, raise KeyError when the path is missing/invalid.
    """
    # Short-circuit: simple top-level key without dots/brackets
    if isinstance(field_path, str) and ("." not in field_path and "[" not in field_path):
        if isinstance(data, dict) and field_path in data:
            return data[field_path]
        if required:
            raise KeyError(f"Field '{field_path}' does not exist.")
        return default

    # Build path parts (allow bracket-only like 'features[0]')
    parts = field_path.split('.') if isinstance(field_path, str) and '.' in field_path else [field_path]
    cur = data
    n = len(parts)

    i = 0
    while i < n:
        raw = parts[i]

        # Extract optional bracket index: name[2]
        name = raw
        bracket_idx = None
        if isinstance(raw, str) and '[' in raw and raw.endswith(']'):
            name, idx_str = raw.split('[', 1)
            idx_str = idx_str[:-1]
            if idx_str.isdigit():
                bracket_idx = int(idx_str)
            else:
                if required:
                    raise KeyError(f"Invalid list index '{idx_str}' in path '{field_path}'.")
                return default

        # Step into dict by key
        if isinstance(cur, dict):
            if name in cur:
                cur = cur[name]
            else:
                if required:
                    raise KeyError(f"Field path '{field_path}' not found at '{name}'.")
                return default
        else:
            if required:
                raise KeyError(f"Field path '{field_path}' not found at segment '{name}'.")
            return default

        # If current value is a list, index into it
        if isinstance(cur, list):
            # 1) explicit bracket index provided at this segment
            if bracket_idx is not None:
                if 0 <= bracket_idx < len(cur):
                    cur = cur[bracket_idx]
                else:
                    if required:
                        raise KeyError(f"Index {bracket_idx} out of range at segment '{name}' for path '{field_path}'.")
                    return default
            # 2) allow dot-number in the NEXT segment (e.g., 'features.0.time')
            elif i + 1 < n and isinstance(parts[i + 1], str) and parts[i + 1].isdigit():
                idx = int(parts[i + 1])
                if 0 <= idx < len(cur):
                    cur = cur[idx]
                    i += 1  # consume numeric segment
                else:
                    if required:
                        raise KeyError(f"Index {idx} out of range at segment '{name}' for path '{field_path}'.")
                    return default
            # 3) fallback to first element if available
            else:
                if cur:
                    cur = cur[0]
                else:
                    if required:
                        raise KeyError(f"List at segment '{name}' is empty for path '{field_path}'.")
                    return default

        i += 1

    return cur
