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
    if not isinstance(field_path, str) or not field_path:
        if required:
            raise KeyError(f"Invalid field path '{field_path}'.")
        return default

    parts = field_path.split('.')
    cur = data
    for raw in parts:
        if not raw:
            if required:
                raise KeyError(f"Invalid empty segment in path '{field_path}'.")
            return default

        name = raw
        bracket_idx = None
        if '[' in raw:
            if not raw.endswith(']') or raw.count('[') != 1:
                if required:
                    raise KeyError(f"Malformed list access in path '{field_path}'.")
                return default

            name, idx_str = raw[:-1].split('[', 1)
            if not name or not idx_str.isdigit():
                if required:
                    raise KeyError(
                        f"Invalid list index '{idx_str}' in path '{field_path}'."
                    )
                return default
            bracket_idx = int(idx_str)

        if isinstance(cur, dict):
            if name in cur:
                cur = cur[name]
            else:
                if required:
                    raise KeyError(f"Field path '{field_path}' not found at '{name}'.")
                return default
        elif isinstance(cur, list) and raw.isdigit():
            idx = int(raw)
            if idx < len(cur):
                cur = cur[idx]
            else:
                if required:
                    raise KeyError(
                        f"Index {idx} out of range for path '{field_path}'."
                    )
                return default
        else:
            if required:
                raise KeyError(
                    f"Cannot access segment '{raw}' in path '{field_path}'."
                )
            return default

        # A list is traversed only when the path supplies its non-negative index.
        if bracket_idx is not None:
            if isinstance(cur, list) and bracket_idx < len(cur):
                cur = cur[bracket_idx]
            else:
                if required:
                    if isinstance(cur, list):
                        raise KeyError(
                            f"Index {bracket_idx} out of range for path "
                            f"'{field_path}'."
                        )
                    raise KeyError(
                        f"Value at '{name}' is not a list in path '{field_path}'."
                    )
                return default

    return cur
