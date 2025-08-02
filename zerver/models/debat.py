from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField  
from zerver.models.users import get_user_profile_by_id
from zerver.models import(
    UserProfile,
) 




class Participant(models.Model):

    """A participant in a debate represent a temporary identity that are linked to a debate.
Therefore a single user can have multiple participants in different debates."""

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='participants', null=True, blank=True)
    pseudo = models.CharField(max_length=100, null=False, default="") # Il faudrait peut être le passer en fonction property si le user change son nom.
    age = models.CharField(max_length=20, blank=True, null=True)
    domaine = models.CharField(max_length=100, blank=True, null=True)
    profession = models.CharField(max_length=100, blank=True, null=True)
    is_register = models.BooleanField(default=False, null=True)
    is_representative = models.BooleanField(default=False, null=True)


    #Defining utility methods that used user.py methods

    def __str__(self):
        return self.pseudo
    
    @property #The decorator @property allows us to access the email as an attribute.
    def email(self) -> str | None:
        return self.user.email if self.user else None
    
    def get_user_profile_by_id(self) -> UserProfile | None:
        if self.user_id:
            return get_user_profile_by_id(self.user_id)
        return None


class Debat(models.Model):

    """The table debat centralize all the debates that are created in the system."""

    class Debate_Kind(models.TextChoices):
        Society = 'Society'
        Politics = 'Politics'
        Science = 'Science'
        Philosophy = 'Philosophy'
        Religion = 'Religion'
        General = 'General'
        #More if you want 

    debat_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100,null=False,default="")
    creator = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_debates', null=True, blank=True,default=None)
    max_per_group = models.IntegerField()
    subscription_end_date = models.DateTimeField()
    start_date = models.DateTimeField(null=True, blank=True)  # Date when the debate starts
    time_between_round = models.IntegerField()
    """There are many steps in a debate, and each step has a function in the process.
        Step 1: Phase of subscription, where users can subscribe to the debate.
        Step 2: Phase of decision, where the creator of the debat chose the appropriate parameters of the debates. It could be skipped in future releases.
        Step 3-n: Phase of the debate, where users can discuss and vote for the representative of their group. We have a new step when each debate session is finished and vote occurs.
    """ 
    step = models.IntegerField(default=1)
    description = models.TextField(null=True, blank=True, default="")
    creation_date = models.DateTimeField(default=timezone.now) 
    debat_created = models.BooleanField(default=False) # A terme, il faudrait plutôt utiliser step pour savoir si le débat à démarré ou pas.
    is_archived = models.BooleanField(default=False, null=True)
    type = models.CharField(max_length=100, choices=Debate_Kind.choices,null=True, default=Debate_Kind.General)
    debat_participant = models.ManyToManyField(Participant)
    #criteres = ArrayField(models.CharField(max_length=50), default=list, blank=True, null=True)

    def __str__(self):
        return self.title
    
    @property
    def creator_email_copilot(self) -> str | None:
        if self.creator_id:
            return self.creator_id.email
        return None

    @property
    def creator_email(self) -> str | None:
        if self.creator_id:
            return get_user_profile_by_id(self.creator_id).email
        return None
    
    def get_participants(self):
        """Return a list of participants in the debate."""
        return self.debat_participant.all()
    
    def update_step1(self):
        """Increment the step of the debate."""
        if self.step == 1:
            if self.subscription_end_date < timezone.now():
                self.step = 2
                self.save()
    
    

def check_subscription_end_date(debat: Debat) -> bool:
    """
    Check if the subscription end date is over.
    This is used to determine if a user can still subscribe to the debate.
    """
    return debat.subscription_end_date > timezone.now()

def check_user_already_participant(debat: Debat, user_profile: UserProfile) -> bool:
    """
    Check if the user is already a participant in the debate.
    This is used to prevent duplicate subscriptions.
    """
    return debat.debat_participant.filter(user_id=user_profile).exists()
    

class Group(models.Model):
    """In Dipayr there a many groups in a phase of a debate. 
    A group is a collection of participants"""

    id = models.AutoField(primary_key=True)
    debat = models.ForeignKey(Debat, on_delete=models.CASCADE, related_name='groups')
    phase = models.IntegerField(default=1)  # Phase of the debate
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(Participant, through='GroupParticipant', related_name='+')

    def __str__(self):
        return f"Group {self.id} for Debate {self.debat.title} (Phase {self.phase})"
    

class GroupParticipant(models.Model):
    """A group participant is a participant that is in a group.
    A participant can be in multiple groups, but only one group per debate."""

    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='+')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='group_participants')

    def __str__(self):
        return f"{self.participant.pseudo} in Group {self.group.id} of Debate {self.group.debat.title}"
    

class Vote(models.Model):
    """
    During the process of a debate, a user can vote for several other users to elect a representative
    There is only one vote per group, and a user can vote for multiple users.
    """

    id = models.AutoField(primary_key=True) 
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='vote')
    voter = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='votes_cast')
    voted_participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='votes_received')
    vote_date = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=20, default='pending',null=True,blank=True)  # pending, accepted, rejected
    phase = models.IntegerField(default=1)  # Phase of the debate

    def __str__(self):
        return f"Vote for group {self.group_id}"
    
    

    
