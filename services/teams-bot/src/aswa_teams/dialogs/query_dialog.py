"""Query dialog for processing user queries."""
from botbuilder.dialogs import (
    ComponentDialog,
    DialogTurnResult,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.dialogs.prompts import TextPrompt, PromptOptions, ConfirmPrompt
from botbuilder.core import MessageFactory
import structlog

logger = structlog.get_logger()


class QueryDialog(ComponentDialog):
    """Dialog for handling document queries."""

    def __init__(self):
        super(QueryDialog, self).__init__(QueryDialog.__name__)

        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))
        self.add_dialog(
            WaterfallDialog(
                "QueryWFDialog",
                [
                    self.process_query_step,
                    self.follow_up_step,
                    self.handle_follow_up_step,
                ],
            )
        )

        self.initial_dialog_id = "QueryWFDialog"

    async def process_query_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Process the query."""
        options = step_context.options or {}
        query = options.get("query", "")

        if not query:
            return await step_context.end_dialog()

        # Store query in step values
        step_context.values["query"] = query

        # The actual query processing is done in the bot handler
        # This dialog handles the conversation flow

        # Ask if user wants to refine
        return await step_context.prompt(
            ConfirmPrompt.__name__,
            PromptOptions(
                prompt=MessageFactory.text("Would you like to ask a follow-up question?"),
            ),
        )

    async def follow_up_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Handle follow-up decision."""
        if step_context.result:
            # User wants follow-up
            return await step_context.prompt(
                TextPrompt.__name__,
                PromptOptions(
                    prompt=MessageFactory.text("What would you like to know?"),
                ),
            )
        return await step_context.end_dialog()

    async def handle_follow_up_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Handle the follow-up query."""
        follow_up = step_context.result

        if follow_up:
            # Restart dialog with new query
            return await step_context.replace_dialog(
                QueryDialog.__name__,
                {"query": follow_up},
            )

        return await step_context.end_dialog()
