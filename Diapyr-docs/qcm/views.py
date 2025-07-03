from django.shortcuts import render, redirect
from django.contrib.auth.models import User  # Ou ton propre modèle si tu as un CustomUser

def sondage_view(request):
    users = User.objects.all()  # Filtre selon ton groupe si besoin

    if request.method == 'POST':
        selected_ids = request.POST.getlist('votes')
        voted_users = User.objects.filter(id__in=selected_ids)

        # Ici tu peux afficher dans la console les utilisateurs sélectionnés
        print("Utilisateurs ayant voté :")
        for user in voted_users:
            print(user.username)

        # Tu peux aussi stocker ou rediriger selon ton besoin
        return redirect('merci')  # Ou une autre vue

    return render(request, 'qcm/sondage.html', {'users': users})
