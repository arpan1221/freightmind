"""Draft reply generator.

Produces an amendment request or approval confirmation email that CG can
edit before sending. The agent never sends autonomously — it only drafts.
"""

import logging

from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

logger = logging.getLogger(__name__)


class VerificationDrafter:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    async def generate(
        self,
        field_results: list,
        overall_status: str,
        rules_config: dict,
    ) -> str:
        """Generate a draft reply email for the CG user to review and edit.

        For amendment_required or uncertain: structured list of discrepancies.
        For approved: concise approval confirmation.
        The agent never sends — CG must confirm before any action is taken.
        """
        customer_name = rules_config.get("customer_name", "Customer")

        if overall_status in ("amendment_required", "uncertain"):
            return await self._draft_amendment(field_results, customer_name)
        elif overall_status == "approved":
            return await self._draft_approval(field_results, customer_name)
        else:
            # failed — return a canned error notice
            return (
                "Dear Shipping Unit,\n\n"
                "We were unable to process your submitted document due to a technical error. "
                "Please resubmit your documents or contact support if the issue persists.\n\n"
                "Regards,\nCargo Control Group"
            )

    async def _draft_amendment(self, field_results: list, customer_name: str) -> str:
        discrepancies = [r for r in field_results if r.status in ("mismatch", "uncertain")]

        discrepancy_lines = []
        for r in discrepancies:
            status_label = "MISMATCH" if r.status == "mismatch" else "UNCERTAIN (needs manual review)"
            discrepancy_lines.append(
                f"- Field: {r.name}\n"
                f"  Extracted: {r.extracted or 'not found'}\n"
                f"  Expected:  {r.expected or 'N/A'}\n"
                f"  Status:    {status_label}\n"
                f"  Rule:      {r.rule_description or 'N/A'}"
            )

        discrepancy_block = "\n".join(discrepancy_lines)

        system_prompt = load_prompt("verification_draft")
        user_prompt = (
            f"Customer: {customer_name}\n"
            f"Overall status: Amendment Required\n\n"
            f"Discrepancies found:\n{discrepancy_block}\n\n"
            "Generate a professional amendment request email from CG to SU. "
            "List each discrepancy with the field name, what was found, and what is required. "
            "Be specific and actionable. Do not include a subject line — body only. "
            "End with 'Regards, Cargo Control Group'."
        )

        try:
            from app.core.config import settings

            draft = await self._client.call(
                model=settings.analytics_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                validate=None,
            )
            return draft.strip()
        except Exception as e:
            logger.warning("Draft generation failed, using fallback template: %s", e)
            return self._fallback_amendment(discrepancy_lines, customer_name)

    async def _draft_approval(self, field_results: list, customer_name: str) -> str:
        matched = [r for r in field_results if r.status == "match"]
        system_prompt = load_prompt("verification_draft")
        user_prompt = (
            f"Customer: {customer_name}\n"
            f"Overall status: Approved\n"
            f"Fields verified and matched: {', '.join(r.name for r in matched)}\n\n"
            "Generate a concise approval confirmation email from CG to SU. "
            "Confirm all documents are in order and cleared for processing. "
            "Do not include a subject line — body only. "
            "End with 'Regards, Cargo Control Group'."
        )

        try:
            from app.core.config import settings

            draft = await self._client.call(
                model=settings.analytics_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                validate=None,
            )
            return draft.strip()
        except Exception as e:
            logger.warning("Approval draft generation failed, using fallback: %s", e)
            return self._fallback_approval(customer_name)

    @staticmethod
    def _fallback_amendment(discrepancy_lines: list[str], customer_name: str) -> str:
        body = "\n\n".join(discrepancy_lines)
        return (
            f"Dear Shipping Unit,\n\n"
            f"We have reviewed the shipping documents submitted for {customer_name} "
            f"and identified the following discrepancies that require correction "
            f"before we can proceed:\n\n"
            f"{body}\n\n"
            f"Please resubmit the corrected documents at your earliest convenience.\n\n"
            f"Regards,\nCargo Control Group"
        )

    @staticmethod
    def _fallback_approval(customer_name: str) -> str:
        return (
            f"Dear Shipping Unit,\n\n"
            f"We have reviewed the shipping documents submitted for {customer_name} "
            f"and confirm that all fields are in order and match the required specifications.\n\n"
            f"The shipment is cleared for processing.\n\n"
            f"Regards,\nCargo Control Group"
        )
