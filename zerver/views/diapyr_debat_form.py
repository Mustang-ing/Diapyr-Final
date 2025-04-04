from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

def formulaire_debat(request: HttpRequest) -> HttpResponse:
    """
    View to render the debate form page.
    """
    return render(request, 'zerver/app/formulaire_debat.html')
