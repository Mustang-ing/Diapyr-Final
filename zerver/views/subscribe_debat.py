from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now

from django.views.decorators.csrf import csrf_exempt
from zerver.decorator import zulip_login_required
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile
from zerver.models.debat import  Debat, Participant
from zerver.actions.subscribe_debat import do_subscribe_user_to_debat
from zerver.lib.exceptions import JsonableError



@zulip_login_required
@csrf_exempt
def subscribe_user_to_debat(
    request: HttpRequest,
    user_profile: UserProfile,
    #*, # Uncomment if you want to enforce keyword-only arguments
    age: int,
    domaine: str,
    profession: str
)-> HttpResponse:
    
    """
    This endpoint is a substitution for the diapyr_join_debat view from diapyr.py, in order to be more RESTful.
    We simply collecting the parameters from the request and calling the do_subscribe_user_to_debat function.
    for subscribing a user to a debate.
    """
    
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST) 

    if request.method == "POST":
        debat_id = request.POST.get('debat', '').strip()
        age = request.POST.get('age', '').strip()
        domaine = request.POST.get('domaine', '').strip()
        profession = request.POST.get('profession', '').strip()

    try:
        debat = Debat.objects.get(debat_id=int(debat_id))
        print(f"Debat : {debat.title} | Utilisateur à inscrire - 1 : { user_profile.full_name} | Utilisateur à inscrire - 2 : {user_profile.get_username()}")
        do_subscribe_user_to_debat(
            user_profile=user_profile.get_username(),
            debat_id=debat.debat_id,
            username=user_profile.full_name,
            age=age,
            domaine=domaine,
            profession=profession
        )
        return json_success(request, data={"message": "User {user_profile.full_name} subscribed sucessfully to the debate {debat.title}"})
    except ValueError as e:
        raise JsonableError(str(e))
    except Debat.DoesNotExist:
        raise JsonableError(("Debate {debat.title} not found"))


    

