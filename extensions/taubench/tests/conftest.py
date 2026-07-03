"""Test-suite conftest for the tau-bench fault-injection harness.

Installs the ZERO-LLM guard (STEP 4): a litellm.completion stub that RAISES, bound BEFORE
tau_bench.envs.user resolves `from litellm import completion`, so no model call anywhere in
the harness or its tests can escape unnoticed. Also puts the repo root on sys.path.
"""
from __future__ import annotations

import os
import sys

import pytest

# Repo root = extensions/taubench/tests -> ../../.. ; ensure `import extensions...` resolves.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# --------------------------------------------------------------- zero-LLM guard
import litellm  # noqa: E402


class LLMCallBlocked(RuntimeError):
    """Raised if any code attempts an LLM completion during the zero-LLM test suite."""


_GUARD = {"attempts": 0}


def _blocked_completion(*args, **kwargs):
    _GUARD["attempts"] += 1
    raise LLMCallBlocked(
        "litellm.completion() is blocked: the tau-bench harness test suite is zero-LLM."
    )


# Patch the litellm entry point first, THEN import tau_bench's user module so its top-level
# `from litellm import completion` binds to the raiser. Re-bind on the module too, so no
# import-order window can escape the guard.
litellm.completion = _blocked_completion
import tau_bench.envs.user as _user_mod  # noqa: E402

_user_mod.completion = _blocked_completion


@pytest.fixture
def llm_guard():
    """The zero-LLM guard state: {'attempts': N}. N counts blocked completion attempts."""
    return _GUARD


def attempt_blocked_completion():
    """Call the (blocked) litellm.completion; always raises LLMCallBlocked. For tests."""
    return litellm.completion(model="none", messages=[])
