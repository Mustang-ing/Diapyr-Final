from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from zerver.decorator import zulip_login_required
from zerver.models import UserProfile
from zerver.models.debat import Debat, Participant
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
        creator_id = request.user
        print(type(creator_id))
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
            creator_id=creator_id,
            max_per_group=max_per_group,
            time_between_round=time_between_round,
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
        user_id = request.user.id
        print(f"User ID : {user_id}")
        username = request.user.full_name
        print(f"Username : {username}")
        age = request.POST.get('age', '').strip()
        domaine = request.POST.get('domaine', '').strip()
        profession = request.POST.get('profession', '').strip()


        try:
            debat = Debat.objects.get(debat_id=debat_id)
            participant = Participant.objects.create(
                user_id=user_id,
                pseudo=username,
                age=age ,
                domaine=domaine ,
                profession=profession
            )
            
            debat.debat_participant.add(participant)
            return redirect(reverse('home'))  # Redirect to diapyr_home after successfully joining a debate
        except Debat.DoesNotExist:
            return HttpResponse("Debate not found.", status=404)

    else:
        return render(request, 'zerver/app/diapyr_join_debat.html', {'debat': debat})



