import django,os,sys


#Old way to set the project root from zerver/lib/contrib_bots/Diapyr_bot/Test_debat.py
""""
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(PROJECT_ROOT)
"""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import zulip
from datetime import datetime, timedelta
from zerver.models.debat import Debat,Participant
from zerver.models import UserProfile
#from zerver.lib.actions import do_delete_stream
import time

def main():
     # Initialize the Zulip client
    client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")

    total = 0
    real_user = []
    # Count the number of users in the Zulip organization
    #print(client.get_members()["members"][0]["is_bot"])
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
        title=f"TestDebate - Beta2 {num}",
        creator=UserProfile.objects.get(id=11),  # Assuming the creator is the first user
        max_per_group=max_per_group,
        subscription_end_date=datetime.now() + timedelta(seconds=5),
        time_between_round=time_between_steps,
        start_date=datetime.now() + timedelta(minutes=30),
        description="This is a test debate")
    print(f"Débat créé : {debat.title}")


    # Create participants
    
    for i,user in zip(range(nb_subscribers),real_user):
        participant = Participant.objects.create(
            user=UserProfile.objects.get(id=user['user_id']),
            pseudo=f"{user['full_name']}",
        )
        debat.debat_participant.add(participant)
        print(f"Participant créé : {participant.pseudo} avec l'email {participant.email}")


    #Get the status 
    while debat.is_archived == False:
        debat.refresh_from_db()
        print(f"Débat {debat.title} - Étape {debat.step} - Participants : {debat.debat_participant.count()}")
        
        
        
        # Wait for the next step
        time.sleep(time_between_steps)

if __name__ == "__main__":
    main()
   


