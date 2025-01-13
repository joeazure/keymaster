from typing import List, Optional, Tuple
from keymaster.providers import get_providers

def prompt_selection(prompt: str, options: List[str], allow_new: bool = False, show_descriptions: bool = False) -> Tuple[str, bool]:
    """
    Prompt user with numbered options and return their selection.
    
    Args:
        prompt: The prompt to show
        options: List of options to choose from
        allow_new: Whether to allow entering a new option
        show_descriptions: Whether to show provider descriptions (if available)
        
    Returns:
        Tuple of (selected option, whether it's a new option)
    """
    print(f"\n{prompt}")
    for i, option in enumerate(options, 1):
        if show_descriptions and option.lower() in get_providers():
            provider = get_providers()[option.lower()]
            print(f"[{i}] {option}: {provider.description}")
        else:
            print(f"[{i}] {option}")
    if allow_new:
        print("[enter] new option...")
    
    while True:
        choice = input("Select option: ").strip()
        
        if not choice and allow_new:
            new_value = input("Enter new value: ").strip()
            if new_value:
                return new_value, True
            continue
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx], False
        except ValueError:
            pass
            
        print("Invalid selection. Please try again.") 