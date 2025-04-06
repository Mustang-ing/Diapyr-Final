from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from zerver.models.debat import Debat
from datetime import datetime, timedelta

@csrf_exempt
def formulaire_debat(request: HttpRequest) -> HttpResponse:
    """
    View to render the debate form page and handle POST requests.
    """
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST)  
    if request.method == "POST":
        #Request POST est un dictionnaire (QueryList)
        title = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        end_date_str =  request.POST.get('Date_fin', '').strip()
        creator_email = request.POST.get('email', '').strip()
        max_per_group = int(request.POST.get('nb_max', 0))
        time_between_round = int(request.POST.get('time_step', 0))
        num_pass = int(request.POST.get('step', 0))

        if not title or not end_date_str or not creator_email or max_per_group <= 0 or time_between_round <= 0 or num_pass <= 0:
            return HttpResponse("Invalid form data. Please fill out all fields correctly.", status=400)

        end_date = datetime.now() + timedelta(minutes=int(end_date_str))

        Debat.objects.create(
            title=title,
            description=description,
            end_date=end_date,
            creator_email=creator_email,
            max_per_group=max_per_group,
            time_between_round=time_between_round,
            num_pass=num_pass
        )

        print(Debat.objects.all())

        return HttpResponse(f"Received debate topic: {title}")
    else:
        # Render the form for GET requests
        return render(request, 'zerver/app/formulaire_debat.html')


def diapyr_home(request: HttpRequest) -> HttpResponse:
    """
    View to render the home page of Diapyr.
    """
    return render(request, 'zerver/app/diapyr_home.html')


