from django.db import transaction
from django.utils import timezone
from zerver.models import Client, UserPresence, UserProfile, Stream
from zerver.models.debat import Debat
from datetime import datetime, timedelta

transaction.atomic(durable=True)
def do_create_debat(title: str,
                    description: str,
                    creator: UserProfile,
                    end_date: datetime,
                    max_per_group: int,
                    time_between_round: int
) -> None:
    
    # We also check if the debate aren't already created or if there another Zulip channel with the same name.
    #Attention, cette méthode devrait être appelée avant la création du débat, pas quand on inscrit qq.
    if Stream.objects.filter(name=title).exists() or Debat.objects.filter(title=title).exists() :
        raise ValueError("A debate or a channel with the same name already exists in this realm")
    
    #Il faudrait ajouter d'autre contrôle sur les valeur, mais pour l'instant c'est géré par la vue.

    diapyr_bot = UserProfile.objects.get(
        email="potobot-bot@zulipdev.com",  # Replace with the actual bot email, should be diapyr-bot@zulipdev.com
        is_bot = True
    )


    debat = Debat(
        title=title,
        description=description,
        subscription_end_date=end_date,
        creator=creator,
        max_per_group=max_per_group,
        time_between_round= timedelta(seconds=time_between_round),
        start_date=end_date + timedelta(minutes=30),
        diapyr_bot=diapyr_bot 
    )
    debat.save()