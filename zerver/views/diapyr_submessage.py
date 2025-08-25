import orjson
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.submessage import do_add_submessage, verify_submessage_sender
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import validate_poll_data, validate_todo_data
from zerver.lib.widget import get_widget_type
from zerver.models import SubMessage, UserProfile
from zerver.models.debat import Group, GroupParticipant, GroupVote, Vote


# transaction.atomic is required since we use FOR UPDATE queries in access_message.
@transaction.atomic(durable=True)
@typed_endpoint
def process_diapyr_submessage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: Json[int],
    msg_type: str,
    content: str,
) -> HttpResponse:
    """Like the core submessage endpoint, but when the widget is a poll and
    the payload represents a vote, record that vote into GroupVote for the
    corresponding debate group.

    This preserves all validation and submessage creation semantics, then
    performs best-effort mapping of the voted option to a GroupParticipant
    using the initial poll widget options and the group's stream.
    """

    message = access_message(
        user_profile, message_id, lock_message=True, is_modifying_message=True
    )

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

    # Create the SubMessage event (same as core endpoint)
    do_add_submessage(
        realm=user_profile.realm,
        sender_id=user_profile.id,
        message_id=message.id,
        msg_type=msg_type,
        content=content,
    )

    # Additional Diapyr behavior: if it's a poll vote, persist GroupVote
    if widget_type == "poll":
        try:
            if isinstance(widget_data, dict) and widget_data.get("type") == "vote":
                key = str(widget_data.get("key", ""))
                vote_flag = int(widget_data.get("vote", 0))

                # Resolve Group via the stream of the poll message.
                # For stream messages, recipient.type_id is the Stream.id
                stream_id = message.recipient.type_id
                group = Group.objects.filter(stream_id=stream_id).first()
                if group is None:
                    return json_success(request)

                # Prefer the vote session whose poll was posted as this message
                vote_session = Vote.objects.filter(vote_message_id=message.id).first()
                # Only persist votes when the submessage belongs to a poll that is explicitly
                # linked to a Vote via vote_message. This prevents unrelated polls from
                # affecting debate data.
                if vote_session is None:
                    return json_success(request)

                # Map the voted option index to a candidate name from the initial widget
                option_index = None
                try:
                    parts = [p for p in key.split(",") if p]
                    if parts:
                        # Heuristic: last segment is the 1-based option index
                        option_index = int(parts[-1]) - 1
                except Exception:
                    option_index = None

                candidate_gp = None
                if option_index is not None and option_index >= 0:
                    init_widget = (
                        SubMessage.objects.filter(message_id=message.id, msg_type="widget")
                        .order_by("id")
                        .first()
                    )
                    if init_widget is not None:
                        try:
                            init_payload = orjson.loads(init_widget.content)
                            if init_payload.get("widget_type") == "poll":
                                options = (
                                    init_payload.get("extra_data", {}).get("options", [])
                                )
                                if 0 <= option_index < len(options):
                                    option_text = options[option_index]
                                    candidate_gp = (
                                        GroupParticipant.objects.filter(
                                            group=group,
                                            participant__full_name=option_text,
                                        ).first()
                                    )
                        except Exception:
                            candidate_gp = None

                voter_gp = GroupParticipant.objects.filter(
                    group=group, participant=user_profile
                ).first()

                # Only persist if we could map both sides
                if voter_gp is not None and candidate_gp is not None:
                    if vote_flag == 1:
                        GroupVote.objects.get_or_create(
                            group=group,
                            vote_session=vote_session,
                            participant=voter_gp,
                            vote_for=candidate_gp,
                        )
                        if voter_gp.has_voted is not True:
                            voter_gp.has_voted = True
                            voter_gp.save(update_fields=["has_voted"])
                    else:
                        # vote_flag 0 means unvote
                        GroupVote.objects.filter(
                            group=group,
                            vote_session=vote_session,
                            participant=voter_gp,
                            vote_for=candidate_gp,
                        ).delete()
        except Exception:
            # Never fail the API due to Diapyr-specific mapping issues
            pass

    return json_success(request)
