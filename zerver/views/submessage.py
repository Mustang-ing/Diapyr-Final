import orjson
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.submessage import do_add_submessage, verify_submessage_sender
from zerver.actions.process_debat_form import NotADebatPollException, process_diapyr_submessage
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import validate_poll_data, validate_todo_data
from zerver.lib.widget import get_widget_type
from zerver.models import UserProfile
import traceback


# transaction.atomic is required since we use FOR UPDATE queries in access_message.
@transaction.atomic(durable=True)
@typed_endpoint
def process_submessage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: Json[int],
    msg_type: str,
    content: str,
) -> HttpResponse:
    message = access_message(user_profile, message_id, lock_message=True, is_modifying_message=True)
   
    verify_submessage_sender(
        message_id=message.id,
        message_sender_id=message.sender_id,
        submessage_sender_id=user_profile.id,
    )

    try:
        widget_data = orjson.loads(content)
    except orjson.JSONDecodeError:
        raise JsonableError(_("Invalid json for submessage"))

    widget_type = get_widget_type(message_id=message.id)

    is_widget_author = message.sender_id == user_profile.id

    if widget_type == "poll":
        try:
            validate_poll_data(poll_data=widget_data, is_widget_author=is_widget_author)
        except ValidationError as error:
            raise JsonableError(error.message)

    if widget_type == "todo":
        try:
            validate_todo_data(todo_data=widget_data, is_widget_author=is_widget_author)
        except ValidationError as error:
            raise JsonableError(error.message)

    do_add_submessage(
        realm=user_profile.realm,
        sender_id=user_profile.id,
        message_id=message.id,
        msg_type=msg_type,
        content=content,
    )

    #We only process widget message of type vote for Diapyr debates
    if widget_type == "poll" and widget_data.get("type") == "vote":
        try:
            print("Processing vote...")
            process_diapyr_submessage(
                realm=user_profile.realm,
                user_profile=user_profile,
                message=message,
                message_id=message.id,
                widget_data=widget_data,
            )
        except NotADebatPollException as e:
            print(e)
        except Exception as e:
            traceback.print_exc()
            raise  # Re-raise the exception to stop execution and see the traceback

    return json_success(request)
