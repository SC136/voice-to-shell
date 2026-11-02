"""
Safety and Human-in-the-Loop Confirmation Gate
Replicates Section III-A & Fig. 1 of IEEE JIOT 2026 paper:
- Analyzes command intent and assigns safety risk level
- Categorizes commands into SAFE (read-only), MEDIUM (state change), HIGH (destructive)
- Generates transparent, human-readable explanations of the intended action
- Enforces user verification before terminal execution
"""

from enum import Enum
from typing import Dict, Any, Tuple


class RiskLevel(str, Enum):
    SAFE = "SAFE"            # Read-only queries, telemetry, status inspections
    MEDIUM = "MEDIUM"        # Normal state transitions, setting brightness/labels
    CRITICAL = "CRITICAL"    # Destructive removals, process kills, system flushes


class CommandSafetyAnalyzer:
    """Classifies command risks and generates human-friendly action summaries."""

    CRITICAL_PATTERNS = [
        "docker rm", "docker rmi", "docker kill", "docker system prune",
        "purge_luminaires", "reset_mesh", "delete_luminaire", "delete_group",
        "delete_test", "rm -rf", "kill -9"
    ]

    SAFE_VERBS = [
        "info", "status", "get_", "docker inspect", "docker ps", "docker images",
        "docker logs", "docker volume ls", "help", "zwp"
    ]

    @classmethod
    def evaluate(cls, command: str) -> Dict[str, Any]:
        cmd = command.strip().lower()

        # Check for critical / destructive actions
        for pattern in cls.CRITICAL_PATTERNS:
            if pattern in cmd:
                return {
                    "risk_level": RiskLevel.CRITICAL,
                    "explanation": f"Destructive command detected ({pattern}). This operation modifies permanent state or terminates processes.",
                    "requires_confirmation": True,
                    "warning": "CRITICAL: Potential data loss or service disruption."
                }

        # Check for safe read-only queries
        for safe in cls.SAFE_VERBS:
            if cmd.startswith(safe):
                return {
                    "risk_level": RiskLevel.SAFE,
                    "explanation": "Read-only inspection or telemetry query. Does not alter system configuration.",
                    "requires_confirmation": False,
                    "warning": None
                }

        # Default is medium risk (configuration changes, turning lights on/off, starting containers)
        return {
            "risk_level": RiskLevel.MEDIUM,
            "explanation": "Operational state change or device configuration update.",
            "requires_confirmation": True,
            "warning": "Notice: This will alter active system parameters."
        }
