from apps.chat.services import get_unread_message_count
from apps.core.services import get_unread_notification_count


def chat_notifications(request):
    unread_message_count = get_unread_message_count(request.user)
    unread_notification_count = get_unread_notification_count(request.user)
    return {
        "unread_message_count": unread_message_count,
        "unread_notification_count": unread_notification_count,
    }
