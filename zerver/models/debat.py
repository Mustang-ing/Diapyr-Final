from datetime import date, timedelta
from django.db import models
from django.utils import timezone
from zerver.models import(
    UserProfile,
    Stream
) 


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
    debat_participants = models.ManyToManyField(UserProfile,through='Participant', related_name='participate_at', blank=True)
    max_per_group = models.IntegerField()  # Maximum number of participants per group)
    max_representant = models.IntegerField(null=True, blank=True)
    subscription_end_date = models.DateTimeField()
    start_date = models.DateTimeField(null=True, blank=True, default=None)  # Date when the debate starts
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
    is_validated = models.BooleanField(default=False, null=True)  # Indicates if the debate parameters are validated by the creator
    type = models.CharField(max_length=100, choices=Debate_Kind.choices,null=True, default=Debate_Kind.General)
    #criteres = ArrayField(models.CharField(max_length=50), default=list, blank=True, null=True)

    def __str__(self):
        return self.title
    
    def get_participants(self):
        """Return a list of participants in the debate."""
        return self.debat_participants.all()
    

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



class Participant(models.Model):

    "The old class/model Participant is now a joint table between Debat and UserProfile"
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE,related_name='participate')
    debat = models.ForeignKey(Debat, on_delete=models.CASCADE,related_name='debat_participant')
    #Those field we're moved out UserProfile because there are specific to a participation on a debate and not to a user (Who can participate at multiple debates)
    is_registered_to_a_debate = models.BooleanField(null=True, default=False)
    is_active_in_diapyr = models.BooleanField(null=True, default=False)
    is_representative = models.BooleanField(null=True, default=False)
    current_tour = models.IntegerField(null=True, default=None)
    
    #The class Meta is used to add a constraint to ensure the couple (user,debat) is unique 
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'debat'], name='unique_participant')
        ]


    def __str__(self):
        return f"Participant {self.user.full_name} in Debate {self.debat.title}"


    def register_to(self) -> None:
        """Register the user to the debate."""
        self.is_registered_to_a_debate = True
        self.save()


class Group(models.Model):
    """In Dipayr there a many groups in a phase of a debate. 
    A group is a collection of participants"""

    id = models.AutoField(primary_key=True)
    debat = models.ForeignKey(Debat, on_delete=models.CASCADE, related_name='groups')
    stream = models.OneToOneField(Stream, on_delete=models.CASCADE, related_name='group', null=True, blank=True) 
    group_name = models.CharField(max_length=100, null=True, blank=True)  # Optional name for the group
    phase = models.IntegerField(default=1)  # Phase of the debate
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(UserProfile, through='GroupParticipant', related_name='group_participants')

    def __str__(self):
        return f"Group {self.id} for Debate {self.debat.title} (Phase {self.phase})"
    
    def get_users_id(self):
        """Return a list of user IDs in the group."""
        return [id for id in self.members.values_list('id', flat=True) ]
    
    def get_users_emails(self):
        """Return a list of user emails in the group."""
        return [email for email in self.members.values_list('email', flat=True)]


class GroupParticipant(models.Model):
    """A group participant is a participant that is in a group.
    A participant can be in multiple groups, but only one group per debate."""

    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    participant = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.participant.full_name} in Group {self.group.id} of Debate {self.group.debat.title}"
    
            

class Vote(models.Model):
    """
    During the process of a debate, a user can vote for several other users to elect a representative
    There is only one vote per group, and a user can vote for multiple users.
    """

    id = models.AutoField(primary_key=True) 
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='vote')
    voter = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='votes_cast')
    voted_participant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='votes_received')
    vote_date = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=20, default='pending',null=True,blank=True)  # pending, accepted, rejected
    phase = models.IntegerField(default=1)  # Phase of the debate

    def __str__(self):
        return f"Vote for group {self.group_id}"
    
    

    
