import json
import os

# --- Configuration des fichiers ---
MAIN_FILE = 'questions_simples.json'
ADD_FILE = 'questions_simples_a_ajouter.json'

class BColors:
    """Classe pour ajouter des couleurs dans la console."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_question_signature(question_data):
    """Crée une signature unique pour une question (texte + réponses triées)."""
    question_text = question_data.get('question', '').lower().strip()
    answers = sorted([ans.get('texte', '').lower().strip() for ans in question_data.get('reponses', [])])
    return (question_text, tuple(answers))

def merge_questions():
    """Fusionne les questions d'un fichier d'ajout dans un fichier principal."""
    print(f"{BColors.HEADER}{BColors.BOLD}--- Script de Fusion de Questions ---{BColors.ENDC}")

    # --- Étape 1: Charger le fichier d'ajout ---
    if not os.path.exists(ADD_FILE):
        print(f"{BColors.FAIL}Erreur : Le fichier d'ajout '{ADD_FILE}' est introuvable.{BColors.ENDC}")
        return

    try:
        with open(ADD_FILE, 'r', encoding='utf-8') as f:
            add_data = json.load(f)
        if not add_data:
            print(f"{BColors.WARNING}Le fichier d'ajout '{ADD_FILE}' est vide. Aucune opération nécessaire.{BColors.ENDC}")
            return
        print(f"{BColors.OKGREEN}Lecture de '{ADD_FILE}' réussie.{BColors.ENDC}")
    except Exception as e:
        print(f"{BColors.FAIL}Erreur de lecture du fichier '{ADD_FILE}': {e}{BColors.ENDC}")
        return

    # --- Étape 2: Charger le fichier principal (ou le créer s'il n'existe pas) ---
    main_data = {}
    if os.path.exists(MAIN_FILE):
        try:
            with open(MAIN_FILE, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
            print(f"{BColors.OKGREEN}Lecture du fichier principal '{MAIN_FILE}' réussie.{BColors.ENDC}")
        except Exception as e:
            print(f"{BColors.FAIL}Erreur de lecture du fichier '{MAIN_FILE}': {e}{BColors.ENDC}")
            return
    else:
        print(f"{BColors.WARNING}Le fichier principal '{MAIN_FILE}' n'existe pas. Il sera créé.{BColors.ENDC}")

    # --- Étape 3: Préparer les données pour la fusion ---
    # Créer un set de signatures de toutes les questions existantes pour une recherche rapide
    existing_signatures = set()
    for questions in main_data.values():
        for q in questions:
            existing_signatures.add(get_question_signature(q))

    # Créer une map des thèmes existants (insensible à la casse)
    theme_map = {theme.lower().strip(): theme for theme in main_data.keys()}
    
    questions_to_add = 0
    duplicates_ignored = 0

    # --- Étape 4: Analyser et préparer la fusion ---
    for theme, questions in add_data.items():
        normalized_theme = theme.lower().strip()
        
        # Déterminer le nom du thème final (canonique)
        if normalized_theme in theme_map:
            canonical_theme = theme_map[normalized_theme]
        else:
            canonical_theme = theme
            theme_map[normalized_theme] = canonical_theme
            main_data[canonical_theme] = []

        for q in questions:
            signature = get_question_signature(q)
            if signature not in existing_signatures:
                # La question est nouvelle, on l'ajoute
                if 'active' not in q:
                    q['active'] = True
                main_data[canonical_theme].append(q)
                existing_signatures.add(signature)
                questions_to_add += 1
            else:
                # La question est un doublon, on l'ignore
                duplicates_ignored += 1

    # --- Étape 5: Afficher le rapport et demander confirmation ---
    print("\n" + BColors.BOLD + "--- RAPPORT DE FUSION ---" + BColors.ENDC)
    if questions_to_add > 0:
        print(f"Questions à ajouter : {BColors.OKGREEN}{questions_to_add}{BColors.ENDC}")
    if duplicates_ignored > 0:
        print(f"Doublons ignorés : {BColors.WARNING}{duplicates_ignored}{BColors.ENDC}")
    
    if questions_to_add == 0:
        print(f"\n{BColors.OKBLUE}Aucune nouvelle question à ajouter. Le fichier principal est déjà à jour.{BColors.ENDC}")
        return

    choice = input(f"\n{BColors.WARNING}Voulez-vous procéder et mettre à jour '{MAIN_FILE}' ? (o/n) : {BColors.ENDC}").lower()
    
    if choice in ['o', 'oui']:
        try:
            with open(MAIN_FILE, 'w', encoding='utf-8') as f:
                json.dump(main_data, f, indent=4, ensure_ascii=False)
            print(f"\n{BColors.OKGREEN}Le fichier '{MAIN_FILE}' a été mis à jour avec succès !{BColors.ENDC}")

            # Proposer de vider le fichier d'ajout
            clear_choice = input(f"Voulez-vous vider le fichier '{ADD_FILE}' maintenant ? (o/n) : ").lower()
            if clear_choice in ['o', 'oui']:
                with open(ADD_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                print(f"Le fichier '{ADD_FILE}' a été vidé.")

        except Exception as e:
            print(f"\n{BColors.FAIL}Une erreur est survenue lors de l'écriture du fichier : {e}{BColors.ENDC}")
    else:
        print("\nOpération annulée. Aucune modification n'a été apportée.")


if __name__ == '__main__':
    merge_questions()