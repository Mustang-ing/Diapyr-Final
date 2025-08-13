import datetime
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now

from django.views.decorators.csrf import csrf_exempt
from zerver.decorator import zulip_login_required
from zerver.lib.response import json_success
from zerver.models import UserProfile
from zerver.models.debat import  Debat
from zerver.actions.subscribe_debat import do_subscribe_user_to_debat
from zerver.lib.exceptions import JsonableError
from zerver.lib.split_into_groups import phase2_preparation

@zulip_login_required
@csrf_exempt
def diapyr_update_debat_phase2(
    request: HttpRequest,
    user_profile: UserProfile,
    debat_id: int
) -> HttpResponse:
    
    """
    This endpoint allows updating the parameters of a debate.
    It collects the parameters from the request and calls the do_update_debat function.
    """

    try: 
        debat = Debat.objects.get(debat_id=debat_id)
         # Get participants in the debate
        participants = debat.get_participants()
        nb_participants = participants.count()
        print(f"Nombre de participants : {nb_participants}")

    except Debat.DoesNotExist:
        raise JsonableError(f"Debate with ID {debat_id} not found")
    
    if debat.creator_id != user_profile:
        raise JsonableError("You are not authorized to update this debate.")
    
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST) 

    if request.method == "POST":
        start_date = request.POST.get('start_date', '').strip()
        start_time = request.POST.get('start_time', '').strip()
        max_per_group = int(request.POST.get('max_per_group', 0))
        time_between_round = int(request.POST.get('time_between_round', 0))
        max_representant = int(request.POST.get('nb_rep_per_grp', 0))

        start_date = f"{start_date} {start_time}" if start_time else start_date

        try:
            # La on doit appeler la méthode pour calculer les paramètres du débat
            result = phase2_preparation(
                debat=debat,
                max_per_group=max_per_group,
                time_between_round=time_between_round,
                max_representant=max_representant
            )

            if result["num_rounds"] == 0:
                raise JsonableError("Only one group created, check the number of participants and max_per_group")
            
            print("Phase 2 preparation result:", result)

             # Update the debate with the new parameters
            debat.max_per_group = max_per_group
            debat.time_between_round = time_between_round
            debat.max_representant = max_representant
            debat.start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M") - timedelta(hours=2) # Set start date substract 2 hours because of the stupid bug of Windows
            debat.save()


            return json_success(request, data={"message": f"Debate {debat.title} updated successfully"})
        except ValueError as e:
            raise JsonableError(str(e))
        except Debat.DoesNotExist:
            raise JsonableError(f"Debate with ID {debat_id} not found")
        
    else:
        return HttpResponse("Method not allowed", status=405)   