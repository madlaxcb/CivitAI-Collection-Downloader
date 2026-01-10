import json
import os
import sys
import logging
from pathlib import Path
from config import config

class LanguageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.locales_dir = self._get_locales_dir()
        self.current_language = config.get('language', 'zh_CN')
        self.translations = {}
        self.default_translations = {} # Fallback (usually zh_CN or en)
        self.available_languages = self._scan_languages()
        
        # Create locales dir if not exists (only if not frozen or if we want to encourage editing)
        # We don't create it automatically if we are using internal fallback, 
        # but for this specific requirement ("editable"), we might want to ensure it exists?
        # Actually, if we use external dir, we assume it's there or we create it.
        
        self.load_language(self.current_language)
        self._initialized = True
        
    def _get_locales_dir(self):
        """Determine the locales directory."""
        # 1. Check external directory (next to executable/script)
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).parent
            
        external_locales = base_path / "locales"
        
        # 2. If external exists, use it (allows user editing)
        if external_locales.exists():
            return external_locales
            
        # 3. If not, and we are frozen, check internal (bundled)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            internal_locales = Path(sys._MEIPASS) / "locales"
            if internal_locales.exists():
                return internal_locales
                
        # 4. Fallback to external path (will be created if needed/possible)
        return external_locales
        
    def _scan_languages(self):
        """Scan locales directory for .json files."""
        languages = {}
        if not self.locales_dir.exists():
            return languages
            
        for file in self.locales_dir.glob("*.json"):
            languages[file.stem] = file
        return languages
        
    def load_language(self, lang_code):
        """Load a specific language."""
        if lang_code not in self.available_languages:
            # Fallback to zh_CN if available, else en, else whatever is there
            if 'zh_CN' in self.available_languages:
                lang_code = 'zh_CN'
            elif 'en' in self.available_languages:
                lang_code = 'en'
            else:
                # If no languages found, we might have a problem.
                # But we just created them.
                pass
        
        file_path = self.available_languages.get(lang_code)
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                self.current_language = lang_code
                config['language'] = lang_code # Update config
            except Exception as e:
                logging.error(f"Failed to load language {lang_code}: {e}")
                self.translations = {}
        
        # Load fallback if needed (e.g. load zh_CN as fallback)
        if lang_code != 'zh_CN' and 'zh_CN' in self.available_languages:
             try:
                with open(self.available_languages['zh_CN'], 'r', encoding='utf-8') as f:
                    self.default_translations = json.load(f)
             except:
                 pass

    def get(self, key_path, **kwargs):
        """
        Get translated text.
        key_path: dot.separated.keys (e.g. "manager.create")
        kwargs: variables for formatting (e.g. name="My Collection")
        """
        keys = key_path.split('.')
        value = self.translations
        
        # Try to find in current language
        found = True
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                found = False
                break
        
        # If not found, try fallback
        if not found and self.default_translations:
            value = self.default_translations
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    break
        
        if not found and not isinstance(value, str):
             # Return key path if still not found or result is not a string
             return key_path

        if isinstance(value, str):
            try:
                return value.format(**kwargs)
            except Exception as e:
                logging.warning(f"Formatting error for key {key_path}: {e}")
                return value
        
        return str(value)

    def get_available_languages(self):
        return list(self.available_languages.keys())

# Global instance
i18n = LanguageManager()
