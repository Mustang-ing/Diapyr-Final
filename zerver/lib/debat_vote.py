from datetime import datetime, timedelta, timezone
import time
import random
import threading
from types import FrameType
from django.db import transaction
import zulip
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.moderate_debat import message_listener
from zerver.lib.streams import list_to_streams
from zerver.models import UserProfile, Stream
from zerver.models.debat import (
    Debat,
    Participant,
    Group,
    GroupParticipant,
    Vote
)
from random import shuffle
import math
import sys,signal
from bs4 import BeautifulSoup


try:  # External API client (used by the _via_api helper below); optional for internal path
    external_client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
    print("Client Zulip initialisé avec succès (API mode disponible).")
except zulip.ZulipError as e:  # pragma: no cover - just defensive logging
    external_client = None
    print(f"Erreur lors de l'initialisation du client Zulip (API mode désactivé): {e}")


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

def collect_responses(group: Group)-> None:
    """
    Collecte les réponses des participants à l'enquête.
    """
    print("Collecte des réponses...")

    for user in group.group_participants.all():

        print(f"Collecte des réponses pour {user}")
         # Fetch the most recent message in the PM conversation

        request = {
            "anchor": "newest",
            "num_before": 1,  # Get only the most recent message
            "num_after": 0,
            "narrow": [
                {"operator": "pm-with", "operand": user.participant.email},
            ],
        }
        response = external_client.get_messages(request)

        if response.get("result") == "success" and response.get("messages"):
            print(f"Messages récupérés pour {user}: {response['messages']}")

            messages = response.get("messages", [])
            print(f"Messages récupérés pour {user}: {messages}")
            # Get the most recent message
            last_message = messages[0]
            content = last_message.get("content", "")
            # Parse HTML and clean text
            content_text = BeautifulSoup(content, "html.parser").get_text().strip().lower()
            # Check if the message is a response to our poll
            if content_text == "oui":
                print(f"réponse positif de {user}")
                user.is_interested = True
                user.save()
            else:
                user.is_interested = False
                user.save()

        else:
            print(f"Failed to fetch messages for {user}: {response.get('msg', 'Unknown error')}")



def start_vote_procedure(debat: Debat):
    print(f"Démarrage de la procédure de vote pour le débat '{debat.title}'")
    #1 - We start by sending a message to all participant in order to see if they want to be a representant

    print(f"envoie enquete...")
    for participant in debat.active_participants:
        message = "Voulez-vous participer aux étapes suivantes? (oui/non)"
        notify_users([participant.email], message)

    #2 - We wait approximatively 30 seconds, this duration could also be chose by the user
    print("\nEn attente des réponses à l'enquéte...")
    time.sleep(10)  # Attendre 30 secondes pour les réponses

    #3 - Then we treat the answers
    print("\nTraitement des réponses...")
    candidates_list: list[list[GroupParticipant]] = []
    print(f"debat.active_groups: {debat.active_groups}")
    for group in debat.active_groups:
        print(f"Traitement des réponses pour le groupe {group.group_name}...")
        obj_vote = Vote.objects.create(
        group=group, 
        state='pending',
        round=group.debat.round,
        )
        obj_vote.save()
        collect_responses(group)
        candidates_list.append(list(group.representant_candidates))

    print(f"candidates_list: {candidates_list}")
    
    #candidates_list = [user for group in debat.active_groups for user in group.members if user.is_interested]





    
