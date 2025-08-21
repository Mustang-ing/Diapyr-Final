import math

import zulip
import random
from datetime import datetime, timedelta, timezone
import threading
import statistics


# Configuration du bot
client = None
# Statistiques pour voir le nb de msg/caracteres envoyés:
stats_utilisateurs = {}  # email → {"messages": 0, "caracteres": 0}
messages_consecutifs = {"last_sender": None, "count": 0}
# Pour le suivi des alertes de participation faible
dernier_alerte_utilisateur = {}  # email → datetime de la dernière alerte
COOLDOWN = 300
dernier_rappel = None
#pour laffichage des stat
id_message_stats = None  # contiendra l'ID du message à mettre à jour
stream_stats = None  # contiendra le nom du stream où poster les stats

historique_messages = {}
inscrits_debat = {}  # Pour stocker les inscrits aux débat
participants = {}  # Pour stocker les participants aux débats



try:  # External API client (used by the _via_api helper below); optional for internal path
    external_client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
    print("Client Zulip initialisé avec succès (API mode disponible).")
except zulip.ZulipError as e:  # pragma: no cover - just defensive logging
    external_client = None
    print(f"Erreur lors de l'initialisation du client Zulip (API mode désactivé): {e}")





#calcul de la médiane, retourne un tuple (médiane des messages, médiane des caracteres)
def get_mediane() -> float:
    """Retourne uniquement la médiane des messages"""
    if not stats_utilisateurs or len(stats_utilisateurs) < 3:
        return 0.0
    
    try:
        messages = [u["messages"] for u in stats_utilisateurs.values() if u["messages"] > 0]
        return float(statistics.median(messages)) if messages else 0.0
    except Exception as e:
        print(f"Erreur calcul médiane: {str(e)}")
        return 0.0


def message_listener() -> None:
    #Fonction pour écouter les messages entrants.
    print("Démarrage de l'écoute des messages...")
    request = {
        "event_types": ["message"],
        "narrow": [],  # vide = écoute tous les messages
        "all_public_streams": True  # écoute même les messages dans les streams publics où il est abonné
    }
    external_client.call_on_each_message(handle_message)


def handle_message(msg: dict[str, str]) -> None:
    print("Message reçu")
    #print(msg)
    global id_message_stats, stream_stats

    # Ignorer les messages envoyés par le bot lui-même
    if msg["sender_email"] == external_client.get_profile()["email"]:
        return
    content = msg["content"].strip()
    user_email = msg["sender_email"]
    user_name = msg["sender_full_name"]
    nb_car = len(content)

    if user_email not in stats_utilisateurs:
        stats_utilisateurs[user_email] = {
            "messages": 0,
            "caracteres": 0,
            "name": user_name,
            "is_subscriber": True
        }
        historique_messages[user_email] = []
    
    stats_utilisateurs[user_email]["messages"] += 1
    stats_utilisateurs[user_email]["caracteres"] += nb_car

    
    # alerte spam ------------------------------------------------------------------------
    now = datetime.now()
    if user_email not in historique_messages:
        historique_messages[user_email] = []

    # Ajout du temps d'envoi du message actuel à l'historique 
    historique_messages[user_email].append(now)

    # Garder uniquement les messages des 10 dernières secondes
    historique_messages[user_email] = [
        t for t in historique_messages[user_email]
        if (now - t).total_seconds() <= 10
    ]

    # Vérifier si l'utilisateur spamme
    if len(historique_messages[user_email]) > 5:
        external_client.send_message({
            "type": "stream",
            "to": msg["display_recipient"],
            "topic": msg["subject"],
            "content": f"@**{msg['sender_full_name']}** ⚠️ Vous envoyez trop de messages en peu de temps. Merci de ralentir pour laisser les autres s’exprimer."
        })
        historique_messages[user_email] = []  # Réinitialise pour ne pas répéter l’alerte
    
    # Affichage des autres alertes ---------------------------------------------------
    if len(stats_utilisateurs) >= 2:
        med_msg = get_mediane()
        #si la mediane des messages est inférieure à 2, trop tôt pour alerter
        if med_msg >= 2:
            user_msgs = stats_utilisateurs.get(user_email, {}).get("messages", 0)
            if user_msgs > 2 * med_msg and user_msgs >= 5: # Au moins 5 msgs
                external_client.send_message({
                    "type": "stream",
                    "to": msg["display_recipient"],
                    "topic": msg["subject"],
                    "content": f"@**{msg['sender_full_name']}** ⚠️ Vous avez envoyé trop de messages (médiane: {med_msg}). Merci de laisser de la place aux autres."
                })
             # Participation faible (messages)
            ratio_msg = user_msgs / med_msg if med_msg > 0 else 0
            maintenant = datetime.now()
            dernier = dernier_alerte_utilisateur.get(user_email, datetime.min)
            COOLDOWN = max(300, len(stats_utilisateurs) * 30)
            if 0 < ratio_msg < 0.5 and (maintenant - dernier).total_seconds() > COOLDOWN :
                if ratio_msg < 0.25 : 
                    texte = "⚠️ **Votre participation est très faible** comparée aux autres. Votre avis est important !"
                elif ratio_msg < 0.5:
                    texte = "💡 **Vous pourriez participer davantage** - le débat a besoin de votre voix !"
                else:
                    return
                def envoyer_alerte():
                    external_client().send_message({
                        "type": "stream",
                        "to": msg["display_recipient"],
                        "topic": msg["subject"],
                        "content": f"@**{user_name}** {texte} (vous: {user_msgs} msg, moyenne du chat: {med_msg})"
                    })
                timer = threading.Timer(30.0, envoyer_alerte)
                timer.start()
                dernier_alerte_utilisateur[user_email] = maintenant    

    # Affichage des statistiques de participation --------------------------------------------------
    if stats_utilisateurs:
    # Construire le contenu du message par utilisateur
        lignes = []
        for email, stats in stats_utilisateurs.items():
            nom = stats["name"]
            nb_msg = stats["messages"]
            nb_car = stats["caracteres"]
            lignes.append(f"- **{nom}** : {nb_msg} message(s), {nb_car} caractère(s) envoyés")

        contenu = (
            "**📊 Contribution détaillée des participants**\n\n"
            + "\n".join(lignes)
        )
        if id_message_stats is None:
            result = external_client.send_message({
                "type": "stream",
                "to": msg["display_recipient"],
                "topic": "📊 Contribution",
                "content": contenu,
            })
            if result["result"] == "success":
                id_message_stats = result["id"]
            else:
                print(f"Erreur lors de l'envoi du message de stats : {result.get('msg', 'Erreur inconnue')}")
        else:
            try:
                external_client.update_message({
                    "message_id": id_message_stats,
                    "content": contenu
                })
            except Exception as e:
                print(f"Erreur mise à jour stats : {e}")
