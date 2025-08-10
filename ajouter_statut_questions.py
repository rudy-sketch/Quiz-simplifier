import json

# Noms de vos fichiers de questions
QUESTIONS_SIMPLES_FILE = 'questions_simples.json'
QUESTIONS_INTRUS_FILE = 'questions_intrus.json'

def add_status_to_simple_questions():
    try:
        with open(QUESTIONS_SIMPLES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False
        for theme, questions in data.items():
            for question in questions:
                if 'active' not in question:
                    question['active'] = True
                    modified = True

        if modified:
            with open(QUESTIONS_SIMPLES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"'{QUESTIONS_SIMPLES_FILE}' a été mis à jour avec le statut 'active'.")
        else:
            print(f"'{QUESTIONS_SIMPLES_FILE}' est déjà à jour.")

    except FileNotFoundError:
        print(f"Erreur: Le fichier '{QUESTIONS_SIMPLES_FILE}' n'a pas été trouvé.")
    except json.JSONDecodeError:
        print(f"Erreur: Le fichier '{QUESTIONS_SIMPLES_FILE}' contient un JSON invalide.")

def add_status_to_intrus_questions():
    try:
        with open(QUESTIONS_INTRUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False
        for question in data:
            if 'active' not in question:
                question['active'] = True
                modified = True

        if modified:
            with open(QUESTIONS_INTRUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"'{QUESTIONS_INTRUS_FILE}' a été mis à jour avec le statut 'active'.")
        else:
            print(f"'{QUESTIONS_INTRUS_FILE}' est déjà à jour.")

    except FileNotFoundError:
        print(f"Erreur: Le fichier '{QUESTIONS_INTRUS_FILE}' n'a pas été trouvé.")
    except json.JSONDecodeError:
        print(f"Erreur: Le fichier '{QUESTIONS_INTRUS_FILE}' contient un JSON invalide.")

if __name__ == '__main__':
    add_status_to_simple_questions()
    add_status_to_intrus_questions()
    print("\nVérification terminée.")