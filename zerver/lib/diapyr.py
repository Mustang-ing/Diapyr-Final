import random
from django.db import transaction
from zerver.models import UserProfile
from zerver.models.debat import (
    Debat,
    Participant,
    Group,
    GroupParticipant
)
from random import shuffle
import math

@transaction.atomic(durable=True)
def split_into_group_db(debat : Debat, max_per_group : int) -> None:
    """
    Split participants into groups for the debate.
    """
    users = list(debat.debat_participants.all())  # On copie la liste des participants pour ne pas la modifier
    shuffle(users)

    n = len(users)


    if n <= max_per_group:
        print(f"Nombre de participants ({n}) inférieur ou égal au nombre maximal de participants par groupe ({max_per_group}).")
        return [users]


    print(f"Nombre de participants : {n}, Nombre maximal de participants par groupe : {max_per_group}")
    try:
        num_groups = math.ceil(n/max_per_group)
        print( math.ceil(n/max_per_group))
        print(f"Nombre de groupes calculé : {num_groups}")
    except ZeroDivisionError:
        print("Erreur : Le nombre maximal de participants par groupe ne peut pas être zéro.")
        return []

    min_per_group = n // num_groups
    r = n % num_groups
    groups = []
    print(f"Resultat de la division : reste = {r}, min_per_group = {min_per_group}, max_per_group = {max_per_group}")
    start = 0
    for i in range(num_groups):
        group_size = min_per_group + (1 if i < r else 0) # On fait +1 tant que le nombre de peronne problématique n'est pas traité 
        print(f"groupe size {group_size}")
        groups.append(users[start:start + group_size])
        start += group_size
    print(f"Groupes créés : {len(groups)} - Groupes : {groups}")

    for group in groups:
        group_instance = Group.objects.create(debat=debat, phase=debat.step)
        for user in group:
            GroupParticipant.objects.create(group=group_instance, participant=user)
            print(f"Participant {user.full_name} ajouté au groupe {group_instance.id} du débat {debat.title}")



def add_users_to_stream_db(stream_name: str, user_emails: list[str]) -> bool:
    print(f"Ajout de {user_emails} dans {stream_name}")
    user_ids = [get_user_id(email) for email in user_emails if get_user_id(email)]
    # Ajout de l'ID du bot lui-même
    bot_user_id = get_user_id(get_client().get_profile()["email"])
    if bot_user_id and bot_user_id not in user_ids:
        user_ids.append(bot_user_id)

    if not user_ids:
        return False
    try:
        result = client.add_subscriptions(
            streams=[{"name": stream_name}],
            principals=user_ids,
        )
        print(f"Ajout réussi")
        return result["result"] == "success"
    except Exception as e:
        print(f"Erreur lors de l'ajout des utilisateurs : {e}")
        return False


def create_streams_for_groups_db(groups:set[Group]) -> list[str]:
        #Crée des streams pour chaque groupe et ajoute les utilisateurs.
        print("Ajout des utilisateurs dans les streams existants...")
        streams = []
        for i, group in enumerate(groups):
            stream_name = Debat.objects.get(id=group.debat_id).title + f"P{groups.step} - Groupe {i+1}" #Changer le nom pour plus de clarté
            print(f"Tentative d'ajout dans le stream : {stream_name}")
            if add_users_to_stream_db(stream_name, group):
                streams.append(stream_name)
               
        return streams
