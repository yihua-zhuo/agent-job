"""AI Draft service — generates email/SMS drafts via AIChatGateway."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from internal.ai_gateway import AIChatGateway, AIResponse
from models.ai_draft import DraftRequest, DraftResponse, SuggestedAction
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class AiDraftService:
    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        self.session = session
        self.gateway = gateway or AIChatGateway()

    async def generate_draft(self, request: DraftRequest, tenant_id: int) -> DraftResponse:
        """Generate a draft using the AI gateway and return structured content."""
        # Verify customer exists
        result = await self.session.execute(
            select(CustomerModel).where(
                CustomerModel.id == request.context.customer_id,
                CustomerModel.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundException("Customer")

        messages = await self._build_prompt(request, tenant_id)
        response: AIResponse = await self.gateway.chat(messages)

        if not response.reply or not response.reply.strip():
            raise ValidationException("AI gateway returned empty content")

        suggested_actions = [
            SuggestedAction(
                label=action.get("label", ""),
                action_type=action.get("type", ""),
                payload=action,
            )
            for action in (response.actions or [])
        ]

        return DraftResponse(body=response.reply, suggested_actions=suggested_actions)

    async def _build_prompt(self, request: DraftRequest, tenant_id: int) -> list[dict[str, str]]:
        """Build the messages list for the AI gateway."""
        system_prompt = (
            "You are an AI assistant that generates professional email and SMS drafts for a CRM system. "
            "Given the draft type, tone, and customer context, produce a high-quality draft body "
            "and suggest relevant actions. Respond only with the draft content and actions."
        )

        subject_line = f"\nSubject: {request.subject}" if request.type.value == "email" and request.subject else ""
        tone_line = f"Tone: {request.tone.value}"
        draft_type_line = f"Draft type: {request.type.value}"
        context_lines = [
            f"Customer ID: {request.context.customer_id}",
            f"Template type: {request.context.template_type.value}",
        ]
        if request.context.opportunity_id is not None:
            context_lines.append(f"Opportunity ID: {request.context.opportunity_id}")

        user_message = (
            f"Generate a {request.type.value} draft.\n"
            f"{draft_type_line}{subject_line}\n"
            f"{tone_line}\n"
            f"Context:\n" + "\n".join(context_lines)
        )

        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
