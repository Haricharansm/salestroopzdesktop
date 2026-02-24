from app.llm.ollama_client import generate_json
from app.agent.prompts import (
    prompt_positioning,
    prompt_messaging,
    prompt_sequence,
)


class StrategyAgent:
    """
    THINKING layer only.
    Responsible for:
    - Positioning
    - Messaging themes
    - Campaign strategy
    - Sequence plan (blueprint only)
    """

    # ---------------------------------------------------
    # Strategy Generation
    # ---------------------------------------------------

    async def generate_positioning(self, offering: dict, icp: dict) -> dict:
        return generate_json(
            prompt_positioning(offering, icp),
            num_predict=512,
        )

    async def generate_messaging(self, offering: dict, icp: dict, positioning: dict) -> dict:
        return generate_json(
            prompt_messaging(offering, icp, positioning),
            num_predict=512,
        )

    async def generate_sequence(self, offering: dict, icp: dict, positioning: dict, messaging: dict) -> dict:
        return generate_json(
            prompt_sequence(offering, icp, positioning, messaging),
            num_predict=2048,
        )

    # ---------------------------------------------------
    # Strategy Storage Format
    # ---------------------------------------------------

    def compose_campaign_strategy(
        self,
        offering: dict,
        icp: dict,
        positioning: dict,
        messaging: dict,
        sequence_plan: dict,
    ) -> dict:
        return {
            "schema_version": "1.0",
            "inputs": {"offering": offering, "icp": icp},
            "positioning": positioning,
            "messaging": messaging,
            "sequence_plan": sequence_plan,
            "guardrails": {
                "compliance": [
                    "no false claims",
                    "honor opt-out immediately",
                ]
            },
        }

    # ---------------------------------------------------
    # Convert Strategy → Runner JSON
    # ---------------------------------------------------

    def to_runner_sequence_json(self, sequence_plan: dict) -> dict:
        """
        Converts strategy blueprint into runner-executable format.

        NOTE:
        Strategy blueprint should NOT contain full email bodies.
        Runner will generate actual email copy later.
        """
        steps = []
        templates = {}

        for idx, step in enumerate(sequence_plan.get("steps", []), start=1):
            sid = step.get("step_id") or f"S{idx}"

            templates[sid] = {
                "template_type": step.get("template_type"),
                "objective": step.get("objective"),
                "key_points": step.get("key_points", []),
                "cta": step.get("cta"),
            }

            steps.append(
                {
                    "step_id": sid,
                    "type": "send_email",
                    "channel": step.get("channel", "email"),
                    "delay_days": int(step.get("day_offset", 0)),
                    "template_key": sid,
                    "stop_if": ["replied", "bounced", "unsubscribed"],
                }
            )

        return {"schema_version": "1.0", "steps": steps, "templates": templates}

    # ---------------------------------------------------
    # Default Execution Config
    # ---------------------------------------------------

    def default_run_config(self) -> dict:
        return {
            "schema_version": "1.0",
            "timezone": "America/Chicago",
            "quiet_hours": {"start": "20:00", "end": "08:00"},
            "daily_send_limit": 50,
            "max_concurrent_leads": 10,
            "min_minutes_between_sends": 2,
            "allowed_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        }
