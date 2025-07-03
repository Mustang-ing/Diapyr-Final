import django,os,sys

# Set project root and settings
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import zulip
from datetime import datetime, timedelta
from zerver.models.debat import Debat,Participant
from zerver.models.streams import Stream
 



if __name__ == "__main__":
    # Initialize the Zulip client
    client = zulip.Client(config_file="zuliprc.txt")

    total = 0
    real_user = []
    # Count the number of users in the Zulip organization
    print(client.get_members()["members"][0]["is_bot"])
    members = client.get_members()["members"]
    for user in members:
        if not bool(user["is_bot"]):
            total += 1
            real_user.append(user)

    
    print(f"Nombre total d'utilisateurs dans l'organisation : {total}")
    print("Script de test choisiser vos parametres")
    nb_subscribers = int(input("Nombre de participants : "))
    if nb_subscribers > total:
        print("Le nombre de participants est supérieur au nombre de personne dans l'organisation")
        exit(1)
    max_per_group = int(input("Nombre de participants maximal dans un groupe : " ))
    time_between_steps = int(input("Temps entre chaque étape (en minutes) : "))


    # Create a new debate
    num = Debat.objects.count() 
    debat = Debat.objects.create(
        title=f"Test Debate {num}",
        creator_email="",
        max_per_group=max_per_group,
        end_date = datetime.now() + timedelta(seconds=30),
        time_between_round=time_between_steps,
        num_pass=3,
        description="This is a test debate")
    print(f"Débat créé : {debat.title}")


    # Create participants
    
    for i,user in zip(range(nb_subscribers),real_user):
        participant = Participant.objects.create(
            email=user['email'],
            pseudo=f"{user['full_name']}",
        )
        debat.debat_participant.add(participant)
        print(f"Participant créé : {participant.pseudo} avec l'email {participant.email}")


