from datetime import datetime, timedelta, timezone
import time
import random
import threading
from types import FrameType
from django import db
from django.db import transaction
from django.core.exceptions import ValidationError
import orjson
import zulip

from zerver.models import UserProfile, Stream,Realm,Message,SubMessage
from zerver.models.debat import (
    Debat,
    GroupVote,
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
            #print(f"Messages récupérés pour {user}: {response['messages']}")

            messages = response.get("messages", [])
            #print(f"Messages récupérés pour {user}: {messages}")
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




def send_poll(group: Group, candidates: list[GroupParticipant]) -> None:
    """Send final poll and process votes allowing multiple votes per member."""
    print(f"Envoi des votes de représentant pour {group.group_name} avec candidats: {candidates}")
    
    # Create multi-choice poll
    question = "Vote des représentant: Sélectionnez les personnes qui vous représenteront à l'étape suivante"
    options = [f"{user.participant.full_name}\n" for user in candidates]
    poll_command = f'/poll {question} \n {" ".join(options)}'
    
    #Dans une autre version, c'est le moment idéal pour appeler un endpoint qui fait la même chose que submessage-pool, mais pour Diapyr
    try:
        response = external_client.send_message({
            "type": "stream",
            "to": group.stream.name,
            "subject": "Sondage final",
            "content": poll_command 
        })
        print(f"Multi-choice poll sent to {group.stream.name}")
        if response.get("result") != "success":
            raise Exception(f"Failed to send poll: {response.get('msg', 'Unknown error')}")
        # Store the created poll message id on the current Vote
        message_id = response.get("id")
        print(f"Message ID : {message_id}")
        if message_id:
            vote_obj = Vote.objects.get(group=group, round=group.debat.round)
            print(f"Vote_obj : {vote_obj}")
            #vote_obj = Vote.objects.filter(group=group, round=group.debat.round).order_by("-vote_date").first()
            if vote_obj is not None:
                vote_obj.vote_message_id = message_id
                vote_obj.save(update_fields=["vote_message"])
                print(f"Poll message ID {message_id} linked to Vote object for group {group.group_name}")
        
        print(f"Result : {vote_obj}")
        
    except Exception as e:
        print(f"Error sending poll: {e}")
        raise e
        



"""
def process_poll():
    # Simulate realistic voting (each member votes for multiple candidates)
    vote_count = {c: 0 for c in valid_candidates}
    voters = [m for m in group ]  
    
    for voter in voters:
        try:
            # Number of votes this member will cast (1 to max_per_group)
            num_votes = random.randint(1, self.max_per_group)
            
            # Select distinct candidates to vote for
            voted_for = random.sample(valid_candidates, min(num_votes, len(valid_candidates)))
            
            for candidate in voted_for:
                vote_count[candidate] += 1
        except Exception as e:
            print(f"Error simulating vote: {e}")

    # Calculate threshold (2/3 of voters)
    threshold = math.ceil(len(voters) * (2 / 3))
    selected = {email for email, count in vote_count.items() if count >= threshold}
    
    print(f"Vote results for {stream_name}: {vote_count}")
    print(f"Threshold: {threshold}, Selected: {selected}")
    return selected
"""    
    

def start_vote_procedure(debat: Debat):
    print(f"Démarrage de la procédure de vote pour le débat '{debat.title}'")
    #1 - We start by sending a message to all participant in order to see if they want to be a representant

    print(f"envoie enquete...")
    for participant in debat.active_participants:
        message = "Voulez-vous participer aux étapes suivantes? (oui/non)"
        notify_users([participant.email], message)

    #2 - We wait approximatively 30 seconds, this duration could also be chose by the user
    print("\nEn attente des réponses à l'enquéte...")
    time.sleep(5)  # Attendre 30 secondes pour les réponses

    #3 - Then we treat the answers
    print("\nTraitement des réponses...")
    candidates_list: dict[Group : list[GroupParticipant]] = {}

    for group in debat.active_groups:
        print(f"Traitement des réponses pour le groupe {group.group_name}...")
        print(f"Création de l'objet Vote pour le groupe {group.group_name}...")
        try : 
            vote_obj =Vote.objects.create(
                group=group, 
                state='pending',
                round=group.debat.round,
            )
            print(vote_obj)
            collect_responses(group)
        except Exception as e:
            print(f"Error creating vote object for group {group.group_name}: {e}")
        candidates_list[group] = list(group.representant_candidates)

    print(f"candidates_list: {candidates_list}")

    for group in debat.active_groups:

        candidates = candidates_list.get(group, [])
        if len(candidates) < 2: 
            message = f"Pas assez de candidats. Selection aléatoire de candidats..."
            print(message)
            notify_users(group.get_users_emails(), message)
            candidates = random.sample(list(group.group_participants.all()), group.debat.max_representant)
            send_poll(group, candidates)
            # group.vote is a RelatedManager (ForeignKey). Update the vote for this round.
            print(Vote.objects.filter(group=group, round=group.debat.round).update(state='voting'))

        else: 
            send_poll(group, candidates)
            # group.vote is a RelatedManager (ForeignKey). Update the vote for this round.
            print(Vote.objects.filter(group=group, round=group.debat.round).update(state='voting'))

        """
        # Notify candidates about the voting process
        candidate_emails = [candidate.participant.email for candidate in candidates]
        notify_users(candidate_emails, f"Le vote va commencer pour le groupe {group.group_name}. Vous pouvez voter pour un représentant parmi les candidats suivants : {', '.join(candidate_emails)}. Envoyez le nom du candidat par message privé.")
        """
        # Wait for votes (for simplicity, we wait a fixed time; in a real system, you'd have a more robust mechanism)


    print(f"En attente des votes ...")

    #Delay to wait for users to choose representatives
    time.sleep(60)


    print("Fin de la période de vote. Traitement des résultats...")
    





    
