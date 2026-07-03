"""A deterministic, zero-LLM user stub for tau-bench oracle replays.

tau-bench's default user simulator (UserStrategy.LLM) calls litellm.completion() inside
its __init__ -- a model call at construction time. NullUser replaces it so no model call
can occur: reset() returns the instruction, step() ends the conversation with '###STOP###',
and get_total_cost() returns 0. It duck-types tau_bench.envs.user.BaseUserSimulationEnv.
"""
from __future__ import annotations
from typing import Optional


class NullUser:
    """reset -> instruction; step -> '###STOP###'; get_total_cost -> 0.0.

    Note on the '###STOP###' contract: this is the episode-end signal the agent's own
    `respond` turn should elicit. tau-bench retail ground-truth `task.actions` contain no
    `respond` actions, so the reward oracle's internal replay never calls step() here (which
    would otherwise recurse via done=True). That invariant is asserted in the self-tests.
    """

    metadata: dict = {}

    def __init__(self) -> None:
        self.instruction: Optional[str] = None
        self.messages: list = []

    def reset(self, instruction: Optional[str] = None) -> str:
        self.instruction = instruction
        self.messages = []
        return instruction if instruction is not None else ""

    def step(self, content: str) -> str:
        self.messages.append(content)
        return "###STOP###"

    def get_total_cost(self) -> float:
        return 0.0
