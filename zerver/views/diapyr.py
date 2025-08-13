from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from zerver.decorator import zulip_login_required
from zerver.lib.split_into_groups import phase2_preparation
from zerver.models import UserProfile
from zerver.models.debat import Debat
from datetime import datetime, timedelta




# Fonctionnalité Diapyr sur la page d'accueil
"""
Zulip_login_required fonctionne de la même manière que login_required, mais il contrôle que les cookies de session sont valides pour Zulip.
"""
@zulip_login_required
@csrf_exempt
@transaction.atomic(durable=True) # Ensure atomicity for database operations
def formulaire_debat(request: HttpRequest) -> HttpResponse:
    
    #View to render the debate form page and handle POST requests.
    
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST) 
    #Enregistrement des champs 
    if request.method == "POST":
        #criteres = request.POST.getlist("criteres[]")
        #print("✅ Critères cochés :", criteres)
        title = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        creator = request.user # We pass a UserProfile object
        end_date_str = request.POST.get('Date_fin', '').strip()
        max_per_group = int(request.POST.get('nb_max', 0))
        time_between_round = int(request.POST.get('time_step', 0))
        num_pass = int(request.POST.get('step', 1))

        if not title or not end_date_str or max_per_group <= 0 or time_between_round <= 0 or num_pass <= 0:
            print("❌ Formulaire invalide : un ou plusieurs champs sont vides ou incorrects.")
            print(f"Form data: title={title}, end_date_str={end_date_str}, max_per_group={max_per_group}, time_between_round={time_between_round}, num_pass={num_pass}")
            return HttpResponse("Invalid form data. Please fill out all fields correctly.", status=400)

        end_date = datetime.now() + timedelta(minutes=int(end_date_str))
        # Initialisation d'un objet debat.
        Debat.objects.create(
            title=title,
            description=description,
            subscription_end_date=end_date,
            creator=creator,
            max_per_group=max_per_group,
            time_between_round=time_between_round,
            start_date=end_date + timedelta(minutes=30),  # Set start date 30 minutes after end date
        )
        return redirect(reverse('home'))  # Redirect to diapyr_home after successful form submission
    else:
        return render(request, 'zerver/app/formulaire_debat.html')

@zulip_login_required
def diapyr_home(request: HttpRequest) -> HttpResponse:
    debat = Debat.objects.all()
    print(request.user)
    print(type(request.user))
    print(request.session.items())
    #print(f"User profile: {user_profile}")
    #print(f"User ID: {user_id}")
    return render(request, 'zerver/app/diapyr_home.html', {'debat': debat})


@zulip_login_required 
@csrf_exempt
@transaction.atomic(durable=True)
def diapyr_join_debat(request: HttpRequest) -> HttpResponse:
    debat = Debat.objects.all()
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST)  

    if request.method == "POST":
        debat_id = request.POST.get('debat', '').strip()
        username = request.user.full_name
        print(f"Username : {username}")
    
        try:
            debat = Debat.objects.get(debat_id=debat_id)
            # Add the participant to the debate
            debat.debat_participants.add(request.user)  # Add the user directly to the debate
            return redirect(reverse('home'))  # Redirect to diapyr_home after successfully joining a debate
        except Debat.DoesNotExist:
            return HttpResponse("Debate not found.", status=404)

    else:
        return render(request, 'zerver/app/diapyr_join_debat.html', {'debat': debat})
    

@zulip_login_required
@transaction.atomic(durable=True)
def show_debates(request: HttpRequest) -> HttpRequest:

    my_debates = Debat.objects.filter(creator=request.user) #Ou encore creator_id=request.user.id
    #1 - Récupérer tous les participant_id associé à l'user
    #2 - Dans la table jointes, récupérer les débat associé à ces participant_id
    #Easiest way is to use the ManyToMany relationship in Django.
    
    joined_debates = list(UserProfile.objects.get(id=request.user.id).debates_participated.all())
    print(f"Joined debates : {joined_debates}")

    active_debates = [ debat for debat in joined_debates if not debat.is_archived ]
    print(f"Active debates: {active_debates}")
    return render(request, 'zerver/app/diapyr_my_debates.html', {
        'my_debates': my_debates,
        'joined_debates': joined_debates,
        'active_debates': active_debates,
    })


@zulip_login_required
@transaction.atomic(durable=True)
def show_debates_detail(request: HttpRequest, debat_id: int) -> HttpResponse:
    try:
        debat = Debat.objects.get(debat_id=debat_id)
        # Get participants in the debate
        participants = debat.get_participants()
        nb_participants = participants.count()
        print(f"Nombre de participants : {nb_participants}")
        
    except Debat.DoesNotExist:
        return HttpResponse("Debate not found.", status=404)

    if debat.creator.id != request.user.id:
        return HttpResponse("Vous n'êtes pas l'organisateur du débat",status=403)
    
    if request.method == "POST":
        print('La méthode de requête est : ', request.method)
        print('Les données POST sont : ', request.POST) 

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
                return HttpResponse("Only one group created, check the number of participants and max_per_group", status=400)
            
            print("Phase 2 preparation result:", result)

            print(f"Old parameters of {debat} : max_per_group={debat.max_per_group}, time_between_round={debat.time_between_round}, max_representant={debat.max_representant}, start_date={debat.start_date}")
            
            # Update the debate with the new parameters
            debat.max_per_group = max_per_group
            debat.time_between_round = time_between_round
            debat.max_representant = max_representant
            debat.start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M") - timedelta(hours=2) # Set start date substract 2 hours because of the stupid bug of Windows
            debat.save()

            print(f"New parameters of {debat} : max_per_group={debat.max_per_group}, time_between_round={debat.time_between_round}, max_representant={debat.max_representant}, start_date={debat.start_date}")


            return render(request,'zerver/app/diapyr_debate_detail.html', {
                    'debat': debat,
                    'participants': participants,
                    'nb_participants': nb_participants,
                    'result': result,
                    'message': f"Debate {debat.title} updated successfully"
                })
        except ValueError as e:
            return HttpResponseBadRequest(str(e))
        except Debat.DoesNotExist:
            return HttpResponse("Debate not found.", status=404)
    else:
        return render(request, 'zerver/app/diapyr_debate_detail.html', {
            'debat': debat,
            'participants': participants,
            'nb_participants': nb_participants,
        })






    

    


