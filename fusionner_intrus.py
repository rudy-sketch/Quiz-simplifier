import json
import os

# --- Configuration des fichiers ---
MAIN_FILE = 'questions_intrus.json'
ADD_FILE = 'questions_intrus_a_ajouter.json'

class BColors:
    """Classe pour ajouter des couleurs dans la console."""
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_intrus_signature(question_data):
    """Crée une signature unique pour une question intrus (thème + réponses triées)."""
    theme_text = question_data.get('theme', '').lower().strip()
    answers = sorted([ans.get('texte', '').lower().strip() for ans in question_data.get('reponses', [])])
    return (theme_text, tuple(answers))

def merge_intrus_questions():
    """Fusionne les questions d'un fichier d'ajout dans le fichier principal des questions intrus."""
    print(f"{BColors.HEADER}{BColors.BOLD}--- Script de Fusion pour Questions 'Intrus' ---{BColors.ENDC}")

    # --- Étape 1: Charger le fichier d'ajout ---
    if not os.path.exists(ADD_FILE):
        print(f"{BColors.FAIL}Erreur : Le fichier d'ajout '{ADD_FILE}' est introuvable.{BColors.ENDC}")
        return

    try:
        with open(ADD_FILE, 'r', encoding='utf-8') as f:
            add_data = json.load(f)
        if not isinstance(add_data, list):
            print(f"{BColors.FAIL}Erreur : Le fichier '{ADD_FILE}' doit être une liste JSON (commençant par '[').{BColors.ENDC}")
            return
        if not add_data:
            print(f"{BColors.WARNING}Le fichier d'ajout '{ADD_FILE}' est vide. Aucune opération nécessaire.{BColors.ENDC}")
            return
        print(f"{BColors.OKGREEN}Lecture de '{ADD_FILE}' réussie.{BColors.ENDC}")
    except Exception as e:
        print(f"{BColors.FAIL}Erreur de lecture du fichier '{ADD_FILE}': {e}{BColors.ENDC}")
        return

    # --- Étape 2: Charger le fichier principal (ou le créer s'il n'existe pas) ---
    main_data = []
    if os.path.exists(MAIN_FILE):
        try:
            with open(MAIN_FILE, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
            if not isinstance(main_data, list):
                print(f"{BColors.FAIL}Erreur : Le fichier principal '{MAIN_FILE}' doit être une liste JSON.{BColors.ENDC}")
                return
            print(f"{BColors.OKGREEN}Lecture du fichier principal '{MAIN_FILE}' réussie.{BColors.ENDC}")
        except Exception as e:
            print(f"{BColors.FAIL}Erreur de lecture du fichier '{MAIN_FILE}': {e}{BColors.ENDC}")
            return
    else:
        print(f"{BColors.WARNING}Le fichier principal '{MAIN_FILE}' n'existe pas. Il sera créé.{BColors.ENDC}")

    # --- Étape 3: Préparer les données pour la fusion ---
    existing_signatures = {get_intrus_signature(q) for q in main_data}
    
    questions_to_add = []
    duplicates_ignored = 0

    # --- Étape 4: Analyser et préparer la fusion ---
    for q_to_add in add_data:
        signature = get_intrus_signature(q_to_add)
        if signature not in existing_signatures:
            if 'active' not in q_to_add:
                q_to_add['active'] = True
            questions_to_add.append(q_to_add)
            existing_signatures.add(signature) # Mettre à jour pour ne pas ajouter de doublons internes au fichier d'ajout
        else:
            duplicates_ignored += 1

    # --- Étape 5: Afficher le rapport et demander confirmation ---
    print("\n" + BColors.BOLD + "--- RAPPORT DE FUSION ---" + BColors.ENDC)
    if questions_to_add:
        print(f"Questions à ajouter : {BColors.OKGREEN}{len(questions_to_add)}{BColors.ENDC}")
    if duplicates_ignored > 0:
        print(f"Doublons ignorés : {BColors.WARNING}{duplicates_ignored}{BColors.ENDC}")
    
    if not questions_to_add:
        print(f"\n{BColors.OKGREEN}Aucune nouvelle question à ajouter. Le fichier principal est déjà à jour.{BColors.ENDC}")
        return

    choice = input(f"\n{BColors.WARNING}Voulez-vous procéder et mettre à jour '{MAIN_FILE}' ? (o/n) : {BColors.ENDC}").lower()
    
    if choice in ['o', 'oui']:
        main_data.extend(questions_to_add)
        try:
            with open(MAIN_FILE, 'w', encoding='utf-8') as f:
                json.dump(main_data, f, indent=4, ensure_ascii=False)
            print(f"\n{BColors.OKGREEN}Le fichier '{MAIN_FILE}' a été mis à jour avec succès !{BColors.ENDC}")

            clear_choice = input(f"Voulez-vous vider le fichier '{ADD_FILE}' maintenant ? (o/n) : ").lower()
            if clear_choice in ['o', 'oui']:
                with open(ADD_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f) # Vider avec une liste vide
                print(f"Le fichier '{ADD_FILE}' a été vidé.")
        except Exception as e:
            print(f"\n{BColors.FAIL}Une erreur est survenue lors de l'écriture du fichier : {e}{BColors.ENDC}")
    else:
        print("\nOpération annulée. Aucune modification n'a été apportée.")

if __name__ == '__main__':
    merge_intrus_questions()