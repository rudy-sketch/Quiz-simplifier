import json
import os

# --- Configuration des fichiers ---
QUESTIONS_SIMPLES_FILE = 'questions_simples.json'
QUESTIONS_INTRUS_FILE = 'questions_intrus.json'

class BColors:
    """Classe pour ajouter des couleurs dans la console."""
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    OKCYAN = '\033[96m'

def are_questions_identical(q1, q2, q_type='simple'):
    """Compare deux objets question pour voir s'ils sont identiques."""
    
    # Normalise et compare le texte principal (question ou thème)
    key_text = 'theme' if q_type == 'intrus' else 'question'
    text1 = q1.get(key_text, '').lower().strip()
    text2 = q2.get(key_text, '').lower().strip()
    if text1 != text2:
        return False

    # Normalise, trie et compare les réponses
    try:
        answers1 = sorted([ans.get('texte', '').lower().strip() for ans in q1.get('reponses', [])])
        answers2 = sorted([ans.get('texte', '').lower().strip() for ans in q2.get('reponses', [])])
        if answers1 != answers2:
            return False
    except (AttributeError, TypeError):
        # En cas de format de réponse inattendu
        return False

    return True

def verify_simple_questions():
    """Analyse le fichier de questions simples avec une comparaison 1 par 1."""
    print(f"\n{BColors.HEADER}--- Analyse de '{QUESTIONS_SIMPLES_FILE}' ---{BColors.ENDC}")
    if not os.path.exists(QUESTIONS_SIMPLES_FILE):
        print(f"{BColors.FAIL}Fichier non trouvé.{BColors.ENDC}")
        return

    try:
        with open(QUESTIONS_SIMPLES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"{BColors.FAIL}Erreur de lecture du fichier : {e}{BColors.ENDC}")
        return
    
    # Aplatir la structure pour une comparaison facile
    flat_list = []
    for theme, questions in data.items():
        for i, q_data in enumerate(questions):
            flat_list.append({'theme': theme, 'index': i, 'data': q_data})

    duplicates_to_remove = set() # Utilise un tuple (thème, index) pour marquer les doublons
    
    print("Analyse en cours (comparaison 1 par 1)...")
    for i in range(len(flat_list)):
        # Si cet élément est déjà marqué comme un doublon d'un autre, on l'ignore
        if (flat_list[i]['theme'], flat_list[i]['index']) in duplicates_to_remove:
            continue
            
        for j in range(i + 1, len(flat_list)):
            if are_questions_identical(flat_list[i]['data'], flat_list[j]['data'], 'simple'):
                print(f"  -> {BColors.WARNING}DOUBLON TROUVÉ :{BColors.ENDC}")
                print(f"     La question \"{flat_list[j]['data'].get('question')[:40]}...\" dans '{BColors.OKCYAN}{flat_list[j]['theme']}{BColors.ENDC}'")
                print(f"     est identique à celle dans '{BColors.OKCYAN}{flat_list[i]['theme']}{BColors.ENDC}'.")
                duplicates_to_remove.add((flat_list[j]['theme'], flat_list[j]['index']))

    if not duplicates_to_remove:
        print(f"{BColors.OKGREEN}Aucun doublon trouvé !{BColors.ENDC}")
        return
        
    choice = input(f"\n{BColors.WARNING}Voulez-vous supprimer les {len(duplicates_to_remove)} doublon(s) trouvé(s) ? (o/n) : {BColors.ENDC}").lower()
    if choice in ['o', 'oui']:
        cleaned_data = {}
        for theme, questions in data.items():
            if theme not in cleaned_data:
                cleaned_data[theme] = []
            for i, q_data in enumerate(questions):
                if (theme, i) not in duplicates_to_remove:
                    cleaned_data[theme].append(q_data)
        
        final_data = {t: q for t, q in cleaned_data.items() if q} # Enlève les thèmes vides
        
        with open(QUESTIONS_SIMPLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"{BColors.OKGREEN}{len(duplicates_to_remove)} doublon(s) supprimé(s). Le fichier a été mis à jour.{BColors.ENDC}")
    else:
        print("Opération annulée.")


def verify_intrus_questions():
    """Analyse le fichier de questions intrus avec une comparaison 1 par 1."""
    print(f"\n{BColors.HEADER}--- Analyse de '{QUESTIONS_INTRUS_FILE}' ---{BColors.ENDC}")
    if not os.path.exists(QUESTIONS_INTRUS_FILE):
        print(f"{BColors.FAIL}Fichier non trouvé.{BColors.ENDC}")
        return

    try:
        with open(QUESTIONS_INTRUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"{BColors.FAIL}Erreur de lecture du fichier : {e}{BColors.ENDC}")
        return
    
    indices_to_remove = set()
    
    print("Analyse en cours (comparaison 1 par 1)...")
    for i in range(len(data)):
        if i in indices_to_remove:
            continue
        for j in range(i + 1, len(data)):
            if are_questions_identical(data[i], data[j], 'intrus'):
                print(f"  -> {BColors.WARNING}DOUBLON TROUVÉ :{BColors.ENDC}")
                print(f"     La question du thème '{data[j].get('theme')}' (position {j+1}) est identique à celle de la position {i+1}.")
                indices_to_remove.add(j)

    if not indices_to_remove:
        print(f"{BColors.OKGREEN}Aucun doublon trouvé !{BColors.ENDC}")
        return

    choice = input(f"\n{BColors.WARNING}Voulez-vous supprimer les {len(indices_to_remove)} doublon(s) trouvé(s) ? (o/n) : {BColors.ENDC}").lower()
    if choice in ['o', 'oui']:
        cleaned_data = [item for index, item in enumerate(data) if index not in indices_to_remove]
        
        with open(QUESTIONS_INTRUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
        print(f"{BColors.OKGREEN}{len(indices_to_remove)} doublon(s) supprimé(s). Le fichier a été mis à jour.{BColors.ENDC}")
    else:
        print("Opération annulée.")

def main():
    """Fonction principale pour lancer les vérifications."""
    print(f"{BColors.HEADER}{'='*50}{BColors.ENDC}")
    print(f"{BColors.HEADER}{BColors.BOLD}   SCRIPT DE DÉTECTION DE DOUBLONS (1 par 1){BColors.ENDC}")
    print(f"{BColors.HEADER}{'='*50}{BColors.ENDC}")

    verify_simple_questions()
    verify_intrus_questions()
    
    print(f"\n{BColors.OKGREEN}Vérification terminée.{BColors.ENDC}")
    print(f"{BColors.HEADER}{'='*50}{BColors.ENDC}")

if __name__ == '__main__':
    main()