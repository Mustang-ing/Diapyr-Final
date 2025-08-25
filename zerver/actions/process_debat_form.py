
from pydantic import ValidationError
from zerver.models import UserProfile, Stream,Realm,Message,SubMessage
from zerver.models.debat import (
    Debat,
    GroupVote,
    Participant,
    Group,
    GroupParticipant,
    Vote
)

import orjson


class NotADebatPollException(Exception):
    pass


def process_diapyr_submessage(
    realm: Realm,
    user_profile: UserProfile,
    message: Message,
    message_id: int,
    widget_data: dict,
) -> None:
    
    try:
        if isinstance(widget_data, dict) and widget_data.get("type") == "vote":
            # Widget data = {'type': 'vote', 'key': 'canned,1', 'vote': -1}
            # widget_data.get("key") -> 'canned,1' 
            # widget_data.get("key").split(",")[1] -> '1'
            option_index = int(widget_data.get("key", "").split(",")[1]) 
            #The vote flag can have 3 value 1: for, -1: against, 0: abstain/default value
            vote_flag = int(widget_data.get("vote", 0))
             

            # Resolve Group via the stream of the poll message.
            # For stream messages, recipient.type_id is the Stream.id
            stream_id = message.recipient.type_id
            try:
                group = Group.objects.get(stream_id=stream_id)
            except Group.DoesNotExist:
                raise ValidationError(f"No group has been found for the stream : {stream_id}")


            # We need to check if this poll was destined to Diapyr debate or not to continue
            vote_session = Vote.objects.filter(vote_message_id=message.id).first()
            # Only persist votes when the submessage belongs to a poll that is explicitly
            # linked to a Vote via vote_message. This prevents unrelated polls from
            # affecting debate data.
            if vote_session is None:
                raise NotADebatPollException(f"No vote session has been found for the message : {message_id}. This usually happen if the poll wasn't generated in a debate context")


            # We get the initial widget for the poll. The 1st widget message contains all the options (Candidates) of the form
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
                            user_option = str(options[option_index]).strip()
                            print(f"Option index : {option_index}, Option text : {user_option}, vote flag : {vote_flag}")
                            #print(f" Candidate_gp : {GroupParticipant.objects.filter(group=group, participant__full_name=user_option)}")
                            candidate_gp = GroupParticipant.objects.filter(
                                group=group, participant__full_name=user_option
                            ).first()
                            print(f"Candidate GroupParticipant : {candidate_gp}")

                    voter_gp = GroupParticipant.objects.get(group=group, participant=user_profile)

                except Exception as e:
                    raise e
                    

            #At last, we will fill the GroupVote table corresponding to the vote_flag value.
            # If vote_flag = 1, we will add a row to count the vote to the table
            # If vote_flag = -1, we will remove the row from the table (The user undo his vote)
            try:
                print("Fill the GroupVote table")
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
                        candidate_gp.vote_count += 1
                        candidate_gp.save(update_fields=["vote_count"])
                    elif vote_flag == -1:
                        # vote_flag -1 means unvote
                        GroupVote.objects.filter(
                            group=group,
                            vote_session=vote_session,
                            participant=voter_gp,
                            vote_for=candidate_gp,
                        ).delete()
                        if candidate_gp.vote_count - 1 >= 0:
                            candidate_gp.vote_count -= 1
                            candidate_gp.save(update_fields=["vote_count"])
                        else:
                            raise ValueError(f"Error votes of {candidate_gp} is negative")
            except Exception as e:
                raise e
    except Exception as e:
        raise e
