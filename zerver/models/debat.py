from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField  




class Participant(models.Model):
    participant_id = models.AutoField(primary_key=True)
    #user_id = models.IntegerField(null=True,blank=True)
    #user = models.OneToOneField('zerver.UserProfile',on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()
    pseudo = models.CharField(max_length=100, null=False, default="")
    age = models.CharField(max_length=20, blank=True, null=True)
    domaine = models.CharField(max_length=100, blank=True, null=True)
    profession = models.CharField(max_length=100, blank=True, null=True)
    is_register = models.BooleanField(default=False)

    def __str__(self):
        return self.pseudo



class Debat(models.Model):

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
    creator_email = models.EmailField()
    max_per_group = models.IntegerField()
    end_date = models.DateTimeField() # To rename to end_subscription_date
    time_between_round = models.IntegerField() 
    num_pass = models.IntegerField() # Il faut choisir l'un ou l'autre
    step = models.IntegerField(default=1)
    description = models.TextField(default="")
    date = models.DateTimeField(default=timezone.now) # C'est quoi la différence avec end_date ?
    channel_created = models.BooleanField(default=False) # To remove, if useless
    debat_created = models.BooleanField(default=False) 
    is_archived = models.BooleanField(default=False, null=True)
    type = models.CharField(max_length=100, choices=Debate_Kind.choices,default=Debate_Kind.General)
    debat_participant = models.ManyToManyField(Participant)
    criteres = ArrayField(models.CharField(max_length=50), default=list, blank=True, null=True)

    #group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)

    #List User ?
    # List Group ?
    def __str__(self):
        return self.title
