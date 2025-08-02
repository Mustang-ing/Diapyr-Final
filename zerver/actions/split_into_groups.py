from django.db import transaction
from zerver.models import(
     UserProfile, 
     Stream,
     debat,
)
from debat import Debat, Participant, Group
from zerver.models.debat import Debat, Participant
from random import shuffle
import math


@transaction.atomic(durable=True)
def split_into_groups(debat: Debat) -> list[list[str]]:
        users = list(debat.get_participants())
        shuffle(users)

        n = len(users)
        m = debat.max_per_group

        if n <= m:
            return [users]

    
        print(f"Nombre de participants : {n}, Nombre maximal de participants par groupe : {m}")
        try:
            num_groups = math.ceil(n/m)
            print( math.ceil(n/m))
            print(f"Nombre de groupes calculé : {num_groups}")
        except ZeroDivisionError:
            return []


        
        min_per_group = n // num_groups
        r = n % num_groups
        groups = []
        print(f"Resultatat de la division : reste = {r}, min_per_group = {min_per_group}, max_per_group = {self.max_per_group}")
        start = 0
        for i in range(num_groups):
            group_size = min_per_group + (1 if i < r else 0) # On fait +1 tant que le nombre de peronne problématique n'est pas traité 
            print(f"groupe size {group_size}")
            groups.append(users[start:start + group_size])
            start += group_size

        print(f"Groupes créés : {len(groups)} - Groupes : {groups}")
        return groups