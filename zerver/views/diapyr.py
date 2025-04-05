from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

def formulaire_debat(request: HttpRequest) -> HttpResponse:
    """
    View to render the debate form page.
    """
    return render(request, 'zerver/app/formulaire_debat.html')


def diapyr_home(request: HttpRequest) -> HttpResponse:
    """
    View to render the home page of Diapyr.
    """
    return render(request, 'zerver/app/diapyr_home.html')


