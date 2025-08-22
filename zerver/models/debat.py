from datetime import date, timedelta
from django.db import models
from django.utils import timezone
import zerver
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
    time_between_round = models.DurationField(null=True)  # Duration between each round in seconds, default is 60 seconds
    """There are many steps in a debate, and each step has a function in the process.
        Step 1: Phase of subscription, where users can subscribe to the debate.
        Step 2: Phase of decision, where the creator of the debat chose the appropriate parameters of the debates. It could be skipped in future releases.
        Step 3-n: Phase of the debate, where users can discuss and vote for the representative of their group. We have a new step when each debate session is finished and vote occurs.
    """ 
    step = models.IntegerField(default=1)

    """ According to the step, there are many important date
        creation_date : Which indicates when the debates has been created (Trivial)
        subscription_end_date : Indicates when the period of subscription for user is over (Step 1 -> Step 2). 
        start_date : It's the date where the debate starts, after the decision time (Step 2 -> Step 3). This date could be set to datime.now() when the skip process will be developped.

    """
    subscription_end_date = models.DateTimeField()
    start_date = models.DateTimeField(null=True, blank=True, default=None)  # Date when the debate starts
    creation_date = models.DateTimeField(default=timezone.now) 
    # A round is number of the debate session
    round = models.IntegerField(default=1)
    type = models.CharField(max_length=100, choices=Debate_Kind.choices,null=True, default=Debate_Kind.General)
    # In the use of API Zulip, we need to now which bot is used for the API functions
    diapyr_bot = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='diapyr_bot', null=True, blank=True, default=None)
    description = models.TextField(null=True, blank=True, default="")
    debat_created = models.BooleanField(default=False) # A terme, il faudrait plutôt utiliser step pour savoir si le débat à démarré ou pas.
    is_archived = models.BooleanField(default=False, null=True)
    is_validated = models.BooleanField(default=False, null=True)  # Indicates if the debate parameters are validated by the creator
    skip_pre_registration = models.BooleanField(default=False, null=True)  # Skip the pre-registration phase a.k.a phase 2, if the user chose default parameters
 
    #criteres = ArrayField(models.CharField(max_length=50), default=list, blank=True, null=True)

    def __str__(self):
        return self.title
    

    def set_default_parameters(self) -> None:
        """Set default parameters for the debate."""
        self.max_per_group = 5
        self.max_representant = 2
        self.time_between_round = 60
        self.subscription_end_date = self.creation_date
        self.skip_pre_registration = True
        self.save()

    def archive_debat(self) -> None:
        """Set the debate to archived."""
        self.is_archived = True
        self.save()
        print(f"Le débat '{self.title}' a été archivé.")

    # --- Convenience properties (preferred over old get_* methods) ---

    @property
    def participants(self) -> list[UserProfile]:
        """Return a list of participants in the debate."""
        return list(self.debat_participants.all())
    
    @property
    def active_participants(self):
        """Return a list of active participants in the debate."""
        return list(self.debat_participant.filter(is_active_in_diapyr=True))
    
    @property
    def bot_email(self) -> str | None:
        """Email of the debate's bot, or None if not set."""
        return self.diapyr_bot.email if self.diapyr_bot else None

    @property
    def bot_id(self) -> int | None:
        """User id of the debate's bot, or None if not set."""
        # Use implicit <field>_id attribute to avoid extra DB fetch.
        return self.diapyr_bot_id if self.diapyr_bot_id else None

    @property
    def all_groups(self):  # QuerySet[Group]
        """QuerySet of all groups in this debate."""
        return self.groups.all()
    @property
    def active_groups(self):
        return self.groups.filter(is_archived=False)

    @property
    def group_count(self) -> int:
        """Number of groups in this debate."""
        return self.groups.count()


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

def archived_all_groups(debat: Debat) -> None:
    """
    Archive all groups in the debate.
    """
    for group in debat.all_groups:
        group.stream.is_archived = True
        group.stream.save()
    print(f"Tous les groupes du débat '{debat.title}' ont été archivés.")

class Participant(models.Model):

    "The old class/model Participant is now a joint table between Debat and UserProfile"
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE,related_name='participate')
    debat = models.ForeignKey(Debat, on_delete=models.CASCADE,related_name='debat_participant')
    #Those field we're moved out UserProfile because there are specific to a participation on a debate and not to a user (Who can participate at multiple debates)
    is_registered_to_a_debate = models.BooleanField(null=True, default=False)
    # A participant is considered active while he hasn't been eliminated to the next phase
    is_active_in_diapyr = models.BooleanField(null=True, default=True)
    is_representative = models.BooleanField(null=True, default=False)
    current_tour = models.IntegerField(null=True, default=1)
    
    #The class Meta is used to add a constraint to ensure the couple (user,debat) is unique 
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'debat'], name='unique_participant')
        ]


    def __str__(self):
        return f"Participant {self.user.full_name} in Debate {self.debat.title}"
    
    @property
    def name(self):
        """Return the full name of the participant."""
        return self.user.full_name if self.user else "Unknown User"
    
    @property
    def email(self):
        """Return the email of the participant."""
        return self.user.email if self.user else "Unknown User"


class Group(models.Model):
    """In Dipayr there a many groups in a phase of a debate. 
    A group is a collection of participants"""

    id = models.AutoField(primary_key=True)
    debat = models.ForeignKey(Debat, on_delete=models.CASCADE, related_name='groups')
    stream = models.OneToOneField(Stream, on_delete=models.CASCADE, related_name='group', null=True, blank=True) 
    group_name = models.CharField(max_length=100, null=True, blank=True)  # Optional name for the group
    group_number = models.IntegerField(null=True,default=1)
    round = models.IntegerField(default=1)  # Phase of the debate
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(UserProfile, through='GroupParticipant', related_name='group_participants')
    is_archived = models.BooleanField(default=False, null=True)  # Indicates if the group is archived
    

    def __str__(self):
        return f"Group {self.id} for Debate {self.debat.title} (Round {self.round})"

    def get_users_id(self):
        """Return a list of user IDs in the group."""
        return [id for id in self.members.values_list('id', flat=True)]

    def get_users_emails(self):
        """Return a list of user emails in the group."""
        return [email for email in self.members.values_list('email', flat=True)]


    @property
    def representant_candidates(self):
        """Return a list of user profiles who are candidates for representative role."""
        return self.group_participants.filter(is_interested=True).values_list('participant', flat=True)

def get_participant_in_a_group(group: Group, user: UserProfile) :
    return group.group_participants.get(participant=user,group=group)


class GroupParticipant(models.Model):
    """A group participant is a participant that is in a group.
    A participant can be in multiple groups.
    The main difference between Participant and GroupParticipant is that GroupParticipant track a participant in all the different groups they are in.
    While Participant will simply linked a user to a debate.
    """

    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE,related_name='group_participants')
    participant = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    #It could be usefull to linked GroupParticipant to Participant
    is_interested = models.BooleanField(null=True, default=None) # Indicates if the voter is interested by becoming a representative
    is_representative = models.BooleanField(null=True, default=False)  # Indicates if the participant is a representative of the group
    has_voted = models.BooleanField(null=True, default=False)  # Indicates if the participant has voted in the current round

    
    #votes = models.ManyToManyField(Vote, related_name='group_participants', blank=True)

    def __str__(self):
        return f"{self.participant.full_name} in Group {self.group.id} of Debate {self.group.debat.title}"

class GroupVote(models.Model):
    """A vote cast by a participant in a group."""
    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_votes')
    participant = models.ForeignKey(GroupParticipant, on_delete=models.CASCADE)
    vote_for = models.ForeignKey(GroupParticipant, on_delete=models.CASCADE, related_name='votes_received', blank=True)

    def __str__(self):
        return f"Vote by {self.participant.full_name} in Group {self.group.id} of Debate {self.group.debat.title}"

class Vote(models.Model):
    """
    This table is used to represent a Vote session that occurs during a debate.
    THIS TABLE DOES NOT REPRESENT THE VOTE OF A USER
    During the process of a debate, a user can vote for several other users to elect a representative
    There is only one vote per group, and a user can vote for multiple users.
    """

    id = models.AutoField(primary_key=True) 
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='vote')
    # A Participant in a group can vote for many user that why we've got another M2M relation with vote
    group_vote = models.ManyToManyField(GroupParticipant, related_name='votes',default=None,blank=True)
    vote_date = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=20, default='pending',null=True,blank=True)  # pending, accepted, rejected
    round = models.IntegerField(default=1)  # Phase of the debate

    def __str__(self):
        return f"Vote for group {self.group_id}"
    

            


    

    
