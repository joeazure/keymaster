import keyring
import keyring.backend
import sys

def print_backend_info():
    try:
        current = keyring.get_keyring()
        print(f"\nCurrent backend: {current.__class__.__name__}")
        print(f"Backend module: {current.__class__.__module__}")
        print(f"Backend path: {current.__class__.__file__}" if hasattr(current.__class__, '__file__') else "No file path")
    except Exception as e:
        print(f"Error getting current backend: {e}")
    
    print("\nAvailable backends:")
    try:
        for backend in keyring.backend.get_all_keyring():
            print(f"- {backend.__class__.__name__} from {backend.__class__.__module__}")
    except Exception as e:
        print(f"Error listing backends: {e}")
        
    print("\nSystem info:")
    print(f"Platform: {sys.platform}")
    print(f"Python version: {sys.version}")
    
    print("\nKeyring config:")
    try:
        from keyring.util import platform_
        print(f"Config path: {platform_.config_root()}")
    except Exception as e:
        print(f"Error getting config: {e}")
        
    print("\nTrying macOS backend:")
    try:
        from keyring.backends import macOS
        k = macOS.Keyring()
        print("MacOS Keyring initialization:", "success")
        print("MacOS Keyring priority:", getattr(k, 'priority', 'unknown'))
        print("MacOS Keyring viable:", k.viable)
    except ImportError:
        print("MacOS backend not available")
    except Exception as e:
        print(f"MacOS Keyring error: {e}")

print_backend_info() 