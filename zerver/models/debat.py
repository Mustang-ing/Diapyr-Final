from django.db import models
from django.utils import timezone


class Participant(models.Model):
    participant_id = models.AutoField(primary_key=True)
    email = models.EmailField()
    pseudo = models.CharField(max_length=100, null=False, default="")
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
    end_date = models.DateTimeField()
    time_between_round = models.IntegerField()
    num_pass = models.IntegerField()
    step = models.IntegerField(default=1)
    description = models.TextField(default="")
    date = models.DateTimeField(default=timezone.now)
    channel_created = models.BooleanField(default=False)
    debat_created = models.BooleanField(default=False)
    type = models.CharField(max_length=100, choices=Debate_Kind.choices,default=Debate_Kind.General)
    debat_participant = models.ManyToManyField(Participant)
    #group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)

    #List User ?
    # List Group ?
    def __str__(self):
        return self.title
