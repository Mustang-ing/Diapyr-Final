from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def formulaire_debat(request: HttpRequest) -> HttpResponse:
    """
    View to render the debate form page and handle POST requests.
    """
    print('La méthode de requête est : ', request.method)
    print('Les données POST sont : ', request.POST)  
    if request.method == "POST":
        # Traitement des données pour une requête POST 
        data = request.POST # --> Contient les données sous forme d'un dictionnaire
        # Example: Extract a field named 'debate_topic'
        debate_topic = data.get('debate_topic', 'No topic provided')
        # You can add logic to save this data or process it further
        return HttpResponse(f"Received debate topic: {debate_topic}")
    else:
        # Render the form for GET requests
        return render(request, 'zerver/app/formulaire_debat.html')


def diapyr_home(request: HttpRequest) -> HttpResponse:
    """
    View to render the home page of Diapyr.
    """
    return render(request, 'zerver/app/diapyr_home.html')


