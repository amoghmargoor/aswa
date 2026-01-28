"""Main dialog for ASWA Teams bot."""
from botbuilder.dialogs import (
    ComponentDialog,
    DialogTurnResult,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.dialogs.prompts import TextPrompt, PromptOptions
from botbuilder.core import MessageFactory
import structlog

from .query_dialog import QueryDialog

logger = structlog.get_logger()


class MainDialog(ComponentDialog):
    """Main dialog that routes user input."""

    def __init__(self, query_dialog: QueryDialog):
        super(MainDialog, self).__init__(MainDialog.__name__)

        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(query_dialog)
        self.add_dialog(
            WaterfallDialog(
                "WFDialog",
                [
                    self.intro_step,
                    self.route_step,
                    self.final_step,
                ],
            )
        )

        self.initial_dialog_id = "WFDialog"

    async def intro_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Initial step to prompt user."""
        if step_context.options:
            # Already have input
            return await step_context.next(step_context.options)

        message_text = "How can I help you today? Ask me a question about your documents."
        prompt_message = MessageFactory.text(message_text, message_text)
        return await step_context.prompt(
            TextPrompt.__name__,
            PromptOptions(prompt=prompt_message),
        )

    async def route_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Route to appropriate dialog based on input."""
        user_input = step_context.result

        if not user_input:
            return await step_context.end_dialog()

        # Route to query dialog
        return await step_context.begin_dialog(QueryDialog.__name__, {"query": user_input})

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Final step."""
        return await step_context.end_dialog()
