# -*- coding: utf-8 -*-
"""
Exceptions for valid ComCat events that lack a requested scientific dataset.

Dataset absence is distinct from malformed successful content, which raises
``ValueError``, and from HTTP or transport failures handled by request code.
"""


class DatasetNotAvailableError(LookupError):
    """The event exists but lacks a dataset requested by the caller."""
