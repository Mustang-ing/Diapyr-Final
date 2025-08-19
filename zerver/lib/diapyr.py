import random
from django.db import transaction
import zulip
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.streams import list_to_streams
from zerver.models import UserProfile, Stream
from zerver.models.debat import (
    Debat,
    Participant,
    Group,
    GroupParticipant
)
from random import shuffle
import math

try:  # External API client (used by the _via_api helper below); optional for internal path
    external_client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
    print("Client Zulip initialisé avec succès (API mode disponible).")
except zulip.ZulipError as e:  # pragma: no cover - just defensive logging
    external_client = None
    print(f"Erreur lors de l'initialisation du client Zulip (API mode désactivé): {e}")


def notify_users(stream_name: str, debat_title: str, user_emails: list[str]) -> None:
    #Notifie les utilisateurs de leur affectation à un groupe.
    print(f"Notification de {user_emails} dans {stream_name}")
    for email in user_emails:
        message = {
            "type": "private",
            "to": email,
            "content": f"Vous avez été affecté au groupe {stream_name} du débat {debat_title}'.",#Plus de clarté quelle groupe en particilier
        }
        external_client.send_message(message)

@transaction.atomic(durable=True)
def split_into_group_db(debat : Debat, max_per_group : int) -> None:
    """
    Split participants into groups for the debate.
    """
    print("------------ Mode DB ------------------")
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

    i = 1
    for group in groups:
        group_instance = Group.objects.create(debat=debat, phase=debat.step, group_name=debat.title + f"Tour {debat.step - 2} - Groupe {i}")
        for user in group:
            GroupParticipant.objects.create(group=group_instance, participant=user)
            print(f"Participant {user.full_name} ajouté au groupe {group_instance.id} du débat {debat.title}")
        i += 1


def create_streams_for_groups_db_via_api(groups: set[Group], bot_user_id: int) -> list[Stream] | bool:
    """Legacy/API version: use Zulip HTTP API (external client) to create + subscribe.

    Returns list of associated Stream objects (after creation/subscription) or False on error.
    """
    print("------------ Mode DB ------------------")
    if external_client is None:
        print("Client API indisponible; impossible d'utiliser create_streams_for_groups_db_via_api.")
        return False

    print("Ajout des utilisateurs dans les streams (mode API HTTP)...")
    created_streams: list[Stream] = []
    i=1
    for i, group in enumerate(groups):
        print(f"Tentative d'ajout via API dans le stream : {group.group_name}")
        try:
            """
            request = { 
                "name": group.group_name,
                "description": f"Group {group.id} du débat {group.debat.title}",
                "subscribers": group.get_users_id() + [bot_user_id]
            }
            result = external_client.call_endpoint(url="channels/create", method="POST", request=request)
            """
            result = external_client.add_subscriptions(
                streams=[{"name": group.group_name}],
                principals=group.get_users_id() + [bot_user_id],
            )
            
            if result.get("result") == "success":
                print(f"Ajout réussi (API) dans le stream : {group.group_name}")
                print(result)
                group.stream = Stream.objects.get(name=group.group_name)
                group.save(update_fields=["stream"])
                created_streams.append(group.stream)
            else:
                print(f"Echec API pour {group.group_name}: {result}")
        except Exception as e:  # pragma: no cover - defensive
            print(f"Erreur lors de l'ajout des utilisateurs via API : {e}")
            return False

        notify_users(i, group.debat.title, group.get_users_emails())
        i+=1
    return created_streams


@transaction.atomic(durable=True)
def create_streams_for_groups_db(groups: set[Group], creator: UserProfile) -> list[Stream]:
    """Internal version using list_to_streams + bulk_add_subscriptions (no HTTP API).

    This will:
      * Create any missing streams for the provided groups (name = group.group_name).
      * Link the created/retrieved Stream object to Group.stream if not already set.
      * Subscribe all current group members + the bot user ONLY to their own group's stream.

    Returns a list of Stream objects (one per group processed).
    """

    print("------------ Mode DB ------------------")
    realm = creator.realm
    processed_streams: list[Stream] = []

    i = 1
    for group in groups:
        stream_name = group.group_name or f"debate-group-{group.id}"
        streams_raw = [
            {
                "name": stream_name.strip(),
                "invite_only": False,
                "is_web_public": False,
                "history_public_to_subscribers": True,
                # message_retention_days optional; defaults to realm policy
            }
        ]
        # Create or fetch stream (autocreate=True). Using creator of the debate as acting user.
        existing_streams, created_streams = list_to_streams(
            streams_raw,
            creator,
            autocreate=True,
            is_default_stream=False,
        )
        stream_obj = (existing_streams + created_streams)[0]

        # Link stream to group if missing
        if group.stream_id != stream_obj.id or group.stream is None:
            group.stream = stream_obj
            group.save(update_fields=["stream"])

        # Gather users (ManyToMany through GroupParticipant)
        users_in_group = list(group.members.all())
        if creator not in users_in_group:
            users_in_group.append(creator)

        # bulk_add_subscriptions subscribes EVERY provided user to EVERY provided stream.
        # Since each group has distinct membership, call it per-group.
        new_subs, already_subs = bulk_add_subscriptions(
            realm,
            [stream_obj],
            users_in_group,
            acting_user=creator,
        )
        print(
            f"Stream '{stream_name}': {len(new_subs)} nouveaux abonnements, {len(already_subs)} déjà abonnés."
        )
        processed_streams.append(stream_obj)
        notify_users(i, group.debat.title, group.get_users_emails())

    return processed_streams

"""
def main() -> None:
    print("Démarrage de la boucle principale...")
    while True:
"""
