from django.db import transaction
from django.utils import timezone
from zerver.models import Client, UserPresence, UserProfile, Stream
from zerver.models.debat import Debat, Participant
from datetime import datetime, timedelta


#On fait comme si on avait toutes les données nécessaires pour inscrire un participant à un débat.

@transaction.atomic(durable=True)
def do_subscribe_user_to_debat(
    user_profile: UserProfile,
    debat_id: int,
    username:str,
    age: int,
    domaine: str,
    profession: str
)->None:
    """
    We subscribe a user to a debate by creating a participant object, with the given parameters.
    This participant is then added to the debate's participants.
    """
    try:
        debat = Debat.objects.get(debat_id=debat_id)

        # We need to check if the user is already a participant on the debate
        #Will do this latter
        """
        print(f"Id de l'utilisateur : {user_profile.id})")
        print(debat.debat_participant.filter(participant_id=user_profile.id).exists())
        if debat.debat_participant.filter(participant_id=user_profile.id).exists():
            raise ValueError("User is already a participant in this debate")

        """
        
        #We also need to check if the time period for subscribing to the debate is still valid.
        #In the old version, a user can subscribe to a debate but are not in a group. We will have to wait the next step in there is one 
        #Also we need to rename the field end_date to something like start_date, because it is the date when the debate starts.

        print(f" Date de fin du débat : {debat.subscription_end_date} | Date actuelle : {datetime.now()}")
       
        if debat.subscription_end_date < timezone.now(): # We use timezone.now() to get the current time in the correct timezone, because the end_date is in UTC.(Offset aware)
            raise ValueError("The debate has already start, you cannot subscribe anymore")         

        if debat.is_archived:
            raise ValueError("The debate is closed, you cannot subscribe anymore")    

        # We also check if the debate aren't already created or if there another Zulip channel with the same name.
        #Attention, cette méthode devrait être appelée avant la création du débat, pas quand on inscrit qq.
        if Stream.objects.filter(name=debat.title).exists() and Debat.objects.filter(title=debat.title).exists() :
            raise ValueError("A debate or a channel with the same name already exists in this realm")
                                      
        # Create a new participant 
        participant = Participant.objects.create(
                pseudo=username,
                user=user_profile,
                age=age ,
                domaine=domaine ,
                profession=profession
            )
        debat.debat_participant.add(participant)
        debat.save()
    except Debat.DoesNotExist:
        raise ValueError("Debate not found")
    except ValueError as e:
        raise ValueError(str(e))
    

















    