from src.domain.value_objects.conversation_role import ConversationRole


def format_messages(messages: list[tuple[ConversationRole, str]]) -> str:
    """Format a list of conversation messages into a single string."""
    return "\n".join([f"{str(role)}: {content}" for role, content in messages])
