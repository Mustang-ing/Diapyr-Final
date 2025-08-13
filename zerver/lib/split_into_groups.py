import random
from zerver.models import UserProfile
from zerver.models.debat import Debat
from random import shuffle
import math


"""
This function is used to split a list of participants into groups.
It takes a list of participants and a maximum number of participants per group.
It returns a list of groups, where each group is a list of participants.
"""
def split_into_groups(debat_users: list[UserProfile], max_per_group: int) -> list[list[UserProfile]]:
        users = list(debat_users)  # On copie la liste des participants pour ne pas la modifier
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
        return groups

"""
This function return a new list of participants by randomly selecting a maximum number of representatives from each group.
Is used only to estimae the duration of a debate. We can compare it to a fast simulation of the debate.
"""
def next_step_preparation(groups:list[list[UserProfile]], max_per_group: int, max_representant: int) -> list[list[UserProfile]]:
        
        nb_groups = len(groups)
        users = [participant for group in groups for participant in group] #We transform the list to list[UserProfile]
        print(f"Nombre de participants : {len(users)}")
        if users is None or len(users) == 0:
            print(f"Aucun utilisateur inscrit !!!")
            return None
           
        """
        #Methode1
        A chaque étape, seul au maximum max_representant utilisateurs sont conservés par groupe.
        Ainsi, dans un débat, on aura max_representant * nb_groups utilisateurs qui passeront à l'étape suivante.
        
        next_user = random.sample(users,max_representant*nb_groups) 
        print(f"Nombre d'utilisateurs sélectionnés pour la prochaine étape : {len(next_user)} - Nombre de représentants par groupe : {max_representant}")
        print(f"Utilisateurs sélectionnés : {next_user}")
        """

        """
        #Methode2
        On utilise directement groups et on sélectionne pour chaque groupe aléatoirement max_representant utilisateurs.
        """

        next_users = [random.sample(group,max_representant) for group in groups ]
        print(f"Nombre de représentants maximum par groupe : {max_representant} - Nombre de groupes : {len(next_users)} - Nombre d'utilisateurs : {sum(len(group) for group in next_users)}")

        new_participants = [participant for group in next_users for participant in group]  # On aplatit la liste des groupes
        print(new_participants)

        
        #On vérifie si leurs nombre est assez grand pour etre divisé OU au qu'il y a au moins 2 utilisateurs
        if len(new_participants) <= max_per_group or len(new_participants) < 2:
            return [new_participants]  # On retourne la liste des utilisateurs sélectionnés comme un seul groupe

        print(f"Test réussi")


        return split_into_groups(new_participants, max_per_group)


"""
This function will simulate a debate base on parameters provided by the user.( Max_per_group, time_between_round, max_representant)
It will return a dictionary who contains the following data:
- groups: a list of groups, where each group is a list of participants. Map by "initial_groups"
- nb_groups: the number of groups created in the first step. Map by "nb_groups"
- num_rounds: the number of rounds in the debate. Map by "num_rounds"
- estimated_duration: the estimated duration of the debate in minutes. Map by "estimated_duration"
"""

def get_composition_groups(groups: list[list[UserProfile]]) -> dict[int: int , int : int]:
    compo = {}
    #Methode1
    
    #compo = { x: 1 if x not in compo else compo[x] + 1 for x in [len(group) for group in groups] }
    #Pour (4,4,3) affiche (4:1,3:1 )
    #Methode2
    raw_compo = [len(group) for group in groups]
    for x in raw_compo:
         if x in compo:
            compo[x] += 1
         else:
            compo[x] = 1
    
    print(f"Composition des groupes : {compo}")
    return compo
         

def phase2_preparation(debat: Debat, max_per_group: int, time_between_round: int, max_representant: int) -> dict[ str:list[list[UserProfile]] , str:int , str:int]:
    
    #Firstly, we are going to check if the max_per_group is coherent with the number of participants.
    participants = debat.get_participants()
    if participants is None or len(participants) == 0:
        raise ValueError("No participants found in the debate. Wait for participants before proceeding.")
    groups = split_into_groups(participants, max_per_group)
    if groups == []:
        raise ValueError("No groups created, check the number of participants and max_per_group")
    elif len(groups) == 1:
        return {
            "initial_groups": {1 : 1},
            "num_rounds": 0,
            "estimated_duration": 0
        }
    
        
    
    else:
        print(f"Nombre de groupes créés : {len(groups)}")
        #initial_group_composition = tuple(len(group) for group in groups)
        #print(initial_group_composition)

        #Secondly, we will estimate the total time of the debate based on the number of groups, the time between rounds and the number of representatives per group.
        # We also take this opportunity to save all the groups that have been computed into a list. Even if not used for now

        debat_groups_structure = [groups]    

        num_rounds = 0
        max_iterations = 30  # Security counter to avoid infinite loop
        while len(groups) > 1 and num_rounds < max_iterations:
            num_rounds += 1
            groups = next_step_preparation(groups, max_per_group, max_representant)
            debat_groups_structure.append(groups)
            print(f"Nombre de groupes après l'étape {num_rounds} : {len(groups)}")
            if num_rounds == max_iterations:
                print("Avertissement : nombre maximal d'itérations atteint, boucle interrompue pour éviter une boucle infinie.")
                return {
                    "initial_groups": get_composition_groups(debat_groups_structure[0]),
                    "nb_groups": len(debat_groups_structure[0]),
                    "num_rounds": num_rounds,
                    "estimated_duration": 0
                }
                

        estimated_duration = num_rounds * time_between_round

       

        print(f"Durée totale estimée du débat : {estimated_duration} minutes")
        return {
            "initial_groups":  get_composition_groups(debat_groups_structure[0]),
            "nb_groups": len(debat_groups_structure[0]),
            "num_rounds": num_rounds,
            "estimated_duration": estimated_duration
        }



        """
        for i, group in enumerate(groups):
            group_obj = Group.objects.create(debat=debat, phase=2)
            for participant in group:
                GroupUserProfile.objects.create(group=group_obj, participant=participant)
            print(f"Groupe {i+1} créé avec {len(group)} participants.")
        
        # Update the debate with the new parameters
        debat.max_per_group = max_per_group
        debat.time_between_round = time_between_round
        debat.max_representant = max_representant
        debat.save()
        
        """
        