from datetime import datetime, timedelta, timezone
import time
import random
import threading
from types import FrameType
from django.db import transaction
import zulip
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.debat_vote import start_vote_procedure
from zerver.lib.moderate_debat import message_listener
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
import sys,signal

try:  # External API client (used by the _via_api helper below); optional for internal path
    external_client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
    print("Client Zulip initialisé avec succès (API mode disponible).")
except zulip.ZulipError as e:  # pragma: no cover - just defensive logging
    external_client = None
    print(f"Erreur lors de l'initialisation du client Zulip (API mode désactivé): {e}")

thread_list = []

def terminate_diapyr() -> None:
    try:
        active_debates = Debat.objects.filter(is_archived=False)
        if not active_debates:
            print("Aucun débat actif à archiver.")
            sys.exit(0)
        
        for debate in active_debates:
            if debate.step == 3:
                archive_all_groups(debate)
                debate.is_archived = True
                debate.save(update_fields=["is_archived"])
                message = f"Attention, le débat {debate.title} à été stopé avant d'arriver à son terme\n Raison : Arret de l'exécution du script"
                for group in debate.active_groups:
                    notify_users(group.get_users_emails(), message)

        print("Tous les débats actifs ont été archivés.")
        sys.exit(0)
    except Exception as e:
        print(f"Erreur lors de l'archivage des débats : {e}")

def signal_handler(signal: int, frame: FrameType):
    print("Signal reçu, arrêt du bot.")
    if signal == 2:  # SIGINT
        print("Arrêt du bot Diapyr.")
        terminate_diapyr()


def notify_users(user_emails: list[str], message: str) -> None:
    # Notifie les utilisateurs d'un message.
    print(f"Notification pour {user_emails}")
    for email in user_emails:
        message = {
            "type": "private",
            "to": email,
            "content": message,
        }
        external_client.send_message(message)

#Il pourrait être intéressant de le déplacer dans un fichier dans actions
def split_into_group_db(debat : Debat, max_per_group : int) ->  list[Group]:
    """
    Split participants into groups for the debate.
    """
    print("------------ Mode DB ------------------")
    users = debat.active_participants  # On copie la liste des participants pour ne pas la modifier
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
    groups_db = []
    for group in groups:
        group_instance = Group.objects.create(debat=debat, round=debat.round, group_name=debat.title + f"Tour {debat.round} - Groupe {i}", group_number=i)
        groups_db.append(group_instance)
        for participant in group:
            GroupParticipant.objects.create(group=group_instance, participant=participant.user)
            participant.is_registered_to_a_debate = True
            participant.save(update_fields=["is_registered_to_a_debate"])
            print(f"Participant {participant.name} ajouté au groupe {group_instance.id} du débat {debat.title}")
        i += 1

    return groups_db



def archive_all_groups(debat: Debat) -> None:
    """
    Archive all groups in the debate.
    This function sets the is_archived field of each group's stream to True.
    """
    for group in debat.all_groups:
        try:
            external_client.delete_stream(group.stream.id)
            print(f"Stream {group.group_name} archived successfully.")
            group.is_archived = True
            group.save()
        except Exception as e:
            print(f"Erreur lors de l'archivage du stream {group.group_name}: {str(e)}")
        
        print(f"Tous les groupes du débat '{debat.title}' ont été archivés.")

#Routine 2 - Gérer un débat
def next_step(debat: Debat) -> bool:
    """
    Move to the next step of the debate.
    """
    # We wait until the end of the debate process to act.
    print(f"Attente de {debat.time_between_round} avant la prochaine étape...")
    time.sleep(debat.time_between_round.total_seconds())

    
    users = debat.active_participants
    if users is None or len(users) == 0:
        print(f"Aucun utilisateur inscrit dans le débat '{debat.name}'.")
        return False
    
    #On vérifie si leurs nombre est assez grand pour etre divisé OU que le nombre de passes choisit est inférieur OU au moins 2 utilisateurs
    elif len(users) <= debat.max_per_group or len(users) < 2:
        return False
    
    #Normalement c'est là qu'on doit commencer la procédure de votes
    #Créer les sessions de vote et laisser les écritures se committer avant d'arrêter le flux
    start_vote_procedure(debat)
    archive_all_groups(debat)
    # Ne pas interrompre le processus brutalement ici (SystemExit annule les transactions).
    # On arrête proprement cette boucle en retournant False.
    return False
    eliminated = random.sample(users, debat.max_per_group)
    users_to_keep = [u for u in users if u not in eliminated]

    if len(users_to_keep) <= debat.max_per_group: #Si apres la suppresion enleve trop de personne
        return False
    
    for user in eliminated:
        user.is_active_in_diapyr = False  # On désactive l'utilisateur dans le débat
        user.save(update_fields=["is_active_in_diapyr"])

    debat.round += 1
    debat.save(update_fields=["round"])

    print(f"Étape {debat.round} du débat '{debat.title}'")
    groups = split_into_group_db(debat,debat.max_per_group)
    create_streams_for_groups_db_via_api(groups,124)

    external_client.send_message({
        "type": "private",
        "to": debat.creator.email,
        "content": f"Étape {debat.round} démarrée pour le débat '{debat.title}'.",
    })
    return True

def get_status(self) -> str:
    users = list(self.subscribers.keys())
    print("gagagaaaaaaaaaaaaaaaaa")

    if self.creator_email not in users:
        users.append(self.creator_email)
    groups = [users[i:i + self.max_per_group] for i in range(0, len(users), self.max_per_group)]
    for group in groups:
        group.append(self.creator_email)
    info = f"Nom: {self.name}\nÉtape: {self.step}\nFin inscription: {self.subscription_end_date}\nTemps entre étapes: {self.time_between_steps}\n"
    info += f"Nombre de groupes: {len(groups)}\n"
    for idx, group in enumerate(groups):
        info += f"Groupe {idx + 1}: {', '.join(group)}\n"
    return info


def start_debate_process(debat: Debat) -> None: #N'aurait t'on pas pu faire une seule fonction pour gérer les étapes ? Ou voir les décorateurs ?
    def run_steps() -> None:
        #We continue the loop until the debate stoped because :
        # 1 - There are no one - users is None or len(users) == 0
        # 2 - There not enough users - len(users) <= debat.max_per_group or len(users) < 2
        # 3 - There not enough users after elimination - len(users_to_keep) <= debat.max_per_group
        # In either case it will return False thus it will be true to execute the termination protocol of a debate
        while next_step(debat) and debat.step < 4:
            print(f"Le débat {debat.title} continue : Phase - {debat.step} | Tour : {debat.round} | Groupes : {debat.active_groups}")
            continue

        # Case of termination
        print(f"Débat '{debat.title}' terminé. Plus qu’un seul groupe.")
        for group in debat.all_groups:
            message = f"Le débat '{debat.title}' est terminé. Merci d'avoir participé !"
            notify_users(group.get_users_emails(), message)

        debat.archive_debat()
        debat.step = 4  # Set step to 4 to indicate the debate is finished
        debat.save(update_fields=["step"])

            

    thread_list.append(threading.Thread(target=run_steps).start())

def create_streams_for_groups_db_via_api(groups: set[Group], bot_user_id: int) -> list[Stream] | bool:
    """Legacy/API version: use Zulip HTTP API (external client) to create + subscribe.

    Returns list of associated Stream objects (after creation/subscription) or False on error.
    """
    print("------------ Mode DB ------------------")
    if external_client is None:
        print("Client API indisponible; impossible d'utiliser create_streams_for_groups_db_via_api.")
        sys.exit(0)
        

    print("Ajout des utilisateurs dans les streams (mode API HTTP)...")
    created_streams: list[Stream] = []
    i=1
    print(groups)
    for i, group in enumerate(groups):
        print(group)
        print(type(group))
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
                raise RuntimeError(f"Echec API pour {group.group_name}: {result}")
        except Exception as e:  # pragma: no cover - defensive
            print(f"Erreur lors de l'ajout des utilisateurs via API : {e}")
            sys.exit(0)

        message = f"Vous avez été affecté au groupe {i} du débat {group.debat.title} - Etape : {group.debat.round}."
        notify_users(group.get_users_emails(), message)
        i += 1
    return created_streams


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
        message = f"Vous avez été affecté au groupe {i} du débat {group.debat.title} - Etape : {group.debat.round}"
        notify_users(group.get_users_emails(), message)

    return processed_streams


#Routine 1 - Checker la préparation de nouveau débat
def check_and_create_channels() -> None:
    #Vérifie si la période d'inscription est terminée et crée les channels si nécessaire.
    listeDebat = Debat.objects.all()
    for debat_obj in listeDebat:
        # We wait for the end of the registration time
        if datetime.now(timezone.utc) > debat_obj.subscription_end_date and not debat_obj.debat_created:
            debat_obj.step = 2
            debat_obj.save()
            #Içi on rajoute la condition pour vérifier la date de début du débat
            print(f" La débat {debat_obj.title} commencera à {debat_obj.start_date}")
            if  debat_obj.start_date < datetime.now(timezone.utc) or debat_obj.skip_pre_registration :
                debat_obj.step=3
                debat_obj.save()
                groups = split_into_group_db(debat_obj, debat_obj.max_per_group)
                if groups == []:
                    print(f"Création de débat imposible pour l'objet D '{debat_obj.title}'. Il n'a pas de participants ou le nombre maximal de participants par groupe est 0.")
                    break
                elif len(groups) == 1:
                    print(f"Création de débat impossible pour l'objet D '{debat_obj.title}'. Il n'y a qu'un seul groupe.")
                    break

                bot_id = debat_obj.bot_id if debat_obj.bot_id else None  # Subterfuge temporaire
                create_streams_for_groups_db_via_api(groups, bot_id if bot_id else 124)  # 2 argt à modif
                print(f"Channels créés pour le débat '{debat_obj.title}'.")
                debat_obj.debat_created = True
                debat_obj.save(update_fields=["debat_created"])
                start_debate_process(debat_obj)  # Démarrer le processus de débat
            


def main_db() -> None:
    print("Démarrage de la boucle principale...")
    threading.Thread(target=message_listener).start()
    while True:
        check_and_create_channels()
        signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C gracefully
        """
        for t in thread_list:
            if t.is_alive():
                t.join(timeout=5)
        """
        time.sleep(5)  # Attendre 5 secondes avant de vérifier à nouveau
        

