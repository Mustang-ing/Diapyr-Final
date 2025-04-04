document.getElementById('debateForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const messageDiv = document.getElementById('message');
    messageDiv.style.display = 'none';

    // Validation client
    const age = parseInt(document.getElementById('age').value);
    if (age < 0 || age > 120) {
        showMessage("Âge invalide !", 'error');
        return;
    }

    // Construction de l'objet données
    const formData = {
        age: age,
        gender: document.getElementById('gender').value,
        country: document.getElementById('country').value,
        level: document.getElementById('level').value,
        timestamp: new Date().toISOString()
    };

    try {
        // Envoi au serveur
        const response = await fetch('https://votre-serveur.com/api/debate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        
        showMessage("Inscription réussie !", 'success');
        document.getElementById('debateForm').reset();

    } catch (error) {
        showMessage(`Échec de l'envoi: ${error.message}`, 'error');
    }
});

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.style.display = 'block';
}