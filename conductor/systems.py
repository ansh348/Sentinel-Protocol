"""S1-S5 configuration table (locked decision #5: conductor configuration, not
separate codebases). S1/S5 are exercised in M3; S2-S4 wire up in M4."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SystemConfig:
    id: str
    description: str
    tripwires_enabled: bool          # compile a TripwireSet and arm the matcher
    judge_enabled: bool              # escalations pass the judge tier
    escalate_any_anomaly: bool       # S2: workers escalate anomalies, no tripwires
    revalidation_every_k: Optional[int]  # S3: orchestrator revalidation cadence
                                         # (cost-matched per task; set at runtime)


SYSTEMS: dict[str, SystemConfig] = {
    "S1": SystemConfig("S1", "Batch: dispatch all, wait, aggregate; one redo round",
                       tripwires_enabled=False, judge_enabled=False,
                       escalate_any_anomaly=False, revalidation_every_k=None),
    "S2": SystemConfig("S2", "Naive interrupt: any anomaly straight to orchestrator",
                       tripwires_enabled=False, judge_enabled=False,
                       escalate_any_anomaly=True, revalidation_every_k=None),
    "S3": SystemConfig("S3", "Heartbeat: periodic revalidation, no tripwires",
                       tripwires_enabled=False, judge_enabled=False,
                       escalate_any_anomaly=False, revalidation_every_k=0),
    "S4": SystemConfig("S4", "Sentinel without judge: fires straight to orchestrator",
                       tripwires_enabled=True, judge_enabled=False,
                       escalate_any_anomaly=False, revalidation_every_k=None),
    "S5": SystemConfig("S5", "Sentinel Protocol: compile + match + judge + routing",
                       tripwires_enabled=True, judge_enabled=True,
                       escalate_any_anomaly=False, revalidation_every_k=None),
}
